import { ref } from 'vue';
import { useSessionStore } from '@/stores/session';
import { useSettingsStore } from '@/stores/settings';
import { useKnowledgeStore } from '@/stores/knowledge';
import type { ToolCall } from '@/types';

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000];
const TOKEN_FLUSH_MS = 50;
const BC_CHANNEL = 'personal-assistant-agent';

let ws: WebSocket | null = null;
let reconnectAttempt = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let pendingCreateTitle: string | undefined;
let tokenBuffer = '';
let tokenFlushTimer: ReturnType<typeof setTimeout> | null = null;
let bc: BroadcastChannel | null = null;

function initBroadcastChannel(sessionStore: ReturnType<typeof useSessionStore>) {
  if (typeof BroadcastChannel === 'undefined') return;
  bc = new BroadcastChannel(BC_CHANNEL);
  bc.onmessage = (e: MessageEvent) => {
    const data = e.data as { type?: string; threadId?: string };
    if (data.type === 'streaming.start' && data.threadId !== sessionStore.currentThreadId) {
      sessionStore.isStreaming = true;
    }
    if (data.type === 'streaming.end') {
      sessionStore.isStreaming = false;
    }
  };
}

const AUTH_STORAGE_KEY = 'pa-sidecar-auth-token';

async function fetchAuthToken(port: number): Promise<string | null> {
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    return await invoke<string>('get_sidecar_token');
  } catch {
    /* web-only mode */
  }
  try {
    const cached = localStorage.getItem(AUTH_STORAGE_KEY);
    if (cached) return cached;
    const resp = await fetch(`http://127.0.0.1:${port}/auth/token`);
    if (!resp.ok) return null;
    const data = (await resp.json()) as { token?: string };
    if (data.token) {
      localStorage.setItem(AUTH_STORAGE_KEY, data.token);
      return data.token;
    }
  } catch {
    /* ignore */
  }
  return null;
}

function flushTokenBuffer(sessionStore: ReturnType<typeof useSessionStore>) {
  if (tokenBuffer) {
    sessionStore.appendToLastAssistant(tokenBuffer);
    tokenBuffer = '';
  }
  tokenFlushTimer = null;
}

export function useAgentWs() {
  const sessionStore = useSessionStore();
  const settingsStore = useSettingsStore();
  const knowledgeStore = useKnowledgeStore();
  const connectionError = ref('');

  if (!bc) initBroadcastChannel(sessionStore);

  function wsUrl() {
    return `ws://127.0.0.1:${settingsStore.sidecarPort}/ws`;
  }

  function isConnected() {
    return ws?.readyState === WebSocket.OPEN;
  }

  function handleMessage(msg: Record<string, unknown>) {
    const type = msg.type as string;

    switch (type) {
      case 'connected':
        if (msg.port) settingsStore.setSidecarPort(msg.port as number);
        settingsStore.setWsConnected(true);
        connectionError.value = '';
        if (msg.auth_required) {
          void (async () => {
            const port = (msg.port as number) || settingsStore.sidecarPort;
            const token = await fetchAuthToken(port);
            if (token) sendRaw({ type: 'auth', token });
          })();
        }
        listSessions();
        if (pendingCreateTitle !== undefined) {
          sendRaw({ type: 'session.create', title: pendingCreateTitle });
          pendingCreateTitle = undefined;
        }
        break;

      case 'auth.ok':
        break;

      case 'tool_progress': {
        const toolName = msg.tool_name as string;
        const toolCallId = msg.tool_call_id as string | undefined;
        sessionStore.updateToolProgress(toolName, toolCallId, msg.status as string);
        break;
      }

      case 'token':
        tokenBuffer += (msg.content as string) || '';
        if (!tokenFlushTimer) {
          tokenFlushTimer = setTimeout(
            () => flushTokenBuffer(sessionStore),
            TOKEN_FLUSH_MS
          );
        }
        break;

      case 'tool_start': {
        const toolCallId = (msg.tool_call_id as string) || crypto.randomUUID();
        const tc: ToolCall = {
          id: toolCallId,
          name: msg.name as string,
          args: (msg.args as Record<string, unknown>) || {},
          category: msg.category as string,
          status: 'running',
        };
        sessionStore.addPendingToolCall(tc);
        sessionStore.addMessage({
          id: toolCallId,
          role: 'tool',
          content: `调用工具: ${tc.name}`,
          toolName: tc.name,
          category: tc.category,
        });
        break;
      }

      case 'tool_end':
        sessionStore.resolveToolCall(
          msg.name as string,
          msg.result as string,
          msg.tool_call_id as string | undefined,
          msg.citations as Array<{ title: string; url: string }> | undefined
        );
        break;

      case 'interrupt':
        sessionStore.interruptQueue.push({
          thread_id: msg.thread_id as string,
          action: msg.action as string,
          preview: msg.preview as string,
          args: (msg.args as Record<string, unknown>) || {},
        });
        break;

      case 'interrupt_timeout_warning':
        sessionStore.addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `⚠️ 操作确认将在 ${msg.seconds_left} 秒后自动拒绝，请尽快确认。`,
        });
        break;

      case 'done': {
        flushTokenBuffer(sessionStore);
        sessionStore.isStreaming = false;
        bc?.postMessage({ type: 'streaming.end' });
        const metadata = msg.metadata as { duration_ms?: number } | undefined;
        if (metadata?.duration_ms != null) {
          settingsStore.setLastTurnDuration(metadata.duration_ms);
        }
        break;
      }

      case 'scheduler.reminder': {
        const title = (msg.title as string) || '提醒';
        const body = (msg.message as string) || '';
        sessionStore.addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `🔔 ${title}: ${body}`,
        });
        import('@tauri-apps/plugin-notification')
          .then(({ sendNotification, isPermissionGranted, requestPermission }) => {
            isPermissionGranted().then((granted) => {
              if (!granted) requestPermission();
              sendNotification({ title, body });
            });
          })
          .catch(() => {
            /* web-only mode */
          });
        break;
      }

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

      case 'session.history':
        if (msg.thread_id === sessionStore.currentThreadId) {
          sessionStore.loadHistory(
            (msg.messages as Array<{
              role: string;
              content: string;
              tool_name?: string;
            }>) || []
          );
        }
        break;

      case 'pong':
        break;

      case 'rag.list':
        knowledgeStore.setSources((msg.sources as string[]) || []);
        knowledgeStore.isLoading = false;
        break;

      case 'rag.ingest':
        knowledgeStore.setIngestResult((msg.result as string) || '完成');
        knowledgeStore.isLoading = false;
        listRagSources();
        break;

      case 'rag.search':
        knowledgeStore.setSearchResults(
          (msg.results as Array<{ source: string; content: string; score: number }>) || []
        );
        knowledgeStore.isLoading = false;
        break;

      case 'rag.deleted':
        knowledgeStore.isLoading = false;
        listRagSources();
        break;
    }
  }

  function connect() {
    if (settingsStore.sidecarStatus === 'starting') {
      connectionError.value = 'Sidecar 正在启动，请稍候…';
      return;
    }
    if (settingsStore.sidecarStatus === 'error') {
      connectionError.value = 'Sidecar 启动失败，请在设置页重启 Sidecar';
      return;
    }

    const url = wsUrl();
    if (ws?.readyState === WebSocket.OPEN && ws.url === url) return;

    ws?.close();
    ws = new WebSocket(url);

    ws.onopen = () => {
      reconnectAttempt = 0;
      settingsStore.setWsConnected(true);
      connectionError.value = '';
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
      connectionError.value = `无法连接 Sidecar (port ${settingsStore.sidecarPort})`;
    };
  }

  function scheduleReconnect() {
    if (reconnectAttempt >= RECONNECT_DELAYS.length) return;
    if (settingsStore.sidecarStatus !== 'running') return;
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
      return true;
    }
    return false;
  }

  function send(
    content: string,
    threadId: string,
    attachments?: Array<{ type: string; name: string; content: string }>
  ) {
    sessionStore.isStreaming = true;
    bc?.postMessage({ type: 'streaming.start', threadId });
    const displayContent =
      attachments?.length && attachments.length > 0
        ? `${content}\n📎 ${attachments.map((a) => a.name).join(', ')}`
        : content;
    sessionStore.addMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: displayContent,
    });
    sessionStore.addMessage({
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
    });
    sendRaw({
      type: 'chat.send',
      thread_id: threadId,
      content,
      attachments: attachments?.length ? attachments : undefined,
    });
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

  function createSession(title?: string): boolean {
    if (isConnected()) {
      return sendRaw({ type: 'session.create', title });
    }
    pendingCreateTitle = title;
    connect();
    return false;
  }

  function deleteSession(threadId: string) {
    sendRaw({ type: 'session.delete', thread_id: threadId });
  }

  function loadSessionHistory(threadId: string) {
    sendRaw({ type: 'session.history', thread_id: threadId });
  }

  function ping() {
    sendRaw({ type: 'ping' });
  }

  function listRagSources() {
    knowledgeStore.isLoading = true;
    sendRaw({ type: 'rag.list' });
  }

  function ingestRagContent(source: string, content: string) {
    knowledgeStore.isLoading = true;
    sendRaw({ type: 'rag.ingest', source, content });
  }

  function searchRag(query: string, topK = 6) {
    knowledgeStore.isLoading = true;
    sendRaw({ type: 'rag.search', query, top_k: topK });
  }

  function deleteRagSource(source: string) {
    knowledgeStore.isLoading = true;
    sendRaw({ type: 'rag.delete', source });
  }

  return {
    connectionError,
    connect,
    disconnect,
    send,
    stop,
    resume,
    listSessions,
    createSession,
    deleteSession,
    loadSessionHistory,
    ping,
    listRagSources,
    ingestRagContent,
    searchRag,
    deleteRagSource,
    isConnected,
  };
}
