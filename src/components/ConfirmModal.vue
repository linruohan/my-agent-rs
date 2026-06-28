<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useSessionStore } from '@/stores/session';
import { useDialogStore } from '@/stores/dialog';
import { formatArgsForDisplay } from '@/utils/formatToolArgs';

const sessionStore = useSessionStore();
const dialog = useDialogStore();

const currentInterrupt = computed(() => sessionStore.interruptQueue[0]);
const editMode = ref(false);
const editedArgsJson = ref('');

watch(currentInterrupt, (intr) => {
  editMode.value = false;
  if (intr?.args) {
    editedArgsJson.value = JSON.stringify(intr.args, null, 2);
  } else {
    editedArgsJson.value = '{}';
  }
});

function approve() {
  sessionStore.resolveInterrupt('approve');
}

function reject() {
  sessionStore.resolveInterrupt('reject');
}

function submitEdit() {
  try {
    const parsed = JSON.parse(editedArgsJson.value) as Record<string, unknown>;
    sessionStore.resolveInterrupt('edit', parsed);
    editMode.value = false;
  } catch {
    void dialog.alert({
      title: '格式错误',
      message: 'JSON 格式无效，请检查后重试',
    });
  }
}
</script>

<template>
  <div v-if="currentInterrupt" class="modal-overlay">
    <div class="modal">
      <h3>确认操作</h3>
      <p class="preview">{{ currentInterrupt.preview }}</p>
      <template v-if="editMode">
        <label class="edit-label">编辑参数 (JSON)</label>
        <textarea v-model="editedArgsJson" class="edit-area" rows="8" />
      </template>
      <pre
        v-else-if="currentInterrupt.args && Object.keys(currentInterrupt.args).length"
        class="args"
      >{{ formatArgsForDisplay(currentInterrupt.args) }}</pre>
      <p class="action">操作: {{ currentInterrupt.action }}</p>
      <div class="buttons">
        <button class="btn-reject" @click="reject">拒绝</button>
        <button v-if="!editMode" class="btn-edit" @click="editMode = true">编辑</button>
        <button v-if="editMode" class="btn-edit" @click="submitEdit">提交编辑</button>
        <button v-if="!editMode" class="btn-approve" @click="approve">批准</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  max-width: 480px;
  width: 90%;
  min-width: 0;
  overflow: hidden;
}

.modal h3 {
  margin-bottom: 12px;
  font-size: 16px;
}

.preview {
  color: var(--text-secondary);
  margin-bottom: 8px;
  font-size: 14px;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.action {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.args {
  background: var(--bg-input);
  border-radius: 6px;
  padding: 10px;
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 16px;
  max-width: 100%;
  max-height: 200px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.edit-label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
}

.edit-area {
  width: 100%;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  padding: 10px;
  font-size: 12px;
  font-family: monospace;
  margin-bottom: 16px;
  resize: vertical;
}

.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn-reject {
  background: var(--btn-secondary-bg);
  color: var(--text-primary);
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
}

.btn-edit {
  background: var(--btn-secondary-bg);
  color: var(--text-primary);
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
}

.btn-approve {
  background: var(--success);
  color: var(--text-on-accent);
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
}
</style>
