export type ColorMode = 'light' | 'dark' | 'system';
export type ToolCallDisplayMode = 'product' | 'technical';
export type InlinePreviewMode = 'off' | 'ask' | 'always';

export interface ThemeDefinition {
  id: string;
  name: string;
  description: string;
  preview: [string, string, string]; // bg, accent, surface
}

export const UI_LANGUAGES = [
  { id: 'zh-CN', label: '简体中文' },
  { id: 'en', label: 'English' },
] as const;

export const THEME_LIST: ThemeDefinition[] = [
  {
    id: 'ember',
    name: 'Ember',
    description: '暖色赤铜 — 锻造氛围',
    preview: ['#f5ebe0', '#c2410c', '#e8d5c4'],
  },
  {
    id: 'nous',
    name: 'Nous',
    description: '玻璃质感中性色 + Nous 蓝点缀',
    preview: ['#eef2f7', '#3b82f6', '#dbeafe'],
  },
  {
    id: 'midnight',
    name: 'Midnight',
    description: '深蓝紫 + 冷色高光',
    preview: ['#1e1b4b', '#818cf8', '#312e81'],
  },
  {
    id: 'mono',
    name: 'Mono',
    description: '干净灰阶 — 极简专注',
    preview: ['#f4f4f5', '#52525b', '#e4e4e7'],
  },
  {
    id: 'cyberpunk',
    name: 'Cyberpunk',
    description: '黑底霓虹绿 — 矩阵终端',
    preview: ['#0a0f0a', '#22c55e', '#14532d'],
  },
  {
    id: 'slate',
    name: 'Slate',
    description: '冷灰蓝 — 开发者主题',
    preview: ['#1e293b', '#64748b', '#334155'],
  },
  {
    id: 'catppuccin',
    name: 'Catppuccin',
    description: '柔和粉彩 — 社区经典',
    preview: ['#1e1e2e', '#89b4fa', '#313244'],
  },
  {
    id: 'tokyonight',
    name: 'Tokyo Night',
    description: '东京霓虹 — 深蓝编辑器',
    preview: ['#1a1b26', '#7aa2f7', '#24283b'],
  },
  {
    id: 'gruvbox',
    name: 'Gruvbox',
    description: '复古暖色 — 护眼经典',
    preview: ['#282828', '#fabd2f', '#3c3836'],
  },
  {
    id: 'everforest',
    name: 'Everforest',
    description: '森林绿 — 自然低饱和',
    preview: ['#2d353b', '#a7c080', '#343f44'],
  },
  {
    id: 'ayu',
    name: 'Ayu',
    description: 'Ayu Mirage — 极简暗色',
    preview: ['#0f1419', '#ffb454', '#1f2430'],
  },
  {
    id: 'solarized',
    name: 'Solarized',
    description: 'Solarized — 科学配色',
    preview: ['#002b36', '#268bd2', '#073642'],
  },
  {
    id: 'molokai',
    name: 'Molokai',
    description: 'Monokai 变体 — 高对比',
    preview: ['#1b1d1e', '#66d9ef', '#272822'],
  },
  {
    id: 'jellybeans',
    name: 'Jellybeans',
    description: '果冻豆 — 多彩暗色',
    preview: ['#151515', '#ff907a', '#2a2a2a'],
  },
  {
    id: 'matrix',
    name: 'Matrix',
    description: '矩阵终端 — 纯绿黑',
    preview: ['#0a0a0a', '#00ff41', '#0d1a0d'],
  },
  {
    id: 'aurora',
    name: 'Aurora',
    description: '极光 — 北欧冷色',
    preview: ['#23262e', '#88c0d0', '#2e3440'],
  },
  {
    id: 'spaceduck',
    name: 'Spaceduck',
    description: '太空鸭 — 紫蓝宇宙',
    preview: ['#161320', '#72b7bf', '#262427'],
  },
  {
    id: 'twilight',
    name: 'Twilight',
    description: 'Twilight — 蓝橙黄昏',
    preview: ['#141414', '#cf6a4c', '#2a2a2a'],
  },
  {
    id: 'adventure',
    name: 'Adventure',
    description: '冒险 — 深红暗色',
    preview: ['#040404', '#d78787', '#1a1010'],
  },
  {
    id: 'alduin',
    name: 'Alduin',
    description: '龙裔 — 暖金暗色',
    preview: ['#1c1c1c', '#d4a574', '#2a2420'],
  },
  {
    id: 'asciinema',
    name: 'Asciinema',
    description: '终端录屏 — 纯黑绿',
    preview: ['#121212', '#00a100', '#1a1a1a'],
  },
  {
    id: 'flexoki',
    name: 'Flexoki',
    description: 'Flexoki — 暖中性色',
    preview: ['#100f0f', '#205ea6', '#1c1b1a'],
  },
  {
    id: 'fahrenheit',
    name: 'Fahrenheit',
    description: '华氏 — 暖橙暗色',
    preview: ['#1a1410', '#ff9933', '#2a2018'],
  },
  {
    id: 'harper',
    name: 'Harper',
    description: 'Harper — 紫罗兰暗色',
    preview: ['#131018', '#a78bfa', '#1e1828'],
  },
  {
    id: 'hybrid',
    name: 'Hybrid',
    description: 'Hybrid — Vim 混合色',
    preview: ['#1d1f21', '#f0c674', '#282a2e'],
  },
  {
    id: 'kibble',
    name: 'Kibble',
    description: 'Kibble — 深蓝编辑器',
    preview: ['#0e0e0e', '#6fb3d2', '#1a1a2e'],
  },
  {
    id: 'macos-classic',
    name: 'macOS Classic',
    description: '经典 Mac — 灰蓝桌面',
    preview: ['#ddd6c9', '#0066cc', '#c0c0c0'],
  },
  {
    id: 'mellifluous',
    name: 'Mellifluous',
    description: '圆润 — 柔和粉彩暗色',
    preview: ['#1a1820', '#c4a7e7', '#252230'],
  },
];

export const DEFAULT_APPEARANCE = {
  uiLanguage: 'zh-CN' as const,
  colorMode: 'dark' as ColorMode,
  themeId: 'slate',
  windowTransparency: 0,
  toolCallDisplay: 'product' as ToolCallDisplayMode,
  inlinePreview: 'off' as InlinePreviewMode,
};

export function resolveColorMode(mode: ColorMode): 'light' | 'dark' {
  if (mode === 'system' && typeof window !== 'undefined') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  if (mode === 'light') return 'light';
  return 'dark';
}
