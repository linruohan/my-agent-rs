import type { TodoItem } from '@/stores/tasks';

export type TaskFilterId = 'inbox' | 'today' | 'scheduled' | 'pinned' | 'labels' | 'completed';

export const TASK_FILTERS: Array<{
  id: TaskFilterId;
  label: string;
  icon: string;
  hint: string;
}> = [
  { id: 'inbox', label: 'Inbox', icon: '📥', hint: '未关联项目的任务（收件箱）' },
  { id: 'today', label: 'Today', icon: '⭐', hint: '今天到期的未完成任务' },
  { id: 'scheduled', label: 'Scheduled', icon: '📅', hint: '已计划、未到期的未完成任务' },
  { id: 'pinned', label: 'Pinned', icon: '📌', hint: '高优先级或重点标记的未完成任务' },
  { id: 'labels', label: 'Labels', icon: '🏷️', hint: '按标签浏览与管理' },
  { id: 'completed', label: 'Completed', icon: '✅', hint: '所有已完成的任务' },
];

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

export function isScatteredTask(t: TodoItem, inboxProjectId: number | null): boolean {
  if (t.project_id == null) return true;
  if (inboxProjectId != null && t.project_id === inboxProjectId) return true;
  return false;
}

export function isUnsectionedProjectTask(t: TodoItem, projectId: number): boolean {
  return t.project_id === projectId && (t.section_id == null || t.section_id === undefined);
}

export function isPinnedTask(t: TodoItem): boolean {
  const tags = t.tags ?? [];
  return t.priority === 'high' || tags.includes('pinned') || tags.includes('重点');
}

export function isScheduledTask(t: TodoItem, now = new Date()): boolean {
  if (t.completed) return false;
  if (t.status === 'planned') return true;
  const due = parseDate(t.due_date);
  if (!due) return false;
  return due.getTime() > now.getTime();
}

export function isTodayTask(t: TodoItem, now = new Date()): boolean {
  if (t.completed) return false;
  const due = parseDate(t.due_date);
  if (!due) return false;
  return isSameDay(due, now);
}

export function collectAllLabels(todos: TodoItem[]): Map<string, number> {
  const map = new Map<string, number>();
  for (const t of todos) {
    for (const tag of t.tags ?? []) {
      map.set(tag, (map.get(tag) ?? 0) + 1);
    }
  }
  return new Map([...map.entries()].sort((a, b) => a[0].localeCompare(b[0], 'zh-CN')));
}

export function filterByTaskFilter(
  todos: TodoItem[],
  filter: TaskFilterId,
  inboxProjectId: number | null,
  label: string | null = null,
  now = new Date()
): TodoItem[] {
  switch (filter) {
    case 'inbox':
      return todos.filter((t) => !t.completed && isScatteredTask(t, inboxProjectId));
    case 'today':
      return todos.filter((t) => isTodayTask(t, now));
    case 'scheduled':
      return todos.filter((t) => isScheduledTask(t, now));
    case 'pinned':
      return todos.filter((t) => !t.completed && isPinnedTask(t));
    case 'labels':
      if (!label) return [];
      return todos.filter((t) => (t.tags ?? []).includes(label));
    case 'completed':
      return todos.filter((t) => t.completed);
    default:
      return todos;
  }
}

export function countForFilter(
  todos: TodoItem[],
  filter: TaskFilterId,
  inboxProjectId: number | null,
  now = new Date()
): number {
  if (filter === 'labels') return collectAllLabels(todos).size;
  return filterByTaskFilter(todos, filter, inboxProjectId, null, now).length;
}

export function formatDueShort(iso: string): string {
  const d = parseDate(iso);
  if (!d) return 'No date';
  const now = new Date();
  if (isSameDay(d, now)) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return d.toLocaleDateString([], { month: '2-digit', day: '2-digit' });
}
