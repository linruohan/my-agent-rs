import { ref } from 'vue';
import { defineStore } from 'pinia';

export type AppView =
  | 'chat'
  | 'projects'
  | 'tasks'
  | 'skills'
  | 'messaging'
  | 'artifacts'
  | 'knowledge'
  | 'settings';

export type SettingsSectionId =
  | 'model'
  | 'conversation'
  | 'appearance'
  | 'workspace'
  | 'security'
  | 'memory'
  | 'language'
  | 'advanced'
  | 'notification'
  | 'provider'
  | 'tools-keys'
  | 'mcp'
  | 'project'
  | 'task'
  | 'archived'
  | 'about';

export type SettingsSection = SettingsSectionId | null;

export const useNavigationStore = defineStore('navigation', () => {
  const activeView = ref<AppView>('chat');
  const sidebarCollapsed = ref(false);
  const settingsSection = ref<SettingsSectionId | null>(null);

  function setView(view: AppView) {
    activeView.value = view;
  }

  function openSettings(section: SettingsSectionId | null = null) {
    settingsSection.value = section;
    activeView.value = 'settings';
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value;
  }

  return { activeView, sidebarCollapsed, settingsSection, setView, openSettings, toggleSidebar };
});
