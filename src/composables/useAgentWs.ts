import { ref } from 'vue';
import { useSessionStore } from '@/stores/session';
import { useSettingsStore } from '@/stores/settings';
import type { ToolCall } from '@/types';

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000];

let ws: WebSocket | null = null;
let reconnectAttempt = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

export function useAgentWs() {
  const sessionStore = useSessionStore();
  const settingsStore = useSettingsStore();
  const port = ref(settingsStore.sidecarPort);

  function handleMessage(msg: Record<string, unknown>) {
    const type = msg.type as string;

    switch (type) {
      case 'connected':
        if (msg.port) settingsStore.setSidecarPort(msg.port as number);
        settingsStore.setWsConnected(true);
        listSessions();
        break;

      case 'token':
        sessionStore.appendToLastAssistant(msg.content as string);
        break;

      case 'tool_start': {
        const tc: ToolCall = {
          id: crypto.randomUUID(),
          name: msg.name as string,
          args: (msg.args as Record<string, unknown>) || {},
          category: msg.category as string,
          status: 'running',
        };
        sessionStore.addPendingToolCall(tc);
        sessionStore.addMessage({
          id: tc.id,
          role: 'tool',
          content: `调用工具: ${tc.name}`,
          toolName: tc.name,
          category: tc.category,
        });
        break;
      }

      case 'tool_end':
        sessionStore.resolveToolCall(msg.name as string, msg.result as string);
        break;

      case 'interrupt':
        sessionStore.interruptQueue.push({
          thread_id: msg.thread_id as string,
          action: msg.action as string,
          preview: msg.preview as string,
        });
        break;

      case 'done':
        sessionStore.isStreaming = false;
        break;

      case 'error':
        sessionStore.isStreaming = false;
        sessionStore.addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `错误: ${msg.message}`,
        });
        break;

      case 'session.list':
        sessionStore.sessions = (msg.sessions as typeof sessionStore.sessions) || [];
        break;

      case 'session.created': {
        const threadId = msg.thread_id as string;
        sessionStore.sessions.unshift({
          thread_id: threadId,
          title: (msg.title as string) || '新会话',
          created_at: (msg.created_at as string) || new Date().toISOString(),
        });
        sessionStore.setCurrentThread(threadId);
        break;
      }

      case 'session.deleted':
        sessionStore.sessions = sessionStore.sessions.filter(
          (s) => s.thread_id !== msg.thread_id
        );
        break;

      case 'pong':
        break;
    }
  }

  function connect() {
    if (ws?.readyState === WebSocket.OPEN) return;

    const url = `ws://127.0.0.1:${port.value}/ws`;
    ws = new WebSocket(url);

    ws.onopen = () => {
      reconnectAttempt = 0;
      settingsStore.setWsConnected(true);
    };

    ws.onmessage = (e) => {
      try {
        handleMessage(JSON.parse(e.data));
      } catch {
        console.error('Failed to parse WS message');
      }
    };

    ws.onclose = () => {
      settingsStore.setWsConnected(false);
      scheduleReconnect();
    };

    ws.onerror = () => {
      settingsStore.setWsConnected(false);
    };
  }

  function scheduleReconnect() {
    if (reconnectAttempt >= RECONNECT_DELAYS.length) return;
    const delay = RECONNECT_DELAYS[reconnectAttempt++];
    reconnectTimer = setTimeout(connect, delay);
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    ws?.close();
    ws = null;
  }

  function sendRaw(data: Record<string, unknown>) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    }
  }

  function send(content: string, threadId: string) {
    sessionStore.isStreaming = true;
    sessionStore.addMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content,
    });
    sessionStore.addMessage({
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
    });
    sendRaw({ type: 'chat.send', thread_id: threadId, content });
  }

  function stop(threadId: string) {
    sendRaw({ type: 'chat.stop', thread_id: threadId });
    sessionStore.isStreaming = false;
  }

  function resume(
    threadId: string,
    decision: 'approve' | 'reject' | 'edit',
    editedArgs?: Record<string, unknown>
  ) {
    sendRaw({ type: 'chat.resume', thread_id: threadId, decision, edited_args: editedArgs });
  }

  function listSessions() {
    sendRaw({ type: 'session.list' });
  }

  function createSession(title?: string) {
    sendRaw({ type: 'session.create', title });
  }

  function deleteSession(threadId: string) {
    sendRaw({ type: 'session.delete', thread_id: threadId });
  }

  function ping() {
    sendRaw({ type: 'ping' });
  }

  return {
    port,
    connect,
    disconnect,
    send,
    stop,
    resume,
    listSessions,
    createSession,
    deleteSession,
    ping,
  };
}
