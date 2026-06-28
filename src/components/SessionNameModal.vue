<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';

const props = defineProps<{
  open: boolean;
  title?: string;
  defaultValue?: string;
  placeholder?: string;
  confirmLabel?: string;
}>();

const emit = defineEmits<{
  confirm: [value: string];
  cancel: void;
}>();

const inputRef = ref<HTMLInputElement | null>(null);
const value = ref('');

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      value.value = props.defaultValue ?? '';
      nextTick(() => inputRef.value?.focus());
    }
  }
);

function submit() {
  const trimmed = value.value.trim();
  if (!trimmed) return;
  emit('confirm', trimmed);
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
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
          <h3>{{ title || '会话名称' }}</h3>
          <button type="button" class="btn-close" aria-label="关闭" @click="emit('cancel')">
            ×
          </button>
        </header>
        <div class="dialog-body">
          <input
            ref="inputRef"
            v-model="value"
            type="text"
            class="name-input"
            :placeholder="placeholder || '输入会话名称'"
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
  background: #1a1c22;
  border: 1px solid #2a2d35;
  border-radius: 12px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.45);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #2a2d35;
}

.dialog-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: #e4e4e7;
  margin: 0;
}

.btn-close {
  background: none;
  border: none;
  color: #71717a;
  font-size: 22px;
  cursor: pointer;
  line-height: 1;
  padding: 0 4px;
}

.btn-close:hover {
  color: #e4e4e7;
}

.dialog-body {
  padding: 16px;
}

.name-input {
  width: 100%;
  box-sizing: border-box;
  background: #0f1117;
  border: 1px solid #2a2d35;
  border-radius: 8px;
  color: #e4e4e7;
  padding: 10px 12px;
  font-size: 14px;
  font-family: inherit;
  outline: none;
}

.name-input:focus {
  border-color: #3b82f6;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #2a2d35;
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
  background: #2a2d35;
  color: #e4e4e7;
}

.btn-secondary:hover {
  background: #374151;
}

.btn-primary {
  background: #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
