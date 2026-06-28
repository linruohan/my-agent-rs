import { ref } from 'vue';
import { getActivePinia } from 'pinia';
import type { ChatAttachment } from '@/utils/attachments';
import { useSessionStore } from '@/stores/session';
import { useSettingsStore } from '@/stores/settings';
import { useKnowledgeStore } from '@/stores/knowledge';
import { useTasksStore } from '@/stores/tasks';
import { useMemoryStore } from '@/stores/memory';
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
import { fetchSidecarAuthToken, sidecarWsUrl } from '@/utils/sidecarFetch';
import {
  initWsLeaderElection,
  isWsLeader,
  postChannelMessage,
  registerChannelHandler,
  registerLeaderCallbacks,
  requestSyncFromLeader,
  tryClaimLeader,
} from '@/utils/wsLeader';
import {
  canUseRestRead,
  canUseRestWrite,
  closeSidecarWs,
  isSidecarWsOpen,
  openSidecarWs,
  resetSidecarWsReconnectAttempt,
  scheduleSidecarWsReconnect,
  sendSidecarWsRaw,
} from '@/utils/sidecarWsConnection';
import { createSidecarWsMessageHandler } from '@/utils/sidecarWsHandler';

let pendingCreateTitle: string | undefined;
let initialSessionBootstrapped = false;
let dispatchWsMessage: ((msg: Record<string, unknown>) => void) | null = null;
let leaderHooksReady = false;
let channelHandlerReady = false;
let chatAbortController: AbortController | null = null;
let pendingHistoryLoads = new Map<string, number>();

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
      const needsHistory = !!tid && sessionStore.messages.length === 0;
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
        sendSidecarWsRaw({ type: 'session.list' });
        sendSidecarWsRaw({ type: 'session.archived' });
      }
      const threadId = data.threadId as string | null | undefined;
      if (threadId) {
        sendSidecarWsRaw({ type: 'session.history', thread_id: threadId });
      }
    }
  });
}

registerWsResumeHandler((threadId, decision, editedArgs) => {
  sendSidecarWsRaw({
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
  const memoryStore = useMemoryStore();
  const connectionError = ref('');

  function restReadOk() {
    return canUseRestRead(settingsStore.sidecarStatus);
  }

  function restWriteOk() {
    return canUseRestWrite(settingsStore.sidecarStatus, settingsStore.wsReadOnly);
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

  function listSessions() {
    if (sendSidecarWsRaw({ type: 'session.list' })) return;
    if (!restReadOk()) return;
    void fetchSessionsRest(settingsStore.sidecarPort)
      .then((sessions) => {
        sessionStore.sessions = sessions;
        if (settingsStore.wsReadOnly) {
          bootstrapFollowerSession(sessionStore);
        } else {
          bootstrapInitialSession();
        }
      })
      .catch(() => {});
  }

  function listArchivedSessions() {
    if (sendSidecarWsRaw({ type: 'session.archived' })) return;
    if (!restReadOk()) return;
    void fetchArchivedSessionsRest(settingsStore.sidecarPort)
      .then((sessions) => {
        sessionStore.archivedSessions = sessions;
      })
      .catch(() => {});
  }

  function listRagSourcesImpl() {
    knowledgeStore.isLoading = true;
    if (sendSidecarWsRaw({ type: 'rag.list' })) return;
    if (!restReadOk()) {
      knowledgeStore.isLoading = false;
      return;
    }
    void listRagSourcesRest(settingsStore.sidecarPort)
      .then((sources) => handleMessage({ type: 'rag.list', sources }))
      .catch(() => {
        knowledgeStore.isLoading = false;
      });
  }

  let handleMessage: (msg: Record<string, unknown>) => void;
  handleMessage = createSidecarWsMessageHandler({
    sessionStore,
    settingsStore,
    knowledgeStore,
    tasksStore,
    memoryStore,
    connectionError,
    pendingHistoryLoads,
    pendingCreateTitle: {
      get: () => pendingCreateTitle,
      set: (v) => {
        pendingCreateTitle = v;
      },
    },
    fetchAuthToken: fetchSidecarAuthToken,
    sendRaw: sendSidecarWsRaw,
    listSessions,
    listArchivedSessions,
    listRagSources: listRagSourcesImpl,
    bootstrapInitialSession,
    bootstrapFollowerSession: () => bootstrapFollowerSession(sessionStore),
  });

  dispatchWsMessage = handleMessage;

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
        closeSidecarWs();
        scheduleFollowerSync(sessionStore);
      },
    });
    initWsLeaderElection();
  }

  function wsUrl() {
    return sidecarWsUrl(settingsStore.sidecarPort);
  }

  function connectInternal() {
    if (settingsStore.sidecarStatus === 'starting') {
      connectionError.value = 'Sidecar 正在启动，请稍候…';
      return;
    }
    if (settingsStore.sidecarStatus === 'error') {
      connectionError.value = 'Sidecar 启动失败，请在设置页重启 Sidecar';
      return;
    }

    openSidecarWs(wsUrl(), {
      onOpen: () => {
        resetSidecarWsReconnectAttempt();
        settingsStore.setWsConnected(true);
        settingsStore.setWsReadOnly(false);
        connectionError.value = '';
        logStartupMilestone('WebSocket connected — loading complete');
      },
      onMessage: handleMessage,
      onClose: () => {
        settingsStore.setWsConnected(false);
        if (isWsLeader()) {
          scheduleSidecarWsReconnect(connect, () => settingsStore.sidecarStatus === 'running');
        }
      },
      onError: () => {
        settingsStore.setWsConnected(false);
        connectionError.value = `无法连接 Sidecar (port ${settingsStore.sidecarPort})`;
      },
    });
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

  function disconnect() {
    closeSidecarWs();
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
      sendSidecarWsRaw({
        type: 'chat.send',
        thread_id: threadId,
        content,
        attachments: attachments?.length ? attachments : undefined,
      })
    ) {
      return;
    }
    if (!restWriteOk()) return;

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
    if (sendSidecarWsRaw({ type: 'chat.stop', thread_id: threadId })) {
      sessionStore.isStreaming = false;
      return;
    }
    chatAbortController?.abort();
    chatAbortController = null;
    if (restWriteOk()) {
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
      sendSidecarWsRaw({
        type: 'chat.resume',
        thread_id: threadId,
        decision,
        edited_args: editedArgs,
      })
    ) {
      return;
    }
    if (!restWriteOk()) return;

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

  function archiveSession(threadId: string) {
    if (sendSidecarWsRaw({ type: 'session.archive', thread_id: threadId })) return;
    if (!restWriteOk()) return;
    void archiveSessionRest(settingsStore.sidecarPort, threadId)
      .then(() => {
        listSessions();
        listArchivedSessions();
      })
      .catch(() => {});
  }

  function unarchiveSession(threadId: string) {
    if (sendSidecarWsRaw({ type: 'session.unarchive', thread_id: threadId })) return;
    if (!restWriteOk()) return;
    void unarchiveSessionRest(settingsStore.sidecarPort, threadId)
      .then(() => {
        listSessions();
        listArchivedSessions();
      })
      .catch(() => {});
  }

  function createSession(title?: string): boolean {
    if (settingsStore.wsReadOnly) return false;
    if (sendSidecarWsRaw({ type: 'session.create', title })) return true;
    if (restWriteOk()) {
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
    if (sendSidecarWsRaw({ type: 'session.delete', thread_id: threadId })) return;
    if (!restWriteOk()) return;
    void deleteSessionRest(settingsStore.sidecarPort, threadId)
      .then(() => applySessionDeleted(threadId))
      .catch(() => {});
  }

  function applyHistoryFromRest(threadId: string) {
    const expectedGen =
      pendingHistoryLoads.get(threadId) ?? sessionStore.historyLoadGeneration;
    return fetchSessionHistoryRest(settingsStore.sidecarPort, threadId)
      .then((messages) => {
        if (
          threadId === sessionStore.currentThreadId &&
          expectedGen === sessionStore.historyLoadGeneration
        ) {
          sessionStore.loadHistory(messages, expectedGen);
        }
      })
      .catch(() => {});
  }

  function loadSessionHistory(threadId: string) {
    pendingHistoryLoads.set(threadId, sessionStore.historyLoadGeneration);
    if (settingsStore.wsReadOnly) {
      requestSyncFromLeader(threadId, { historyOnly: true });
      if (restReadOk()) {
        void applyHistoryFromRest(threadId);
      }
      window.setTimeout(() => {
        if (
          threadId === sessionStore.currentThreadId &&
          sessionStore.messages.length === 0 &&
          restReadOk()
        ) {
          void applyHistoryFromRest(threadId);
        }
      }, 800);
      return;
    }
    if (sendSidecarWsRaw({ type: 'session.history', thread_id: threadId })) return;
    if (!restReadOk()) return;
    void applyHistoryFromRest(threadId);
  }

  function ping() {
    sendSidecarWsRaw({ type: 'ping' });
  }

  function ingestRagContent(source: string, content: string) {
    knowledgeStore.isLoading = true;
    if (sendSidecarWsRaw({ type: 'rag.ingest', source, content })) return;
    if (!restWriteOk()) {
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
    if (sendSidecarWsRaw({ type: 'rag.search', query, top_k: topK })) return;
    if (!restReadOk()) {
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
    if (sendSidecarWsRaw({ type: 'rag.delete', source })) return;
    if (!restWriteOk()) {
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
    listRagSources: listRagSourcesImpl,
    ingestRagContent,
    searchRag,
    deleteRagSource,
    isConnected: isSidecarWsOpen,
  };
}
