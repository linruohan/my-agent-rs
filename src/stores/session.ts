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

  function resolveToolCall(name: string, result: string) {
    for (const [id, tc] of pendingToolCalls.value) {
      if (tc.name === name && tc.status === 'running') {
        tc.status = 'done';
        tc.result = result;
        pendingToolCalls.value.set(id, tc);
        break;
      }
    }
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

  function setCurrentThread(threadId: string | null) {
    currentThreadId.value = threadId;
    clearMessages();
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
    setCurrentThread,
  };
});
