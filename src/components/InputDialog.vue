<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';

const props = defineProps<{
  open: boolean;
  title?: string;
  defaultValue?: string;
  placeholder?: string;
  confirmLabel?: string;
  multiline?: boolean;
}>();

const emit = defineEmits<{
  confirm: [value: string];
  cancel: [];
}>();

const inputRef = ref<HTMLInputElement | HTMLTextAreaElement | null>(null);
const value = ref('');

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      value.value = props.defaultValue ?? '';
      nextTick(() => {
        inputRef.value?.focus();
        if (inputRef.value instanceof HTMLInputElement) {
          inputRef.value.select();
        }
      });
    }
  }
);

function submit() {
  const trimmed = value.value.trim();
  if (!trimmed) return;
  emit('confirm', trimmed);
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !props.multiline) {
    e.preventDefault();
    submit();
  }
  if (e.key === 'Escape') {
    emit('cancel');
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="overlay" @click.self="emit('cancel')">
      <div class="dialog" role="dialog" aria-modal="true">
        <header class="dialog-header">
          <h3>{{ title || '输入' }}</h3>
          <button type="button" class="btn-close" aria-label="关闭" @click="emit('cancel')">
            ×
          </button>
        </header>
        <div class="dialog-body">
          <textarea
            v-if="multiline"
            ref="inputRef"
            v-model="value"
            class="text-input textarea"
            :placeholder="placeholder"
            rows="4"
            @keydown="onKeydown"
          />
          <input
            v-else
            ref="inputRef"
            v-model="value"
            type="text"
            class="text-input"
            :placeholder="placeholder"
            @keydown="onKeydown"
          />
        </div>
        <footer class="dialog-footer">
          <button type="button" class="btn-secondary" @click="emit('cancel')">取消</button>
          <button type="button" class="btn-primary" :disabled="!value.trim()" @click="submit">
            {{ confirmLabel || '确定' }}
          </button>
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
  padding: 0 4px;
}

.btn-close:hover {
  color: var(--text-primary);
}

.dialog-body {
  padding: 16px;
}

.text-input {
  width: 100%;
  box-sizing: border-box;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  padding: 10px 12px;
  font-size: 14px;
  font-family: inherit;
  outline: none;
}

.textarea {
  resize: vertical;
  min-height: 96px;
  line-height: 1.5;
}

.text-input:focus {
  border-color: var(--accent);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

.btn-secondary,
.btn-primary {
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
}

.btn-secondary {
  background: var(--border);
  color: var(--text-primary);
}

.btn-secondary:hover {
  background: var(--btn-secondary-bg);
}

.btn-primary {
  background: var(--accent);
  color: var(--text-on-accent);
}

.btn-primary:hover:not(:disabled) {
  background: var(--user-bubble);
}

.btn-primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
