<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useSettingsStore, type CustomProviderEntry } from '@/stores/settings';
import type { ProviderInfo } from '@/composables/useChatInputModels';
import { buildLlmConfigPayload, slugProviderId } from '@/utils/llmConfig';
import { isTauriEnv } from '@/utils/tauri';
import { sidecarJson } from '@/utils/sidecarFetch';
import { waitSidecarHealthy } from '@/utils/sidecarConfig';
import ProviderEditDialog, { type ProviderEditMode } from '@/components/ProviderEditDialog.vue';

interface ProviderRow {
  id: string;
  name: string;
  model: string;
  baseUrl: string;
  kind: 'builtin' | 'custom';
  isOllama: boolean;
  entry?: CustomProviderEntry;
}

const props = defineProps<{
  storedProviders: string[];
  sidecarKeyReady: boolean | null;
}>();

const emit = defineEmits<{
  saved: [message: string];
  error: [message: string];
  refreshStored: [];
}>();

const settings = useSettingsStore();
const builtinProviders = ref<ProviderInfo[]>([]);
const persisting = ref(false);

const editOpen = ref(false);
const editMode = ref<ProviderEditMode>('custom-edit');
const editProviderId = ref('');
const editEntry = ref<CustomProviderEntry | undefined>();

const builtinList = computed(() =>
  builtinProviders.value.filter((p) => !p.is_custom && p.id !== 'custom')
);

const providerRows = computed<ProviderRow[]>(() => {
  const builtins: ProviderRow[] = builtinList.value.map((p) => ({
    id: p.id,
    name: p.label || p.id,
    model: settings.getSelectedModel(p.id) || p.model || '—',
    baseUrl: p.base_url || '—',
    kind: 'builtin' as const,
    isOllama: p.type === 'ollama',
  }));

  const customs: ProviderRow[] = settings.customProviders.map((e) => ({
    id: e.id,
    name: e.name || e.id,
    model: e.model || '—',
    baseUrl: e.baseUrl || '—',
    kind: 'custom' as const,
    isOllama: false,
    entry: e,
  }));

  return [...builtins, ...customs];
});

function isActive(id: string) {
  return settings.provider === id;
}

function hasStoredKey(id: string) {
  return props.storedProviders.includes(id);
}

async function loadBuiltinProviders() {
  if (settings.sidecarStatus !== 'running') {
    builtinProviders.value = [];
    return;
  }
  try {
    const data = await sidecarJson<{ providers?: ProviderInfo[] }>('/providers');
    builtinProviders.value = data.providers || [];
  } catch {
    builtinProviders.value = [];
  }
}

async function saveLlmConfigLocal() {
  const payload = buildLlmConfigPayload(settings);
  if (isTauriEnv()) {
    const { invoke } = await import('@tauri-apps/api/core');
    await invoke('store_llm_user_config', { config: payload });
    return;
  }
  if (settings.sidecarStatus !== 'running') {
    throw new Error('Sidecar 未就绪，无法保存配置');
  }
  await sidecarJson('/config/llm', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

async function syncConfigToSidecar() {
  if (settings.sidecarStatus !== 'running') return;
  const payload = buildLlmConfigPayload(settings);
  await sidecarJson('/config/llm', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

async function restartSidecar(): Promise<number> {
  const { invoke } = await import('@tauri-apps/api/core');
  await invoke('stop_sidecar');
  settings.setSidecarStatus('starting');
  const port = await invoke<number>('start_sidecar');
  settings.setSidecarPort(port);
  await waitSidecarHealthy(port);
  settings.setSidecarStatus('running');
  return port;
}

async function storeKey(providerId: string, key: string) {
  const { invoke } = await import('@tauri-apps/api/core');
  await invoke('store_api_key', { provider: providerId, apiKey: key });
}

async function persistChanges(message: string) {
  persisting.value = true;
  try {
    await saveLlmConfigLocal();
    try {
      await syncConfigToSidecar();
    } catch {
      /* 重启时从本地文件加载 */
    }
    const port = await restartSidecar();
    emit('refreshStored');
    await loadBuiltinProviders();
    emit('saved', `${message}（Sidecar 端口 ${port}）`);
  } catch (e) {
    settings.setSidecarStatus('error');
    emit('error', e instanceof Error ? e.message : String(e));
  } finally {
    persisting.value = false;
  }
}

function openCreate() {
  editMode.value = 'custom-create';
  editProviderId.value = slugProviderId('gateway');
  editEntry.value = {
    id: editProviderId.value,
    name: '自定义网关',
    baseUrl: '',
    model: '',
  };
  editOpen.value = true;
}

function openEdit(row: ProviderRow) {
  if (row.kind === 'builtin') {
    editMode.value = 'builtin';
    editProviderId.value = row.id;
    editEntry.value = undefined;
  } else {
    editMode.value = 'custom-edit';
    editProviderId.value = row.id;
    editEntry.value = { ...row.entry! };
  }
  editOpen.value = true;
}

function closeEdit() {
  editOpen.value = false;
}

async function onEditSave(payload: {
  id: string;
  name: string;
  baseUrl: string;
  model: string;
  apiKey?: string;
}) {
  closeEdit();

  try {
    if (editMode.value === 'builtin') {
      if (payload.apiKey) {
        await storeKey(payload.id, payload.apiKey);
      }
      await persistChanges('预置提供方已更新');
      return;
    }

    if (editMode.value === 'custom-create') {
      settings.customProviders.push({
        id: payload.id,
        name: payload.name,
        baseUrl: payload.baseUrl,
        model: payload.model,
      });
    } else {
      const idx = settings.customProviders.findIndex((e) => e.id === payload.id);
      if (idx >= 0) {
        settings.customProviders[idx] = {
          id: payload.id,
          name: payload.name,
          baseUrl: payload.baseUrl,
          model: payload.model,
        };
      }
    }

    if (payload.apiKey) {
      await storeKey(payload.id, payload.apiKey);
    }

    await persistChanges(
      editMode.value === 'custom-create' ? '提供方已添加' : '提供方已更新'
    );
  } catch (e) {
    emit('error', e instanceof Error ? e.message : String(e));
  }
}

async function deleteProvider(row: ProviderRow) {
  if (row.kind !== 'custom') return;

  if (settings.provider === row.id) {
    settings.provider = 'deepseek';
  }

  settings.customProviders = settings.customProviders.filter((e) => e.id !== row.id);

  try {
    const { invoke } = await import('@tauri-apps/api/core');
    await invoke('delete_api_key', { provider: row.id });
  } catch {
    /* ignore */
  }

  await persistChanges('提供方已删除');
}

const editLabel = computed(() => {
  const row = providerRows.value.find((r) => r.id === editProviderId.value);
  return row?.name;
});

onMounted(() => {
  void loadBuiltinProviders();
});
</script>

<template>
  <div class="provider-settings">
    <div class="section-head">
      <div>
        <h3>提供方列表</h3>
        <p class="section-desc">预置与自定义提供方；状态 Active 表示当前聊天使用的提供方</p>
      </div>
      <button type="button" class="btn-add" :disabled="persisting" @click="openCreate">
        + 添加自定义
      </button>
    </div>

    <div v-if="providerRows.length === 0" class="empty-hint">暂无提供方</div>

    <table v-else class="provider-table">
      <thead>
        <tr>
          <th>名称</th>
          <th>模型</th>
          <th>Base URL</th>
          <th>状态</th>
          <th class="col-actions">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in providerRows" :key="row.id">
          <td class="col-name">
            <span class="name">{{ row.name }}</span>
            <span v-if="row.kind === 'custom'" class="sub-id">{{ row.id }}</span>
            <span v-if="hasStoredKey(row.id)" class="key-tag">Key</span>
          </td>
          <td class="col-model" :title="row.model">{{ row.model }}</td>
          <td class="col-url" :title="row.baseUrl">{{ row.baseUrl }}</td>
          <td class="col-status">
            <span v-if="isActive(row.id)" class="badge active">Active</span>
            <span v-else class="badge idle">—</span>
          </td>
          <td class="col-actions">
            <button type="button" class="btn-link" :disabled="persisting" @click="openEdit(row)">
              修改
            </button>
            <button
              v-if="row.kind === 'custom'"
              type="button"
              class="btn-link danger"
              :disabled="persisting"
              @click="deleteProvider(row)"
            >
              删除
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <p v-if="sidecarKeyReady === true" class="field-hint ok">Sidecar 已加载 API Key</p>
    <p v-else-if="sidecarKeyReady === false" class="field-hint warn">Sidecar 未加载 API Key</p>
    <p v-if="persisting" class="field-hint">正在同步 Sidecar…</p>

    <ProviderEditDialog
      :open="editOpen"
      :mode="editMode"
      :provider-id="editProviderId"
      :provider-label="editLabel"
      :entry="editEntry"
      :has-stored-key="hasStoredKey(editProviderId)"
      :is-ollama="editMode === 'builtin' && builtinList.find((p) => p.id === editProviderId)?.type === 'ollama'"
      @save="onEditSave"
      @cancel="closeEdit"
    />
  </div>
</template>

<style scoped>
.provider-settings {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.section-head h3 {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 4px;
}

.section-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0;
}

.btn-add {
  background: var(--bg-hover);
  border: 1px solid var(--border);
  color: var(--text-primary);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  flex-shrink: 0;
}

.btn-add:hover:not(:disabled) {
  background: var(--border);
}

.btn-add:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.provider-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.provider-table th {
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  text-transform: uppercase;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
}

.provider-table td {
  padding: 10px;
  border-bottom: 1px solid var(--bg-hover);
  vertical-align: middle;
}

.col-name {
  min-width: 120px;
}

.name {
  display: block;
  color: var(--text-primary);
  font-weight: 500;
}

.sub-id {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.key-tag {
  display: inline-block;
  margin-top: 4px;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-success-subtle);
  color: var(--text-success-soft);
}

.col-model,
.col-url {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
}

.col-status {
  width: 80px;
}

.col-actions {
  width: 120px;
  text-align: right;
  white-space: nowrap;
}

.badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 500;
}

.badge.active {
  background: var(--accent-subtle);
  color: var(--accent);
}

.badge.idle {
  color: var(--text-muted);
}

.btn-link {
  background: none;
  border: none;
  color: var(--accent);
  font-size: 12px;
  cursor: pointer;
  padding: 4px 8px;
  font-family: inherit;
}

.btn-link:hover:not(:disabled) {
  color: var(--text-link);
}

.btn-link.danger {
  color: var(--text-danger-soft);
}

.btn-link.danger:hover:not(:disabled) {
  color: var(--text-danger-soft);
}

.btn-link:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.field-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.field-hint.ok {
  color: var(--success);
}

.field-hint.warn {
  color: var(--warning);
}

.empty-hint {
  font-size: 13px;
  color: var(--text-muted);
  padding: 24px 0;
  text-align: center;
}
</style>
