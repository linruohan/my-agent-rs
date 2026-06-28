import type { TodoItem } from '@/stores/tasks';

function parseDate(iso: string): Date | null {
  if (!iso?.trim()) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function formatDueColumn(iso: string): string {
  const d = parseDate(iso);
  if (!d) return '—';
  const now = new Date();
  if (isSameDay(d, now)) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  return d.toLocaleDateString([], { month: '2-digit', day: '2-digit' });
}

export function formatRemindColumn(iso: string): string {
  if (!iso?.trim()) return '—';
  return formatDueColumn(iso);
}

const STATUS_LABELS: Record<string, string> = {
  pending: '待办',
  done: '已完成',
  planned: '已计划',
  expired: '已过期',
};

export function todoStatusLabel(todo: TodoItem): string {
  if (todo.completed) return '已完成';
  return STATUS_LABELS[todo.status ?? ''] ?? todo.status ?? '待办';
}

export function hasTaskDetails(todo: TodoItem): boolean {
  const desc = todo.description?.trim();
  const atts = todo.attachments?.length ?? 0;
  return Boolean(desc) || atts > 0;
}

export function attachmentSummary(todo: TodoItem): string {
  const parts: string[] = [];
  for (const att of todo.attachments ?? []) {
    const val = (att.value || '').trim();
    if (!val) continue;
    if (att.type === 'url') parts.push(`🔗 ${val}`);
    else {
      const name = val.split(/[/\\]/).pop() || val;
      parts.push(`📎 ${name}`);
    }
  }
  if (todo.description?.trim()) {
    parts.push(`📝 ${todo.description.trim().slice(0, 80)}${todo.description.length > 80 ? '…' : ''}`);
  }
  return parts.join('\n');
}
