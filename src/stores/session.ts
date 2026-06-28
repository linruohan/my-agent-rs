import { ref } from 'vue';
import { defineStore } from 'pinia';
import type { InterruptEvent, Message, ToolCall } from '@/types';
import { wsResume } from '@/utils/wsBridge';

const PINNED_KEY = 'pa-pinned-sessions';
const PREVIEW_KEY = 'pa-session-previews';
const CURRENT_THREAD_KEY = 'pa-current-thread';

function loadCurrentThread(): string | null {
  try {
    return localStorage.getItem(CURRENT_THREAD_KEY);
  } catch {
    return null;
  }
}

function loadPinned(): string[] {
  try {
    const raw = localStorage.getItem(PINNED_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function savePinned(ids: string[]) {
  localStorage.setItem(PINNED_KEY, JSON.stringify(ids));
}

function loadPreviews(): Record<string, string> {
  try {
    const raw = localStorage.getItem(PREVIEW_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function savePreviews(map: Record<string, string>) {
  localStorage.setItem(PREVIEW_KEY, JSON.stringify(map));
}

export const useSessionStore = defineStore('session', () => {
  const currentThreadId = ref<string | null>(loadCurrentThread());
  const pendingToolCalls = ref<Map<string, ToolCall>>(new Map());
  const interruptQueue = ref<InterruptEvent[]>([]);
  const messages = ref<Message[]>([]);
  const isStreaming = ref(false);
  const sessions = ref<Array<{ thread_id: string; title: string; created_at: string; archived?: boolean }>>([]);
  const archivedSessions = ref<Array<{ thread_id: string; title: string; created_at: string; archived?: boolean }>>([]);
  const pinnedIds = ref<string[]>(loadPinned());
  const sessionPreviews = ref<Record<string, string>>(loadPreviews());
  const inputFocusGeneration = ref(0);
  const historyLoadedGeneration = ref(0);
  const historyLoadGeneration = ref(0);

  function bumpInputFocus() {
    inputFocusGeneration.value += 1;
  }

  function bumpHistoryLoaded() {
    historyLoadedGeneration.value += 1;
  }

  function addMessage(msg: Message) {
    messages.value.push(msg);
    if (currentThreadId.value && msg.role === 'user') {
      const preview = msg.content.replace(/\n📎 .+$/, '').trim().slice(0, 80);
      sessionPreviews.value[currentThreadId.value] = preview;
      savePreviews(sessionPreviews.value);
    }
  }

  function appendToLastAssistant(content: string) {
    const last = messages.value[messages.value.length - 1];
    if (last && last.role === 'assistant') {
      last.content += content;
    } else {
      addMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content,
      });
    }
  }

  function setLastAssistantDuration(ms: number) {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const msg = messages.value[i];
      if (msg.role === 'assistant') {
        msg.durationMs = ms;
        return;
      }
    }
  }

  function addPendingToolCall(tc: ToolCall) {
    pendingToolCalls.value.set(tc.id, tc);
  }

  function resolveToolCall(
    name: string,
    result: string,
    toolCallId?: string,
    citations?: Array<{ title: string; url: string }>
  ) {
    for (const [id, tc] of pendingToolCalls.value) {
      const idMatch = toolCallId && (id === toolCallId || tc.id === toolCallId);
      const nameMatch = tc.name === name && tc.status === 'running';
      if (idMatch || (!toolCallId && nameMatch)) {
        tc.status = 'done';
        tc.result = result;
        if (citations?.length) tc.citations = citations;
        pendingToolCalls.value.set(id, tc);
        const msg = messages.value.find((m) => m.id === id || m.id === tc.id);
        if (msg) {
          msg.content = result;
          if (citations?.length) msg.citations = citations;
        }
        break;
      }
    }
  }

  function updateToolProgress(toolName: string, toolCallId: string | undefined, status: string) {
    for (const [id, tc] of pendingToolCalls.value) {
      const idMatch = toolCallId && (id === toolCallId || tc.id === toolCallId);
      const nameMatch = tc.name === toolName && tc.status === 'running';
      if (idMatch || (!toolCallId && nameMatch)) {
        const msg = messages.value.find((m) => m.id === id || m.id === tc.id);
        if (msg) {
          msg.content = `执行中: ${toolName} (${status})`;
        }
        break;
      }
    }
  }

  function loadHistory(
    historyMessages: Array<{
      role: string;
      content: string;
      tool_name?: string;
      citations?: Array<{ title: string; url: string }>;
    }>,
    loadGeneration?: number
  ) {
    if (
      loadGeneration !== undefined &&
      loadGeneration !== historyLoadGeneration.value
    ) {
      return;
    }
    messages.value = historyMessages.map((m) => ({
      id: crypto.randomUUID(),
      role: m.role as Message['role'],
      content: m.content,
      toolName: m.tool_name,
      citations: m.citations,
    }));
    pendingToolCalls.value.clear();
    bumpHistoryLoaded();
  }

  function setCurrentThread(threadId: string | null) {
    currentThreadId.value = threadId;
    historyLoadGeneration.value += 1;
    if (threadId) {
      localStorage.setItem(CURRENT_THREAD_KEY, threadId);
    } else {
      localStorage.removeItem(CURRENT_THREAD_KEY);
    }
    clearMessages();
  }

  function resolveInterrupt(decision: 'approve' | 'reject' | 'edit', editedArgs?: Record<string, unknown>) {
    const event = interruptQueue.value.shift();
    if (event) {
      wsResume(event.thread_id, decision, editedArgs);
    }
  }

  function clearMessages() {
    messages.value = [];
    pendingToolCalls.value.clear();
  }

  function togglePin(threadId: string) {
    const idx = pinnedIds.value.indexOf(threadId);
    if (idx >= 0) {
      pinnedIds.value.splice(idx, 1);
    } else {
      pinnedIds.value.unshift(threadId);
    }
    savePinned(pinnedIds.value);
  }

  function isPinned(threadId: string) {
    return pinnedIds.value.includes(threadId);
  }

  function getPreview(threadId: string) {
    return sessionPreviews.value[threadId] || '';
  }

  function removePreview(threadId: string) {
    if (!sessionPreviews.value[threadId]) return;
    const next = { ...sessionPreviews.value };
    delete next[threadId];
    sessionPreviews.value = next;
    savePreviews(next);
  }

  return {
    currentThreadId,
    pendingToolCalls,
    interruptQueue,
    messages,
    isStreaming,
    sessions,
    archivedSessions,
    pinnedIds,
    sessionPreviews,
    inputFocusGeneration,
    historyLoadedGeneration,
    historyLoadGeneration,
    bumpInputFocus,
    bumpHistoryLoaded,
    addMessage,
    appendToLastAssistant,
    setLastAssistantDuration,
    addPendingToolCall,
    resolveToolCall,
    updateToolProgress,
    resolveInterrupt,
    clearMessages,
    loadHistory,
    setCurrentThread,
    togglePin,
    isPinned,
    getPreview,
    removePreview,
  };
});
