<script setup lang="ts">
import { computed } from 'vue';
import { useSessionStore } from '@/stores/session';
import { useAgentWs } from '@/composables/useAgentWs';
import ToolCallCard from '@/components/ToolCallCard.vue';
import ChatInputBar from '@/components/ChatInputBar.vue';
import { renderMarkdown } from '@/utils/markdown';

const sessionStore = useSessionStore();
const { send } = useAgentWs();

function handleSend(
  text: string,
  attachments?: Array<{ type: string; name: string; content: string }>
) {
  if (!sessionStore.currentThreadId) return;
  send(text, sessionStore.currentThreadId, attachments);
}

const runningTools = () =>
  [...sessionStore.pendingToolCalls.values()].filter((t) => t.status === 'running');

function isStreamingPlaceholder(msg: { role: string; content: string }, index: number) {
  return (
    msg.role === 'assistant' &&
    !msg.content.trim() &&
    sessionStore.isStreaming &&
    index === sessionStore.messages.length - 1
  );
}

function shouldShowMessage(msg: { role: string; content: string }, index: number) {
  if (msg.role !== 'assistant') return true;
  if (msg.content.trim()) return true;
  return isStreamingPlaceholder(msg, index);
}

const showWelcome = computed(
  () =>
    sessionStore.currentThreadId &&
    sessionStore.messages.length === 0 &&
    !sessionStore.isStreaming
);
</script>

<template>
  <div class="chat-panel">
    <div class="messages">
      <div
        v-if="!sessionStore.currentThreadId || showWelcome"
        class="welcome"
      >
        <h1 class="welcome-title">个人助理 Agent</h1>
        <p class="welcome-sub">
          提问、粘贴错误日志，或指向一个仓库。我可以阅读代码、调用工具，帮你推进任务。
        </p>
      </div>
      <template v-else>
        <div
          v-for="(msg, index) in sessionStore.messages"
          :key="msg.id"
          v-show="shouldShowMessage(msg, index)"
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
          <div
            v-else-if="isStreamingPlaceholder(msg, index)"
            class="bubble typing-indicator"
          >
            正在生成…
          </div>
          <div
            v-else-if="msg.role === 'assistant'"
            class="bubble markdown-body"
            v-html="renderMarkdown(msg.content)"
          />
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
      <ChatInputBar @send="handleSend" />
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
  padding: 24px 32px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 40px 24px;
}

.welcome-title {
  font-size: 42px;
  font-weight: 700;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, #f97316 0%, #fb923c 50%, #fbbf24 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 16px;
}

.welcome-sub {
  color: #71717a;
  font-size: 15px;
  line-height: 1.6;
  max-width: 480px;
  margin: 0;
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

.message.assistant {
  display: flex;
  justify-content: flex-start;
}

.message.assistant .bubble {
  background: #1f2128;
  max-width: 85%;
  padding: 12px 16px;
  border-radius: 12px 12px 12px 4px;
  font-size: 14px;
  line-height: 1.6;
  color: #e4e4e7;
  word-break: break-word;
}

.message.assistant .bubble.markdown-body :deep(p) {
  margin: 0.4em 0;
}

.message.assistant .bubble.markdown-body :deep(p:first-child) {
  margin-top: 0;
}

.message.assistant .bubble.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.message.assistant .bubble.markdown-body :deep(ul),
.message.assistant .bubble.markdown-body :deep(ol) {
  margin: 0.4em 0;
  padding-left: 1.4em;
}

.message.assistant .bubble.markdown-body :deep(li) {
  margin: 0.25em 0;
}

.message.assistant .bubble.markdown-body :deep(h1),
.message.assistant .bubble.markdown-body :deep(h2),
.message.assistant .bubble.markdown-body :deep(h3) {
  margin: 0.6em 0 0.3em;
  font-size: 1em;
  font-weight: 600;
  color: #f4f4f5;
}

.message.assistant .bubble.markdown-body :deep(h1:first-child),
.message.assistant .bubble.markdown-body :deep(h2:first-child),
.message.assistant .bubble.markdown-body :deep(h3:first-child) {
  margin-top: 0;
}

.message.assistant .bubble.markdown-body :deep(strong) {
  font-weight: 600;
  color: #f4f4f5;
}

.message.assistant .bubble.markdown-body :deep(a) {
  color: #60a5fa;
  text-decoration: none;
}

.message.assistant .bubble.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.message.assistant .bubble.markdown-body :deep(code) {
  background: #0f1117;
  border-radius: 4px;
  padding: 0.1em 0.35em;
  font-size: 0.9em;
  font-family: ui-monospace, 'Cascadia Code', monospace;
}

.message.assistant .bubble.markdown-body :deep(pre) {
  background: #0f1117;
  border-radius: 6px;
  padding: 10px 12px;
  overflow-x: auto;
  margin: 0.5em 0;
}

.message.assistant .bubble.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
}

.message.assistant .bubble.markdown-body :deep(blockquote) {
  margin: 0.5em 0;
  padding-left: 12px;
  border-left: 3px solid #3b82f6;
  color: #a1a1aa;
}

.message.assistant .bubble.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #2a2d35;
  margin: 0.8em 0;
}

.typing-indicator {
  color: #71717a;
  font-style: italic;
}

.tool-wrapper {
  max-width: 80%;
}

.input-area {
  padding: 16px 32px 24px;
  flex-shrink: 0;
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
}
</style>
