import { ref } from 'vue';
import { defineStore } from 'pinia';

export type ProjectStats = {
  total: number;
  completed: number;
  by_priority: Record<string, number>;
  by_status?: Record<string, number>;
};

export type SectionItem = {
  id: number;
  project_id: number;
  name: string;
  start_at: string;
  end_at: string;
  owner: string;
  goals: string;
  status: string;
  stats?: ProjectStats;
};

export type SectionSummary = {
  id: number;
  section_id: number;
  summary_date: string;
  progress: string;
  risks: string;
  challenges: string;
  notes: string;
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
  start_at?: string;
  end_at?: string;
  due_date: string;
  owner?: string;
  is_inbox?: boolean;
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
  section_id?: number | null;
  description: string;
  remind_at?: string;
  owner?: string;
  status?: string;
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
  const sections = ref<SectionItem[]>([]);
  const todos = ref<TodoItem[]>([]);
  const inbox = ref<ProjectItem | null>(null);
  const selectedProjectId = ref<number | null>(null);
  const selectedSectionId = ref<number | null>(null);
  const loading = ref(false);
  const error = ref('');
  const projectDocs = ref<ProjectDoc[]>([]);
  const sectionSummaries = ref<SectionSummary[]>([]);
  const lastDocMessage = ref('');
  const reminders = ref<ReminderItem[]>([]);

  function toIsoDatetime(local: string): string {
    if (!local.trim()) return '';
    const d = new Date(local);
    return Number.isNaN(d.getTime()) ? local : d.toISOString();
  }

  async function refresh(port: number) {
    loading.value = true;
    error.value = '';
    try {
      const params = new URLSearchParams({ include_completed: 'true' });
      if (selectedProjectId.value != null) {
        params.set('project_id', String(selectedProjectId.value));
      }
      if (selectedSectionId.value != null) {
        params.set('section_id', String(selectedSectionId.value));
      }
      const res = await fetch(`${sidecarBase(port)}/tasks/snapshot?${params}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      inbox.value = data.inbox ?? null;
      projects.value = data.projects ?? [];
      sections.value = data.sections ?? [];
      todos.value = data.todos ?? [];
      reminders.value = data.reminders ?? [];
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e);
      projects.value = [];
      sections.value = [];
      todos.value = [];
    } finally {
      loading.value = false;
    }
  }

  function selectProject(id: number | null) {
    selectedProjectId.value = id;
    selectedSectionId.value = null;
    sectionSummaries.value = [];
  }

  function selectSection(id: number | null) {
    selectedSectionId.value = id;
  }

  async function loadSections(port: number, projectId: number) {
    const res = await fetch(`${sidecarBase(port)}/tasks/projects/${projectId}/sections`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    sections.value = data.sections ?? [];
  }

  async function fetchProjectDetail(port: number, projectId: number) {
    const res = await fetch(`${sidecarBase(port)}/tasks/projects/${projectId}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    projectDocs.value = data.docs ?? [];
    sections.value = data.sections ?? [];
    return data;
  }

  async function fetchSectionDetail(port: number, sectionId: number) {
    const res = await fetch(`${sidecarBase(port)}/tasks/sections/${sectionId}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    sectionSummaries.value = data.summaries ?? [];
    return data;
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
      section_id?: number;
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
    startAt = '',
    endAt = '',
    owner = ''
  ) {
    const res = await fetch(`${sidecarBase(port)}/tasks/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        description,
        status: 'active',
        start_at: toIsoDatetime(startAt),
        end_at: toIsoDatetime(endAt),
        owner,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh(port);
  }

  async function createSection(
    port: number,
    projectId: number,
    payload: { name: string; start_at?: string; end_at?: string; owner?: string; goals?: string }
  ) {
    const res = await fetch(`${sidecarBase(port)}/tasks/projects/${projectId}/sections`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...payload,
        start_at: payload.start_at ? toIsoDatetime(payload.start_at) : '',
        end_at: payload.end_at ? toIsoDatetime(payload.end_at) : '',
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    await loadSections(port, projectId);
    await refresh(port);
  }

  async function saveSectionSummary(
    port: number,
    sectionId: number,
    payload: {
      summary_date: string;
      progress?: string;
      risks?: string;
      challenges?: string;
      notes?: string;
    }
  ) {
    const res = await fetch(`${sidecarBase(port)}/tasks/sections/${sectionId}/summaries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    await fetchSectionDetail(port, sectionId);
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

  async function fetchTodos(port: number, projectId: number | null) {
    selectedProjectId.value = projectId;
    selectedSectionId.value = null;
    await refresh(port);
  }

  async function setProjectReminder(port: number, projectId: number, remindAt: string) {
    const res = await fetch(`${sidecarBase(port)}/tasks/projects/${projectId}/reminder`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ remind_at: remindAt ? toIsoDatetime(remindAt) : '' }),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh(port);
  }

  async function deleteTodo(port: number, todoId: number) {
    const res = await fetch(`${sidecarBase(port)}/tasks/todos/${todoId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    await refresh(port);
  }

  return {
    projects,
    sections,
    todos,
    inbox,
    projectDocs,
    sectionSummaries,
    lastDocMessage,
    reminders,
    selectedProjectId,
    selectedSectionId,
    loading,
    error,
    refresh,
    selectProject,
    selectSection,
    loadSections,
    fetchProjectDetail,
    fetchSectionDetail,
    fetchTodos,
    toggleTodoComplete,
    createTodo,
    createProject,
    createSection,
    saveSectionSummary,
    updateProjectStatus,
    setProjectReminder,
    addProjectDoc,
    deleteTodo,
  };
});
