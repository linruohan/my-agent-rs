<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { CustomProviderEntry } from '@/stores/settings';
import { fetchOpenAiCompatibleModels } from '@/utils/providerModels';
import { resolveProviderApiKey } from '@/utils/sidecarFetch';

export type ProviderEditMode = 'builtin' | 'custom-create' | 'custom-edit';

const props = defineProps<{
  open: boolean;
  mode: ProviderEditMode;
  providerId: string;
  providerLabel?: string;
  entry?: CustomProviderEntry;
  hasStoredKey?: boolean;
  isOllama?: boolean;
}>();

const emit = defineEmits<{
  save: [payload: {
    id: string;
    name: string;
    baseUrl: string;
    model: string;
    apiKey?: string;
  }];
  cancel: [];
}>();

const name = ref('');
const baseUrl = ref('');
const model = ref('');
const apiKey = ref('');
const models = ref<string[]>([]);
const loadingModels = ref(false);
const dialogError = ref('');

const title = computed(() => {
  if (props.mode === 'custom-create') return '添加自定义提供方';
  if (props.mode === 'custom-edit') return '修改提供方';
  return `修改 ${props.providerLabel || props.providerId}`;
});

const isCustom = computed(() => props.mode.startsWith('custom'));

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return;
    dialogError.value = '';
    apiKey.value = '';
    models.value = [];
    if (props.mode === 'builtin') {
      name.value = props.providerLabel || props.providerId;
      baseUrl.value = '';
      model.value = '';
      return;
    }
    const e = props.entry;
    name.value = e?.name ?? '自定义网关';
    baseUrl.value = e?.baseUrl ?? '';
    model.value = e?.model ?? '';
    if (e?.model) models.value = [e.model];
  }
);

async function fetchModels() {
  dialogError.value = '';
  if (!baseUrl.value.trim()) {
    dialogError.value = '请先填写 Base URL';
    return;
  }
  loadingModels.value = true;
  try {
    let key = apiKey.value.trim();
    if (!key && props.mode === 'custom-edit') {
      key = (await resolveProviderApiKey(props.providerId, '')) || '';
    }
    if (!key) {
      dialogError.value = '请填写 API Key 以获取模型列表';
      return;
    }
    const list = await fetchOpenAiCompatibleModels(baseUrl.value, key);
    models.value = list;
    if (!model.value && list.length) model.value = list[0];
  } catch (e) {
    dialogError.value = e instanceof Error ? e.message : String(e);
  } finally {
    loadingModels.value = false;
  }
}

function submit() {
  dialogError.value = '';
  if (isCustom.value) {
    if (!name.value.trim() || !baseUrl.value.trim() || !model.value.trim()) {
      dialogError.value = '请填写名称、Base URL 和模型';
      return;
    }
  }
  emit('save', {
    id: props.providerId,
    name: name.value.trim(),
    baseUrl: baseUrl.value.trim(),
    model: model.value.trim(),
    apiKey: apiKey.value.trim() || undefined,
  });
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('cancel');
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="overlay" @click.self="emit('cancel')">
      <div class="dialog" role="dialog" aria-modal="true" @keydown="onKeydown">
        <header class="dialog-header">
          <h3>{{ title }}</h3>
          <button type="button" class="btn-close" aria-label="关闭" @click="emit('cancel')">×</button>
        </header>

        <div class="dialog-body">
          <template v-if="isCustom">
            <div class="field">
              <label>名称</label>
              <input v-model="name" type="text" placeholder="例如：公司内网网关" />
            </div>
            <div class="field">
              <label>Base URL</label>
              <input v-model="baseUrl" type="text" placeholder="https://api.example.com/v1" />
            </div>
            <div class="field">
              <label>API Key</label>
              <input
                v-model="apiKey"
                type="password"
                placeholder="sk-..."
                autocomplete="off"
              />
              <p v-if="hasStoredKey && !apiKey" class="hint">已保存密钥，留空表示不修改</p>
            </div>
            <div class="field">
              <label>模型</label>
              <div class="model-row">
                <select v-model="model">
                  <option v-if="!model" value="" disabled>选择或获取模型</option>
                  <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
                  <option v-if="model && !models.includes(model)" :value="model">{{ model }}</option>
                </select>
                <button
                  type="button"
                  class="btn-secondary"
                  :disabled="loadingModels || !baseUrl.trim()"
                  @click="fetchModels"
                >
                  {{ loadingModels ? '获取中…' : '获取模型' }}
                </button>
              </div>
            </div>
            <p class="hint">获取模型由桌面应用直连厂商 API，不依赖 Sidecar</p>
          </template>

          <template v-else>
            <div v-if="isOllama" class="hint">本地 Ollama 无需 API Key</div>
            <div v-else class="field">
              <label>API Key</label>
              <input
                v-model="apiKey"
                type="password"
                placeholder="sk-..."
                autocomplete="off"
              />
              <p v-if="hasStoredKey && !apiKey" class="hint">已保存密钥，留空表示不修改</p>
            </div>
          </template>

          <p v-if="dialogError" class="error">{{ dialogError }}</p>
        </div>

        <footer class="dialog-footer">
          <button type="button" class="btn-secondary" @click="emit('cancel')">取消</button>
          <button type="button" class="btn-primary" @click="submit">保存</button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 24px;
}

.dialog {
  width: 100%;
  max-width: 480px;
  background: var(--bg-popover);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 16px 48px var(--shadow-color);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}

.dialog-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.btn-close {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 22px;
  cursor: pointer;
  line-height: 1;
}

.dialog-body {
  padding: 16px;
}

.field {
  margin-bottom: 14px;
}

.field label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 6px;
}

.field input,
.field select {
  width: 100%;
  box-sizing: border-box;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  padding: 8px 12px;
  font-size: 13px;
  font-family: inherit;
}

.model-row {
  display: flex;
  gap: 8px;
}

.model-row select {
  flex: 1;
}

.btn-secondary {
  background: var(--btn-secondary-bg);
  color: var(--text-primary);
  border: none;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 6px 0 0;
}

.error {
  font-size: 12px;
  color: var(--danger);
  margin: 8px 0 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

.btn-primary {
  background: var(--accent);
  color: var(--text-on-accent);
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
}

.dialog-footer .btn-secondary {
  padding: 8px 16px;
}
</style>
