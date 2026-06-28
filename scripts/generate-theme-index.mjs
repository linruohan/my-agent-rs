import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const themesDir = path.join(root, 'src/themes');

const themeIds = fs
  .readdirSync(themesDir)
  .filter((f) => f.endsWith('.css') && f !== 'base.css' && f !== 'index.css')
  .map((f) => f.replace('.css', ''))
  .sort((a, b) => {
    const order = fs.readFileSync(path.join(root, 'src/utils/themes.ts'), 'utf8');
    return order.indexOf(`id: '${a}'`) - order.indexOf(`id: '${b}'`);
  });

const cssImports = ['@import "./base.css";', ...themeIds.map((id) => `@import "./${id}.css";`)].join(
  '\n'
);
fs.writeFileSync(path.join(themesDir, 'index.css'), `${cssImports}\n`);

const tsImports = themeIds
  .map((id) => `import ${id.replace(/-/g, '_')} from './${id}.meta';`)
  .join('\n');
const tsList = themeIds.map((id) => `  ${id.replace(/-/g, '_')},`).join('\n');

const indexTs = `${tsImports}

import type { ColorMode, InlinePreviewMode, ThemeDefinition, ToolCallDisplayMode } from './types';

export type { ColorMode, InlinePreviewMode, ThemeDefinition, ToolCallDisplayMode };

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
`;

fs.writeFileSync(path.join(themesDir, 'index.ts'), indexTs);
console.log(`Generated index for ${themeIds.length} themes`);
