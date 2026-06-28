<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { LabelItem } from '@/stores/tasks';
import { DEFAULT_LABEL_COLOR, LABEL_COLORS } from '@/utils/labelColors';

export type LabelFormPayload = {
  name: string;
  color: string;
};

const props = defineProps<{
  open: boolean;
  mode: 'create' | 'edit';
  label?: LabelItem | null;
}>();

const emit = defineEmits<{
  save: [payload: LabelFormPayload];
  cancel: [];
}>();

const name = ref('');
const color = ref(DEFAULT_LABEL_COLOR);
const dialogError = ref('');

const dialogTitle = computed(() => (props.mode === 'create' ? '新建标签' : '编辑标签'));
const submitLabel = computed(() => (props.mode === 'create' ? '添加' : '保存'));

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return;
    dialogError.value = '';
    if (props.mode === 'edit' && props.label) {
      name.value = props.label.name;
      color.value = props.label.color || DEFAULT_LABEL_COLOR;
    } else if (props.label?.name) {
      name.value = props.label.name;
      color.value = props.label.color || DEFAULT_LABEL_COLOR;
    } else {
      name.value = '';
      color.value = DEFAULT_LABEL_COLOR;
    }
  }
);

function submit() {
  dialogError.value = '';
  if (!name.value.trim()) {
    dialogError.value = '请填写标签名称';
    return;
  }
  emit('save', { name: name.value.trim(), color: color.value });
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
          <h3>{{ dialogTitle }}</h3>
          <button type="button" class="btn-close" aria-label="关闭" @click="emit('cancel')">×</button>
        </header>

        <div class="dialog-body">
          <div class="field">
            <label>标签名称</label>
            <input v-model="name" type="text" placeholder="输入标签名称…" />
          </div>

          <div class="color-section">
            <div class="color-preview" :style="{ background: color }" />
            <div class="color-grid">
              <button
                v-for="c in LABEL_COLORS"
                :key="c"
                type="button"
                class="color-swatch"
                :class="{ active: c === color }"
                :style="{ background: c }"
                :aria-label="c"
                @click="color = c"
              />
            </div>
          </div>

          <p v-if="dialogError" class="error">{{ dialogError }}</p>
        </div>

        <footer class="dialog-footer">
          <button type="button" class="btn-cancel" @click="emit('cancel')">取消</button>
          <button type="button" class="btn-primary" @click="submit">{{ submitLabel }}</button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: var(--overlay-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 24px;
}

.dialog {
  width: 100%;
  max-width: 420px;
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

.field input {
  width: 100%;
  box-sizing: border-box;
  background: var(--bg-input, var(--bg-code));
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  padding: 8px 12px;
  font-size: 13px;
  font-family: inherit;
}

.color-section {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 10px;
}

.color-preview {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  flex-shrink: 0;
}

.color-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 6px;
  flex: 1;
}

.color-swatch {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  padding: 0;
}

.color-swatch.active {
  border-color: var(--text-primary);
  box-shadow: 0 0 0 2px var(--bg-popover);
}

.error {
  font-size: 12px;
  color: var(--danger);
  margin: 8px 0 0;
}

.dialog-footer {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

.btn-cancel {
  background: var(--btn-secondary-bg);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
}

.btn-primary {
  background: var(--accent);
  color: var(--text-on-accent);
  border: none;
  border-radius: 8px;
  padding: 10px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
}
</style>
