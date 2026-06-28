import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const cssPath = path.join(root, 'src/styles/themes.css');
const css = fs.readFileSync(cssPath, 'utf8');
const themesDir = path.join(root, 'src/themes');
fs.mkdirSync(themesDir, { recursive: true });

const firstThemeMatch = css.match(/\/\* Ember/);
const baseEnd = firstThemeMatch ? css.indexOf(firstThemeMatch[0]) : css.length;
const base = css.slice(0, baseEnd).trim();
fs.writeFileSync(path.join(themesDir, 'base.css'), `${base}\n`);

const blockRegex =
  /\/\* ([^\n*]+)\*\/\n(html\[data-theme='([^']+)'\]\[data-color-mode='[^']+'\] \{[\s\S]*?\})/g;
const themeBlocks = new Map();

let match;
while ((match = blockRegex.exec(css)) !== null) {
  const [, comment, block, id] = match;
  if (!themeBlocks.has(id)) themeBlocks.set(id, []);
  themeBlocks.get(id).push(`/* ${comment.trim()} */\n${block}`);
}

for (const [id, blocks] of themeBlocks) {
  fs.writeFileSync(path.join(themesDir, `${id}.css`), `${blocks.join('\n\n')}\n`);
}

console.log(`Themes split: ${themeBlocks.size}`);
console.log([...themeBlocks.keys()].join(', '));
