import { ref } from 'vue';
import { defineStore } from 'pinia';

export type ProjectStats = {
  total: number;
  completed: number;
  by_priority: Record<string, number>;
};

export type ProjectDoc = {
  id: number;
  project_id: number;
  title: string;
  file_path: string;
  note: string;
  rag_ingest?: string;
};

export type ProjectItem = {
  id: number;
  name: string;
  description: string;
  status: string;
  due_date: string;
  stats?: ProjectStats;
  doc_count?: number;
  remind_at?: string;
};

export type TodoItem = {
  id: number;
  title: string;
  due_date: string;
  priority: string;
  completed: boolean;
  project_id: number | null;
  description: string;
  remind_at?: string;
};

export type ReminderItem = {
  job_id: string;
  run_at: string;
  title: string;
  message: string;
  entity_type: string;
  entity_id?: number;
};

function sidecarBase(port: number) {
  return `http://127.0.0.1:${port}`;
}

export const useTasksStore = defineStore('tasks', () => {
  const projects = ref<ProjectItem[]>([]);
  const todos = ref<TodoItem[]>([]);
  const selectedProjectId = ref<number | null>(null);
  const loading = ref(false);
  const error = ref('');
  const projectDocs = ref<ProjectDoc[]>([]);
  const lastDocMessage = ref('');
  const reminders = ref<ReminderItem[]>([]);

  function toIsoDatetime(local: string): string {
    if (!local.trim()) return '';
    const d = new Date(local);
    return Number.isNaN(d.getTime()) ? local : d.toISOString();
  }

  async function fetchProjects(port: number) {
    loading.value = true;
    error.value = '';
    try {
      const res = await fetch(`${sidecarBase(port)}/tasks/projects`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      projects.value = data.projects ?? [];
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e);
      projects.value = [];
    } finally {
      loading.value = false;
    }
  }

  async function fetchTodos(port: number, projectId: number | null = selectedProjectId.value) {
    loading.value = true;
    error.value = '';
    try {
      const params = new URLSearchParams({ include_completed: 'true' });
      if (projectId != null) params.set('project_id', String(projectId));
      const res = await fetch(`${sidecarBase(port)}/tasks/todos?${params}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      todos.value = data.todos ?? [];
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e);
      todos.value = [];
    } finally {
      loading.value = false;
    }
  }

  async function fetchReminders(port: number) {
    try {
      const res = await fetch(`${sidecarBase(port)}/tasks/reminders`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      reminders.value = data.reminders ?? [];
    } catch {
      reminders.value = [];
    }
  }

  async function refresh(port: number) {
    await fetchProjects(port);
    await fetchTodos(port, selectedProjectId.value);
    await fetchReminders(port);
  }

  function selectProject(id: number | null) {
    selectedProjectId.value = id;
  }

  async function toggleTodoComplete(port: number, todo: TodoItem) {
    const res = await fetch(`${sidecarBase(port)}/tasks/todos/${todo.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ completed: !todo.completed }),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh(port);
  }

  async function createTodo(
    port: number,
    payload: {
      title: string;
      project_id?: number;
      priority?: string;
      due_date?: string;
      remind_at?: string;
    }
  ) {
    const body = {
      ...payload,
      due_date: payload.due_date ? toIsoDatetime(payload.due_date) : '',
      remind_at: payload.remind_at ? toIsoDatetime(payload.remind_at) : '',
    };
    const res = await fetch(`${sidecarBase(port)}/tasks/todos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh(port);
  }

  async function createProject(
    port: number,
    name: string,
    description = '',
    dueDate = '',
    remindAt = ''
  ) {
    const res = await fetch(`${sidecarBase(port)}/tasks/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        description,
        status: 'active',
        due_date: toIsoDatetime(dueDate),
        remind_at: toIsoDatetime(remindAt),
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh(port);
  }

  async function fetchProjectDetail(port: number, projectId: number) {
    const res = await fetch(`${sidecarBase(port)}/tasks/projects/${projectId}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    projectDocs.value = data.docs ?? [];
    return data;
  }

  async function updateProjectStatus(port: number, projectId: number, status: string) {
    const res = await fetch(`${sidecarBase(port)}/tasks/projects/${projectId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh(port);
  }

  async function addProjectDoc(
    port: number,
    projectId: number,
    payload: { title: string; file_path?: string; note?: string }
  ) {
    const res = await fetch(`${sidecarBase(port)}/tasks/projects/${projectId}/docs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, auto_ingest: true }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    lastDocMessage.value = data.doc?.rag_ingest ?? '文档已添加';
    await fetchProjectDetail(port, projectId);
    await refresh(port);
  }

  async function deleteTodo(port: number, todoId: number) {
    const res = await fetch(`${sidecarBase(port)}/tasks/todos/${todoId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    await refresh(port);
  }

  async function setTodoReminder(port: number, todoId: number, remindAt: string) {
    const res = await fetch(`${sidecarBase(port)}/tasks/todos/${todoId}/reminder`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ remind_at: toIsoDatetime(remindAt) }),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh(port);
  }

  async function setProjectReminder(port: number, projectId: number, remindAt: string) {
    const res = await fetch(`${sidecarBase(port)}/tasks/projects/${projectId}/reminder`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ remind_at: toIsoDatetime(remindAt) }),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh(port);
  }

  return {
    projects,
    todos,
    projectDocs,
    lastDocMessage,
    reminders,
    selectedProjectId,
    loading,
    error,
    fetchProjects,
    fetchTodos,
    refresh,
    selectProject,
    toggleTodoComplete,
    createTodo,
    createProject,
    fetchProjectDetail,
    updateProjectStatus,
    addProjectDoc,
    deleteTodo,
    setTodoReminder,
    setProjectReminder,
    fetchReminders,
  };
});
