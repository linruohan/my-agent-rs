<script setup lang="ts">
import { ref } from 'vue';
import SessionSidebar from '@/components/SessionSidebar.vue';
import ChatPanel from '@/components/ChatPanel.vue';
import ConfirmModal from '@/components/ConfirmModal.vue';
import StatusBar from '@/components/StatusBar.vue';
import SettingsView from '@/views/SettingsView.vue';
import KnowledgeBaseView from '@/views/KnowledgeBaseView.vue';
import TasksView from '@/views/TasksView.vue';
import StartupOverlay from '@/components/StartupOverlay.vue';

const tab = ref<'chat' | 'tasks' | 'knowledge' | 'settings'>('chat');
</script>

<template>
  <div class="chat-view">
    <SessionSidebar />
    <div class="main-area">
      <nav class="tabs">
        <button :class="{ active: tab === 'chat' }" @click="tab = 'chat'">聊天</button>
        <button :class="{ active: tab === 'tasks' }" @click="tab = 'tasks'">任务</button>
        <button :class="{ active: tab === 'knowledge' }" @click="tab = 'knowledge'">知识库</button>
        <button :class="{ active: tab === 'settings' }" @click="tab = 'settings'">设置</button>
      </nav>
      <ChatPanel v-show="tab === 'chat'" />
      <TasksView v-show="tab === 'tasks'" />
      <KnowledgeBaseView v-show="tab === 'knowledge'" />
      <SettingsView v-show="tab === 'settings'" />
      <StatusBar />
    </div>
    <ConfirmModal />
    <StartupOverlay />
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  height: 100vh;
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.tabs {
  display: flex;
  gap: 4px;
  padding: 8px 16px;
  background: #16181d;
  border-bottom: 1px solid #2a2d35;
}

.tabs button {
  background: none;
  border: none;
  color: #71717a;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.tabs button.active {
  background: #1f2128;
  color: #e4e4e7;
}
</style>
