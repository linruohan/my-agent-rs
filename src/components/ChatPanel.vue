<script setup lang="ts">
import { computed, ref } from 'vue';
import { useSessionStore } from '@/stores/session';
import { useAgentWs } from '@/composables/useAgentWs';
import ProcessSteps from '@/components/ProcessSteps.vue';
import ChatInputBar from '@/components/ChatInputBar.vue';
import MarkdownContent from '@/components/MarkdownContent.vue';
import MessageAttachments from '@/components/MessageAttachments.vue';
import { hasFencedCodeBlock } from '@/utils/markdown';
import { formatDuration } from '@/utils/formatDuration';
import { buildMessageBlocks, type AssistantTurnBlock } from '@/utils/messageBlocks';
import type { Message } from '@/types';
import type { ChatAttachment } from '@/utils/attachments';

const sessionStore = useSessionStore();
const { send } = useAgentWs();

const previewSrc = ref<string | null>(null);
const previewAlt = ref('');

function handleSend(text: string, attachments?: ChatAttachment[]) {
  if (!sessionStore.currentThreadId) return;
  send(text, sessionStore.currentThreadId, attachments);
}

function onPreviewImage(src: string, name: string) {
  previewSrc.value = src;
  previewAlt.value = name;
}

function closePreview() {
  previewSrc.value = null;
  previewAlt.value = '';
}

const messageBlocks = computed(() => buildMessageBlocks(sessionStore.messages));

function isStreamingPlaceholder(assistant: Message | null, blockIndex: number) {
  if (!assistant) return false;
  return (
    !assistant.content.trim() &&
    sessionStore.isStreaming &&
    blockIndex === messageBlocks.value.length - 1
  );
}

function turnInProgress(block: AssistantTurnBlock, blockIndex: number) {
  const isLast = blockIndex === messageBlocks.value.length - 1;
  if (!isLast) return false;
  if (sessionStore.isStreaming) {
    if (!block.assistant?.content.trim()) return true;
    if (block.tools.some((t) => sessionStore.pendingToolCalls.get(t.id)?.status === 'running')) {
      return true;
    }
  }
  return block.tools.some((t) => sessionStore.pendingToolCalls.get(t.id)?.status === 'running');
}

function processDefaultExpanded(block: AssistantTurnBlock, blockIndex: number) {
  return turnInProgress(block, blockIndex);
}

function userHasCode(msg: Message) {
  return msg.role === 'user' && hasFencedCodeBlock(msg.content);
}

function userHasAttachments(msg: Message) {
  return msg.role === 'user' && !!msg.attachments?.length;
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
        <template v-for="(block, blockIndex) in messageBlocks" :key="block.kind === 'user' ? block.message.id : block.id">
          <div v-if="block.kind === 'user'" class="message user">
            <div v-if="userHasCode(block.message) || userHasAttachments(block.message)" class="bubble bubble-user-md">
              <MarkdownContent v-if="block.message.content.trim()" :content="block.message.content" variant="user" />
              <MessageAttachments
                v-if="block.message.attachments?.length"
                :attachments="block.message.attachments"
                @preview-image="onPreviewImage"
              />
            </div>
            <div v-else class="bubble">{{ block.message.content }}</div>
          </div>

          <div v-else class="message assistant">
            <div class="assistant-wrap">
              <ProcessSteps
                v-if="block.tools.length"
                :tools="block.tools"
                :duration-ms="block.assistant?.durationMs"
                :in-progress="turnInProgress(block, blockIndex)"
                :default-expanded="processDefaultExpanded(block, blockIndex)"
              />

              <div
                v-if="isStreamingPlaceholder(block.assistant, blockIndex)"
                class="bubble typing-indicator"
              >
                正在生成…
              </div>
              <template v-else-if="block.assistant?.content.trim()">
                <div class="bubble bubble-final">
                  <MarkdownContent :content="block.assistant.content" variant="assistant" />
                </div>
                <div v-if="block.assistant.durationMs != null && !block.tools.length" class="message-meta">
                  耗时 {{ formatDuration(block.assistant.durationMs) }}
                </div>
              </template>
              <div
                v-else-if="turnInProgress(block, blockIndex) && !block.tools.length"
                class="bubble typing-indicator"
              >
                正在处理…
              </div>
            </div>
          </div>
        </template>
      </template>
    </div>
    <div class="input-area">
      <ChatInputBar @send="handleSend" />
    </div>

    <Teleport to="body">
      <div v-if="previewSrc" class="image-preview-overlay" @click="closePreview">
        <div class="image-preview-wrap" @click.stop>
          <button type="button" class="preview-close" aria-label="关闭" @click="closePreview">×</button>
          <img :src="previewSrc" :alt="previewAlt" class="preview-image" />
          <p v-if="previewAlt" class="preview-caption">{{ previewAlt }}</p>
        </div>
      </div>
    </Teleport>
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
  margin-bottom: 16px;
}

.welcome-sub {
  font-size: 16px;
  color: #71717a;
  max-width: 480px;
  line-height: 1.6;
}

.message {
  display: flex;
  flex-direction: column;
}

.message.user {
  align-items: flex-end;
}

.message.assistant {
  align-items: flex-start;
}

.bubble {
  max-width: 85%;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.5;
  font-size: 14px;
  white-space: pre-wrap;
  word-break: break-word;
}

.message.user .bubble {
  background: #2563eb;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.message.user .bubble-user-md {
  background: #1e3a5f;
  white-space: normal;
}

.message.assistant .bubble {
  background: var(--assistant-bubble, #16181d);
  border: 1px solid var(--border, #2a2d35);
  color: var(--text-primary, #e4e4e7);
  border-bottom-left-radius: 4px;
}

.message.assistant .bubble-final {
  max-width: 100%;
}

.typing-indicator {
  color: var(--text-muted, #71717a);
  font-style: italic;
}

.assistant-wrap {
  max-width: 85%;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.message-meta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-muted, #71717a);
}

.input-area {
  padding: 0 24px 16px;
  flex-shrink: 0;
}

.image-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.image-preview-wrap {
  position: relative;
  max-width: min(90vw, 1200px);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.preview-close {
  position: absolute;
  top: -36px;
  right: 0;
  background: none;
  border: none;
  color: #fff;
  font-size: 28px;
  cursor: pointer;
  line-height: 1;
}

.preview-image {
  max-width: 100%;
  max-height: calc(90vh - 40px);
  object-fit: contain;
  border-radius: 8px;
}

.preview-caption {
  margin-top: 12px;
  color: #a1a1aa;
  font-size: 13px;
  text-align: center;
}
</style>
