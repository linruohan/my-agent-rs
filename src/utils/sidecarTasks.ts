import type {
  LabelItem,
  ProjectDoc,
  ProjectItem,
  SectionItem,
  SectionSummary,
  TaskReminderRow,
  TasksSnapshot,
  TodoItem,
} from '@/types/tasks';
import {
  fetchSidecarAuthToken,
  parseResponseError,
  sidecarAuthHeaders,
  sidecarBaseUrl,
} from '@/utils/sidecarFetch';

export type {
  LabelItem,
  ProjectDoc,
  ProjectItem,
  SectionItem,
  SectionSummary,
  TaskReminderRow,
  TasksSnapshot,
  TodoItem,
} from '@/types/tasks';

async function tasksJson<T>(
  port: number,
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const token = await fetchSidecarAuthToken(port);
  const headers = new Headers(sidecarAuthHeaders(token, { json: init.body != null }));
  if (init.headers) {
    new Headers(init.headers).forEach((value, key) => headers.set(key, value));
  }
  const resp = await fetch(`${sidecarBaseUrl(port)}/tasks${path}`, { ...init, headers });
  if (!resp.ok) {
    throw new Error(await parseResponseError(resp));
  }
  if (resp.status === 204) {
    return undefined as T;
  }
  return (await resp.json()) as T;
}

export async function fetchTasksSnapshot(
  port: number,
  includeCompleted = true
): Promise<TasksSnapshot> {
  const query = includeCompleted ? '?include_completed=true' : '';
  return tasksJson<TasksSnapshot>(port, `/snapshot${query}`);
}

/** Entity-aware reminders (todo/project/task + scheduler jobs). */
export async function fetchTaskRemindersRest(port: number): Promise<TaskReminderRow[]> {
  try {
    const data = await tasksJson<{ reminders?: TaskReminderRow[] }>(port, '/reminders');
    return data.reminders ?? [];
  } catch {
    return [];
  }
}

export async function fetchProjectSectionsRest(
  port: number,
  projectId: number
): Promise<SectionItem[]> {
  const data = await tasksJson<{ sections?: SectionItem[] }>(
    port,
    `/projects/${projectId}/sections`
  );
  return data.sections ?? [];
}

export async function fetchProjectDetailRest(
  port: number,
  projectId: number
): Promise<{ docs?: ProjectDoc[]; sections?: SectionItem[] } & Record<string, unknown>> {
  return tasksJson(port, `/projects/${projectId}`);
}

export async function fetchSectionDetailRest(
  port: number,
  sectionId: number
): Promise<{ summaries?: SectionSummary[] } & Record<string, unknown>> {
  return tasksJson(port, `/sections/${sectionId}`);
}

export async function patchTodoRest(
  port: number,
  todoId: number,
  body: Record<string, unknown>
): Promise<{ todo?: TodoItem }> {
  return tasksJson(port, `/todos/${todoId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function createTodoRest(
  port: number,
  body: Record<string, unknown>
): Promise<{ todo?: TodoItem }> {
  return tasksJson(port, '/todos', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function deleteTodoRest(port: number, todoId: number): Promise<void> {
  await tasksJson(port, `/todos/${todoId}`, { method: 'DELETE' });
}

export async function createProjectRest(
  port: number,
  body: Record<string, unknown>
): Promise<{ project?: ProjectItem }> {
  return tasksJson(port, '/projects', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function patchProjectRest(
  port: number,
  projectId: number,
  body: Record<string, unknown>
): Promise<{ project?: ProjectItem }> {
  return tasksJson(port, `/projects/${projectId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteProjectRest(port: number, projectId: number): Promise<void> {
  await tasksJson(port, `/projects/${projectId}`, { method: 'DELETE' });
}

export async function createSectionRest(
  port: number,
  projectId: number,
  body: Record<string, unknown>
): Promise<{ section?: SectionItem }> {
  return tasksJson(port, `/projects/${projectId}/sections`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function patchSectionRest(
  port: number,
  sectionId: number,
  body: Record<string, unknown>
): Promise<{ section?: SectionItem }> {
  return tasksJson(port, `/sections/${sectionId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteSectionRest(port: number, sectionId: number): Promise<void> {
  await tasksJson(port, `/sections/${sectionId}`, { method: 'DELETE' });
}

export async function saveSectionSummaryRest(
  port: number,
  sectionId: number,
  body: Record<string, unknown>
): Promise<void> {
  await tasksJson(port, `/sections/${sectionId}/summaries`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function addProjectDocRest(
  port: number,
  projectId: number,
  body: Record<string, unknown>
): Promise<{ doc?: ProjectDoc & { rag_ingest?: string } }> {
  return tasksJson(port, `/projects/${projectId}/docs`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function setProjectReminderRest(
  port: number,
  projectId: number,
  remindAt: string
): Promise<void> {
  await tasksJson(port, `/projects/${projectId}/reminder`, {
    method: 'PUT',
    body: JSON.stringify({ remind_at: remindAt }),
  });
}

export async function createLabelRest(
  port: number,
  body: { name: string; color: string }
): Promise<{ label: LabelItem }> {
  return tasksJson(port, '/labels', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function patchLabelRest(
  port: number,
  labelId: number,
  body: Record<string, unknown>
): Promise<{ label: LabelItem }> {
  return tasksJson(port, `/labels/${labelId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteLabelRest(port: number, labelId: number): Promise<void> {
  await tasksJson(port, `/labels/${labelId}`, { method: 'DELETE' });
}
