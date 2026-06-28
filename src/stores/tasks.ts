import { ref } from 'vue';
import { defineStore } from 'pinia';
import { localDatetimeToIso } from '@/utils/dateTime';
import { useSettingsStore } from '@/stores/settings';

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
  tags?: string[];
  attachments?: Array<{ type: string; value: string }>;
};

export type LabelItem = {
  id: number;
  name: string;
  color: string;
  created_at?: string;
  updated_at?: string;
};

export type TaskViewMode = 'filter' | 'project';

export type TaskFilterId = import('@/utils/taskFilters').TaskFilterId;

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
  const allTodos = ref<TodoItem[]>([]);
  const labels = ref<LabelItem[]>([]);
  const viewMode = ref<TaskViewMode>('filter');
  const activeFilter = ref<TaskFilterId>('inbox');
  const activeLabel = ref<string | null>(null);
  const revision = ref(0);

  function bumpRevision() {
    revision.value += 1;
  }

  function mergeTodo(todo: TodoItem) {
    const idx = allTodos.value.findIndex((t) => t.id === todo.id);
    if (idx >= 0) {
      const next = [...allTodos.value];
      next[idx] = { ...next[idx], ...todo };
      allTodos.value = next;
    } else {
      allTodos.value = [todo, ...allTodos.value];
    }
    todos.value = allTodos.value;
    bumpRevision();
  }

  function mergeProject(project: ProjectItem) {
    if (project.is_inbox) {
      inbox.value = project;
      return;
    }
    const idx = projects.value.findIndex((p) => p.id === project.id);
    if (idx >= 0) {
      const next = [...projects.value];
      next[idx] = { ...next[idx], ...project };
      projects.value = next;
    } else {
      projects.value = [project, ...projects.value];
    }
    bumpRevision();
  }

  function removeTodoLocal(todoId: number) {
    allTodos.value = allTodos.value.filter((t) => t.id !== todoId);
    todos.value = allTodos.value;
    bumpRevision();
  }

  async function refresh(port: number) {
    loading.value = true;
    error.value = '';
    try {
      const res = await fetch(`${sidecarBase(port)}/tasks/snapshot?include_completed=true`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      inbox.value = data.inbox ?? null;
      projects.value = (data.projects ?? []).filter((p: ProjectItem) => !p.is_inbox);
      allTodos.value = data.todos ?? [];
      todos.value = allTodos.value;
      labels.value = data.labels ?? [];
      reminders.value = data.reminders ?? [];
      bumpRevision();

      if (viewMode.value === 'project' && selectedProjectId.value != null) {
        const detail = await fetch(`${sidecarBase(port)}/tasks/projects/${selectedProjectId.value}`);
        if (detail.ok) {
          const pj = await detail.json();
          sections.value = pj.sections ?? [];
          projectDocs.value = pj.docs ?? [];
        }
      } else if (viewMode.value === 'project' && selectedProjectId.value == null) {
        sections.value = [];
      } else {
        sections.value = [];
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e);
    } finally {
      loading.value = false;
    }
  }

  async function refreshIfRunning(port?: number) {
    const settings = useSettingsStore();
    const p = port ?? settings.sidecarPort;
    if (settings.sidecarStatus !== 'running') return;
    await refresh(p);
  }

  function selectFilter(filter: TaskFilterId) {
    viewMode.value = 'filter';
    activeFilter.value = filter;
    activeLabel.value = null;
    selectedProjectId.value = null;
    selectedSectionId.value = null;
    sectionSummaries.value = [];
    projectDocs.value = [];
    sections.value = [];
  }

  function selectLabel(label: string) {
    viewMode.value = 'filter';
    activeFilter.value = 'labels';
    activeLabel.value = label;
    selectedProjectId.value = null;
    selectedSectionId.value = null;
  }

  async function selectProjectView(port: number, id: number) {
    viewMode.value = 'project';
    selectedProjectId.value = id;
    selectedSectionId.value = null;
    sectionSummaries.value = [];
    lastDocMessage.value = '';
    try {
      await fetchProjectDetail(port, id);
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e);
    }
  }

  function selectProject(id: number | null) {
    selectedProjectId.value = id;
    selectedSectionId.value = null;
    sectionSummaries.value = [];
  }

  function toIsoDatetime(local: string): string {
    return localDatetimeToIso(local);
  }

  function toIsoDate(isoOrLocal: string): string {
    if (!isoOrLocal.trim()) return '';
    const d = new Date(isoOrLocal);
    return Number.isNaN(d.getTime()) ? isoOrLocal : d.toISOString();
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
    const data = await res.json();
    if (data.todo) mergeTodo(data.todo as TodoItem);
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
      description?: string;
      tags?: string[];
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
    const data = await res.json();
    if (data.todo) mergeTodo(data.todo as TodoItem);
    await refresh(port);
    return data.todo as TodoItem | undefined;
  }

  async function updateTodo(
    port: number,
    todoId: number,
    payload: {
      title?: string;
      description?: string;
      due_date?: string;
      remind_at?: string;
      priority?: string;
      completed?: boolean;
      project_id?: number | null;
      section_id?: number | null;
      tags?: string[];
      clear_reminder?: boolean;
    }
  ) {
    const body: Record<string, unknown> = { ...payload };
    if (payload.due_date !== undefined) {
      body.due_date = payload.due_date ? toIsoDatetime(payload.due_date) : '';
    }
    if (payload.remind_at !== undefined) {
      body.remind_at = payload.remind_at ? toIsoDatetime(payload.remind_at) : '';
    }
    const res = await fetch(`${sidecarBase(port)}/tasks/todos/${todoId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    if (data.todo) mergeTodo(data.todo as TodoItem);
    await refresh(port);
  }

  async function createProject(
    port: number,
    payload: {
      name: string;
      description?: string;
      status?: string;
      start_at?: string;
      end_at?: string;
      owner?: string;
      remind_at?: string;
    }
  ) {
    const res = await fetch(`${sidecarBase(port)}/tasks/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: payload.name,
        description: payload.description ?? '',
        status: payload.status ?? 'active',
        start_at: payload.start_at ? toIsoDate(payload.start_at) : '',
        end_at: payload.end_at ? toIsoDate(payload.end_at) : '',
        due_date: payload.end_at ? toIsoDate(payload.end_at) : '',
        owner: payload.owner ?? '',
        remind_at: payload.remind_at ? toIsoDatetime(payload.remind_at) : '',
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    if (data.project) {
      mergeProject(data.project as ProjectItem);
    }
    await refresh(port);
    return data.project as ProjectItem | undefined;
  }

  /** @deprecated 使用 createProject(port, { name, ... }) */
  async function createProjectLegacy(
    port: number,
    name: string,
    description = '',
    startAt = '',
    endAt = '',
    owner = ''
  ) {
    await createProject(port, { name, description, start_at: startAt, end_at: endAt, owner });
  }

  async function updateProject(
    port: number,
    projectId: number,
    payload: {
      name?: string;
      description?: string;
      status?: string;
      start_at?: string;
      end_at?: string;
      owner?: string;
      remind_at?: string;
    }
  ) {
    const body: Record<string, unknown> = {};
    if (payload.name !== undefined) body.name = payload.name;
    if (payload.description !== undefined) body.description = payload.description;
    if (payload.status !== undefined) body.status = payload.status;
    if (payload.start_at !== undefined) {
      body.start_at = payload.start_at ? toIsoDate(payload.start_at) : '';
    }
    if (payload.end_at !== undefined) {
      body.end_at = payload.end_at ? toIsoDate(payload.end_at) : '';
      body.due_date = payload.end_at ? toIsoDate(payload.end_at) : '';
    }
    if (payload.owner !== undefined) body.owner = payload.owner;
    if (payload.remind_at !== undefined) {
      body.remind_at = payload.remind_at ? toIsoDatetime(payload.remind_at) : '';
    }
    const res = await fetch(`${sidecarBase(port)}/tasks/projects/${projectId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh(port);
    if (selectedProjectId.value === projectId) {
      await fetchProjectDetail(port, projectId);
    }
  }

  async function updateSection(
    port: number,
    sectionId: number,
    payload: {
      name?: string;
      goals?: string;
      status?: string;
      start_at?: string;
      end_at?: string;
      owner?: string;
    }
  ) {
    const body: Record<string, unknown> = { ...payload };
    if (payload.start_at !== undefined) {
      body.start_at = payload.start_at ? toIsoDate(payload.start_at) : '';
    }
    if (payload.end_at !== undefined) {
      body.end_at = payload.end_at ? toIsoDate(payload.end_at) : '';
    }
    const res = await fetch(`${sidecarBase(port)}/tasks/sections/${sectionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(await res.text());
    const pid = selectedProjectId.value;
    if (pid != null) await loadSections(port, pid);
    await refresh(port);
  }

  async function createSection(
    port: number,
    projectId: number,
    payload: {
      name: string;
      start_at?: string;
      end_at?: string;
      owner?: string;
      goals?: string;
      status?: string;
    }
  ) {
    const res = await fetch(`${sidecarBase(port)}/tasks/projects/${projectId}/sections`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: payload.name,
        goals: payload.goals ?? '',
        owner: payload.owner ?? '',
        status: payload.status ?? 'active',
        start_at: payload.start_at ? toIsoDate(payload.start_at) : '',
        end_at: payload.end_at ? toIsoDate(payload.end_at) : '',
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
    removeTodoLocal(todoId);
    await refresh(port);
  }

  async function createLabel(port: number, payload: { name: string; color: string }) {
    const res = await fetch(`${sidecarBase(port)}/tasks/labels`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh(port);
    return (await res.json()).label as LabelItem;
  }

  async function updateLabel(
    port: number,
    labelId: number,
    payload: { name?: string; color?: string }
  ) {
    const res = await fetch(`${sidecarBase(port)}/tasks/labels/${labelId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh(port);
    return (await res.json()).label as LabelItem;
  }

  async function deleteLabel(port: number, labelId: number) {
    const res = await fetch(`${sidecarBase(port)}/tasks/labels/${labelId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    if (activeLabel.value) {
      const deleted = labels.value.find((l) => l.id === labelId);
      if (deleted && activeLabel.value === deleted.name) {
        activeLabel.value = null;
      }
    }
    await refresh(port);
  }

  return {
    projects,
    sections,
    todos,
    allTodos,
    labels,
    inbox,
    projectDocs,
    sectionSummaries,
    lastDocMessage,
    reminders,
    selectedProjectId,
    selectedSectionId,
    viewMode,
    activeFilter,
    activeLabel,
    revision,
    loading,
    error,
    refresh,
    refreshIfRunning,
    mergeTodo,
    mergeProject,
    selectFilter,
    selectLabel,
    selectProjectView,
    selectProject,
    selectSection,
    loadSections,
    fetchProjectDetail,
    fetchSectionDetail,
    fetchTodos,
    toggleTodoComplete,
    createTodo,
    updateTodo,
    createProject,
    createProjectLegacy,
    updateProject,
    updateSection,
    createSection,
    saveSectionSummary,
    updateProjectStatus,
    setProjectReminder,
    addProjectDoc,
    deleteTodo,
    createLabel,
    updateLabel,
    deleteLabel,
  };
});
