import type { TodoItem } from '@/stores/tasks';

export type DeleteTargetKind = 'task' | 'project' | 'section';

export type DeleteConfirmAnalysis = {
  incomplete: TodoItem[];
  completed: TodoItem[];
  total: number;
};

export function tasksForProject(allTodos: TodoItem[], projectId: number): TodoItem[] {
  return allTodos.filter((t) => t.project_id === projectId);
}

export function tasksForSection(allTodos: TodoItem[], sectionId: number): TodoItem[] {
  return allTodos.filter((t) => t.section_id === sectionId);
}

export function analyzeTasksForDelete(tasks: TodoItem[]): DeleteConfirmAnalysis {
  const incomplete = tasks.filter((t) => !t.completed);
  const completed = tasks.filter((t) => t.completed);
  return { incomplete, completed, total: tasks.length };
}

export function priorityLabel(priority: string): string {
  const map: Record<string, string> = {
    low: '低',
    normal: '普通',
    high: '高',
  };
  return map[priority] ?? priority;
}

export function deleteHintFor(kind: DeleteTargetKind): string {
  if (kind === 'project') return '删除后，项目内任务将移入 Inbox。';
  if (kind === 'section') return '删除后，Section 内任务将变为无 Section。';
  return '删除后任务不可恢复。';
}
