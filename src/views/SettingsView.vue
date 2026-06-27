<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useSettingsStore } from '@/stores/settings';

const settings = useSettingsStore();
const apiKey = ref('');
const storedProviders = ref<string[]>([]);
const saveMessage = ref('');
const updateMessage = ref('');
const sidecarVersion = ref('');
const sidecarKeyReady = ref<boolean | null>(null);
const toolStats = ref({ count: 0, enabled_count: 0 });
const mcpStatus = ref<{
  any_enabled: boolean;
  loaded_count: number;
  configured: Record<string, { enabled: boolean; transport: string }>;
} | null>(null);
const providers = ['deepseek', 'openai', 'anthropic', 'qwen', 'ollama', 'custom'];

const isCustom = computed(() => settings.provider === 'custom');
const keyProvider = computed(() => (settings.provider === 'custom' ? 'custom' : settings.provider));
const hasStoredKey = computed(() => storedProviders.value.includes(keyProvider.value));
const needsApiKey = computed(
  () => settings.provider !== 'ollama' && !hasStoredKey.value && !apiKey.value.trim()
);

async function loadStoredProviders() {
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    storedProviders.value = await invoke<string[]>('list_stored_providers');
  } catch {
    storedProviders.value = [];
  }
}

async function loadLlmConfig() {
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    const cfg = await invoke<{
      default_provider: string;
      custom?: { base_url: string; model: string };
    }>('get_llm_user_config');
    settings.applyLlmConfig(cfg);
    return;
  } catch {
    /* fall through to HTTP */
  }

  const base = `http://127.0.0.1:${settings.sidecarPort}`;
  try {
    const cfg = await fetch(`${base}/config/llm`).then((r) => r.json());
    settings.applyLlmConfig(cfg);
  } catch {
    /* use localStorage defaults */
  }
}

async function loadSidecarInfo() {
  const base = `http://127.0.0.1:${settings.sidecarPort}`;
  try {
    const [health, tools, mcp] = await Promise.all([
      fetch(`${base}/health`).then((r) => r.json()),
      fetch(`${base}/tools`).then((r) => r.json()),
      fetch(`${base}/mcp/status`).then((r) => r.json()),
    ]);
    sidecarVersion.value = health.version ?? '';
    sidecarKeyReady.value =
      typeof health.llm_key_configured === 'boolean' ? health.llm_key_configured : null;
    toolStats.value = {
      count: tools.count ?? tools.tools?.length ?? 0,
      enabled_count: tools.enabled_count ?? 0,
    };
    mcpStatus.value = mcp;
  } catch {
    sidecarVersion.value = '';
    sidecarKeyReady.value = null;
    toolStats.value = { count: 0, enabled_count: 0 };
    mcpStatus.value = null;
  }
}

async function saveLlmConfig() {
  const payload = {
    default_provider: settings.provider,
    custom:
      settings.provider === 'custom'
        ? {
            base_url: settings.customBaseUrl.trim(),
            model: settings.customModel.trim(),
          }
        : undefined,
  };

  if (settings.provider === 'custom') {
    if (!payload.custom?.base_url || !payload.custom?.model) {
      throw new Error('请填写自定义 API Base URL 和模型名');
    }
  }

  try {
    const { invoke } = await import('@tauri-apps/api/core');
    await invoke('store_llm_user_config', { config: payload });
    return;
  } catch {
    /* fall through */
  }

  const base = `http://127.0.0.1:${settings.sidecarPort}`;
  const resp = await fetch(`${base}/config/llm`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    throw new Error('保存 LLM 配置失败');
  }
}

async function saveApiKey() {
  saveMessage.value = '';
  try {
    const keyProviderName = keyProvider.value;
    const hasKey =
      apiKey.value.trim().length > 0 || storedProviders.value.includes(keyProviderName);
    if (settings.provider !== 'ollama' && !hasKey) {
      throw new Error('请填写 API Key');
    }

    await saveLlmConfig();

    const keyWasUpdated = apiKey.value.trim().length > 0;
    if (keyWasUpdated) {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('store_api_key', {
        provider: keyProviderName,
        apiKey: apiKey.value.trim(),
      });
      apiKey.value = '';
      await loadStoredProviders();
      if (!storedProviders.value.includes(keyProviderName)) {
        throw new Error('API Key 保存失败，请重试或检查磁盘/密钥链权限');
      }
    }

    await restartSidecar();

    const base = `http://127.0.0.1:${settings.sidecarPort}`;
    const health = await fetch(`${base}/health`).then((r) => r.json());
    sidecarKeyReady.value = health.llm_key_configured ?? null;
    if (settings.provider !== 'ollama' && health.llm_key_configured === false) {
      throw new Error(
        'Sidecar 仍未加载 API Key。请在 API Key 输入框粘贴密钥后再次保存'
      );
    }

    saveMessage.value = keyWasUpdated
      ? '配置与 API Key 已保存，Sidecar 已自动重启'
      : '配置已保存，Sidecar 已重启';
  } catch (e) {
    settings.setSidecarStatus('error');
    const detail = e instanceof Error ? e.message : String(e);
    saveMessage.value = `保存失败: ${detail}`;
  }
}

async function restartSidecar(): Promise<number> {
  const { invoke } = await import('@tauri-apps/api/core');
  await invoke('stop_sidecar');
  const port = await invoke<number>('start_sidecar');
  settings.setSidecarPort(port);
  settings.setSidecarStatus('running');
  await loadSidecarInfo();
  return port;
}

async function restartSidecarFromUi() {
  saveMessage.value = '';
  try {
    const port = await restartSidecar();
    saveMessage.value = `Sidecar 已重启，端口 ${port}`;
  } catch (e) {
    settings.setSidecarStatus('error');
    const detail = e instanceof Error ? e.message : String(e);
    saveMessage.value = `Sidecar 重启失败: ${detail}`;
  }
}

async function checkUpdates() {
  updateMessage.value = '';
  try {
    const { check } = await import('@tauri-apps/plugin-updater');
    const update = await check();
    if (update) {
      updateMessage.value = `发现新版本 ${update.version}（updater 已配置后可安装）`;
    } else {
      updateMessage.value = '已是最新版本';
    }
  } catch {
    updateMessage.value = '更新检查不可用（Web 模式或未启用 updater）';
  }
}

watch(
  () => [settings.sidecarPort, settings.sidecarStatus],
  () => {
    if (settings.sidecarStatus === 'running') {
      loadSidecarInfo();
    }
  }
);

onMounted(async () => {
  await loadLlmConfig();
  await loadStoredProviders();
  await loadSidecarInfo();
});
</script>

<template>
  <div class="settings">
    <h2>设置</h2>

    <section>
      <label>LLM Provider</label>
      <select v-model="settings.provider">
        <option v-for="p in providers" :key="p" :value="p">{{ p }}</option>
      </select>
    </section>

    <section v-if="isCustom">
      <label>API Base URL</label>
      <input
        v-model="settings.customBaseUrl"
        type="text"
        placeholder="https://your-gateway.com/v1"
      />
      <label>模型名</label>
      <input v-model="settings.customModel" type="text" placeholder="your-model-name" />
    </section>

    <section v-if="isCustom && !hasStoredKey" class="warn-box">
      <strong>尚未保存 API Key</strong>
      <p>Provider / URL / 模型名已保存不等于 Key 已配置。请在下方输入框粘贴 NVIDIA API Key，再点「保存配置」。</p>
    </section>

    <section>
      <label>温度 ({{ settings.temperature }})</label>
      <input v-model.number="settings.temperature" type="range" min="0" max="1" step="0.1" />
    </section>

    <section>
      <label>API Key（保存到系统密钥链，不会写入配置文件）</label>
      <input v-model="apiKey" type="password" placeholder="sk-..." />
      <p v-if="hasStoredKey" class="info-inline">{{ keyProvider }} 的 Key 已保存在本地（密钥链/加密文件）</p>
      <p v-if="sidecarKeyReady === true" class="info-inline">Sidecar 已加载当前 Provider 的 API Key</p>
      <p v-else-if="sidecarKeyReady === false" class="warn">Sidecar 未加载 API Key，聊天会失败</p>
      <div class="btn-row">
        <button @click="saveApiKey" :disabled="needsApiKey && settings.provider !== 'ollama'">
          保存配置
        </button>
        <button class="btn-secondary" @click="restartSidecarFromUi">重启 Sidecar</button>
      </div>
      <p v-if="saveMessage" class="msg" :class="{ 'msg-error': settings.sidecarStatus === 'error' }">{{ saveMessage }}</p>
    </section>

    <section v-if="storedProviders.length" class="info">
      <p>已存储 Key 的 Provider: {{ storedProviders.join(', ') }}</p>
    </section>

    <section class="info">
      <p>Sidecar 端口: {{ settings.sidecarPort }}</p>
      <p>Sidecar 状态: {{ settings.sidecarStatus }}</p>
      <p v-if="sidecarVersion">Sidecar 版本: {{ sidecarVersion }}</p>
      <p v-if="toolStats.count">已注册工具: {{ toolStats.enabled_count }} / {{ toolStats.count }}</p>
      <p>WebSocket: {{ settings.wsConnected ? '已连接' : '未连接' }}</p>
    </section>

    <section v-if="mcpStatus" class="info">
      <h3>MCP 扩展</h3>
      <p v-for="(server, name) in mcpStatus.configured" :key="name">
        {{ name }}: {{ server.enabled ? '已启用' : '未启用' }} ({{ server.transport }})
      </p>
      <p>已加载 MCP 工具: {{ mcpStatus.loaded_count }}</p>
      <p v-if="mcpStatus.any_enabled && mcpStatus.loaded_count === 0" class="warn">
        MCP 已启用但未加载工具，请检查依赖 (pip install -e "./agent[mcp]") 与 Token
      </p>
    </section>

    <section>
      <label>应用更新</label>
      <div class="btn-row">
        <button class="btn-secondary" @click="checkUpdates">检查更新</button>
      </div>
      <p v-if="updateMessage" class="msg">{{ updateMessage }}</p>
    </section>
  </div>
</template>

<style scoped>
.settings {
  padding: 24px;
  max-width: 480px;
}

h2 {
  margin-bottom: 20px;
  font-size: 18px;
}

h3 {
  font-size: 14px;
  color: #e4e4e7;
  margin-bottom: 8px;
}

section {
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

label {
  font-size: 13px;
  color: #a1a1aa;
}

select,
input[type='password'],
input[type='text'] {
  background: #16181d;
  border: 1px solid #2a2d35;
  border-radius: 6px;
  color: #e4e4e7;
  padding: 8px 12px;
  font-size: 14px;
}

.btn-row {
  display: flex;
  gap: 8px;
}

button {
  background: #3b82f6;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  align-self: flex-start;
}

.btn-secondary {
  background: #374151;
}

.msg {
  font-size: 12px;
  color: #10b981;
}

.msg-error {
  color: #ef4444;
}

.info {
  font-size: 12px;
  color: #71717a;
}

.warn-box {
  background: #451a03;
  border: 1px solid #92400e;
  border-radius: 8px;
  padding: 12px;
  font-size: 13px;
  color: #fcd34d;
}

.warn-box p {
  margin: 6px 0 0;
  color: #fde68a;
}

.warn-box strong {
  color: #fbbf24;
}

.warn {
  color: #f59e0b;
}

.info-inline {
  font-size: 12px;
  color: #71717a;
}
</style>
