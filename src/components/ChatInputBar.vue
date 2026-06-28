<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useSessionStore } from '@/stores/session';
import { useSettingsStore } from '@/stores/settings';
import { useAgentWs } from '@/composables/useAgentWs';
import { useChatInputModels } from '@/composables/useChatInputModels';
import {
  SESSION_COMMANDS,
  filterCommands,
  toolToSkill,
  type ChatCommand,
} from '@/utils/chatCommands';

const emit = defineEmits<{
  send: [text: string, attachments?: Array<{ type: string; name: string; content: string }>];
}>();

const sessionStore = useSessionStore();
const settings = useSettingsStore();
const { createSession, stop, send: wsSend } = useAgentWs();
const {
  currentModelLabel,
  fetchProviders,
  fetchOllamaModels,
  selectModel,
  filterModels,
} = useChatInputModels();

const input = ref('');
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const pendingAttachments = ref<Array<{ type: string; name: string; content: string }>>([]);

const showAttachMenu = ref(false);
const showModelMenu = ref(false);
const showSlashMenu = ref(false);
const slashQuery = ref('');
const slashMode = ref<'slash' | 'at'>('slash');
const modelSearch = ref('');
const slashHighlight = ref(0);
const modelHighlight = ref(0);

const skills = ref<ChatCommand[]>([]);
const ATTACH_ACCEPT = '.md,.txt,.markdown,.pdf,.json,.csv,.png,.jpg,.jpeg,.webp,.gif';
const IMAGE_ACCEPT = '.png,.jpg,.jpeg,.webp,.gif';

const filteredSlash = computed(() => {
  const result = filterCommands(slashQuery.value, SESSION_COMMANDS, skills.value);
  if (slashMode.value === 'at') {
    return { session: [], skills: result.skills };
  }
  return result;
});

const filteredModels = computed(() => filterModels(modelSearch.value));

const slashItems = computed(() => [
  ...filteredSlash.value.session,
  ...filteredSlash.value.skills,
]);

const canSend = computed(
  () =>
    input.value.trim().length > 0 &&
    !!sessionStore.currentThreadId &&
    !sessionStore.isStreaming
);

watch(input, (val) => {
  const atMatch = val.match(/(?:^|\s)@(\S*)$/);
  const slashMatch = val.match(/(?:^|\s)\/(\S*)$/);
  if (atMatch) {
    showSlashMenu.value = true;
    slashMode.value = 'at';
    slashQuery.value = atMatch[1] || '';
    slashHighlight.value = 0;
  } else if (slashMatch) {
    showSlashMenu.value = true;
    slashMode.value = 'slash';
    slashQuery.value = slashMatch[1] || '';
    slashHighlight.value = 0;
  } else {
    showSlashMenu.value = false;
    slashQuery.value = '';
  }
});

function closeAllMenus() {
  showAttachMenu.value = false;
  showModelMenu.value = false;
  showSlashMenu.value = false;
}

function onDocClick(e: MouseEvent) {
  const target = e.target as HTMLElement;
  if (!target.closest('.input-bar-root')) closeAllMenus();
}

onMounted(async () => {
  document.addEventListener('click', onDocClick);
  await loadSkills();
});

onUnmounted(() => {
  document.removeEventListener('click', onDocClick);
});

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

function autoResize() {
  const el = textareaRef.value;
  if (!el) return;
  el.style.height = 'auto';
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
}

function stripSlashToken(text: string) {
  return text.replace(/(?:^|\s)(?:\/|@)\S*$/, '').trimEnd();
}

function applySlashItem(item: ChatCommand) {
  if (item.category === 'skill') {
    const token = item.label;
    input.value = `${stripSlashToken(input.value)} ${token} `.trimStart();
    showSlashMenu.value = false;
    nextTick(() => textareaRef.value?.focus());
    return;
  }
  executeCommand(item.id);
  input.value = stripSlashToken(input.value);
  showSlashMenu.value = false;
}

function executeCommand(id: string) {
  switch (id) {
    case 'new':
      createSession();
      break;
    case 'save':
      saveTranscript();
      break;
    case 'retry':
      retryLastMessage();
      break;
    case 'undo':
      undoLastExchange();
      break;
    case 'title':
      renameSession();
      break;
    case 'clear':
      input.value = '';
      pendingAttachments.value = [];
      break;
    case 'stop':
      if (sessionStore.currentThreadId) stop(sessionStore.currentThreadId);
      break;
  }
}

function saveTranscript() {
  const payload = {
    thread_id: sessionStore.currentThreadId,
    messages: sessionStore.messages,
    exported_at: new Date().toISOString(),
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `chat-${sessionStore.currentThreadId || 'export'}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function retryLastMessage() {
  const msgs = sessionStore.messages;
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'user') {
      const content = msgs[i].content.replace(/\n📎 .+$/, '').trim();
      if (content && sessionStore.currentThreadId) {
        wsSend(content, sessionStore.currentThreadId);
      }
      break;
    }
  }
}

function undoLastExchange() {
  const msgs = sessionStore.messages;
  let removed = 0;
  while (msgs.length > 0 && removed < 2) {
    const last = msgs[msgs.length - 1];
    if (last.role === 'assistant' || last.role === 'user') {
      msgs.pop();
      removed++;
    } else {
      break;
    }
  }
}

function renameSession() {
  const title = window.prompt('输入新会话标题');
  if (!title?.trim() || !sessionStore.currentThreadId) return;
  const session = sessionStore.sessions.find(
    (s) => s.thread_id === sessionStore.currentThreadId
  );
  if (session) session.title = title.trim();
}

async function handleFileSelect(e: Event) {
  const inputEl = e.target as HTMLInputElement;
  if (!inputEl.files?.length) return;
  for (const file of Array.from(inputEl.files)) {
    if (file.type.startsWith('image/')) {
      const buf = await file.arrayBuffer();
      const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
      pendingAttachments.value.push({
        type: 'image',
        name: file.name,
        content: b64,
      });
    } else {
      const content = await file.text();
      pendingAttachments.value.push({ type: 'text', name: file.name, content });
    }
  }
  inputEl.value = '';
  showAttachMenu.value = false;
}

async function handleFolderSelect(e: Event) {
  const inputEl = e.target as HTMLInputElement;
  if (!inputEl.files?.length) return;
  const names = Array.from(inputEl.files).map((f) => f.name);
  pendingAttachments.value.push({
    type: 'folder',
    name: names[0]?.split('/')[0] || 'folder',
    content: names.join('\n'),
  });
  inputEl.value = '';
  showAttachMenu.value = false;
}

async function pasteImageFromClipboard() {
  try {
    const items = await navigator.clipboard.read();
    for (const item of items) {
      const type = item.types.find((t) => t.startsWith('image/'));
      if (!type) continue;
      const blob = await item.getType(type);
      const buf = await blob.arrayBuffer();
      const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
      pendingAttachments.value.push({
        type: 'image',
        name: `paste-${Date.now()}.png`,
        content: b64,
      });
      showAttachMenu.value = false;
      return;
    }
  } catch {
    /* clipboard not available */
  }
}

function attachUrl() {
  const url = window.prompt('输入 URL');
  if (!url?.trim()) return;
  pendingAttachments.value.push({ type: 'url', name: url.trim(), content: url.trim() });
  showAttachMenu.value = false;
}

function insertPromptSnippet() {
  const snippet = window.prompt('输入提示词片段');
  if (!snippet?.trim()) return;
  input.value = `${input.value}${input.value ? '\n' : ''}${snippet.trim()}`;
  showAttachMenu.value = false;
  nextTick(() => {
    autoResize();
    textareaRef.value?.focus();
  });
}

function removeAttachment(index: number) {
  pendingAttachments.value.splice(index, 1);
}

function handleSend() {
  const text = input.value.trim();
  if (!text || !sessionStore.currentThreadId) return;
  const attachments =
    pendingAttachments.value.length > 0 ? [...pendingAttachments.value] : undefined;
  emit('send', text, attachments);
  input.value = '';
  pendingAttachments.value = [];
  nextTick(autoResize);
}

function handleStop() {
  if (sessionStore.currentThreadId) stop(sessionStore.currentThreadId);
}

function handleKeydown(e: KeyboardEvent) {
  if (showSlashMenu.value && slashItems.value.length) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      slashHighlight.value = (slashHighlight.value + 1) % slashItems.value.length;
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      slashHighlight.value =
        (slashHighlight.value - 1 + slashItems.value.length) % slashItems.value.length;
      return;
    }
    if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
      e.preventDefault();
      applySlashItem(slashItems.value[slashHighlight.value]);
      return;
    }
    if (e.key === 'Escape') {
      showSlashMenu.value = false;
      return;
    }
  }

  if (showModelMenu.value && filteredModels.value.length) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      modelHighlight.value = (modelHighlight.value + 1) % filteredModels.value.length;
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      modelHighlight.value =
        (modelHighlight.value - 1 + filteredModels.value.length) % filteredModels.value.length;
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      selectModel(filteredModels.value[modelHighlight.value]);
      showModelMenu.value = false;
      return;
    }
    if (e.key === 'Escape') {
      showModelMenu.value = false;
      return;
    }
  }

  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (canSend.value) handleSend();
  }
}

function toggleAttach(e: Event) {
  e.stopPropagation();
  showAttachMenu.value = !showAttachMenu.value;
  showModelMenu.value = false;
  showSlashMenu.value = false;
}

function toggleModel(e: Event) {
  e.stopPropagation();
  showModelMenu.value = !showModelMenu.value;
  showAttachMenu.value = false;
  modelSearch.value = '';
  modelHighlight.value = 0;
  if (showModelMenu.value) {
    void fetchProviders();
    void fetchOllamaModels();
  }
}

function pickModel(option: (typeof filteredModels.value)[0]) {
  selectModel(option);
  showModelMenu.value = false;
}

defineExpose({ pendingAttachments });
</script>

<template>
  <div class="input-bar-root">
    <div v-if="pendingAttachments.length" class="attachments">
      <span v-for="(att, i) in pendingAttachments" :key="i" class="attachment-chip">
        📎 {{ att.name }}
        <button type="button" class="remove-att" @click="removeAttachment(i)">×</button>
      </span>
    </div>

    <!-- Slash command / skill menu -->
    <div v-if="showSlashMenu && slashItems.length" class="popup slash-popup">
      <div v-if="filteredSlash.session.length" class="popup-section">
        <div class="popup-label">会话</div>
        <button
          v-for="(item, i) in filteredSlash.session"
          :key="item.id"
          type="button"
          class="popup-item"
          :class="{ active: slashHighlight === i }"
          @click="applySlashItem(item)"
          @mouseenter="slashHighlight = i"
        >
          <span class="item-label">{{ item.label }}</span>
          <span class="item-desc">{{ item.description }}</span>
        </button>
      </div>
      <div v-if="filteredSlash.skills.length" class="popup-section">
        <div class="popup-label">技能</div>
        <button
          v-for="(item, i) in filteredSlash.skills"
          :key="item.id"
          type="button"
          class="popup-item"
          :class="{ active: slashHighlight === filteredSlash.session.length + i }"
          @click="applySlashItem(item)"
          @mouseenter="slashHighlight = filteredSlash.session.length + i"
        >
          <span class="item-label">{{ item.label }}</span>
          <span class="item-desc">{{ item.description }}</span>
        </button>
      </div>
    </div>

    <!-- Model selector popup -->
    <div v-if="showModelMenu" class="popup model-popup">
      <input
        v-model="modelSearch"
        class="popup-search"
        placeholder="搜索模型"
        @click.stop
        @keydown.stop
      />
      <div class="popup-list">
        <button
          v-for="(opt, i) in filteredModels"
          :key="opt.id"
          type="button"
          class="popup-item model-item"
          :class="{ active: modelHighlight === i || settings.provider === opt.provider && currentModelLabel === opt.label }"
          @click="pickModel(opt)"
          @mouseenter="modelHighlight = i"
        >
          <span class="item-label">{{ opt.label }}</span>
          <span class="item-desc">{{ opt.provider }}</span>
        </button>
        <div v-if="!filteredModels.length" class="popup-empty">无匹配模型</div>
      </div>
      <div class="popup-footer">
        <button type="button" class="footer-btn" @click.stop="fetchOllamaModels(); fetchProviders()">
          ↻ 刷新模型
        </button>
      </div>
    </div>

    <!-- Attach menu -->
    <div v-if="showAttachMenu" class="popup attach-popup">
      <div class="popup-label">附加</div>
      <label class="popup-item attach-item">
        <span class="attach-icon">📄</span>
        <span>文件…</span>
        <input type="file" :accept="ATTACH_ACCEPT" multiple hidden @change="handleFileSelect($event)" />
      </label>
      <label class="popup-item attach-item">
        <span class="attach-icon">📁</span>
        <span>文件夹…</span>
        <input
          type="file"
          webkitdirectory
          directory
          multiple
          hidden
          @change="handleFolderSelect"
        />
      </label>
      <label class="popup-item attach-item">
        <span class="attach-icon">🖼</span>
        <span>图片…</span>
        <input type="file" :accept="IMAGE_ACCEPT" multiple hidden @change="handleFileSelect" />
      </label>
      <button type="button" class="popup-item attach-item" @click="pasteImageFromClipboard">
        <span class="attach-icon">📋</span>
        <span>粘贴图片</span>
      </button>
      <button type="button" class="popup-item attach-item" @click="attachUrl">
        <span class="attach-icon">🔗</span>
        <span>URL…</span>
      </button>
      <button type="button" class="popup-item attach-item highlight" @click="insertPromptSnippet">
        <span class="attach-icon">💬</span>
        <span>提示词片段…</span>
      </button>
      <p class="attach-hint">提示：输入 @ 引用技能，输入 / 搜索命令</p>
    </div>

    <!-- Main input bar -->
    <div class="input-bar" :class="{ disabled: !sessionStore.currentThreadId }">
      <button
        type="button"
        class="btn-icon btn-plus"
        title="附加"
        :disabled="!sessionStore.currentThreadId"
        @click="toggleAttach"
      >
        +
      </button>

      <textarea
        ref="textareaRef"
        v-model="input"
        placeholder="你在想什么？ (Enter 发送, / 命令, @ 技能)"
        :disabled="!sessionStore.currentThreadId"
        rows="1"
        @input="autoResize"
        @keydown="handleKeydown"
      />

      <button
        type="button"
        class="btn-model"
        :disabled="!sessionStore.currentThreadId"
        @click="toggleModel"
      >
        <span class="model-name">{{ currentModelLabel }}</span>
        <span class="chevron">▾</span>
      </button>

      <div class="bar-actions">
        <button
          v-if="sessionStore.isStreaming"
          type="button"
          class="btn-stop-round"
          title="停止"
          @click="handleStop"
        >
          ■
        </button>
        <button
          v-else
          type="button"
          class="btn-send-round"
          title="发送"
          :disabled="!canSend"
          @click="handleSend"
        >
          ↑
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.input-bar-root {
  position: relative;
}

.attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.attachment-chip {
  background: #1f2128;
  border: 1px solid #2a2d35;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  color: #a1a1aa;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.remove-att {
  background: none;
  border: none;
  color: #71717a;
  cursor: pointer;
  font-size: 14px;
  padding: 0 2px;
}

.popup {
  position: absolute;
  bottom: calc(100% + 8px);
  background: #1a1c22;
  border: 1px solid #2a2d35;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45);
  z-index: 100;
  overflow: hidden;
}

.slash-popup,
.model-popup {
  left: 0;
  right: 0;
  max-height: 320px;
  display: flex;
  flex-direction: column;
}

.attach-popup {
  left: 0;
  width: 240px;
  padding-bottom: 8px;
}

.popup-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #71717a;
  padding: 10px 14px 6px;
  text-transform: uppercase;
}

.popup-section + .popup-section {
  border-top: 1px solid #2a2d35;
}

.popup-search {
  width: 100%;
  box-sizing: border-box;
  background: #16181d;
  border: none;
  border-bottom: 1px solid #2a2d35;
  color: #e4e4e7;
  padding: 10px 14px;
  font-size: 13px;
  outline: none;
}

.popup-list {
  overflow-y: auto;
  flex: 1;
  max-height: 220px;
}

.popup-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  width: 100%;
  background: none;
  border: none;
  color: #e4e4e7;
  padding: 8px 14px;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
}

.popup-item:hover,
.popup-item.active {
  background: #252830;
}

.model-item {
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
}

.item-label {
  font-size: 13px;
  font-weight: 500;
}

.item-desc {
  font-size: 12px;
  color: #71717a;
  margin-top: 2px;
}

.model-item .item-desc {
  margin-top: 0;
}

.popup-empty {
  padding: 16px;
  text-align: center;
  color: #71717a;
  font-size: 13px;
}

.popup-footer {
  border-top: 1px solid #2a2d35;
  padding: 6px;
}

.footer-btn {
  width: 100%;
  background: none;
  border: none;
  color: #a1a1aa;
  padding: 8px;
  cursor: pointer;
  font-size: 12px;
  border-radius: 6px;
  font-family: inherit;
}

.footer-btn:hover {
  background: #252830;
  color: #e4e4e7;
}

.attach-item {
  flex-direction: row;
  align-items: center;
  gap: 10px;
}

.attach-item.highlight {
  background: #252830;
}

.attach-icon {
  width: 20px;
  text-align: center;
  font-size: 14px;
}

.attach-hint {
  font-size: 11px;
  color: #52525b;
  padding: 8px 14px 0;
  margin: 0;
}

.input-bar {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: #16181d;
  border: 1px solid #2a2d35;
  border-radius: 16px;
  padding: 8px 8px 8px 4px;
  transition: border-color 0.15s;
}

.input-bar:focus-within {
  border-color: #3b82f6;
}

.input-bar.disabled {
  opacity: 0.6;
}

.btn-icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 10px;
  background: none;
  color: #a1a1aa;
  font-size: 22px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.btn-icon:hover:not(:disabled) {
  background: #252830;
  color: #e4e4e7;
}

.btn-icon:disabled {
  cursor: not-allowed;
}

textarea {
  flex: 1;
  min-width: 0;
  min-height: 36px;
  max-height: 160px;
  background: transparent;
  border: none;
  color: #e4e4e7;
  padding: 8px 4px;
  font-size: 14px;
  resize: none;
  font-family: inherit;
  line-height: 1.5;
}

textarea:focus {
  outline: none;
}

textarea::placeholder {
  color: #52525b;
}

.btn-model {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: #a1a1aa;
  font-size: 12px;
  cursor: pointer;
  padding: 6px 8px;
  border-radius: 8px;
  max-width: 160px;
  font-family: inherit;
}

.btn-model:hover:not(:disabled) {
  background: #252830;
  color: #e4e4e7;
}

.btn-model:disabled {
  cursor: not-allowed;
}

.model-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chevron {
  font-size: 10px;
  opacity: 0.7;
}

.bar-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding-left: 4px;
  border-left: 1px solid #2a2d35;
}

.btn-send-round,
.btn-stop-round {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: inherit;
}

.btn-send-round {
  background: #e4e4e7;
  color: #0f1117;
}

.btn-send-round:hover:not(:disabled) {
  background: #fff;
}

.btn-send-round:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.btn-stop-round {
  background: #ef4444;
  color: white;
  font-size: 12px;
}

.btn-stop-round:hover {
  background: #dc2626;
}
</style>
