<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useSettingsStore } from '@/stores/settings';

const settings = useSettingsStore();
const apiKey = ref('');
const storedProviders = ref<string[]>([]);
const saveMessage = ref('');
const updateMessage = ref('');
const sidecarVersion = ref('');
const toolStats = ref({ count: 0, enabled_count: 0 });
const mcpStatus = ref<{
  any_enabled: boolean;
  loaded_count: number;
  configured: Record<string, { enabled: boolean; transport: string }>;
} | null>(null);
const providers = ['deepseek', 'openai', 'anthropic', 'qwen', 'ollama', 'custom'];

const isCustom = computed(() => settings.provider === 'custom');

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
    toolStats.value = {
      count: tools.count ?? tools.tools?.length ?? 0,
      enabled_count: tools.enabled_count ?? 0,
    };
    mcpStatus.value = mcp;
  } catch {
    sidecarVersion.value = '';
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
    await saveLlmConfig();

    if (apiKey.value.trim()) {
      const { invoke } = await import('@tauri-apps/api/core');
      const keyProvider = settings.provider === 'custom' ? 'custom' : settings.provider;
      await invoke('store_api_key', {
        provider: keyProvider,
        apiKey: apiKey.value.trim(),
      });
      apiKey.value = '';
      await loadStoredProviders();
    }

    saveMessage.value = '配置已保存，请点击「重启 Sidecar」使 LLM 设置生效';
  } catch (e) {
    const detail = e instanceof Error ? e.message : String(e);
    saveMessage.value = `保存失败: ${detail}`;
  }
}

async function restartSidecar() {
  saveMessage.value = '';
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    await invoke('stop_sidecar');
    const port = await invoke<number>('start_sidecar');
    settings.setSidecarPort(port);
    settings.setSidecarStatus('running');
    saveMessage.value = `Sidecar 已重启，端口 ${port}`;
    await loadSidecarInfo();
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

    <section>
      <label>温度 ({{ settings.temperature }})</label>
      <input v-model.number="settings.temperature" type="range" min="0" max="1" step="0.1" />
    </section>

    <section>
      <label>API Key（存入系统密钥链）</label>
      <input v-model="apiKey" type="password" placeholder="sk-..." />
      <div class="btn-row">
        <button @click="saveApiKey">保存配置</button>
        <button class="btn-secondary" @click="restartSidecar">重启 Sidecar</button>
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

.warn {
  color: #f59e0b;
}
</style>
