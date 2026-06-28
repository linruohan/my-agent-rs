import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const replacements = [
  ['#2a2d35', 'var(--border)'],
  ['#1f2128', 'var(--bg-hover)'],
  ['#252830', 'var(--bg-hover)'],
  ['#16181d', 'var(--bg-panel)'],
  ['#1a1c22', 'var(--bg-popover)'],
  ['#0f1117', 'var(--bg-input)'],
  ['#12141a', 'var(--bg-sidebar)'],
  ['#e4e4e7', 'var(--text-primary)'],
  ['#a1a1aa', 'var(--text-secondary)'],
  ['#71717a', 'var(--text-muted)'],
  ['#52525b', 'var(--text-muted)'],
  ['#3b82f6', 'var(--accent)'],
  ['#2563eb', 'var(--user-bubble)'],
  ['#60a5fa', 'var(--accent)'],
  ['#10b981', 'var(--success)'],
  ['#ef4444', 'var(--danger)'],
  ['#dc2626', 'var(--danger-hover)'],
  ['#f59e0b', 'var(--warning)'],
  ['#374151', 'var(--btn-secondary-bg)'],
  ['#1e3a5f', 'var(--accent-subtle)'],
  ['rgba(59, 130, 246, 0.12)', 'var(--accent-muted)'],
  ['rgba(59, 130, 246, 0.1)', 'var(--accent-muted)'],
  ['rgba(16, 185, 129, 0.12)', 'var(--success-muted)'],
  ['rgba(239, 68, 68, 0.12)', 'var(--danger-muted)'],
  ['rgba(113, 113, 122, 0.12)', 'color-mix(in srgb, var(--text-muted) 12%, transparent)'],
  ['rgba(0, 0, 0, 0.85)', 'var(--overlay-bg)'],
  ['rgba(0, 0, 0, 0.4)', 'var(--shadow-color)'],
  ['rgba(0, 0, 0, 0.45)', 'var(--shadow-color)'],
  ['color: white', 'color: var(--text-on-accent)'],
  ['color: #fff', 'color: var(--text-on-accent)'],
  ['background: #fff', 'background: var(--text-on-accent)'],
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
