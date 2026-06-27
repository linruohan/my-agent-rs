<script setup lang="ts">
import { ref } from 'vue';
import { useSessionStore } from '@/stores/session';
import { useAgentWs } from '@/composables/useAgentWs';
import ToolCallCard from '@/components/ToolCallCard.vue';

const sessionStore = useSessionStore();
const { send, stop } = useAgentWs();
const input = ref('');
const pendingAttachments = ref<Array<{ type: string; name: string; content: string }>>([]);

const ATTACH_ACCEPT = '.md,.txt,.markdown,.pdf,.json,.csv';

async function handleFileSelect(e: Event) {
  const inputEl = e.target as HTMLInputElement;
  if (!inputEl.files?.length) return;
  for (const file of Array.from(inputEl.files)) {
    const content = await file.text();
    pendingAttachments.value.push({ type: 'text', name: file.name, content });
  }
  inputEl.value = '';
}

function removeAttachment(index: number) {
  pendingAttachments.value.splice(index, 1);
}

function handleSend() {
  const text = input.value.trim();
  if (!text || !sessionStore.currentThreadId) return;
  const attachments =
    pendingAttachments.value.length > 0 ? [...pendingAttachments.value] : undefined;
  send(text, sessionStore.currentThreadId, attachments);
  input.value = '';
  pendingAttachments.value = [];
}

function handleStop() {
  if (sessionStore.currentThreadId) {
    stop(sessionStore.currentThreadId);
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
}

const runningTools = () =>
  [...sessionStore.pendingToolCalls.values()].filter((t) => t.status === 'running');
</script>

<template>
  <div class="chat-panel">
    <div class="messages">
      <div v-if="!sessionStore.currentThreadId" class="placeholder">
        请选择或新建一个会话
      </div>
      <template v-else>
        <div
          v-for="msg in sessionStore.messages"
          :key="msg.id"
          :class="['message', msg.role]"
        >
          <div v-if="msg.role === 'tool'" class="tool-wrapper">
            <ToolCallCard
              :name="msg.toolName || ''"
              :category="msg.category"
              :content="msg.content"
              :citations="msg.citations"
            />
          </div>
          <div v-else class="bubble">{{ msg.content }}</div>
        </div>
        <ToolCallCard
          v-for="tc in runningTools()"
          :key="tc.id"
          :name="tc.name"
          :category="tc.category"
          :args="tc.args"
          :status="tc.status"
        />
      </template>
    </div>
    <div class="input-area">
      <div v-if="pendingAttachments.length" class="attachments">
        <span
          v-for="(att, i) in pendingAttachments"
          :key="i"
          class="attachment-chip"
        >
          📎 {{ att.name }}
          <button type="button" class="remove-att" @click="removeAttachment(i)">×</button>
        </span>
      </div>
      <textarea
        v-model="input"
        placeholder="输入消息… (Enter 发送, Shift+Enter 换行)"
        :disabled="!sessionStore.currentThreadId"
        @keydown="handleKeydown"
      />
      <div class="actions">
        <label class="btn-attach">
          附件
          <input type="file" :accept="ATTACH_ACCEPT" multiple hidden @change="handleFileSelect" />
        </label>
        <button
          v-if="sessionStore.isStreaming"
          class="btn-stop"
          @click="handleStop"
        >
          停止
        </button>
        <button
          class="btn-send"
          :disabled="!input.trim() || !sessionStore.currentThreadId || sessionStore.isStreaming"
          @click="handleSend"
        >
          发送
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.placeholder {
  color: #71717a;
  text-align: center;
  margin-top: 40%;
}

.message.user {
  display: flex;
  justify-content: flex-end;
}

.message.user .bubble {
  background: #2563eb;
  color: white;
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 12px 12px 4px 12px;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.message.assistant .bubble {
  background: #1f2128;
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 12px 12px 12px 4px;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.tool-wrapper {
  max-width: 80%;
}

.input-area {
  border-top: 1px solid #2a2d35;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

textarea {
  width: 100%;
  min-height: 60px;
  max-height: 160px;
  background: #16181d;
  border: 1px solid #2a2d35;
  border-radius: 8px;
  color: #e4e4e7;
  padding: 10px 12px;
  font-size: 14px;
  resize: vertical;
  font-family: inherit;
}

textarea:focus {
  outline: none;
  border-color: #3b82f6;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn-send {
  background: #3b82f6;
  color: white;
  border: none;
  padding: 8px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.btn-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-stop {
  background: #ef4444;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.attachment-chip {
  background: #1f2128;
  border: 1px solid #2a2d35;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  color: #a1a1aa;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.remove-att {
  background: none;
  border: none;
  color: #71717a;
  cursor: pointer;
  font-size: 14px;
  padding: 0 2px;
}

.btn-attach {
  background: #374151;
  color: #e4e4e7;
  border: none;
  padding: 8px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  margin-right: auto;
}
</style>
