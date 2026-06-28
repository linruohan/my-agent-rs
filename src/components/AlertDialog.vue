<script setup lang="ts">
defineProps<{
  open: boolean;
  title?: string;
  message?: string;
  confirmLabel?: string;
}>();

const emit = defineEmits<{
  confirm: [];
}>();
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="overlay" @click.self="emit('confirm')">
      <div class="dialog" role="alertdialog" aria-modal="true">
        <header class="dialog-header">
          <h3>{{ title || '提示' }}</h3>
        </header>
        <div class="dialog-body">
          <p class="message">{{ message }}</p>
        </div>
        <footer class="dialog-footer">
          <button type="button" class="btn-primary" @click="emit('confirm')">
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
  max-width: 400px;
  background: var(--bg-popover);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 16px 48px var(--shadow-color);
}

.dialog-header {
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}

.dialog-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.dialog-body {
  padding: 16px;
}

.message {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
  word-break: break-all;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

.btn-primary {
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  background: var(--accent);
  color: var(--text-on-accent);
}

.btn-primary:hover {
  background: var(--user-bubble);
}
</style>
