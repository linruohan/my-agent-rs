import adventure from './adventure.meta';
import alduin from './alduin.meta';
import asciinema from './asciinema.meta';
import aurora from './aurora.meta';
import ayu from './ayu.meta';
import catppuccin from './catppuccin.meta';
import everforest from './everforest.meta';
import fahrenheit from './fahrenheit.meta';
import flexoki from './flexoki.meta';
import gruvbox from './gruvbox.meta';
import harper from './harper.meta';
import hybrid from './hybrid.meta';
import jellybeans from './jellybeans.meta';
import kibble from './kibble.meta';
import macos_classic from './macos-classic.meta';
import matrix from './matrix.meta';
import mellifluous from './mellifluous.meta';
import molokai from './molokai.meta';
import solarized from './solarized.meta';
import spaceduck from './spaceduck.meta';
import tokyonight from './tokyonight.meta';
import twilight from './twilight.meta';

import type { ColorMode, InlinePreviewMode, ThemeDefinition, ToolCallDisplayMode } from './types';

export type { ColorMode, InlinePreviewMode, ThemeDefinition, ToolCallDisplayMode };

export const THEME_IDS = [
  'adventure',
  'alduin',
  'asciinema',
  'aurora',
  'ayu',
  'catppuccin',
  'everforest',
  'fahrenheit',
  'flexoki',
  'gruvbox',
  'harper',
  'hybrid',
  'jellybeans',
  'kibble',
  'macos-classic',
  'matrix',
  'mellifluous',
  'molokai',
  'solarized',
  'spaceduck',
  'tokyonight',
  'twilight',
] as const;

export type ThemeId = (typeof THEME_IDS)[number];

export const UI_LANGUAGES = [
  { id: 'zh-CN', label: '简体中文' },
  { id: 'en', label: 'English' },
] as const;

export const THEME_LIST: ThemeDefinition[] = [
  adventure,
  alduin,
  asciinema,
  aurora,
  ayu,
  catppuccin,
  everforest,
  fahrenheit,
  flexoki,
  gruvbox,
  harper,
  hybrid,
  jellybeans,
  kibble,
  macos_classic,
  matrix,
  mellifluous,
  molokai,
  solarized,
  spaceduck,
  tokyonight,
  twilight,
];

export const DEFAULT_APPEARANCE = {
  uiLanguage: 'zh-CN' as const,
  colorMode: 'dark' as ColorMode,
  themeId: 'catppuccin' as ThemeId,
  windowTransparency: 0,
  toolCallDisplay: 'product' as ToolCallDisplayMode,
  inlinePreview: 'off' as InlinePreviewMode,
};

export function resolveThemeId(themeId: string): ThemeId {
  return (THEME_IDS as readonly string[]).includes(themeId) ? (themeId as ThemeId) : DEFAULT_APPEARANCE.themeId;
}

export function resolveColorMode(mode: ColorMode): 'light' | 'dark' {
  if (mode === 'system' && typeof window !== 'undefined') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  if (mode === 'light') return 'light';
  return 'dark';
}
