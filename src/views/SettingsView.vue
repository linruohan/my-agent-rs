<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useSettingsStore } from '@/stores/settings';
import { useNavigationStore, type SettingsSectionId } from '@/stores/navigation';
import type { ProviderInfo } from '@/composables/useChatInputModels';
import { SETTINGS_NAV_GROUPS, TOOL_KEY_FIELDS } from '@/utils/settingsSections';
import AppearanceSettings from '@/components/AppearanceSettings.vue';
import ProviderSettings from '@/components/ProviderSettings.vue';
import { buildLlmConfigPayload, isUserCustomProviderId } from '@/utils/llmConfig';
import { isTauriEnv } from '@/utils/tauri';
import { pickWorkspaceFolderPath } from '@/utils/nativeOpen';
import { loadWorkspaceFromSidecar } from '@/utils/workspaceConfig';
import {
  applyUserConfigToStore,
  loadUserConfigFromSidecar,
  syncUserConfigToSidecar,
} from '@/utils/userConfig';
import { syncLlmConfigToSidecar } from '@/utils/llmUserConfig';
import {
  loadToolsConfigFromSidecar,
  saveToolsConfigToSidecar,
  type ConfigurableTool,
} from '@/utils/toolsConfig';
import { useSessionStore } from '@/stores/session';
import { useAgentWs } from '@/composables/useAgentWs';
import {
  fetchSidecarBootstrap,
  fetchSidecarHealth,
  fetchSidecarProviders,
  postSidecar,
  putSidecarJson,
} from '@/utils/sidecarConfig';
import { listSchedulerJobsRest, type SchedulerJob } from '@/utils/sidecarScheduler';
import { useTasksStore } from '@/stores/tasks';
import { useMemoryStore } from '@/stores/memory';
import { sidecarBaseUrl } from '@/utils/sidecarFetch';

const settings = useSettingsStore();
const navigation = useNavigationStore();
const sessionStore = useSessionStore();
const tasksStore = useTasksStore();
const memoryStore = useMemoryStore();
const { listArchivedSessions, unarchiveSession, archiveSession } = useAgentWs();

const activeSection = ref<SettingsSectionId>('model');
const apiKey = ref('');
const storedProviders = ref<string[]>([]);
const providerList = ref<ProviderInfo[]>([]);
const saveMessage = ref('');
const updateMessage = ref('');
const pendingUpdate = ref<{ version: string; downloadAndInstall: () => Promise<void> } | null>(null);
const updateInstalling = ref(false);
const sidecarVersion = ref('');
const sidecarVersionOk = ref<boolean | null>(null);
const sidecarKeyReady = ref<boolean | null>(null);
const schedulerJobs = ref<SchedulerJob[]>([]);
const schedulerLoading = ref(false);
const toolStats = ref({ count: 0, enabled_count: 0 });
const mcpToggles = ref<Record<string, boolean>>({});
const mcpSaving = ref(false);
const mcpStatus = ref<{
  any_enabled: boolean;
  loaded_count: number;
  configured: Record<string, { enabled: boolean; transport: string }>;
} | null>(null);
const toolItems = ref<ConfigurableTool[]>([]);
const toolSaving = ref(false);

const providers = computed(() =>
  providerList.value.length
    ? providerList.value
    : [{ id: 'deepseek', label: 'DeepSeek', type: 'openai_compatible', model: 'deepseek-chat' }]
);

const currentProviderInfo = computed(() => providers.value.find((p) => p.id === settings.provider));
const isOllama = computed(() => settings.provider === 'ollama');
const isUserCustom = computed(() => isUserCustomProviderId(settings.provider));

const memoryPrefsModel = computed({
  get: () => memoryStore.prefsJson,
  set: (v: string) => memoryStore.markPrefsEdited(v),
});

function formatIsoLocal(iso: string) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

const sectionTitle = computed(() => {
  for (const g of SETTINGS_NAV_GROUPS) {
    const item = g.items.find((i) => i.id === activeSection.value);
    if (item) return item.label;
  }
  return '设置';
});

function setSection(id: SettingsSectionId) {
  activeSection.value = id;
  navigation.settingsSection = null;
}

function toolKeyValue(id: string) {
  return settings.toolKeys[id] ?? '';
}

function setToolKey(id: string, value: string) {
  settings.toolKeys = { ...settings.toolKeys, [id]: value };
}

async function loadProviderList() {
  const data = await fetchSidecarProviders(settings.sidecarPort);
  providerList.value = data?.providers || [];
}

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
      provider_models?: Record<string, string>;
    }>('get_llm_user_config');
    settings.applyLlmConfig(cfg);
    return;
  } catch {
    /* HTTP fallback */
  }
  const base = sidecarBaseUrl(settings.sidecarPort);
  try {
    const cfg = await fetch(`${base}/config/llm`).then((r) => r.json());
    settings.applyLlmConfig(cfg);
  } catch {
    /* defaults */
  }
}

async function loadWorkspaceConfig() {
  const path = await loadWorkspaceFromSidecar(settings.sidecarPort);
  if (path) settings.workspacePath = path;
}

async function browseWorkspaceFolder() {
  const picked = await pickWorkspaceFolderPath(settings.workspacePath);
  if (picked) {
    settings.setWorkspacePath(picked);
    return;
  }
  if (!isTauriEnv()) {
    saveMessage.value = '浏览器模式下请直接输入路径';
  }
}

function onWorkspacePathBlur() {
  settings.setWorkspacePath(settings.workspacePath);
}

async function loadSidecarInfo() {
  try {
    const data = await fetchSidecarBootstrap(settings.sidecarPort);
    if (!data) throw new Error('bootstrap unavailable');
    const health = data.health ?? {};
    const tools = data.tools ?? {};
    const mcp = data.mcp ?? null;
    sidecarVersion.value = String(health.version ?? '');
    sidecarVersionOk.value =
      typeof health.version_ok === 'boolean' ? health.version_ok : null;
    sidecarKeyReady.value =
      typeof health.llm_key_configured === 'boolean' ? health.llm_key_configured : null;
    toolStats.value = {
      count: tools.count ?? tools.tools?.length ?? 0,
      enabled_count: tools.enabled_count ?? 0,
    };
    mcpStatus.value = mcp
      ? {
          any_enabled: mcp.any_enabled ?? false,
          loaded_count: mcp.loaded_count ?? 0,
          configured: Object.fromEntries(
            Object.entries(mcp.configured ?? {}).map(([name, server]) => [
              name,
              {
                enabled: server.enabled ?? false,
                transport: server.transport ?? '',
              },
            ])
          ),
        }
      : null;
    if (mcp?.configured) {
      const toggles: Record<string, boolean> = {};
      for (const [name, server] of Object.entries(mcp.configured)) {
        toggles[name] = (server as { enabled?: boolean }).enabled ?? false;
      }
      mcpToggles.value = toggles;
    }
  } catch {
    sidecarVersion.value = '';
    sidecarVersionOk.value = null;
    toolStats.value = { count: 0, enabled_count: 0 };
    mcpStatus.value = null;
  }
}

async function saveLlmConfig() {
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    const payload = buildLlmConfigPayload(settings);
    await invoke('store_llm_user_config', { config: payload });
    const { purgeLegacySidecarFieldsFromStorage } = await import('@/utils/settingsStorage');
    purgeLegacySidecarFieldsFromStorage();
    return;
  } catch {
    /* HTTP */
  }
  await syncLlmConfigToSidecar(settings);
}

async function loadUserAppConfig() {
  const cfg = await loadUserConfigFromSidecar(settings.sidecarPort);
  if (cfg) applyUserConfigToStore(settings, cfg);
}

async function saveUserAppConfig() {
  await syncUserConfigToSidecar(settings);
}

async function saveApiKey() {
  saveMessage.value = '';
  try {
    await saveLlmConfig();
    await saveUserAppConfig();
    const keyWasUpdated = apiKey.value.trim().length > 0;
    if (keyWasUpdated) {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('store_api_key', {
        provider: settings.provider,
        apiKey: apiKey.value.trim(),
      });
      apiKey.value = '';
      await loadStoredProviders();
    }
    await restartSidecar();
    const health = await fetchSidecarHealth(settings.sidecarPort);
    sidecarKeyReady.value =
      typeof health?.llm_key_configured === 'boolean' ? health.llm_key_configured : null;
    saveMessage.value = keyWasUpdated
      ? '配置与 API Key 已保存，Sidecar 已重启'
      : '配置已保存，Sidecar 已重启';
  } catch (e) {
    settings.setSidecarStatus('error');
    saveMessage.value = `保存失败: ${e instanceof Error ? e.message : String(e)}`;
  }
}

async function saveSecuritySettings() {
  saveMessage.value = '';
  try {
    await saveUserAppConfig();
    saveMessage.value = '安全设置已保存';
  } catch (e) {
    saveMessage.value = `保存失败: ${e instanceof Error ? e.message : String(e)}`;
  }
}

async function saveConversationSettings() {
  saveMessage.value = '';
  try {
    await saveUserAppConfig();
    saveMessage.value = '对话设置已保存';
  } catch (e) {
    saveMessage.value = `保存失败: ${e instanceof Error ? e.message : String(e)}`;
  }
}

async function loadMemorySummary() {
  await memoryStore.refreshSummary();
}

async function loadMemoryPreferences() {
  await memoryStore.refreshPreferences(undefined, true);
}

async function saveLearnedPreferences() {
  saveMessage.value = '';
  try {
    await memoryStore.savePreferences();
    saveMessage.value = '已保存学习偏好';
  } catch (e) {
    saveMessage.value = `保存失败: ${e instanceof Error ? e.message : String(e)}`;
  }
}

async function loadSchedulerDebug() {
  if (settings.sidecarStatus !== 'running' || !settings.sidecarPort) {
    schedulerJobs.value = [];
    return;
  }
  schedulerLoading.value = true;
  try {
    const [jobs] = await Promise.all([
      listSchedulerJobsRest(settings.sidecarPort),
      tasksStore.refreshReminders(settings.sidecarPort),
    ]);
    schedulerJobs.value = jobs;
  } catch {
    schedulerJobs.value = [];
  } finally {
    schedulerLoading.value = false;
  }
}

async function saveMemorySettings() {
  saveMessage.value = '';
  try {
    await saveUserAppConfig();
    await loadMemorySummary();
    await loadMemoryPreferences();
    saveMessage.value = '记忆设置已保存';
  } catch (e) {
    saveMessage.value = `保存失败: ${e instanceof Error ? e.message : String(e)}`;
  }
}

async function saveNotificationSettings() {
  saveMessage.value = '';
  try {
    await saveUserAppConfig();
    saveMessage.value = '通知设置已保存';
  } catch (e) {
    saveMessage.value = `保存失败: ${e instanceof Error ? e.message : String(e)}`;
  }
}

async function saveSearchSettings() {
  saveMessage.value = '';
  try {
    await saveUserAppConfig();
    saveMessage.value = '搜索后端设置已保存';
  } catch (e) {
    saveMessage.value = `保存失败: ${e instanceof Error ? e.message : String(e)}`;
  }
}

async function refreshArchivedSessions() {
  listArchivedSessions();
}

async function handleUnarchive(threadId: string) {
  unarchiveSession(threadId);
}

async function handleArchiveCurrent() {
  const id = sessionStore.currentThreadId;
  if (!id) return;
  archiveSession(id);
  saveMessage.value = '当前会话已归档';
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
    saveMessage.value = `Sidecar 重启失败: ${e instanceof Error ? e.message : String(e)}`;
  }
}

async function loadToolsConfig() {
  const data = await loadToolsConfigFromSidecar(settings.sidecarPort);
  toolItems.value = data?.tools ?? [];
}

async function saveToolsConfig() {
  toolSaving.value = true;
  saveMessage.value = '';
  try {
    const data = await saveToolsConfigToSidecar(settings.sidecarPort, toolItems.value);
    toolItems.value = data.tools ?? toolItems.value;
    toolStats.value = {
      count: data.count ?? toolItems.value.length,
      enabled_count: data.enabled_count ?? toolItems.value.filter((t) => t.enabled).length,
    };
    saveMessage.value = '工具配置已保存并生效';
  } catch (e) {
    saveMessage.value = `工具保存失败: ${e instanceof Error ? e.message : String(e)}`;
  } finally {
    toolSaving.value = false;
  }
}

function toggleToolEnabled(name: string, enabled: boolean) {
  toolItems.value = toolItems.value.map((t) =>
    t.name === name ? { ...t, enabled } : t
  );
}

async function saveMcpConfig() {
  mcpSaving.value = true;
  saveMessage.value = '';
  try {
    const servers: Record<string, { enabled: boolean }> = {};
    for (const [name, enabled] of Object.entries(mcpToggles.value)) {
      servers[name] = { enabled };
    }
    await putSidecarJson(settings.sidecarPort, '/config/mcp', { servers });
    await postSidecar(settings.sidecarPort, '/tools/reload');
    await restartSidecar();
    saveMessage.value = 'MCP 配置已保存，Sidecar 已重启';
  } catch (e) {
    saveMessage.value = `MCP 保存失败: ${e instanceof Error ? e.message : String(e)}`;
  } finally {
    mcpSaving.value = false;
  }
}

async function checkUpdates() {
  updateMessage.value = '';
  pendingUpdate.value = null;
  try {
    const { check } = await import('@tauri-apps/plugin-updater');
    const update = await check();
    if (update) {
      pendingUpdate.value = {
        version: update.version,
        downloadAndInstall: () => update.downloadAndInstall(),
      };
      updateMessage.value = `发现新版本 ${update.version}`;
    } else {
      updateMessage.value = '已是最新版本';
    }
  } catch {
    updateMessage.value = '更新检查不可用（Web 模式或未启用 updater）';
  }
}

async function installPendingUpdate() {
  if (!pendingUpdate.value || updateInstalling.value) return;
  updateInstalling.value = true;
  updateMessage.value = '正在下载并安装更新…';
  try {
    await pendingUpdate.value.downloadAndInstall();
    updateMessage.value = '更新已安装，应用将重启';
    pendingUpdate.value = null;
  } catch (e) {
    updateMessage.value = `安装失败: ${e instanceof Error ? e.message : String(e)}`;
  } finally {
    updateInstalling.value = false;
  }
}

function applyNavigationSection(section: SettingsSectionId | null) {
  if (section) {
    activeSection.value = section;
    navigation.settingsSection = null;
  }
}

watch(
  () => navigation.settingsSection,
  (section: SettingsSectionId | null) => applyNavigationSection(section)
);

watch(
  () => [settings.sidecarPort, settings.sidecarStatus],
  () => {
    if (settings.sidecarStatus === 'running') loadSidecarInfo();
  }
);

watch(
  () => activeSection.value,
  (section) => {
    if (section === 'tools' && settings.sidecarStatus === 'running') {
      void loadToolsConfig();
    }
    if (section === 'memory' && settings.sidecarStatus === 'running') {
      void loadMemoryPreferences();
    }
    if (section === 'task' && settings.sidecarStatus === 'running') {
      void loadSchedulerDebug();
    }
  }
);

onMounted(async () => {
  await loadLlmConfig();
  await loadUserAppConfig();
  await loadStoredProviders();
  await loadProviderList();
  await loadSidecarInfo();
  await loadWorkspaceConfig();
  await loadMemorySummary();
  await loadMemoryPreferences();
  await loadToolsConfig();
  listArchivedSessions();
  applyNavigationSection(navigation.settingsSection);
});
</script>

<template>
  <div class="settings-layout">
    <nav class="settings-nav">
      <div v-for="(group, gi) in SETTINGS_NAV_GROUPS" :key="gi" class="nav-group">
        <div v-if="group.label" class="nav-group-label">{{ group.label }}</div>
        <button
          v-for="item in group.items"
          :key="item.id"
          type="button"
          class="nav-item"
          :class="{ active: activeSection === item.id }"
          @click="setSection(item.id)"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </button>
      </div>
    </nav>

    <div class="settings-main">
      <header class="settings-header">
        <h2>{{ sectionTitle }}</h2>
        <button type="button" class="btn-close-settings" @click="navigation.setView('chat')">
          ×
        </button>
      </header>

      <div class="settings-body">
        <!-- 模型 -->
        <template v-if="activeSection === 'model'">
          <div class="field-row">
            <label>LLM PROVIDER</label>
            <select v-model="settings.provider">
              <option v-for="p in providers" :key="p.id" :value="p.id">
                {{ p.label || p.id }}
              </option>
            </select>
          </div>
          <div v-if="currentProviderInfo" class="field-hint">
            类型 {{ currentProviderInfo.type }}
            <template v-if="currentProviderInfo.model"> · 默认 {{ currentProviderInfo.model }}</template>
          </div>
          <div v-if="isOllama" class="field-row">
            <label>OLLAMA MODEL</label>
            <input v-model="settings.customModel" type="text" placeholder="qwen2.5:7b" />
          </div>
          <div v-if="isUserCustom" class="field-hint">
            自定义提供方请在「集成 → 提供方」中管理；当前：
            {{ currentProviderInfo?.label || settings.provider }}
            <template v-if="settings.getSelectedModel()"> · {{ settings.getSelectedModel() }}</template>
          </div>
          <div class="field-row">
            <label>TEMPERATURE ({{ settings.temperature }})</label>
            <input v-model.number="settings.temperature" type="range" min="0" max="1" step="0.1" class="range" />
          </div>
          <div class="field-row">
            <label>MAX TOKENS</label>
            <input v-model.number="settings.maxTokens" type="number" min="256" max="128000" step="256" />
          </div>
          <div class="actions">
            <button type="button" @click="saveApiKey">保存模型配置</button>
          </div>
        </template>

        <!-- 对话 -->
        <template v-else-if="activeSection === 'conversation'">
          <div class="field-row">
            <label>MAX HISTORY MESSAGES</label>
            <input
              v-model.number="settings.conversationPrefs.maxHistoryMessages"
              type="number"
              min="10"
              max="500"
            />
          </div>
          <div class="field-row mcp-row">
            <label>AUTO TITLE</label>
            <label class="checkbox-label">
              <input v-model="settings.conversationPrefs.autoTitle" type="checkbox" />
              新会话自动生成标题
            </label>
          </div>
          <div class="actions">
            <button type="button" @click="saveConversationSettings">保存对话设置</button>
          </div>
        </template>

        <!-- 记忆 -->
        <template v-else-if="activeSection === 'memory'">
          <div class="field-row mcp-row">
            <label>HISTORY RECALL</label>
            <label class="checkbox-label">
              <input v-model="settings.memoryPrefs.historyRecall" type="checkbox" />
              相似问题命中历史回答时直接复用（跳过 LLM）
            </label>
          </div>
          <div class="field-row">
            <label>SIMILARITY ({{ settings.memoryPrefs.historySimilarityMin }})</label>
            <input
              v-model.number="settings.memoryPrefs.historySimilarityMin"
              type="range"
              min="0.5"
              max="1"
              step="0.02"
              class="range"
            />
          </div>
          <div class="field-row">
            <label>HISTORY MAX AGE (DAYS)</label>
            <input
              v-model.number="settings.memoryPrefs.historyMaxAgeDays"
              type="number"
              min="1"
              max="36500"
            />
          </div>
          <p class="field-hint">历史问答索引保留天数，设为较大值可长期复用（最大 36500 天）</p>
          <div class="field-row mcp-row">
            <label>AUTO LEARN</label>
            <label class="checkbox-label">
              <input v-model="settings.memoryPrefs.autoLearn" type="checkbox" />
              自动从对话提取偏好（「请记住…」「我喜欢…」等）
            </label>
          </div>
          <p v-if="memoryStore.summary" class="field-hint">
            历史问答索引：{{ memoryStore.summary.history_stats.total_entries }} 条，
            命中 {{ memoryStore.summary.history_stats.total_hits }} 次
          </p>
          <div class="field-row">
            <label>LEARNED PREFERENCES (JSON)</label>
            <textarea
              v-model="memoryPrefsModel"
              class="prefs-editor"
              rows="10"
              spellcheck="false"
              placeholder='{"tone": "简洁"}'
            />
          </div>
          <p v-if="memoryStore.prefsError" class="field-hint warn">{{ memoryStore.prefsError }}</p>
          <p v-else class="field-hint">通过 REST 读写 user/preferences；自动学习与此处编辑共用同一存储</p>
          <div class="actions">
            <button type="button" @click="saveMemorySettings">保存记忆设置</button>
            <button type="button" class="btn-secondary" @click="saveLearnedPreferences">保存学习偏好</button>
            <button type="button" class="btn-secondary" @click="loadMemorySummary(); loadMemoryPreferences()">
              刷新
            </button>
          </div>
        </template>

        <!-- 语言 -->
        <template v-else-if="activeSection === 'language'">
          <div class="field-row">
            <label>UI LANGUAGE</label>
            <select v-model="settings.appearance.uiLanguage">
              <option value="zh-CN">简体中文</option>
              <option value="en-US">English</option>
            </select>
          </div>
          <p class="field-hint">界面语言偏好（部分文案仍为中英混合）</p>
        </template>

        <!-- 通知 -->
        <template v-else-if="activeSection === 'notification'">
          <div class="field-row mcp-row">
            <label>DESKTOP NOTIFICATIONS</label>
            <label class="checkbox-label">
              <input v-model="settings.notificationPrefs.desktopEnabled" type="checkbox" />
              启用桌面通知（待办/项目提醒）
            </label>
          </div>
          <div class="field-row mcp-row">
            <label>SOUND</label>
            <label class="checkbox-label">
              <input v-model="settings.notificationPrefs.soundEnabled" type="checkbox" />
              通知时播放提示音（预留）
            </label>
          </div>
          <div class="actions">
            <button type="button" @click="saveNotificationSettings">保存通知设置</button>
          </div>
        </template>

        <!-- 已归档对话 -->
        <template v-else-if="activeSection === 'archived'">
          <div class="actions">
            <button type="button" class="btn-secondary" @click="refreshArchivedSessions">刷新列表</button>
            <button
              type="button"
              class="btn-secondary"
              :disabled="!sessionStore.currentThreadId"
              @click="handleArchiveCurrent"
            >
              归档当前会话
            </button>
          </div>
          <ul class="archived-list">
            <li v-for="s in sessionStore.archivedSessions" :key="s.thread_id">
              <span>{{ s.title }}</span>
              <button type="button" class="btn-secondary" @click="handleUnarchive(s.thread_id)">恢复</button>
            </li>
            <li v-if="!sessionStore.archivedSessions.length" class="empty">暂无归档会话</li>
          </ul>
        </template>

        <!-- 提供方 -->
        <template v-else-if="activeSection === 'provider'">
          <ProviderSettings
            :stored-providers="storedProviders"
            :sidecar-key-ready="sidecarKeyReady"
            @saved="(msg) => (saveMessage = msg)"
            @error="(msg) => (saveMessage = `保存失败: ${msg}`)"
            @refresh-stored="loadStoredProviders"
          />
        </template>

        <!-- 工具与密钥 -->
        <template v-else-if="activeSection === 'tools-keys'">
          <div v-for="field in TOOL_KEY_FIELDS" :key="field.id" class="field-row">
            <label>{{ field.label }}</label>
            <input
              :type="field.type === 'password' ? 'password' : 'text'"
              :value="toolKeyValue(field.id)"
              :placeholder="field.placeholder"
              @input="setToolKey(field.id, ($event.target as HTMLInputElement).value)"
            />
          </div>
          <p class="field-hint">密钥保存在本地设置中，不会写入日志</p>
        </template>

        <!-- 工具 -->
        <template v-else-if="activeSection === 'tools'">
          <p class="field-hint">控制 Agent 可调用的能力工具与业务工具。保存后立即生效。</p>
          <div v-if="!toolItems.length" class="placeholder-text">Sidecar 未连接或暂无工具</div>
          <ul v-else class="tool-settings-grid">
            <li v-for="t in toolItems" :key="t.name" :class="{ disabled: t.enabled === false }">
              <div class="tool-settings-head">
                <span class="tool-settings-name">{{ t.name }}</span>
                <span v-if="t.category" class="tool-settings-cat">{{ t.category }}</span>
              </div>
              <p v-if="t.description" class="tool-settings-desc">{{ t.description }}</p>
              <label class="checkbox-label tool-toggle">
                <input
                  type="checkbox"
                  :checked="t.enabled !== false"
                  @change="toggleToolEnabled(t.name, ($event.target as HTMLInputElement).checked)"
                />
                {{ t.enabled !== false ? '已启用' : '已禁用' }}
              </label>
            </li>
          </ul>
          <div class="actions">
            <button type="button" class="btn-secondary" :disabled="toolSaving" @click="saveToolsConfig">
              {{ toolSaving ? '保存中…' : '保存工具配置' }}
            </button>
          </div>
        </template>

        <!-- MCP -->
        <template v-else-if="activeSection === 'mcp'">
          <template v-if="mcpStatus">
            <div v-for="(server, name) in mcpStatus.configured" :key="name" class="field-row mcp-row">
              <label>{{ name.toUpperCase() }}</label>
              <label class="checkbox-label">
                <input v-model="mcpToggles[name]" type="checkbox" />
                启用 ({{ server.transport }})
              </label>
            </div>
            <p class="field-hint">已加载 MCP 工具: {{ mcpStatus.loaded_count }}</p>
            <div class="actions">
              <button type="button" class="btn-secondary" :disabled="mcpSaving" @click="saveMcpConfig">
                {{ mcpSaving ? '保存中…' : '保存 MCP 并重启' }}
              </button>
            </div>
          </template>
          <p v-else class="placeholder-text">Sidecar 未连接，无法加载 MCP 状态</p>
        </template>

        <!-- 工作区 -->
        <template v-else-if="activeSection === 'workspace'">
          <div class="field-row">
            <label>WORKSPACE PATH</label>
            <div class="path-input-row">
              <input
                v-model="settings.workspacePath"
                type="text"
                placeholder="~/AssistantWorkspace"
                @blur="onWorkspacePathBlur"
              />
              <button type="button" class="btn-secondary btn-browse" @click="browseWorkspaceFolder">
                浏览…
              </button>
            </div>
          </div>
          <p class="field-hint">Agent 文件工具与项目文档的默认工作目录</p>
        </template>

        <!-- 安全 -->
        <template v-else-if="activeSection === 'security'">
          <div class="field-row">
            <label>HITL TIMEOUT (SEC)</label>
            <input v-model.number="settings.hitlTimeoutSec" type="number" min="30" max="3600" />
          </div>
          <p class="field-hint">人工确认操作超时时间（秒），超时后自动拒绝</p>
          <div class="actions">
            <button type="button" @click="saveSecuritySettings">保存安全设置</button>
          </div>
        </template>

        <!-- 项目设置 -->
        <template v-else-if="activeSection === 'project'">
          <div class="field-row">
            <label>DEFAULT STATUS</label>
            <select v-model="settings.projectPrefs.defaultStatus">
              <option value="planning">规划中</option>
              <option value="active">进行中</option>
              <option value="on_hold">暂停</option>
            </select>
          </div>
          <div class="field-row mcp-row">
            <label>AUTO INDEX DOCS</label>
            <label class="checkbox-label">
              <input v-model="settings.projectPrefs.autoIndexDocs" type="checkbox" />
              添加项目文档时自动索引到知识库
            </label>
          </div>
        </template>

        <!-- 任务设置 -->
        <template v-else-if="activeSection === 'task'">
          <div class="field-row">
            <label>DEFAULT PRIORITY</label>
            <select v-model="settings.taskPrefs.defaultPriority">
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
            </select>
          </div>
          <div class="field-row mcp-row">
            <label>SHOW COMPLETED</label>
            <label class="checkbox-label">
              <input v-model="settings.taskPrefs.showCompleted" type="checkbox" />
              默认显示已完成任务
            </label>
          </div>
          <div class="field-row">
            <label>DEFAULT REMIND OFFSET (H)</label>
            <input v-model.number="settings.taskPrefs.defaultRemindHours" type="number" min="0" max="168" />
          </div>
          <h3 class="subsection-title">即将提醒</h3>
          <p class="field-hint">来自 GET /tasks/reminders（实体提醒 + 调度任务合并视图）</p>
          <ul v-if="tasksStore.reminders.length" class="scheduler-list">
            <li v-for="r in tasksStore.reminders.slice(0, 10)" :key="r.job_id">
              <span class="mono">{{ formatIsoLocal(r.run_at) }}</span>
              {{ r.title }} — {{ r.message }}
              <span class="tag">{{ r.entity_type }}</span>
            </li>
          </ul>
          <p v-else class="field-hint">暂无待触发提醒</p>
          <h3 class="subsection-title">调度队列（调试）</h3>
          <p class="field-hint">来自 GET /scheduler/jobs（APScheduler 原始 pending jobs）</p>
          <ul v-if="schedulerJobs.length" class="scheduler-list">
            <li v-for="j in schedulerJobs" :key="j.id">
              <span class="mono">{{ formatIsoLocal(j.run_at) }}</span>
              <span class="tag">{{ j.job_type }}</span>
              <span class="mono">{{ j.id }}</span>
              {{ j.payload }}
            </li>
          </ul>
          <p v-else-if="!schedulerLoading" class="field-hint">队列为空或 Sidecar 未运行</p>
          <div class="actions">
            <button type="button" class="btn-secondary" :disabled="schedulerLoading" @click="loadSchedulerDebug">
              {{ schedulerLoading ? '加载中…' : '刷新提醒与队列' }}
            </button>
          </div>
        </template>

        <!-- 关于 -->
        <template v-else-if="activeSection === 'about'">
          <div class="info-block">
            <p>Sidecar 端口: {{ settings.sidecarPort }}</p>
            <p>Sidecar 状态: {{ settings.sidecarStatus }}</p>
            <p v-if="sidecarVersion">版本: {{ sidecarVersion }}</p>
            <p v-if="sidecarVersionOk === false" class="warn">API 版本与桌面壳不一致</p>
            <p v-if="toolStats.count">工具: {{ toolStats.enabled_count }} / {{ toolStats.count }}</p>
            <p>WebSocket: {{ settings.wsConnected ? '已连接' : '未连接' }}</p>
          </div>
          <div class="actions">
            <button type="button" class="btn-secondary" @click="checkUpdates">检查更新</button>
            <button
              v-if="pendingUpdate"
              type="button"
              :disabled="updateInstalling"
              @click="installPendingUpdate"
            >
              {{ updateInstalling ? '安装中…' : `安装 ${pendingUpdate.version}` }}
            </button>
            <button type="button" class="btn-secondary" @click="restartSidecarFromUi">重启 Sidecar</button>
          </div>
          <p v-if="updateMessage" class="field-hint">{{ updateMessage }}</p>
        </template>

        <!-- 外观 -->
        <template v-else-if="activeSection === 'appearance'">
          <AppearanceSettings />
        </template>

        <!-- 高级 -->
        <template v-else-if="activeSection === 'advanced'">
          <div class="field-row">
            <label>SEARCH BACKEND</label>
            <select v-model="settings.searchBackend">
              <option value="">默认（tools.yaml）</option>
              <option value="race">Race（多引擎并行）</option>
              <option value="duckduckgo">DuckDuckGo</option>
              <option value="tavily">Tavily</option>
              <option value="searxng">SearXNG</option>
              <option value="bing">Bing</option>
              <option value="brave">Brave</option>
            </select>
          </div>
          <p class="field-hint">覆盖 web_search 默认后端；Tavily 需配置 TAVILY_API_KEY</p>
          <div class="actions">
            <button type="button" class="btn-secondary" @click="saveSearchSettings">保存搜索设置</button>
            <button type="button" class="btn-secondary" @click="restartSidecarFromUi">重启 Sidecar</button>
          </div>
          <p class="field-hint">重启后重新加载配置与工具注册</p>
        </template>

        <p v-if="saveMessage" class="save-msg" :class="{ error: saveMessage.startsWith('保存失败') }">
          {{ saveMessage }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-layout {
  flex: 1;
  display: flex;
  min-height: 0;
  width: 100%;
  background: var(--bg-app);
}

.settings-nav {
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  padding: 12px 8px;
  overflow-y: auto;
  background: var(--bg-sidebar);
}

.nav-group {
  margin-bottom: 12px;
}

.nav-group-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  padding: 8px 12px 4px;
  text-transform: uppercase;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 12px;
  background: none;
  border: none;
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--settings-nav-active);
  color: var(--text-primary);
}

.nav-icon {
  width: 18px;
  text-align: center;
  font-size: 13px;
}

.settings-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  width: 100%;
  background: var(--bg-panel);
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  background: var(--bg-panel);
}

.settings-header h2 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.btn-close-settings {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 22px;
  cursor: pointer;
  line-height: 1;
}

.btn-close-settings:hover {
  color: var(--text-primary);
}

.settings-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px 32px;
  width: 100%;
  box-sizing: border-box;
}

.field-row {
  display: grid;
  grid-template-columns: 200px 1fr;
  align-items: center;
  gap: 16px;
  padding: 10px 0;
  border-bottom: 1px solid var(--bg-hover);
}

.field-row label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.field-row input[type='text'],
.field-row input[type='password'],
.field-row input[type='number'],
.field-row select {
  width: 100%;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  padding: 8px 12px;
  font-size: 13px;
  font-family: inherit;
}

.path-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 0;
}

.path-input-row input {
  flex: 1;
  min-width: 0;
}

.btn-browse {
  flex-shrink: 0;
  white-space: nowrap;
}

.field-row .range {
  width: 100%;
}

.mcp-row {
  align-items: flex-start;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px !important;
  color: var(--text-primary) !important;
  text-transform: none !important;
  font-weight: 400 !important;
}

.field-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 8px 0 16px;
}

.field-hint.ok {
  color: var(--success);
}

.field-hint.warn,
.warn {
  color: var(--warning);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.actions button {
  background: var(--accent);
  color: var(--text-on-accent);
  border: none;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
}

.btn-secondary {
  background: var(--btn-secondary-bg) !important;
}

.info-block {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.8;
}

.info-block p {
  margin: 0;
}

.placeholder-text {
  color: var(--text-muted);
  font-size: 14px;
  padding: 24px 0;
}

.save-msg {
  margin-top: 16px;
  font-size: 12px;
  color: var(--success);
}

.save-msg.error {
  color: var(--danger);
}

.tool-settings-grid {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  margin: 16px 0;
  padding: 0;
}

.tool-settings-grid li {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
}

.tool-settings-grid li.disabled {
  opacity: 0.55;
}

.tool-settings-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.tool-settings-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.tool-settings-cat {
  font-size: 10px;
  color: var(--accent);
  text-transform: uppercase;
}

.tool-settings-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0 0 10px;
  line-height: 1.45;
}

.tool-toggle {
  font-size: 12px;
  color: var(--text-muted);
}

.archived-list {
  list-style: none;
  padding: 0;
  margin: 16px 0 0;
}

.archived-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--bg-hover);
  font-size: 13px;
}

.archived-list li.empty {
  color: var(--text-muted);
  justify-content: flex-start;
}

.prefs-preview {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  max-height: 240px;
}

.prefs-editor {
  width: 100%;
  min-height: 180px;
  margin-top: 8px;
  padding: 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 12px;
  line-height: 1.5;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  resize: vertical;
}

.subsection-title {
  margin: 20px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.scheduler-list {
  list-style: none;
  margin: 0 0 12px;
  padding: 0;
  font-size: 12px;
  line-height: 1.6;
}

.scheduler-list li {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 6px;
  background: var(--bg-input);
}

.scheduler-list .mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color: var(--text-muted);
  margin-right: 8px;
}

.scheduler-list .tag {
  display: inline-block;
  margin: 0 6px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--btn-secondary-bg);
  font-size: 11px;
}
</style>
