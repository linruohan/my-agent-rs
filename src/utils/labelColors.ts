import type { LabelItem } from '@/stores/tasks';

export const LABEL_COLORS = [
  '#fca5a5', '#fdba74', '#fde047', '#bef264', '#86efac', '#5eead4',
  '#67e8f9', '#93c5fd', '#a5b4fc', '#c4b5fd', '#f0abfc', '#fda4af',
  '#e5e7eb', '#d1d5db', '#9ca3af', '#78716c',
];

export const DEFAULT_LABEL_COLOR = '#93c5fd';

export function labelColorMap(labels: LabelItem[]): Map<string, string> {
  const map = new Map<string, string>();
  for (const l of labels) {
    map.set(l.name, l.color || DEFAULT_LABEL_COLOR);
  }
  return map;
}

export function colorForLabel(name: string, colorMap: Map<string, string>): string {
  return colorMap.get(name) ?? DEFAULT_LABEL_COLOR;
}

export function labelChipStyle(color: string): Record<string, string> {
  return {
    backgroundColor: color,
    color: contrastText(color),
  };
}

function contrastText(hex: string): string {
  const h = hex.replace('#', '');
  if (h.length !== 6) return '#1f2937';
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum > 0.62 ? '#1f2937' : '#f9fafb';
}
