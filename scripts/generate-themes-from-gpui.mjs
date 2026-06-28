/**
 * Generate theme CSS + meta from gpui-component JSON theme files.
 * Source: ../gpui-component/themes/*.json (copied to src/themes/json/)
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const gpuiThemesDir = path.resolve(root, '../gpui-component/themes');
const themesDir = path.join(root, 'src/themes');
const jsonDir = path.join(themesDir, 'json');

const DESCRIPTIONS = {
  adventure: '冒险 — 深红暗色',
  alduin: '龙裔 — 暖金暗色',
  asciinema: '终端录屏 — 纯黑绿',
  aurora: '极光 — 北欧冷色（gpui 官方）',
  ayu: 'Ayu — 极简编辑器配色',
  catppuccin: 'Catppuccin — 柔和粉彩社区经典',
  everforest: 'Everforest — 森林绿自然低饱和',
  fahrenheit: 'Fahrenheit — 暖橙暗色',
  flexoki: 'Flexoki — 暖中性色',
  gruvbox: 'Gruvbox — 复古暖色护眼经典',
  harper: 'Harper — 紫罗兰暗色',
  hybrid: 'Hybrid — Vim 混合色',
  jellybeans: 'Jellybeans — 多彩暗色',
  kibble: 'Kibble — 深蓝编辑器',
  'macos-classic': '经典 Mac — 灰蓝桌面',
  matrix: 'Matrix — 矩阵终端纯绿黑',
  mellifluous: 'Mellifluous — 圆润柔和粉彩',
  molokai: 'Molokai — Monokai 高对比变体',
  solarized: 'Solarized — 科学配色',
  spaceduck: 'Spaceduck — 紫蓝宇宙',
  tokyonight: 'Tokyo Night — 东京霓虹深蓝',
  twilight: 'Twilight — 蓝橙黄昏',
};

function ensureJsonSources() {
  fs.mkdirSync(jsonDir, { recursive: true });
  if (!fs.existsSync(gpuiThemesDir)) {
    console.warn(`gpui themes not found at ${gpuiThemesDir}, using existing json/`);
    return;
  }
  for (const file of fs.readdirSync(gpuiThemesDir).filter((f) => f.endsWith('.json'))) {
    fs.copyFileSync(path.join(gpuiThemesDir, file), path.join(jsonDir, file));
  }
}

function parseSolidColor(value) {
  if (!value || typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (trimmed.startsWith('linear-gradient') || trimmed.includes('gradient(')) {
    const match = trimmed.match(/#[0-9a-fA-F]{3,8}/);
    return match ? normalizeHex(match[0]) : null;
  }
  if (trimmed.startsWith('#')) return normalizeHex(trimmed);
  return null;
}

function normalizeHex(hex) {
  if (hex.length === 4) {
    const r = hex[1];
    const g = hex[2];
    const b = hex[3];
    return `#${r}${r}${g}${g}${b}${b}`.toLowerCase();
  }
  if (hex.length === 9) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const a = parseInt(hex.slice(7, 9), 16) / 255;
    const alpha = Math.round(a * 1000) / 1000;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }
  return hex.slice(0, 7).toLowerCase();
}

function pick(c, ...keys) {
  for (const key of keys) {
    const v = parseSolidColor(c[key]);
    if (v) return v;
  }
  return null;
}

function pickHighlight(h, ...keys) {
  for (const key of keys) {
    const v = parseSolidColor(h?.[key]);
    if (v) return v;
  }
  return null;
}

function mapGpuiToCssVars(colors, highlight, mode) {
  const bg = pick(colors, 'background') ?? (mode === 'dark' ? '#0f1117' : '#ffffff');
  const fg = pick(colors, 'foreground') ?? (mode === 'dark' ? '#e4e4e7' : '#18181b');
  const border = pick(colors, 'border', 'input.border') ?? bg;
  const sidebar =
    pick(colors, 'sidebar.background', 'tab_bar.background', 'title_bar.background', 'muted.background') ?? bg;
  const panel = pick(colors, 'panel.background', 'secondary.background', 'muted.background') ?? bg;
  const elevated = pick(colors, 'secondary.background', 'accent.background', 'muted.background') ?? panel;
  const inputBg = pick(colors, 'tab.active.background', 'popover.background', 'background') ?? bg;
  const hover = pick(colors, 'list.hover.background', 'secondary.hover.background', 'accent.background') ?? elevated;
  const popover = pick(colors, 'popover.background', 'background') ?? elevated;
  const primary = pick(colors, 'primary.background', 'ring', 'base.blue') ?? fg;
  const primaryHover = pick(colors, 'primary.hover.background', 'primary.active.background') ?? primary;
  const accent = pick(colors, 'ring', 'primary.background', 'list.active.border', 'base.blue') ?? primary;
  const accentSubtle =
    pick(colors, 'list.active.background', 'accent.background') ??
    `color-mix(in srgb, ${accent} 18%, ${bg})`;
  const textSecondary = pick(colors, 'secondary.foreground', 'accent.foreground', 'sidebar.foreground') ?? fg;
  const textMuted = pick(colors, 'muted.foreground', 'tab.foreground') ?? textSecondary;
  const success = pick(colors, 'base.green') ?? pickHighlight(highlight, 'success') ?? '#10b981';
  const warning = pick(colors, 'base.yellow') ?? pickHighlight(highlight, 'warning') ?? '#f59e0b';
  const danger = pick(colors, 'base.red', 'danger.background') ?? pickHighlight(highlight, 'error') ?? '#ef4444';
  const userBubble = primary;
  const assistantBubble = pick(colors, 'secondary.background', 'panel.background', 'muted.background') ?? panel;
  const settingsNavActive =
    pick(colors, 'list.active.background', 'accent.background', 'sidebar.accent.background') ?? elevated;
  const textOnAccent = pick(colors, 'primary.foreground') ?? '#ffffff';

  return {
    '--bg-app': bg,
    '--bg-sidebar': sidebar,
    '--bg-panel': panel,
    '--bg-elevated': elevated,
    '--bg-input': inputBg,
    '--bg-hover': hover,
    '--bg-popover': popover,
    '--bg-subtle': panel,
    '--border': border,
    '--text-primary': fg,
    '--text-secondary': textSecondary,
    '--text-muted': textMuted,
    '--text-on-accent': textOnAccent,
    '--accent': accent,
    '--accent-hover': primaryHover,
    '--accent-subtle': accentSubtle,
    '--success': success,
    '--warning': warning,
    '--danger': danger,
    '--user-bubble': userBubble,
    '--assistant-bubble': assistantBubble,
    '--settings-nav-active': settingsNavActive,
  };
}

function cssBlock(themeId, mode, vars, variantName) {
  const lines = Object.entries(vars).map(([k, v]) => `  ${k}: ${v};`);
  return `/* ${variantName} — ${mode} */\nhtml[data-theme='${themeId}'][data-color-mode='${mode}'] {\n${lines.join('\n')}\n}`;
}

function pickLightVariant(themes) {
  return themes.find((t) => t.mode === 'light') ?? null;
}

function pickDarkVariant(themes) {
  const dark = themes.filter((t) => t.mode === 'dark');
  if (dark.length === 0) return null;
  const preferred = dark.find((t) => /mocha/i.test(t.name)) ??
    dark.find((t) => /dark/i.test(t.name)) ??
    dark[0];
  return preferred;
}

function toImportId(id) {
  return id.replace(/-/g, '_');
}

function generateMeta(id, themeSet) {
  const light = pickLightVariant(themeSet.themes);
  const dark = pickDarkVariant(themeSet.themes);
  const sample = (light ?? dark)?.colors ?? {};
  const preview = [
    pick(sample, 'background') ?? '#f4f4f5',
    pick(sample, 'ring', 'primary.background', 'base.blue') ?? '#3b82f6',
    pick(sample, 'panel.background', 'secondary.background', 'muted.background') ?? '#e4e4e7',
  ];
  const name = themeSet.name;
  const description = DESCRIPTIONS[id] ?? `${name} 主题`;
  return `import type { ThemeDefinition } from './types';

const theme: ThemeDefinition = {
  id: '${id}',
  name: ${JSON.stringify(name)},
  description: ${JSON.stringify(description)},
  preview: [${preview.map((p) => JSON.stringify(p)).join(', ')}],
  source: 'gpui-component',
};

export default theme;
`;
}

ensureJsonSources();

const jsonFiles = fs
  .readdirSync(jsonDir)
  .filter((f) => f.endsWith('.json'))
  .sort((a, b) => a.localeCompare(b));

const themeIds = [];

for (const file of jsonFiles) {
  const id = file.replace(/\.json$/, '');
  themeIds.push(id);
  const themeSet = JSON.parse(fs.readFileSync(path.join(jsonDir, file), 'utf8'));
  const light = pickLightVariant(themeSet.themes);
  const dark = pickDarkVariant(themeSet.themes);
  const blocks = [];

  if (light) {
    blocks.push(cssBlock(id, 'light', mapGpuiToCssVars(light.colors, light.highlight, 'light'), light.name));
  } else if (dark) {
    blocks.push(
      cssBlock(id, 'light', mapGpuiToCssVars(dark.colors, dark.highlight, 'light'), `${dark.name} (fallback)`)
    );
  }

  if (dark) {
    blocks.push(cssBlock(id, 'dark', mapGpuiToCssVars(dark.colors, dark.highlight, 'dark'), dark.name));
  } else if (light) {
    blocks.push(
      cssBlock(id, 'dark', mapGpuiToCssVars(light.colors, light.highlight, 'dark'), `${light.name} (fallback)`)
    );
  }

  fs.writeFileSync(path.join(themesDir, `${id}.css`), `${blocks.join('\n\n')}\n`);
  fs.writeFileSync(path.join(themesDir, `${id}.meta.ts`), generateMeta(id, themeSet));
}

// Remove legacy themes not sourced from gpui JSON
const legacy = ['ember', 'nous', 'midnight', 'mono', 'cyberpunk', 'slate'];
for (const id of legacy) {
  for (const ext of ['.css', '.meta.ts']) {
    const p = path.join(themesDir, `${id}${ext}`);
    if (fs.existsSync(p)) fs.unlinkSync(p);
  }
}

const cssImports = ['@import "./base.css";', ...themeIds.map((id) => `@import "./${id}.css";`)].join('\n');
fs.writeFileSync(path.join(themesDir, 'index.css'), `${cssImports}\n`);

const tsImports = themeIds.map((id) => `import ${toImportId(id)} from './${id}.meta';`).join('\n');
const tsList = themeIds.map((id) => `  ${toImportId(id)},`).join('\n');

const indexTs = `${tsImports}

import type { ColorMode, InlinePreviewMode, ThemeDefinition, ToolCallDisplayMode } from './types';

export type { ColorMode, InlinePreviewMode, ThemeDefinition, ToolCallDisplayMode };

export const THEME_IDS = [
${themeIds.map((id) => `  '${id}',`).join('\n')}
] as const;

export type ThemeId = (typeof THEME_IDS)[number];

export const UI_LANGUAGES = [
  { id: 'zh-CN', label: '简体中文' },
  { id: 'en', label: 'English' },
] as const;

export const THEME_LIST: ThemeDefinition[] = [
${tsList}
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
`;

fs.writeFileSync(path.join(themesDir, 'index.ts'), indexTs);

console.log(`Generated ${themeIds.length} themes from gpui JSON:`);
console.log(themeIds.join(', '));
