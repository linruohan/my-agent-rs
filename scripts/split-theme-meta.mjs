import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const tsPath = path.join(root, 'src/utils/themes.ts');
const content = fs.readFileSync(tsPath, 'utf8');
const themesDir = path.join(root, 'src/themes');

const listMatch = content.match(/export const THEME_LIST[\s\S]*?= \[([\s\S]*?)\];/);
if (!listMatch) throw new Error('THEME_LIST not found');

const itemRegex =
  /\{\s*id:\s*'([^']+)',\s*name:\s*'([^']+)',\s*description:\s*'([^']+)',\s*preview:\s*\[([^\]]+)\],\s*\}/g;

let match;
const ids = [];
while ((match = itemRegex.exec(listMatch[1])) !== null) {
  const [, id, name, description, previewRaw] = match;
  const previewMatch = previewRaw.match(/'([^']+)'/g);
  const preview = previewMatch ? previewMatch.map((s) => s.slice(1, -1)) : [];
  const meta = `import type { ThemeDefinition } from './types';

const theme: ThemeDefinition = {
  id: '${id}',
  name: ${JSON.stringify(name)},
  description: ${JSON.stringify(description)},
  preview: [${preview.map((p) => JSON.stringify(p)).join(', ')}],
};

export default theme;
`;
  fs.writeFileSync(path.join(themesDir, `${id}.meta.ts`), meta);
  ids.push(id);
}

console.log(`Meta files: ${ids.length}`);
