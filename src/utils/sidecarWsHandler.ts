import type { Ref } from 'vue';
import type { useKnowledgeStore } from '@/stores/knowledge';
import type { useMemoryStore } from '@/stores/memory';
import type { useSessionStore } from '@/stores/session';
import type { useSettingsStore } from '@/stores/settings';
import type { useTasksStore } from '@/stores/tasks';
import type { ToolCall } from '@/types';
import { hydrateUserConfigFromSidecar } from '@/utils/userConfig';
import { WS_TOKEN_FLUSH_MS } from '@/utils/sidecarWsConnection';
import { isWsLeader, postChannelMessage } from '@/utils/wsLeader';

type SessionStore = ReturnType<typeof useSessionStore>;
type SettingsStore = ReturnType<typeof useSettingsStore>;
type KnowledgeStore = ReturnType<typeof useKnowledgeStore>;
type TasksStore = ReturnType<typeof useTasksStore>;
type MemoryStore = ReturnType<typeof useMemoryStore>;

export type SidecarWsHandlerContext = {
  sessionStore: SessionStore;
  settingsStore: SettingsStore;
  knowledgeStore: KnowledgeStore;
  tasksStore: TasksStore;
  memoryStore: MemoryStore;
  connectionError: Ref<string>;
  pendingHistoryLoads: Map<string, number>;
  pendingCreateTitle: { get: () => string | undefined; set: (v: string | undefined) => void };
  fetchAuthToken: (port: number) => Promise<string | null>;
  sendRaw: (data: Record<string, unknown>) => boolean;
  listSessions: () => void;
  listArchivedSessions: () => void;
  listRagSources: () => void;
  bootstrapInitialSession: () => void;
  bootstrapFollowerSession: () => void;
};

export function createSidecarWsMessageHandler(ctx: SidecarWsHandlerContext) {
  let tokenBuffer = '';
  let tokenFlushTimer: ReturnType<typeof setTimeout> | null = null;

  function flushTokenBuffer() {
    if (tokenBuffer) {
      ctx.sessionStore.appendToLastAssistant(tokenBuffer);
      tokenBuffer = '';
    }
    tokenFlushTimer = null;
  }

  return function handleMessage(msg: Record<string, unknown>) {
    const type = msg.type as string;

    switch (type) {
      case 'connected':
        if (msg.port) {
          ctx.settingsStore.setSidecarPort(msg.port as number);
          void hydrateUserConfigFromSidecar(msg.port as number);
        }
        ctx.settingsStore.setWsConnected(true);
        ctx.connectionError.value = '';
        if (msg.auth_required) {
          void (async () => {
            const port = (msg.port as number) || ctx.settingsStore.sidecarPort;
            const token = await ctx.fetchAuthToken(port);
            if (token) ctx.sendRaw({ type: 'auth', token });
          })();
        }
        ctx.listSessions();
        if (ctx.pendingCreateTitle.get() !== undefined) {
          ctx.sendRaw({ type: 'session.create', title: ctx.pendingCreateTitle.get() });
          ctx.pendingCreateTitle.set(undefined);
        }
        break;

      case 'auth.ok':
        break;

      case 'tool_progress': {
        const toolName = msg.tool_name as string;
        const toolCallId = msg.tool_call_id as string | undefined;
        ctx.sessionStore.updateToolProgress(toolName, toolCallId, msg.status as string);
        break;
      }

      case 'token':
        tokenBuffer += (msg.content as string) || '';
        if (!tokenFlushTimer) {
          tokenFlushTimer = setTimeout(flushTokenBuffer, WS_TOKEN_FLUSH_MS);
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
        ctx.sessionStore.addPendingToolCall(tc);
        ctx.sessionStore.addMessage({
          id: toolCallId,
          role: 'tool',
          content: `调用工具: ${tc.name}`,
          toolName: tc.name,
          category: tc.category,
        });
        break;
      }

      case 'tool_end':
        ctx.sessionStore.resolveToolCall(
          msg.name as string,
          msg.result as string,
          msg.tool_call_id as string | undefined,
          msg.citations as Array<{ title: string; url: string }> | undefined
        );
        break;

      case 'interrupt':
        ctx.sessionStore.interruptQueue.push({
          thread_id: msg.thread_id as string,
          action: msg.action as string,
          preview: msg.preview as string,
          args: (msg.args as Record<string, unknown>) || {},
        });
        break;

      case 'interrupt_timeout_warning':
        ctx.sessionStore.addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `⚠️ 操作确认将在 ${msg.seconds_left} 秒后自动拒绝，请尽快确认。`,
        });
        break;

      case 'done': {
        flushTokenBuffer();
        ctx.sessionStore.isStreaming = false;
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
          ctx.settingsStore.setLastTurnDuration(metadata.duration_ms);
          ctx.sessionStore.setLastAssistantDuration(metadata.duration_ms);
        }
        if (metadata?.token_usage?.total_tokens) {
          ctx.settingsStore.setLastTokenUsage({
            prompt_tokens: metadata.token_usage.prompt_tokens ?? 0,
            completion_tokens: metadata.token_usage.completion_tokens ?? 0,
            total_tokens: metadata.token_usage.total_tokens ?? 0,
          });
        }
        if (metadata?.task_data_changed) {
          void ctx.tasksStore.refreshIfRunning();
        }
        void ctx.memoryStore.refreshAfterConversationTurn();
        break;
      }

      case 'tasks.changed':
        void ctx.tasksStore.refreshIfRunning();
        break;

      case 'scheduler.reminder': {
        const title = (msg.title as string) || '提醒';
        const body = (msg.message as string) || '';
        ctx.sessionStore.addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `🔔 ${title}: ${body}`,
        });
        void ctx.tasksStore.refreshReminders();
        if (!ctx.settingsStore.notificationPrefs.desktopEnabled) break;
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
        ctx.sessionStore.archivedSessions =
          (msg.sessions as typeof ctx.sessionStore.archivedSessions) || [];
        break;

      case 'session.archived_one':
        if (msg.ok) {
          ctx.listSessions();
          ctx.listArchivedSessions();
        }
        break;

      case 'session.unarchived_one':
        if (msg.ok) {
          ctx.listSessions();
          ctx.listArchivedSessions();
        }
        break;

      case 'error':
        ctx.sessionStore.isStreaming = false;
        ctx.sessionStore.addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `错误: ${msg.message}`,
        });
        break;

      case 'session.list':
        ctx.sessionStore.sessions = (msg.sessions as typeof ctx.sessionStore.sessions) || [];
        if (ctx.settingsStore.wsReadOnly) {
          ctx.bootstrapFollowerSession();
        } else {
          ctx.bootstrapInitialSession();
        }
        break;

      case 'session.created': {
        const threadId = msg.thread_id as string;
        ctx.sessionStore.sessions.unshift({
          thread_id: threadId,
          title: (msg.title as string) || '新会话',
          created_at: (msg.created_at as string) || new Date().toISOString(),
        });
        ctx.sessionStore.setCurrentThread(threadId);
        ctx.sessionStore.bumpInputFocus();
        break;
      }

      case 'session.deleted': {
        const deletedId = msg.thread_id as string;
        ctx.sessionStore.sessions = ctx.sessionStore.sessions.filter(
          (s) => s.thread_id !== deletedId
        );
        ctx.sessionStore.removePreview(deletedId);
        break;
      }

      case 'session.history': {
        const threadId = msg.thread_id as string;
        const expectedGen = ctx.pendingHistoryLoads.get(threadId);
        ctx.pendingHistoryLoads.delete(threadId);
        if (
          threadId === ctx.sessionStore.currentThreadId &&
          expectedGen === ctx.sessionStore.historyLoadGeneration
        ) {
          ctx.sessionStore.loadHistory(
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
        ctx.knowledgeStore.setSources((msg.sources as string[]) || []);
        ctx.knowledgeStore.isLoading = false;
        break;

      case 'rag.ingest':
        ctx.knowledgeStore.setIngestResult((msg.result as string) || '完成');
        ctx.knowledgeStore.isLoading = false;
        ctx.listRagSources();
        break;

      case 'rag.search':
        ctx.knowledgeStore.setSearchResults(
          (msg.results as Array<{ source: string; content: string; score: number }>) || []
        );
        ctx.knowledgeStore.isLoading = false;
        break;

      case 'rag.deleted':
        ctx.knowledgeStore.isLoading = false;
        ctx.listRagSources();
        break;
    }

    if (isWsLeader() && type !== 'pong') {
      postChannelMessage({ type: 'ws.forward', msg });
    }
  };
}
