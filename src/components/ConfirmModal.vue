<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useSessionStore } from '@/stores/session';

const sessionStore = useSessionStore();

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
    alert('JSON 格式无效，请检查后重试');
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
      >{{ JSON.stringify(currentInterrupt.args, null, 2) }}</pre>
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
  background: #1f2128;
  border: 1px solid #2a2d35;
  border-radius: 12px;
  padding: 24px;
  max-width: 480px;
  width: 90%;
}

.modal h3 {
  margin-bottom: 12px;
  font-size: 16px;
}

.preview {
  color: #a1a1aa;
  margin-bottom: 8px;
  font-size: 14px;
}

.action {
  font-size: 13px;
  color: #71717a;
  margin-bottom: 12px;
}

.args {
  background: #0f1117;
  border-radius: 6px;
  padding: 10px;
  font-size: 11px;
  color: #a1a1aa;
  margin-bottom: 16px;
  overflow-x: auto;
}

.edit-label {
  display: block;
  font-size: 12px;
  color: #71717a;
  margin-bottom: 6px;
}

.edit-area {
  width: 100%;
  background: #0f1117;
  border: 1px solid #2a2d35;
  border-radius: 6px;
  color: #e4e4e7;
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
  background: #374151;
  color: #e4e4e7;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
}

.btn-edit {
  background: #4b5563;
  color: #e4e4e7;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
}

.btn-approve {
  background: #10b981;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
}
</style>
