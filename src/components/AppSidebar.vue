<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useSessionStore } from '@/stores/session';
import { useNavigationStore, type AppView } from '@/stores/navigation';
import { useAgentWs } from '@/composables/useAgentWs';
import { useSettingsStore } from '@/stores/settings';
import SessionListItem from '@/components/SessionListItem.vue';
import {
  SESSION_COMMANDS,
  filterCommands,
  toolToSkill,
  type ChatCommand,
} from '@/utils/chatCommands';

const WORKSPACE_KEY = 'pa-workspace-path';
const DEFAULT_WORKSPACE = '~/AssistantWorkspace';

const sessionStore = useSessionStore();
const navigation = useNavigationStore();
const settings = useSettingsStore();
const { createSession, deleteSession, loadSessionHistory, connectionError, isConnected } =
  useAgentWs();

const searchQuery = ref('');
const showSearchPopup = ref(false);
const skills = ref<ChatCommand[]>([]);
const workspaceMenuOpen = ref(false);
const openSessionMenuId = ref<string | null>(null);
const workspacePath = ref(localStorage.getItem(WORKSPACE_KEY) || DEFAULT_WORKSPACE);

const navItems: Array<{ id: AppView; label: string; icon: string }> = [
  { id: 'skills', label: '技能与工具', icon: '⚡' },
  { id: 'messaging', label: '消息平台', icon: '💬' },
  { id: 'artifacts', label: '产物', icon: '📦' },
  { id: 'tasks', label: '任务和项目管理', icon: '✓' },
  { id: 'knowledge', label: '知识库', icon: '📚' },
];

const workspaceDisplay = computed(() => {
  const p = workspacePath.value;
  if (p.length > 28) return '…' + p.slice(-25);
  return p;
});

const filteredSessions = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  let list = [...sessionStore.sessions];
  if (q && !searchQuery.value.startsWith('/') && !searchQuery.value.startsWith('@')) {
    list = list.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        sessionStore.getPreview(s.thread_id).toLowerCase().includes(q)
    );
  }
  const pinned = list.filter((s) => sessionStore.isPinned(s.thread_id));
  const unpinned = list.filter((s) => !sessionStore.isPinned(s.thread_id));
  return { pinned, unpinned };
});

const searchSlash = computed(() => {
  const q = searchQuery.value.trim();
  if (!q.startsWith('/') && !q.startsWith('@')) return null;
  const token = q.slice(1);
  return filterCommands(token, SESSION_COMMANDS, skills.value);
});

const searchItems = computed(() => {
  const slash = searchSlash.value;
  if (!slash) return [];
  return [...slash.session, ...slash.skills];
});

function selectSession(threadId: string) {
  navigation.setView('chat');
  sessionStore.setCurrentThread(threadId);
  loadSessionHistory(threadId);
  searchQuery.value = '';
  showSearchPopup.value = false;
  openSessionMenuId.value = null;
}

function handleNewSession() {
  navigation.setView('chat');
  if (!isConnected()) {
    createSession();
    return;
  }
  createSession();
}

function handleDelete(threadId: string) {
  deleteSession(threadId);
  if (sessionStore.currentThreadId === threadId) {
    sessionStore.setCurrentThread(null);
  }
  openSessionMenuId.value = null;
}

function handleSessionClick(threadId: string, e: MouseEvent) {
  if (e.shiftKey) {
    sessionStore.togglePin(threadId);
    return;
  }
  selectSession(threadId);
}

function goToView(view: AppView) {
  navigation.setView(view);
  workspaceMenuOpen.value = false;
}

function onSearchInput() {
  const q = searchQuery.value.trim();
  showSearchPopup.value = q.startsWith('/') || q.startsWith('@');
}

function applySearchItem(item: ChatCommand) {
  if (item.category === 'skill') {
    navigation.setView('chat');
    searchQuery.value = '';
    showSearchPopup.value = false;
    return;
  }
  switch (item.id) {
    case 'new':
      handleNewSession();
      break;
    case 'title':
      navigation.setView('chat');
      break;
    default:
      navigation.setView('chat');
      break;
  }
  searchQuery.value = '';
  showSearchPopup.value = false;
}

function onKeydown(e: KeyboardEvent) {
  if (e.ctrlKey && e.key === 'n') {
    e.preventDefault();
    handleNewSession();
  }
}

function closeMenus(e: MouseEvent) {
  const target = e.target as HTMLElement;
  if (!target.closest('.workspace-footer')) workspaceMenuOpen.value = false;
  if (!target.closest('.session-menu-wrap')) openSessionMenuId.value = null;
}

function toggleSessionMenu(threadId: string) {
  openSessionMenuId.value = openSessionMenuId.value === threadId ? null : threadId;
}

function renameSession(threadId: string) {
  const session = sessionStore.sessions.find((s) => s.thread_id === threadId);
  if (!session) return;
  const title = window.prompt('输入新会话标题', session.title);
  if (!title?.trim()) return;
  session.title = title.trim();
  openSessionMenuId.value = null;
}

function togglePinFromMenu(threadId: string) {
  sessionStore.togglePin(threadId);
  openSessionMenuId.value = null;
}

function editWorkspacePath() {
  const path = window.prompt('工作区路径', workspacePath.value);
  if (!path?.trim()) return;
  workspacePath.value = path.trim();
  localStorage.setItem(WORKSPACE_KEY, workspacePath.value);
  workspaceMenuOpen.value = false;
}

async function openWorkspaceFolder() {
  workspaceMenuOpen.value = false;
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    await invoke('open_workspace_folder', { path: workspacePath.value });
  } catch {
    window.alert(`工作区路径：${workspacePath.value}`);
  }
}

async function loadSkills() {
  try {
    const base = `http://127.0.0.1:${settings.sidecarPort}`;
    const resp = await fetch(`${base}/bootstrap`);
    if (!resp.ok) return;
    const data = (await resp.json()) as {
      tools?: { tools?: Array<{ name: string; description?: string; enabled?: boolean }> };
    };
    const tools = data.tools?.tools || [];
    skills.value = tools
      .filter((t) => t.enabled !== false)
      .map((t) => toolToSkill(t.name, t.description));
  } catch {
    skills.value = [];
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown);
  document.addEventListener('click', closeMenus);
  void loadSkills();
});

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown);
  document.removeEventListener('click', closeMenus);
});
</script>

<template>
  <aside class="sidebar" :class="{ collapsed: navigation.sidebarCollapsed }">
    <nav class="nav-section">
      <button type="button" class="nav-item primary" @click="handleNewSession">
        <span class="nav-icon">✏️</span>
        <span class="nav-label">新建会话</span>
        <kbd class="nav-kbd">Ctrl N</kbd>
      </button>
      <button
        v-for="item in navItems"
        :key="item.id"
        type="button"
        class="nav-item"
        :class="{ active: navigation.activeView === item.id }"
        @click="goToView(item.id)"
      >
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-label">{{ item.label }}</span>
      </button>
    </nav>

    <div class="session-section">
      <div class="search-wrap">
        <input
          v-model="searchQuery"
          class="search-input"
          placeholder="搜索会话、/ 命令、@ 技能…"
          @input="onSearchInput"
          @focus="onSearchInput"
        />
        <div v-if="showSearchPopup && searchItems.length" class="search-popup">
          <div v-if="searchSlash?.session.length" class="popup-group">
            <div class="popup-label">命令</div>
            <button
              v-for="item in searchSlash.session"
              :key="item.id"
              type="button"
              class="popup-item"
              @click="applySearchItem(item)"
            >
              <span>{{ item.label }}</span>
              <span class="popup-desc">{{ item.description }}</span>
            </button>
          </div>
          <div v-if="searchSlash?.skills.length" class="popup-group">
            <div class="popup-label">技能</div>
            <button
              v-for="item in searchSlash.skills"
              :key="item.id"
              type="button"
              class="popup-item"
              @click="applySearchItem(item)"
            >
              <span>{{ item.label }}</span>
              <span class="popup-desc">{{ item.description }}</span>
            </button>
          </div>
        </div>
      </div>

      <div v-if="filteredSessions.pinned.length" class="session-group">
        <div class="group-label">已置顶</div>
        <p class="group-hint">Shift+ 单击对话以置顶</p>
        <ul class="session-list">
          <SessionListItem
            v-for="s in filteredSessions.pinned"
            :key="s.thread_id"
            :thread-id="s.thread_id"
            :title="s.title"
            :active="s.thread_id === sessionStore.currentThreadId"
            :pinned="true"
            :menu-open="openSessionMenuId === s.thread_id"
            @select="handleSessionClick"
            @toggle-menu="toggleSessionMenu"
            @rename="renameSession"
            @delete="handleDelete"
            @toggle-pin="togglePinFromMenu"
          />
        </ul>
      </div>

      <ul class="session-list scrollable">
        <SessionListItem
          v-for="s in filteredSessions.unpinned"
          :key="s.thread_id"
          :thread-id="s.thread_id"
          :title="s.title"
          :active="s.thread_id === sessionStore.currentThreadId"
          :pinned="false"
          :menu-open="openSessionMenuId === s.thread_id"
          @select="handleSessionClick"
          @toggle-menu="toggleSessionMenu"
          @rename="renameSession"
          @delete="handleDelete"
          @toggle-pin="togglePinFromMenu"
        />
        <li v-if="sessionStore.sessions.length === 0" class="empty">
          {{ connectionError || '暂无会话，点击新建' }}
        </li>
      </ul>
    </div>

  <!-- 工作区 -->
    <div class="workspace-footer">
      <button
        type="button"
        class="ws-btn ws-home"
        title="返回聊天"
        :class="{ active: navigation.activeView === 'chat' }"
        @click="goToView('chat')"
      >
        🏠
      </button>
      <button
        type="button"
        class="workspace-info"
        title="点击修改工作区路径"
        @click="editWorkspacePath"
      >
        <span class="ws-label">工作区</span>
        <span class="ws-path">{{ workspaceDisplay }}</span>
      </button>
      <div class="ws-menu-wrap">
        <button
          type="button"
          class="ws-btn ws-more"
          title="工作区操作"
          @click.stop="workspaceMenuOpen = !workspaceMenuOpen"
        >
          ⋯
        </button>
        <div v-if="workspaceMenuOpen" class="ws-menu">
          <button type="button" @click="editWorkspacePath">修改路径</button>
          <button type="button" @click="openWorkspaceFolder">在文件夹中打开</button>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 280px;
  background: #12141a;
  border-right: 1px solid #2a2d35;
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex-shrink: 0;
  transition: width 0.2s ease;
}

.sidebar.collapsed {
  width: 0;
  overflow: hidden;
  border-right: none;
}

.nav-section {
  padding: 12px 10px;
  border-bottom: 1px solid #2a2d35;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 12px;
  background: none;
  border: none;
  border-radius: 8px;
  color: #a1a1aa;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
}

.nav-item:hover {
  background: #1f2128;
  color: #e4e4e7;
}

.nav-item.active {
  background: #1f2128;
  color: #e4e4e7;
}

.nav-item.primary {
  color: #e4e4e7;
  font-weight: 500;
}

.nav-icon {
  width: 20px;
  text-align: center;
  font-size: 14px;
  flex-shrink: 0;
}

.nav-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-kbd {
  font-size: 10px;
  color: #52525b;
  background: #1f2128;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: inherit;
}

.session-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 12px 10px 8px;
  gap: 8px;
}

.search-wrap {
  position: relative;
}

.search-input {
  width: 100%;
  box-sizing: border-box;
  background: #16181d;
  border: 1px solid #2a2d35;
  border-radius: 8px;
  color: #e4e4e7;
  padding: 8px 12px;
  font-size: 13px;
  outline: none;
  font-family: inherit;
}

.search-input:focus {
  border-color: #3b82f6;
}

.search-input::placeholder {
  color: #52525b;
}

.search-popup {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: #1a1c22;
  border: 1px solid #2a2d35;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  z-index: 50;
  max-height: 240px;
  overflow-y: auto;
}

.popup-group + .popup-group {
  border-top: 1px solid #2a2d35;
}

.popup-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #71717a;
  padding: 8px 12px 4px;
  text-transform: uppercase;
}

.popup-item {
  display: flex;
  flex-direction: column;
  width: 100%;
  background: none;
  border: none;
  color: #e4e4e7;
  padding: 8px 12px;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  font-size: 13px;
}

.popup-item:hover {
  background: #252830;
}

.popup-desc {
  font-size: 11px;
  color: #71717a;
  margin-top: 2px;
}

.session-group {
  flex-shrink: 0;
}

.group-label {
  font-size: 11px;
  font-weight: 600;
  color: #71717a;
  padding: 4px 4px 2px;
}

.group-hint {
  font-size: 10px;
  color: #52525b;
  padding: 0 4px 6px;
  margin: 0;
}

.session-list {
  list-style: none;
}

.session-list.scrollable {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.empty {
  color: #71717a;
  font-size: 12px;
  cursor: default;
  padding: 12px;
  list-style: none;
}

.workspace-footer {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 10px 12px;
  border-top: 1px solid #2a2d35;
  background: #12141a;
}

.ws-btn {
  background: #16181d;
  border: 1px solid #2a2d35;
  border-radius: 8px;
  color: #a1a1aa;
  cursor: pointer;
  font-family: inherit;
  flex-shrink: 0;
}

.ws-home {
  width: 40px;
  height: 36px;
  font-size: 16px;
}

.ws-more {
  width: 36px;
  height: 36px;
  font-size: 14px;
}

.ws-btn:hover,
.ws-btn.active {
  background: #1f2128;
  color: #e4e4e7;
}

.workspace-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  background: #16181d;
  border: 1px solid #2a2d35;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
}

.workspace-info:hover {
  background: #1f2128;
}

.ws-label {
  font-size: 10px;
  color: #71717a;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.ws-path {
  font-size: 11px;
  color: #a1a1aa;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.ws-menu-wrap {
  position: relative;
  flex-shrink: 0;
}

.ws-menu {
  position: absolute;
  bottom: calc(100% + 6px);
  right: 0;
  min-width: 160px;
  background: #1a1c22;
  border: 1px solid #2a2d35;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  z-index: 50;
  padding: 4px;
}

.ws-menu button {
  display: block;
  width: 100%;
  background: none;
  border: none;
  color: #e4e4e7;
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
  border-radius: 6px;
  text-align: left;
  font-family: inherit;
}

.ws-menu button:hover {
  background: #252830;
}
</style>
