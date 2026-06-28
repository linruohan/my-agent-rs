export type ColorMode = 'light' | 'dark' | 'system';
export type ToolCallDisplayMode = 'product' | 'technical';
export type InlinePreviewMode = 'off' | 'ask' | 'always';

export interface ThemeDefinition {
  id: string;
  name: string;
  description: string;
  preview: [string, string, string];
}

export interface ThemeColorTokens {
  bgApp: string;
  bgSidebar: string;
  bgPanel: string;
  bgElevated: string;
  bgInput: string;
  border: string;
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  accent: string;
  accentHover?: string;
  accentSubtle: string;
  userBubble: string;
  assistantBubble: string;
  settingsNavActive: string;
}
