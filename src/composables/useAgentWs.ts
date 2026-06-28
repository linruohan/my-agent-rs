import { ref } from 'vue';
import { getActivePinia } from 'pinia';
import type { ChatAttachment } from '@/utils/attachments';
import { useSessionStore } from '@/stores/session';
import { useSettingsStore } from '@/stores/settings';
import { useKnowledgeStore } from '@/stores/knowledge';
import { useTasksStore } from '@/stores/tasks';
import type { ToolCall } from '@/types';
import { logStartupMilestone } from '@/utils/startupTiming';
import {
  archiveSessionRest,
  createSessionRest,
  deleteSessionRest,
  fetchArchivedSessionsRest,
  fetchSessionHistoryRest,
  fetchSessionsRest,
  unarchiveSessionRest,
} from '@/utils/sidecarSessions';
import { stopChatRest, streamChatRest, streamChatResumeRest } from '@/utils/sidecarChat';
import {
  deleteRagSourceRest,
  ingestRagRest,
  listRagSourcesRest,
  searchRagRest,
} from '@/utils/sidecarRag';
import { registerWsResumeHandler } from '@/utils/wsBridge';
import {
  initWsLeaderElection,
  isWsLeader,
  postChannelMessage,
  registerChannelHandler,
  registerLeaderCallbacks,
  requestSyncFromLeader,
  tryClaimLeader,
} from '@/utils/wsLeader';

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000];
const TOKEN_FLUSH_MS = 50;

const WRITE_MSG_TYPES = new Set([
  'chat.send',
  'chat.stop',
  'chat.resume',
  'session.create',
  'session.delete',
  'session.archive',
  'session.unarchive',
  'rag.ingest',
  'rag.delete',
  'memory.set',
]);

let ws: WebSocket | null = null;
let reconnectAttempt = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let pendingCreateTitle: string | undefined;
let initialSessionBootstrapped = false;
let tokenBuffer = '';
let tokenFlushTimer: ReturnType<typeof setTimeout> | null = null;
let dispatchWsMessage: ((msg: Record<string, unknown>) => void) | null = null;
let leaderHooksReady = false;
let channelHandlerReady = false;
let chatAbortController: AbortController | null = null;

async function tryRestFollowerSync(
  sessionStore: ReturnType<typeof useSessionStore>,
  settingsStore: ReturnType<typeof useSettingsStore>
) {
  const port = settingsStore.sidecarPort;
  if (!port || !settingsStore.wsReadOnly) return;

  try {
    if (sessionStore.sessions.length === 0) {
      const sessions = await fetchSessionsRest(port);
      sessionStore.sessions = sessions;
      if (sessions.length > 0) {
        bootstrapFollowerSession(sessionStore);
      }
    }

    const threadId = sessionStore.currentThreadId;
    if (!threadId || sessionStore.messages.length > 0) return;

    const expectedGen =
      pendingHistoryLoads.get(threadId) ?? sessionStore.historyLoadGeneration;
    const messages = await fetchSessionHistoryRest(port, threadId);
    if (
      threadId === sessionStore.currentThreadId &&
      expectedGen === sessionStore.historyLoadGeneration
    ) {
      sessionStore.loadHistory(messages, expectedGen);
    }
  } catch {
    // Leader BroadcastChannel sync is primary; REST is offline fallback.
  }
}

function scheduleFollowerSync(sessionStore: ReturnType<typeof useSessionStore>) {
  const threadId = sessionStore.currentThreadId;
  if (threadId) {
    pendingHistoryLoads.set(threadId, sessionStore.historyLoadGeneration);
  }
  requestSyncFromLeader(threadId);
  window.setTimeout(() => {
    const pinia = getActivePinia();
    if (!pinia) return;
    const settings = useSettingsStore(pinia);
    const tid = sessionStore.currentThreadId;
    if (
      settings.wsReadOnly &&
      tid &&
      sessionStore.messages.length === 0
    ) {
      pendingHistoryLoads.set(tid, sessionStore.historyLoadGeneration);
      requestSyncFromLeader(tid, { historyOnly: true });
    }
    if (settings.wsReadOnly) {
      const needsSessions = sessionStore.sessions.length === 0;
      const needsHistory =
        !!tid && sessionStore.messages.length === 0;
      if (needsSessions || needsHistory) {
        void tryRestFollowerSync(sessionStore, settings);
      }
    }
  }, 800);
}

function bootstrapFollowerSession(sessionStore: ReturnType<typeof useSessionStore>) {
  if (sessionStore.sessions.length === 0) return;
  let tid = sessionStore.currentThreadId;
  if (!tid || !sessionStore.sessions.some((s) => s.thread_id === tid)) {
    tid = sessionStore.sessions[0].thread_id;
    sessionStore.setCurrentThread(tid);
  }
  pendingHistoryLoads.set(tid, sessionStore.historyLoadGeneration);
  requestSyncFromLeader(tid, { historyOnly: true });
}

function setupChannelHandler(sessionStore: ReturnType<typeof useSessionStore>) {
  if (channelHandlerReady) return;
  channelHandlerReady = true;
  registerChannelHandler((data) => {
    if (data.type === 'streaming.start' && data.threadId !== sessionStore.currentThreadId) {
      sessionStore.isStreaming = true;
    }
    if (data.type === 'streaming.end') {
      sessionStore.isStreaming = false;
    }
    if (data.type === 'ws.forward' && data.msg && dispatchWsMessage) {
      const pinia = getActivePinia();
      if (!pinia) return;
      const settings = useSettingsStore(pinia);
      if (settings.wsReadOnly) {
        dispatchWsMessage(data.msg as Record<string, unknown>);
      }
    }
    if (data.type === 'sync.request' && isWsLeader()) {
      if (!data.historyOnly) {
        sendRaw({ type: 'session.list' });
        sendRaw({ type: 'session.archived' });
      }
      const threadId = data.threadId as string | null | undefined;
      if (threadId) {
        sendRaw({ type: 'session.history', thread_id: threadId });
      }
    }
  });
}

let pendingHistoryLoads = new Map<string, number>();

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

function sendRaw(data: Record<string, unknown>) {
  const pinia = getActivePinia();
  if (pinia) {
    const settings = useSettingsStore(pinia);
    const msgType = data.type as string | undefined;
    if (settings.wsReadOnly && msgType && WRITE_MSG_TYPES.has(msgType)) {
      return false;
    }
  }
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
    return true;
  }
  return false;
}

registerWsResumeHandler((threadId, decision, editedArgs) => {
  sendRaw({
    type: 'chat.resume',
    thread_id: threadId,
    decision,
    edited_args: editedArgs,
  });
});

export function useAgentWs() {
  const sessionStore = useSessionStore();
  const settingsStore = useSettingsStore();
  const knowledgeStore = useKnowledgeStore();
  const tasksStore = useTasksStore();
  const connectionError = ref('');

  if (!leaderHooksReady) {
    leaderHooksReady = true;
    setupChannelHandler(sessionStore);
    registerLeaderCallbacks({
      onBecomeLeader: () => {
        settingsStore.setWsReadOnly(false);
        connectionError.value = '';
        connectInternal();
      },
      onBecomeFollower: () => {
        settingsStore.setWsReadOnly(true);
        settingsStore.setWsConnected(false);
        connectionError.value = '已在其他标签页打开，当前为只读模式';
        disconnectInternal();
        scheduleFollowerSync(sessionStore);
      },
    });
    initWsLeaderElection();
  }

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
        postChannelMessage({ type: 'streaming.end' });
        const metadata = msg.metadata as {
          duration_ms?: number;
          task_data_changed?: boolean;
          token_usage?: {
            prompt_tokens?: number;
            completion_tokens?: number;
            total_tokens?: number;
          };
        } | undefined;
        if (metadata?.duration_ms != null) {
          settingsStore.setLastTurnDuration(metadata.duration_ms);
          sessionStore.setLastAssistantDuration(metadata.duration_ms);
        }
        if (metadata?.token_usage?.total_tokens) {
          settingsStore.setLastTokenUsage({
            prompt_tokens: metadata.token_usage.prompt_tokens ?? 0,
            completion_tokens: metadata.token_usage.completion_tokens ?? 0,
            total_tokens: metadata.token_usage.total_tokens ?? 0,
          });
        }
        if (metadata?.task_data_changed) {
          void tasksStore.refreshIfRunning();
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
        if (!settingsStore.notificationPrefs.desktopEnabled) break;
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

      case 'session.archived':
        sessionStore.archivedSessions =
          (msg.sessions as typeof sessionStore.archivedSessions) || [];
        break;

      case 'session.archived_one':
        if (msg.ok) {
          listSessions();
          listArchivedSessions();
        }
        break;

      case 'session.unarchived':
        if (msg.ok) {
          listSessions();
          listArchivedSessions();
        }
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
        if (settingsStore.wsReadOnly) {
          bootstrapFollowerSession(sessionStore);
        } else {
          bootstrapInitialSession();
        }
        break;

      case 'session.created': {
        const threadId = msg.thread_id as string;
        sessionStore.sessions.unshift({
          thread_id: threadId,
          title: (msg.title as string) || '新会话',
          created_at: (msg.created_at as string) || new Date().toISOString(),
        });
        sessionStore.setCurrentThread(threadId);
        sessionStore.bumpInputFocus();
        break;
      }

      case 'session.deleted': {
        const deletedId = msg.thread_id as string;
        sessionStore.sessions = sessionStore.sessions.filter(
          (s) => s.thread_id !== deletedId
        );
        sessionStore.removePreview(deletedId);
        break;
      }

      case 'session.history': {
        const threadId = msg.thread_id as string;
        const expectedGen = pendingHistoryLoads.get(threadId);
        pendingHistoryLoads.delete(threadId);
        if (
          threadId === sessionStore.currentThreadId &&
          expectedGen === sessionStore.historyLoadGeneration
        ) {
          sessionStore.loadHistory(
            (msg.messages as Array<{
              role: string;
              content: string;
              tool_name?: string;
            }>) || [],
            expectedGen
          );
        }
        break;
      }

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

    if (isWsLeader() && type !== 'pong') {
      postChannelMessage({ type: 'ws.forward', msg });
    }
  }

  dispatchWsMessage = handleMessage;

  function connectInternal() {
    if (settingsStore.sidecarStatus === 'starting') {
      connectionError.value = 'Sidecar 正在启动，请稍候…';
      return;
    }
    if (settingsStore.sidecarStatus === 'error') {
      connectionError.value = 'Sidecar 启动失败，请在设置页重启 Sidecar';
      return;
    }

    const url = wsUrl();
    const state = ws?.readyState;
    if (state === WebSocket.OPEN && ws!.url === url) return;
    if (state === WebSocket.CONNECTING && ws!.url === url) return;

    ws?.close();
    ws = new WebSocket(url);

    ws.onopen = () => {
      reconnectAttempt = 0;
      settingsStore.setWsConnected(true);
      settingsStore.setWsReadOnly(false);
      connectionError.value = '';
      logStartupMilestone('WebSocket connected — loading complete');
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
      if (isWsLeader()) scheduleReconnect();
    };

    ws.onerror = () => {
      settingsStore.setWsConnected(false);
      connectionError.value = `无法连接 Sidecar (port ${settingsStore.sidecarPort})`;
    };
  }

  function connect() {
    tryClaimLeader();
    if (!isWsLeader()) {
      settingsStore.setWsReadOnly(true);
      settingsStore.setWsConnected(false);
      connectionError.value = '已在其他标签页打开，当前为只读模式';
      scheduleFollowerSync(sessionStore);
      return;
    }
    settingsStore.setWsReadOnly(false);
    connectInternal();
  }

  function disconnectInternal() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = null;
    ws?.close();
    ws = null;
  }

  function scheduleReconnect() {
    if (reconnectAttempt >= RECONNECT_DELAYS.length) return;
    if (settingsStore.sidecarStatus !== 'running') return;
    const delay = RECONNECT_DELAYS[reconnectAttempt++];
    reconnectTimer = setTimeout(connect, delay);
  }

  function disconnect() {
    disconnectInternal();
  }

  function beginChatTurn(content: string, threadId: string, attachments?: ChatAttachment[]) {
    sessionStore.isStreaming = true;
    postChannelMessage({ type: 'streaming.start', threadId });
    sessionStore.addMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content,
      attachments: attachments?.length ? [...attachments] : undefined,
    });
    sessionStore.addMessage({
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
    });
  }

  function send(content: string, threadId: string, attachments?: ChatAttachment[]) {
    beginChatTurn(content, threadId, attachments);
    if (
      sendRaw({
        type: 'chat.send',
        thread_id: threadId,
        content,
        attachments: attachments?.length ? attachments : undefined,
      })
    ) {
      return;
    }
    if (!canUseSessionRest()) return;

    chatAbortController?.abort();
    chatAbortController = new AbortController();
    const signal = chatAbortController.signal;
    void streamChatRest(
      settingsStore.sidecarPort,
      threadId,
      content,
      (msg) => {
        if (!msg.thread_id) msg.thread_id = threadId;
        handleMessage(msg);
      },
      attachments,
      signal
    ).catch((err: unknown) => {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      handleMessage({
        type: 'error',
        thread_id: threadId,
        message: err instanceof Error ? err.message : String(err),
      });
    });
  }

  function stop(threadId: string) {
    if (sendRaw({ type: 'chat.stop', thread_id: threadId })) {
      sessionStore.isStreaming = false;
      return;
    }
    chatAbortController?.abort();
    chatAbortController = null;
    if (canUseSessionRest()) {
      void stopChatRest(settingsStore.sidecarPort, threadId).catch(() => {});
    }
    sessionStore.isStreaming = false;
  }

  function resume(
    threadId: string,
    decision: 'approve' | 'reject' | 'edit',
    editedArgs?: Record<string, unknown>
  ) {
    sessionStore.isStreaming = true;
    if (
      sendRaw({
        type: 'chat.resume',
        thread_id: threadId,
        decision,
        edited_args: editedArgs,
      })
    ) {
      return;
    }
    if (!canUseSessionRest()) return;

    chatAbortController?.abort();
    chatAbortController = new AbortController();
    const signal = chatAbortController.signal;
    void streamChatResumeRest(
      settingsStore.sidecarPort,
      threadId,
      decision,
      (msg) => {
        if (!msg.thread_id) msg.thread_id = threadId;
        handleMessage(msg);
      },
      editedArgs,
      signal
    ).catch((err: unknown) => {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      handleMessage({
        type: 'error',
        thread_id: threadId,
        message: err instanceof Error ? err.message : String(err),
      });
    });
  }

  function canUseRestRead() {
    return settingsStore.sidecarStatus === 'running';
  }

  function canUseRestWrite() {
    return !settingsStore.wsReadOnly && settingsStore.sidecarStatus === 'running';
  }

  /** @deprecated alias */
  function canUseSessionRest() {
    return canUseRestWrite();
  }

  function applySessionCreated(session: {
    thread_id: string;
    title: string;
    created_at: string;
  }) {
    sessionStore.sessions.unshift({
      thread_id: session.thread_id,
      title: session.title || '新会话',
      created_at: session.created_at || new Date().toISOString(),
    });
    sessionStore.setCurrentThread(session.thread_id);
    sessionStore.bumpInputFocus();
  }

  function applySessionDeleted(threadId: string) {
    sessionStore.sessions = sessionStore.sessions.filter(
      (s) => s.thread_id !== threadId
    );
    sessionStore.removePreview(threadId);
  }

  function listSessions() {
    if (sendRaw({ type: 'session.list' })) return;
    if (settingsStore.wsReadOnly) return;
    if (!canUseSessionRest()) return;
    void fetchSessionsRest(settingsStore.sidecarPort)
      .then((sessions) => {
        sessionStore.sessions = sessions;
        bootstrapInitialSession();
      })
      .catch(() => {});
  }

  function listArchivedSessions() {
    if (sendRaw({ type: 'session.archived' })) return;
    if (settingsStore.wsReadOnly) return;
    if (!canUseSessionRest()) return;
    void fetchArchivedSessionsRest(settingsStore.sidecarPort)
      .then((sessions) => {
        sessionStore.archivedSessions = sessions;
      })
      .catch(() => {});
  }

  function archiveSession(threadId: string) {
    if (sendRaw({ type: 'session.archive', thread_id: threadId })) return;
    if (!canUseSessionRest()) return;
    void archiveSessionRest(settingsStore.sidecarPort, threadId)
      .then(() => {
        listSessions();
        listArchivedSessions();
      })
      .catch(() => {});
  }

  function unarchiveSession(threadId: string) {
    if (sendRaw({ type: 'session.unarchive', thread_id: threadId })) return;
    if (!canUseSessionRest()) return;
    void unarchiveSessionRest(settingsStore.sidecarPort, threadId)
      .then(() => {
        listSessions();
        listArchivedSessions();
      })
      .catch(() => {});
  }

  function bootstrapInitialSession() {
    if (sessionStore.currentThreadId || initialSessionBootstrapped) return;
    initialSessionBootstrapped = true;

    if (settingsStore.wsReadOnly) {
      bootstrapFollowerSession(sessionStore);
      return;
    }

    if (sessionStore.sessions.length > 0) {
      const latest = sessionStore.sessions[0];
      sessionStore.setCurrentThread(latest.thread_id);
      loadSessionHistory(latest.thread_id);
      sessionStore.bumpInputFocus();
    } else {
      createSession('新会话');
    }
  }

  function createSession(title?: string): boolean {
    if (settingsStore.wsReadOnly) return false;
    if (sendRaw({ type: 'session.create', title })) return true;
    if (canUseSessionRest()) {
      void createSessionRest(settingsStore.sidecarPort, title)
        .then((session) => applySessionCreated(session))
        .catch(() => {
          pendingCreateTitle = title;
          connect();
        });
      return false;
    }
    pendingCreateTitle = title;
    connect();
    return false;
  }

  function deleteSession(threadId: string) {
    if (settingsStore.wsReadOnly) return;
    if (sendRaw({ type: 'session.delete', thread_id: threadId })) return;
    if (!canUseSessionRest()) return;
    void deleteSessionRest(settingsStore.sidecarPort, threadId)
      .then(() => applySessionDeleted(threadId))
      .catch(() => {});
  }

  function loadSessionHistory(threadId: string) {
    pendingHistoryLoads.set(threadId, sessionStore.historyLoadGeneration);
    if (settingsStore.wsReadOnly) {
      requestSyncFromLeader(threadId, { historyOnly: true });
      window.setTimeout(() => {
        if (
          threadId === sessionStore.currentThreadId &&
          sessionStore.messages.length === 0
        ) {
          void tryRestFollowerSync(sessionStore, settingsStore);
        }
      }, 800);
      return;
    }
    sendRaw({ type: 'session.history', thread_id: threadId });
  }

  function ping() {
    sendRaw({ type: 'ping' });
  }

  function listRagSources() {
    knowledgeStore.isLoading = true;
    if (sendRaw({ type: 'rag.list' })) return;
    if (!canUseRestRead()) {
      knowledgeStore.isLoading = false;
      return;
    }
    void listRagSourcesRest(settingsStore.sidecarPort)
      .then((sources) => handleMessage({ type: 'rag.list', sources }))
      .catch(() => {
        knowledgeStore.isLoading = false;
      });
  }

  function ingestRagContent(source: string, content: string) {
    knowledgeStore.isLoading = true;
    if (sendRaw({ type: 'rag.ingest', source, content })) return;
    if (!canUseRestWrite()) {
      knowledgeStore.isLoading = false;
      return;
    }
    void ingestRagRest(settingsStore.sidecarPort, source, content)
      .then((result) => handleMessage({ type: 'rag.ingest', result }))
      .catch((err: unknown) => {
        knowledgeStore.isLoading = false;
        knowledgeStore.setIngestResult(
          err instanceof Error ? err.message : String(err)
        );
      });
  }

  function searchRag(query: string, topK = 6) {
    knowledgeStore.isLoading = true;
    if (sendRaw({ type: 'rag.search', query, top_k: topK })) return;
    if (!canUseRestRead()) {
      knowledgeStore.isLoading = false;
      return;
    }
    void searchRagRest(settingsStore.sidecarPort, query, topK)
      .then((results) => handleMessage({ type: 'rag.search', query, results }))
      .catch(() => {
        knowledgeStore.isLoading = false;
      });
  }

  function deleteRagSource(source: string) {
    knowledgeStore.isLoading = true;
    if (sendRaw({ type: 'rag.delete', source })) return;
    if (!canUseRestWrite()) {
      knowledgeStore.isLoading = false;
      return;
    }
    void deleteRagSourceRest(settingsStore.sidecarPort, source)
      .then((ok) => handleMessage({ type: 'rag.deleted', source, ok }))
      .catch(() => {
        knowledgeStore.isLoading = false;
      });
  }

  return {
    connectionError,
    connect,
    disconnect,
    send,
    stop,
    resume,
    listSessions,
    listArchivedSessions,
    archiveSession,
    unarchiveSession,
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
