import { ref } from 'vue';
import { defineStore } from 'pinia';
import { localDatetimeToIso } from '@/utils/dateTime';
import { useSettingsStore } from '@/stores/settings';
import type {
  LabelItem,
  ProjectDoc,
  ProjectItem,
  SectionItem,
  SectionSummary,
  TaskReminderRow,
  TodoItem,
} from '@/types/tasks';
import {
  addProjectDocRest,
  createLabelRest,
  createProjectRest,
  createSectionRest,
  createTodoRest,
  deleteLabelRest,
  deleteProjectRest,
  deleteSectionRest,
  deleteTodoRest,
  fetchProjectDetailRest,
  fetchProjectSectionsRest,
  fetchSectionDetailRest,
  fetchTaskRemindersRest,
  fetchTasksSnapshot,
  patchLabelRest,
  patchProjectRest,
  patchSectionRest,
  patchTodoRest,
  saveSectionSummaryRest,
  setProjectReminderRest,
} from '@/utils/sidecarTasks';

export type {
  LabelItem,
  ProjectDoc,
  ProjectItem,
  ProjectStats,
  SectionItem,
  SectionSummary,
  TodoItem,
} from '@/types/tasks';

export type TaskViewMode = 'filter' | 'project';

export type TaskFilterId = import('@/utils/taskFilters').TaskFilterId;

export type ReminderItem = TaskReminderRow;

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

  function removeProjectLocal(projectId: number) {
    projects.value = projects.value.filter((p) => p.id !== projectId);
    if (selectedProjectId.value === projectId) {
      selectedProjectId.value = null;
      selectedSectionId.value = null;
      sections.value = [];
      projectDocs.value = [];
      sectionSummaries.value = [];
      viewMode.value = 'filter';
    }
    bumpRevision();
  }

  function removeSectionLocal(sectionId: number) {
    sections.value = sections.value.filter((s) => s.id !== sectionId);
    if (selectedSectionId.value === sectionId) {
      selectedSectionId.value = null;
      sectionSummaries.value = [];
    }
    allTodos.value = allTodos.value.map((t) =>
      t.section_id === sectionId ? { ...t, section_id: null } : t
    );
    todos.value = allTodos.value;
    bumpRevision();
  }

  async function refresh(port: number) {
    loading.value = true;
    error.value = '';
    try {
      const data = await fetchTasksSnapshot(port);
      inbox.value = data.inbox ?? null;
      projects.value = (data.projects ?? []).filter((p: ProjectItem) => !p.is_inbox);
      allTodos.value = data.todos ?? [];
      todos.value = allTodos.value;
      labels.value = data.labels ?? [];
      reminders.value = data.reminders ?? [];
      bumpRevision();

      if (viewMode.value === 'project' && selectedProjectId.value != null) {
        const pj = await fetchProjectDetailRest(port, selectedProjectId.value);
        sections.value = pj.sections ?? [];
        projectDocs.value = pj.docs ?? [];
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

  /** Lightweight refresh for Todos「即将提醒」banner (uses `/tasks/reminders`, includes scheduler jobs). */
  async function refreshReminders(port?: number) {
    const settings = useSettingsStore();
    const p = port ?? settings.sidecarPort;
    if (settings.sidecarStatus !== 'running' || !p) return;
    reminders.value = await fetchTaskRemindersRest(p);
    bumpRevision();
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
    sections.value = await fetchProjectSectionsRest(port, projectId);
  }

  async function fetchProjectDetail(port: number, projectId: number) {
    const data = await fetchProjectDetailRest(port, projectId);
    projectDocs.value = data.docs ?? [];
    sections.value = data.sections ?? [];
    return data;
  }

  async function fetchSectionDetail(port: number, sectionId: number) {
    const data = await fetchSectionDetailRest(port, sectionId);
    sectionSummaries.value = data.summaries ?? [];
    return data;
  }

  async function toggleTodoComplete(port: number, todo: TodoItem) {
    const data = await patchTodoRest(port, todo.id, { completed: !todo.completed });
    if (data.todo) mergeTodo(data.todo);
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
    const data = await createTodoRest(port, body);
    if (data.todo) mergeTodo(data.todo);
    await refresh(port);
    return data.todo;
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
    const data = await patchTodoRest(port, todoId, body);
    if (data.todo) mergeTodo(data.todo);
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
    const data = await createProjectRest(port, {
      name: payload.name,
      description: payload.description ?? '',
      status: payload.status ?? 'active',
      start_at: payload.start_at ? toIsoDate(payload.start_at) : '',
      end_at: payload.end_at ? toIsoDate(payload.end_at) : '',
      due_date: payload.end_at ? toIsoDate(payload.end_at) : '',
      owner: payload.owner ?? '',
      remind_at: payload.remind_at ? toIsoDatetime(payload.remind_at) : '',
    });
    if (data.project) {
      mergeProject(data.project);
    }
    await refresh(port);
    return data.project;
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
    await patchProjectRest(port, projectId, body);
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
    await patchSectionRest(port, sectionId, body);
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
    await createSectionRest(port, projectId, {
      name: payload.name,
      goals: payload.goals ?? '',
      owner: payload.owner ?? '',
      status: payload.status ?? 'active',
      start_at: payload.start_at ? toIsoDate(payload.start_at) : '',
      end_at: payload.end_at ? toIsoDate(payload.end_at) : '',
    });
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
    await saveSectionSummaryRest(port, sectionId, payload);
    await fetchSectionDetail(port, sectionId);
  }

  async function updateProjectStatus(port: number, projectId: number, status: string) {
    await patchProjectRest(port, projectId, { status });
    await refresh(port);
  }

  async function addProjectDoc(
    port: number,
    projectId: number,
    payload: { title: string; file_path?: string; note?: string }
  ) {
    const data = await addProjectDocRest(port, projectId, { ...payload, auto_ingest: true });
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
    await setProjectReminderRest(
      port,
      projectId,
      remindAt ? toIsoDatetime(remindAt) : ''
    );
    await refresh(port);
  }

  async function deleteTodo(port: number, todoId: number) {
    await deleteTodoRest(port, todoId);
    removeTodoLocal(todoId);
    await refresh(port);
  }

  async function deleteProject(port: number, projectId: number) {
    await deleteProjectRest(port, projectId);
    removeProjectLocal(projectId);
    await refresh(port);
  }

  async function deleteSection(port: number, sectionId: number) {
    await deleteSectionRest(port, sectionId);
    removeSectionLocal(sectionId);
    const pid = selectedProjectId.value;
    if (pid != null) await loadSections(port, pid);
    await refresh(port);
  }

  async function createLabel(port: number, payload: { name: string; color: string }) {
    const data = await createLabelRest(port, payload);
    await refresh(port);
    return data.label;
  }

  async function updateLabel(
    port: number,
    labelId: number,
    payload: { name?: string; color?: string }
  ) {
    const data = await patchLabelRest(port, labelId, payload);
    await refresh(port);
    return data.label;
  }

  async function deleteLabel(port: number, labelId: number) {
    await deleteLabelRest(port, labelId);
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
    refreshReminders,
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
    deleteProject,
    deleteSection,
    createLabel,
    updateLabel,
    deleteLabel,
  };
});
