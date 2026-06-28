<script setup lang="ts">
import { computed } from 'vue';
import AppSidebar from '@/components/AppSidebar.vue';
import ChatPanel from '@/components/ChatPanel.vue';
import ConfirmModal from '@/components/ConfirmModal.vue';
import StatusBar from '@/components/StatusBar.vue';
import SettingsView from '@/views/SettingsView.vue';
import KnowledgeBaseView from '@/views/KnowledgeBaseView.vue';
import TasksView from '@/views/TasksView.vue';
import SkillsToolsView from '@/views/SkillsToolsView.vue';
import PlaceholderView from '@/views/PlaceholderView.vue';
import StartupOverlay from '@/components/StartupOverlay.vue';
import { useNavigationStore } from '@/stores/navigation';

const navigation = useNavigationStore();

const viewTitle = computed(() => {
  const map: Record<string, string> = {
    chat: '聊天',
    tasks: '任务和项目管理',
    skills: '技能与工具',
    messaging: '消息平台',
    artifacts: '产物',
    knowledge: '知识库',
    settings: '设置',
  };
  return map[navigation.activeView] || '';
});
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <div class="main-column">
      <header class="top-bar">
        <span class="view-title">{{ viewTitle }}</span>
        <div class="top-actions">
          <button
            type="button"
            class="top-btn"
            title="设置"
            :class="{ active: navigation.activeView === 'settings' }"
            @click="navigation.setView('settings')"
          >
            ⚙
          </button>
          <button
            type="button"
            class="top-btn"
            title="收起/展开侧栏"
            @click="navigation.toggleSidebar()"
          >
            ☰
          </button>
        </div>
      </header>

      <main class="content-area">
        <ChatPanel v-if="navigation.activeView === 'chat'" />
        <TasksView v-else-if="navigation.activeView === 'tasks'" />
        <SkillsToolsView v-else-if="navigation.activeView === 'skills'" />
        <KnowledgeBaseView v-else-if="navigation.activeView === 'knowledge'" />
        <SettingsView v-else-if="navigation.activeView === 'settings'" />
        <PlaceholderView
          v-else-if="navigation.activeView === 'messaging'"
          title="消息平台"
          description="连接 Telegram、Slack 等消息渠道，在对话中接收与回复消息。"
          icon="💬"
        />
        <PlaceholderView
          v-else-if="navigation.activeView === 'artifacts'"
          title="产物"
          description="查看 Agent 生成的文件、代码片段与导出内容。"
          icon="📦"
        />
      </main>

      <StatusBar />
    </div>

    <ConfirmModal />
    <StartupOverlay />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  background: #0f1117;
  color: #e4e4e7;
}

.main-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  background: #0f1117;
  border-bottom: 1px solid #2a2d35;
  flex-shrink: 0;
}

.view-title {
  font-size: 13px;
  color: #71717a;
}

.top-actions {
  display: flex;
  gap: 4px;
}

.top-btn {
  width: 32px;
  height: 32px;
  background: none;
  border: none;
  border-radius: 8px;
  color: #71717a;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.top-btn:hover,
.top-btn.active {
  background: #1f2128;
  color: #e4e4e7;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
</style>
