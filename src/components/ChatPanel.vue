<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { useSessionStore } from '@/stores/session';
import { useSettingsStore } from '@/stores/settings';
import { useAgentWs } from '@/composables/useAgentWs';
import ProcessSteps from '@/components/ProcessSteps.vue';
import ChatInputBar from '@/components/ChatInputBar.vue';
import MarkdownContent from '@/components/MarkdownContent.vue';
import MessageAttachments from '@/components/MessageAttachments.vue';
import { hasFencedCodeBlock } from '@/utils/markdown';
import { formatDuration } from '@/utils/formatDuration';
import { buildMessageBlocks, type AssistantTurnBlock } from '@/utils/messageBlocks';
import { extractSearchTerms } from '@/utils/highlightTerms';
import type { Message } from '@/types';
import type { ChatAttachment } from '@/utils/attachments';

const sessionStore = useSessionStore();
const settings = useSettingsStore();
const { send } = useAgentWs();

const previewSrc = ref<string | null>(null);
const previewAlt = ref('');
const messagesEl = ref<HTMLElement | null>(null);

function scrollToBottom(instant = false) {
  nextTick(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const el = messagesEl.value;
        if (!el) return;
        el.scrollTo({ top: el.scrollHeight, behavior: instant ? 'auto' : 'smooth' });
      });
    });
  });
}

function handleSend(text: string, attachments?: ChatAttachment[]) {
  if (!sessionStore.currentThreadId) return;
  send(text, sessionStore.currentThreadId, attachments);
  scrollToBottom();
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

watch(
  () => sessionStore.messages,
  () => scrollToBottom(sessionStore.isStreaming),
  { deep: true }
);

watch(messageBlocks, () => scrollToBottom(sessionStore.isStreaming), { deep: true });

watch(
  () => sessionStore.historyLoadedGeneration,
  () => {
    if (sessionStore.messages.length === 0 || sessionStore.isStreaming) return;
    scrollToBottom(true);
    setTimeout(() => scrollToBottom(true), 120);
    setTimeout(() => scrollToBottom(true), 320);
  }
);

watch(
  () => sessionStore.isStreaming,
  (streaming, wasStreaming) => {
    if (wasStreaming && !streaming) {
      scrollToBottom();
      setTimeout(() => scrollToBottom(true), 120);
    }
  }
);

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

function getHighlightTerms(block: AssistantTurnBlock, blockIndex: number): string[] {
  const terms = new Set<string>();

  const prev = messageBlocks.value[blockIndex - 1];
  if (prev?.kind === 'user') {
    extractSearchTerms(prev.message.content).forEach((term) => terms.add(term));
  }

  for (const tool of block.tools) {
    if (tool.toolName === 'web_search') {
      const tc = sessionStore.pendingToolCalls.get(tool.id);
      const query = tc?.args?.query;
      if (typeof query === 'string') {
        extractSearchTerms(query).forEach((term) => terms.add(term));
      }
    }
  }

  return [...terms];
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
    <div v-if="settings.wsReadOnly" class="readonly-banner">
      已在其他标签页打开 Agent 连接，当前标签页为只读模式。请切换到主标签页发送消息。
    </div>
    <div ref="messagesEl" class="messages">
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
                  <MarkdownContent
                    :content="block.assistant.content"
                    variant="assistant"
                    :highlight-terms="getHighlightTerms(block, blockIndex)"
                  />
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
  min-width: 0;
  min-height: 0;
}

.readonly-banner {
  flex-shrink: 0;
  padding: 8px 16px;
  background: color-mix(in srgb, var(--warning) 15%, var(--bg-sidebar));
  border-bottom: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
}

.messages {
  flex: 1;
  min-width: 0;
  overflow-x: hidden;
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
  background: linear-gradient(
    135deg,
    var(--accent) 0%,
    color-mix(in srgb, var(--accent) 55%, var(--warning)) 50%,
    var(--warning) 100%
  );
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 16px;
}

.welcome-sub {
  font-size: 16px;
  color: var(--text-muted);
  max-width: 480px;
  line-height: 1.6;
}

.message {
  display: flex;
  flex-direction: column;
  min-width: 0;
  max-width: 100%;
}

.message.user {
  align-items: flex-end;
}

.message.assistant {
  align-items: flex-start;
}

.bubble {
  max-width: 85%;
  min-width: 0;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.5;
  font-size: 14px;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.message.user .bubble {
  background: var(--user-bubble);
  color: var(--text-on-accent);
  border-bottom-right-radius: 4px;
}

.message.user .bubble-user-md {
  background: var(--accent-subtle);
  white-space: normal;
}

.message.assistant .bubble {
  background: var(--assistant-bubble, var(--bg-panel));
  border: 1px solid var(--border, var(--border));
  color: var(--text-primary, var(--text-primary));
  border-bottom-left-radius: 4px;
}

:global(html[data-color-mode='dark']) .message.assistant .bubble {
  background: var(--bg-elevated);
  border-color: color-mix(in srgb, var(--border) 80%, var(--text-muted) 20%);
}

.message.assistant .bubble-final {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.typing-indicator {
  color: var(--text-muted, var(--text-muted));
  font-style: italic;
}

.assistant-wrap {
  max-width: 85%;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

.message-meta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-muted, var(--text-muted));
}

.input-area {
  padding: 0 24px 16px;
  flex-shrink: 0;
}

.image-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: var(--overlay-bg);
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
  color: var(--text-on-accent);
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
  color: var(--text-secondary);
  font-size: 13px;
  text-align: center;
}
</style>
