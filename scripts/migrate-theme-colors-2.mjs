import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const replacements = [
  ['#0f1115', 'var(--bg-code)'],
  ['#fbbf24', 'var(--text-highlight)'],
  ['#fcd34d', 'var(--text-highlight)'],
  ['#93c5fd', 'var(--text-link)'],
  ['#cbd5e1', 'var(--text-secondary)'],
  ['#f87171', 'var(--text-danger-soft)'],
  ['#fca5a5', 'var(--text-danger-soft)'],
  ['#064e3b', 'var(--bg-success-subtle)'],
  ['#6ee7b7', 'var(--text-success-soft)'],
  ['#4b5563', 'var(--btn-secondary-bg)'],
  ['#3f3f46', 'var(--text-muted)'],
  ['#2a1515', 'var(--bg-danger-subtle)'],
];

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full);
    else if (entry.name.endsWith('.vue')) processFile(full);
  }
}

function processFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  let changed = false;
  for (const [from, to] of replacements) {
    if (content.includes(from)) {
      content = content.split(from).join(to);
      changed = true;
    }
  }
  if (changed) {
    fs.writeFileSync(filePath, content);
    console.log('Updated:', path.relative(root, filePath));
  }
}

walk(path.join(root, 'src/components'));
walk(path.join(root, 'src/views'));
