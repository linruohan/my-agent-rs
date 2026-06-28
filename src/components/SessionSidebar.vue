<script setup lang="ts">
import { useSessionStore } from '@/stores/session';
import { useAgentWs } from '@/composables/useAgentWs';

const sessionStore = useSessionStore();
const { createSession, deleteSession, loadSessionHistory, connectionError, isConnected } = useAgentWs();

function selectSession(threadId: string) {
  sessionStore.setCurrentThread(threadId);
  loadSessionHistory(threadId);
}

function handleNewSession() {
  if (!isConnected()) {
    createSession();
    return;
  }
  createSession();
}

function handleDelete(threadId: string, e: Event) {
  e.stopPropagation();
  deleteSession(threadId);
  if (sessionStore.currentThreadId === threadId) {
    sessionStore.setCurrentThread(null);
  }
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <h2>会话</h2>
      <button class="btn-new" @click="handleNewSession">+ 新建</button>
    </div>
    <ul class="session-list">
      <li
        v-for="s in sessionStore.sessions"
        :key="s.thread_id"
        :class="{ active: s.thread_id === sessionStore.currentThreadId }"
        @click="selectSession(s.thread_id)"
      >
        <span class="title">{{ s.title }}</span>
        <button class="btn-delete" @click="handleDelete(s.thread_id, $event)">×</button>
      </li>
      <li v-if="sessionStore.sessions.length === 0" class="empty">
        {{ connectionError || '暂无会话，点击新建' }}
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 240px;
  background: var(--bg-panel);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border);
}

.sidebar-header h2 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
}

.btn-new {
  background: var(--accent);
  color: var(--text-on-accent);
  border: none;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}

.btn-new:hover {
  background: var(--user-bubble);
}

.session-list {
  list-style: none;
  overflow-y: auto;
  flex: 1;
}

.session-list li {
  padding: 12px 16px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--bg-hover);
}

.session-list li:hover {
  background: var(--bg-hover);
}

.session-list li.active {
  background: var(--accent-subtle);
}

.title {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.btn-delete {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 16px;
  padding: 0 4px;
}

.btn-delete:hover {
  color: var(--danger);
}

.empty {
  color: var(--text-muted);
  font-size: 12px;
  cursor: default;
}
</style>
