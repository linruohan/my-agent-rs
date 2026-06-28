<script setup lang="ts">
import { useSessionStore } from '@/stores/session';

defineProps<{
  threadId: string;
  title: string;
  preview?: string;
  active: boolean;
  pinned: boolean;
  menuOpen: boolean;
}>();

const emit = defineEmits<{
  select: [threadId: string, e: MouseEvent];
  toggleMenu: [threadId: string];
  rename: [threadId: string];
  delete: [threadId: string];
  togglePin: [threadId: string];
}>();

const sessionStore = useSessionStore();
</script>

<template>
  <li
    :class="{ active }"
    @click="emit('select', threadId, $event)"
  >
    <div class="session-info">
      <span class="session-title">{{ title }}</span>
      <span v-if="preview || sessionStore.getPreview(threadId)" class="session-preview">
        {{ preview || sessionStore.getPreview(threadId) }}
      </span>
    </div>
    <div class="session-menu-wrap">
      <button
        type="button"
        class="btn-more"
        title="更多"
        @click.stop="emit('toggleMenu', threadId)"
      >
        ⋯
      </button>
      <div v-if="menuOpen" class="session-menu" @click.stop>
        <button type="button" @click="emit('rename', threadId)">重命名</button>
        <button type="button" @click="emit('togglePin', threadId)">
          {{ pinned ? '取消置顶' : '置顶' }}
        </button>
        <button type="button" class="danger" @click="emit('delete', threadId)">删除</button>
      </div>
    </div>
  </li>
</template>

<style scoped>
li {
  padding: 10px 12px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  border-radius: 8px;
  margin-bottom: 2px;
  list-style: none;
}

li:hover {
  background: var(--bg-hover);
}

li.active {
  background: var(--accent-subtle);
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-preview {
  font-size: 11px;
  color: var(--text-muted);
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
}

.session-menu-wrap {
  position: relative;
  flex-shrink: 0;
}

.btn-more {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 14px;
  padding: 2px 4px;
  line-height: 1;
  border-radius: 4px;
}

.btn-more:hover,
li:hover .btn-more {
  color: var(--text-secondary);
  background: var(--bg-hover);
}

.session-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  min-width: 128px;
  background: var(--bg-popover);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 8px 24px var(--shadow-color);
  z-index: 60;
  padding: 4px;
}

.session-menu button {
  display: block;
  width: 100%;
  background: none;
  border: none;
  color: var(--text-primary);
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
  border-radius: 6px;
  text-align: left;
  font-family: inherit;
}

.session-menu button:hover {
  background: var(--bg-hover);
}

.session-menu button.danger {
  color: var(--text-danger-soft);
}

.session-menu button.danger:hover {
  background: var(--bg-danger-subtle);
}
</style>
