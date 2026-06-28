import type { SettingsSectionId } from '@/stores/navigation';

export interface SettingsNavItem {
  id: SettingsSectionId;
  label: string;
  icon: string;
}

export interface SettingsNavGroup {
  label?: string;
  items: SettingsNavItem[];
}

export const SETTINGS_NAV_GROUPS: SettingsNavGroup[] = [
  {
    items: [
      { id: 'model', label: '模型', icon: '🧠' },
      { id: 'conversation', label: '对话', icon: '💬' },
      { id: 'appearance', label: '外观', icon: '🎨' },
      { id: 'workspace', label: '工作区', icon: '📁' },
      { id: 'security', label: '安全', icon: '🔒' },
      { id: 'memory', label: '记忆与上下文', icon: '📚' },
      { id: 'language', label: '语言', icon: '🌐' },
      { id: 'advanced', label: '高级', icon: '⚙' },
      { id: 'notification', label: '通知', icon: '🔔' },
    ],
  },
  {
    label: '集成',
    items: [
      { id: 'provider', label: '提供方', icon: '🔌' },
      { id: 'tools-keys', label: '工具与密钥', icon: '🔑' },
      { id: 'mcp', label: 'MCP', icon: '🔗' },
      { id: 'project', label: '项目', icon: '📋' },
      { id: 'task', label: '任务', icon: '✓' },
      { id: 'archived', label: '已归档对话', icon: '🗄' },
    ],
  },
  {
    items: [{ id: 'about', label: '关于', icon: 'ℹ' }],
  },
];

export interface ToolKeyField {
  id: string;
  label: string;
  placeholder: string;
  type?: 'text' | 'password' | 'url';
}

export const TOOL_KEY_FIELDS: ToolKeyField[] = [
  { id: 'agent_browser_engine', label: 'AGENT BROWSER ENGINE', placeholder: '可选' },
  { id: 'brave_search', label: 'BRAVE SEARCH', placeholder: '粘贴 Brave Search 密钥', type: 'password' },
  { id: 'browser_use', label: 'BROWSER USE', placeholder: '粘贴 Browser Use 密钥', type: 'password' },
  { id: 'browserbase', label: 'BROWSERBASE', placeholder: '粘贴 Browserbase 密钥', type: 'password' },
  { id: 'browserbase_project_id', label: 'BROWSERBASE PROJECT ID', placeholder: '可选' },
  { id: 'camofox_url', label: 'CAMOFOX URL', placeholder: 'https://...', type: 'url' },
  { id: 'elevenlabs', label: 'ELEVENLABS', placeholder: '粘贴 ElevenLabs 密钥', type: 'password' },
  { id: 'exa', label: 'EXA', placeholder: '粘贴 Exa 密钥', type: 'password' },
  { id: 'fal', label: 'FAL', placeholder: '粘贴 FAL 密钥', type: 'password' },
  { id: 'firecrawl', label: 'FIRECRAWL', placeholder: '粘贴 Firecrawl 密钥', type: 'password' },
  { id: 'firecrawl_api_url', label: 'FIRECRAWL API URL', placeholder: 'https://...', type: 'url' },
  { id: 'firecrawl_browser_ttl', label: 'FIRECRAWL BROWSER TTL', placeholder: '可选' },
  { id: 'firecrawl_gateway_url', label: 'FIRECRAWL GATEWAY URL', placeholder: 'https://...', type: 'url' },
  { id: 'github', label: 'GITHUB', placeholder: '粘贴 GitHub 密钥', type: 'password' },
  { id: 'langfuse_base_url', label: 'LANGFUSE BASE URL', placeholder: 'https://...', type: 'url' },
  { id: 'langfuse_public', label: 'LANGFUSE PUBLIC', placeholder: '粘贴 Langfuse Public Key', type: 'password' },
];
