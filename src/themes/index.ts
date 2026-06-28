import ember from './ember.meta';
import nous from './nous.meta';
import midnight from './midnight.meta';
import mono from './mono.meta';
import cyberpunk from './cyberpunk.meta';
import slate from './slate.meta';
import catppuccin from './catppuccin.meta';
import tokyonight from './tokyonight.meta';
import gruvbox from './gruvbox.meta';
import everforest from './everforest.meta';
import ayu from './ayu.meta';
import solarized from './solarized.meta';
import molokai from './molokai.meta';
import jellybeans from './jellybeans.meta';
import matrix from './matrix.meta';
import aurora from './aurora.meta';
import spaceduck from './spaceduck.meta';
import twilight from './twilight.meta';
import adventure from './adventure.meta';
import alduin from './alduin.meta';
import asciinema from './asciinema.meta';
import flexoki from './flexoki.meta';
import fahrenheit from './fahrenheit.meta';
import harper from './harper.meta';
import hybrid from './hybrid.meta';
import kibble from './kibble.meta';
import macos_classic from './macos-classic.meta';
import mellifluous from './mellifluous.meta';

import type { ColorMode, InlinePreviewMode, ThemeDefinition, ToolCallDisplayMode } from './types';

export type { ColorMode, InlinePreviewMode, ThemeDefinition, ToolCallDisplayMode };

export const UI_LANGUAGES = [
  { id: 'zh-CN', label: '简体中文' },
  { id: 'en', label: 'English' },
] as const;

export const THEME_LIST: ThemeDefinition[] = [
  ember,
  nous,
  midnight,
  mono,
  cyberpunk,
  slate,
  catppuccin,
  tokyonight,
  gruvbox,
  everforest,
  ayu,
  solarized,
  molokai,
  jellybeans,
  matrix,
  aurora,
  spaceduck,
  twilight,
  adventure,
  alduin,
  asciinema,
  flexoki,
  fahrenheit,
  harper,
  hybrid,
  kibble,
  macos_classic,
  mellifluous,
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
