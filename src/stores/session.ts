import { ref } from 'vue';
import { defineStore } from 'pinia';
import type { InterruptEvent, Message, ToolCall } from '@/types';
import { useAgentWs } from '@/composables/useAgentWs';

export const useSessionStore = defineStore('session', () => {
  const currentThreadId = ref<string | null>(null);
  const pendingToolCalls = ref<Map<string, ToolCall>>(new Map());
  const interruptQueue = ref<InterruptEvent[]>([]);
  const messages = ref<Message[]>([]);
  const isStreaming = ref(false);
  const sessions = ref<Array<{ thread_id: string; title: string; created_at: string }>>([]);

  function addMessage(msg: Message) {
    messages.value.push(msg);
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

  function loadHistory(
    historyMessages: Array<{
      role: string;
      content: string;
      tool_name?: string;
      citations?: Array<{ title: string; url: string }>;
    }>
  ) {
    messages.value = historyMessages.map((m) => ({
      id: crypto.randomUUID(),
      role: m.role as Message['role'],
      content: m.content,
      toolName: m.tool_name,
      citations: m.citations,
    }));
    pendingToolCalls.value.clear();
  }

  function setCurrentThread(threadId: string | null) {
    currentThreadId.value = threadId;
    clearMessages();
  }

  function resolveInterrupt(decision: 'approve' | 'reject' | 'edit', editedArgs?: Record<string, unknown>) {
    const event = interruptQueue.value.shift();
    if (event) {
      useAgentWs().resume(event.thread_id, decision, editedArgs);
    }
  }

  function clearMessages() {
    messages.value = [];
    pendingToolCalls.value.clear();
  }

  return {
    currentThreadId,
    pendingToolCalls,
    interruptQueue,
    messages,
    isStreaming,
    sessions,
    addMessage,
    appendToLastAssistant,
    addPendingToolCall,
    resolveToolCall,
    resolveInterrupt,
    clearMessages,
    loadHistory,
    setCurrentThread,
  };
});
