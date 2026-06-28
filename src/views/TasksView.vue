<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useTasksStore, type ProjectItem, type SectionItem, type TodoItem } from '@/stores/tasks';
import { useSettingsStore } from '@/stores/settings';
import {
  TASK_FILTERS,
  collectAllLabels,
  countForFilter,
  filterByTaskFilter,
  formatDueShort,
  isScatteredTask,
  isScheduledTask,
  isTodayTask,
  isUnsectionedProjectTask,
  type TaskFilterId,
} from '@/utils/taskFilters';
import TaskEditDialog, { type TaskFormPayload } from '@/components/TaskEditDialog.vue';
import ProjectEditDialog, { type ProjectFormPayload } from '@/components/ProjectEditDialog.vue';
import SectionEditDialog, { type SectionFormPayload } from '@/components/SectionEditDialog.vue';
import AppDatePicker from '@/components/AppDatePicker.vue';

const tasksStore = useTasksStore();
const settings = useSettingsStore();

const newTodoTitle = ref('');
const newTodoDue = ref('');
const summaryDate = ref('');
const summaryProgress = ref('');
const summaryRisks = ref('');
const summaryChallenges = ref('');

const taskDialogOpen = ref(false);
const taskDialogMode = ref<'create' | 'edit'>('create');
const editingTodo = ref<TodoItem | null>(null);

const projectDialogOpen = ref(false);
const projectDialogMode = ref<'create' | 'edit'>('create');
const editingProject = ref<ProjectItem | null>(null);

const sectionDialogOpen = ref(false);
const sectionDialogMode = ref<'create' | 'edit'>('create');
const editingSection = ref<SectionItem | null>(null);

const UNSECTIONED_SECTION = 0;

const inboxProjectId = computed(() => tasksStore.inbox?.id ?? null);

const filterCounts = computed(() => {
  const todos = tasksStore.allTodos;
  const inboxId = inboxProjectId.value;
  const counts = {} as Record<TaskFilterId, number>;
  for (const f of TASK_FILTERS) {
    counts[f.id] = countForFilter(todos, f.id, inboxId);
  }
  return counts;
});

const labelMap = computed(() => collectAllLabels(tasksStore.allTodos));

const availableLabels = computed(() => [...labelMap.value.keys()]);

const activeFilterMeta = computed(
  () => TASK_FILTERS.find((f) => f.id === tasksStore.activeFilter) ?? TASK_FILTERS[0]
);

const filteredTasks = computed(() => {
  if (tasksStore.viewMode === 'project') return [];
  return filterByTaskFilter(
    tasksStore.allTodos,
    tasksStore.activeFilter,
    inboxProjectId.value,
    tasksStore.activeLabel
  );
});

const selectedProject = computed(() =>
  tasksStore.projects.find((p) => p.id === tasksStore.selectedProjectId) ?? null
);

const selectedSection = computed(() =>
  tasksStore.sections.find((s) => s.id === tasksStore.selectedSectionId) ?? null
);

const projectTasksUnsectioned = computed(() => {
  const pid = tasksStore.selectedProjectId;
  if (pid == null) return [];
  return tasksStore.allTodos.filter((t) => isUnsectionedProjectTask(t, pid));
});

function tasksForSection(sectionId: number): TodoItem[] {
  const pid = tasksStore.selectedProjectId;
  if (pid == null) return [];
  return tasksStore.allTodos.filter((t) => t.project_id === pid && t.section_id === sectionId);
}

function progressPercent(stats?: { total: number; completed: number }) {
  if (!stats?.total) return 0;
  return Math.round((stats.completed / stats.total) * 100);
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    planning: '规划中',
    active: '进行中',
    on_hold: '暂停',
    completed: '已完成',
    archived: '已归档',
  };
  return map[status] ?? status;
}

async function load() {
  if (settings.sidecarStatus !== 'running') return;
  await tasksStore.refresh(settings.sidecarPort);
}

function pickFilter(id: TaskFilterId) {
  tasksStore.selectFilter(id);
}

function pickLabel(label: string) {
  tasksStore.selectLabel(label);
}

async function pickProject(id: number) {
  await tasksStore.selectProjectView(settings.sidecarPort, id);
}

async function pickSection(id: number | null) {
  tasksStore.selectSection(id);
  if (id != null && id !== UNSECTIONED_SECTION) {
    try {
      await tasksStore.fetchSectionDetail(settings.sidecarPort, id);
    } catch (e) {
      tasksStore.error = e instanceof Error ? e.message : String(e);
    }
  } else {
    tasksStore.sectionSummaries = [];
  }
}

function ensureTodoVisible(todo: TodoItem) {
  if (tasksStore.viewMode === 'project') return;
  const inboxId = inboxProjectId.value;
  const visible = filterByTaskFilter(
    [todo],
    tasksStore.activeFilter,
    inboxId,
    tasksStore.activeLabel
  ).length > 0;
  if (visible) return;
  if (isScatteredTask(todo, inboxId)) {
    tasksStore.selectFilter('inbox');
  } else if (isTodayTask(todo)) {
    tasksStore.selectFilter('today');
  } else if (isScheduledTask(todo)) {
    tasksStore.selectFilter('scheduled');
  } else {
    tasksStore.selectFilter('inbox');
  }
}

async function addTodo() {
  const title = newTodoTitle.value.trim();
  if (!title) {
    openCreateTask();
    return;
  }
  try {
    const payload: Parameters<typeof tasksStore.createTodo>[1] = {
      title,
      due_date: newTodoDue.value,
    };
    if (tasksStore.viewMode === 'project' && tasksStore.selectedProjectId != null) {
      payload.project_id = tasksStore.selectedProjectId;
      const sid = tasksStore.selectedSectionId;
      if (sid != null && sid !== UNSECTIONED_SECTION) payload.section_id = sid;
    } else if (inboxProjectId.value != null) {
      payload.project_id = inboxProjectId.value;
    }
    const created = await tasksStore.createTodo(settings.sidecarPort, payload);
    if (created) ensureTodoVisible(created);
    newTodoTitle.value = '';
    newTodoDue.value = '';
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

function openCreateTask() {
  taskDialogMode.value = 'create';
  editingTodo.value = null;
  taskDialogOpen.value = true;
}

function openEditTask(todo: TodoItem) {
  taskDialogMode.value = 'edit';
  editingTodo.value = todo;
  taskDialogOpen.value = true;
}

async function onTaskDialogProjectChange(projectId: number | null) {
  if (projectId == null || projectId === inboxProjectId.value) return;
  try {
    await tasksStore.loadSections(settings.sidecarPort, projectId);
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function saveTask(payload: TaskFormPayload) {
  try {
    const inboxId = inboxProjectId.value;
    const isInbox = payload.project_id == null || payload.project_id === inboxId;
    const projectId = isInbox ? inboxId : payload.project_id;
    const sectionId = isInbox ? null : payload.section_id;
    if (taskDialogMode.value === 'edit' && editingTodo.value) {
      await tasksStore.updateTodo(settings.sidecarPort, editingTodo.value.id, {
        title: payload.title,
        description: payload.description,
        due_date: payload.due_date,
        remind_at: payload.remind_at,
        priority: payload.priority,
        project_id: projectId,
        section_id: sectionId,
        tags: payload.tags,
        clear_reminder: !payload.remind_at,
      });
    } else {
      const created = await tasksStore.createTodo(settings.sidecarPort, {
        title: payload.title,
        description: payload.description,
        due_date: payload.due_date,
        remind_at: payload.remind_at,
        priority: payload.priority,
        tags: payload.tags,
        project_id: isInbox ? inboxId ?? undefined : projectId ?? undefined,
        section_id: isInbox ? undefined : sectionId ?? undefined,
      });
      if (created) ensureTodoVisible(created);
    }
    taskDialogOpen.value = false;
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

function openCreateProject() {
  projectDialogMode.value = 'create';
  editingProject.value = null;
  projectDialogOpen.value = true;
}

function openEditProject(project: ProjectItem, e?: Event) {
  e?.stopPropagation();
  projectDialogMode.value = 'edit';
  editingProject.value = project;
  projectDialogOpen.value = true;
}

async function saveProject(payload: ProjectFormPayload) {
  try {
    if (projectDialogMode.value === 'edit' && editingProject.value) {
      await tasksStore.updateProject(settings.sidecarPort, editingProject.value.id, payload);
    } else {
      const created = await tasksStore.createProject(settings.sidecarPort, payload);
      if (created?.id != null) {
        await tasksStore.selectProjectView(settings.sidecarPort, created.id);
      }
    }
    projectDialogOpen.value = false;
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

function openCreateSection() {
  sectionDialogMode.value = 'create';
  editingSection.value = null;
  sectionDialogOpen.value = true;
}

function openEditSection(section: SectionItem, e?: Event) {
  e?.stopPropagation();
  sectionDialogMode.value = 'edit';
  editingSection.value = section;
  sectionDialogOpen.value = true;
}

async function saveSection(payload: SectionFormPayload) {
  const pid = tasksStore.selectedProjectId;
  if (pid == null) return;
  try {
    if (sectionDialogMode.value === 'edit' && editingSection.value) {
      await tasksStore.updateSection(settings.sidecarPort, editingSection.value.id, payload);
    } else {
      await tasksStore.createSection(settings.sidecarPort, pid, payload);
    }
    sectionDialogOpen.value = false;
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function toggleTodo(todo: TodoItem) {
  try {
    await tasksStore.toggleTodoComplete(settings.sidecarPort, todo);
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function removeTodo(id: number) {
  if (!confirm(`删除任务 #${id}？`)) return;
  try {
    await tasksStore.deleteTodo(settings.sidecarPort, id);
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function saveSummary() {
  const sid = tasksStore.selectedSectionId;
  const date = summaryDate.value.trim();
  if (sid == null || sid === UNSECTIONED_SECTION || !date) return;
  try {
    await tasksStore.saveSectionSummary(settings.sidecarPort, sid, {
      summary_date: date,
      progress: summaryProgress.value,
      risks: summaryRisks.value,
      challenges: summaryChallenges.value,
    });
    summaryProgress.value = '';
    summaryRisks.value = '';
    summaryChallenges.value = '';
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

onMounted(load);
watch(
  () => [settings.sidecarPort, settings.sidecarStatus],
  () => {
    if (settings.sidecarStatus === 'running') load();
  }
);
</script>

<template>
  <div class="task-hub">
    <aside class="sidebar">
      <div class="filter-grid">
        <button
          v-for="f in TASK_FILTERS"
          :key="f.id"
          class="filter-card"
          :class="[`filter-${f.id}`, { active: tasksStore.viewMode === 'filter' && tasksStore.activeFilter === f.id }]"
          @click="pickFilter(f.id)"
        >
          <span class="filter-icon">{{ f.icon }}</span>
          <span class="filter-label">{{ f.label }}</span>
          <span v-if="filterCounts[f.id]" class="filter-count">{{ filterCounts[f.id] }}</span>
        </button>
      </div>

      <div class="projects-block">
        <div class="projects-head">
          <span>On This Computer</span>
          <button class="icon-btn" title="新建项目" @click="openCreateProject">+</button>
        </div>
        <ul class="project-list">
          <li
            v-for="p in tasksStore.projects"
            :key="p.id"
            :class="{ active: tasksStore.viewMode === 'project' && p.id === tasksStore.selectedProjectId }"
            @click="pickProject(p.id)"
          >
            <span class="proj-name">{{ p.name }}</span>
            <span class="proj-actions">
              <span class="proj-meta">{{ p.stats?.completed ?? 0 }}/{{ p.stats?.total ?? 0 }}</span>
              <button class="btn-edit" title="编辑项目" @click="openEditProject(p, $event)">✎</button>
            </span>
          </li>
          <li v-if="!tasksStore.projects.length" class="empty">暂无项目</li>
        </ul>
      </div>
    </aside>

    <main class="main-panel">
      <header class="main-head">
        <div>
          <h2>
            <template v-if="tasksStore.viewMode === 'project' && selectedProject">
              {{ selectedProject.name }}
            </template>
            <template v-else-if="tasksStore.activeFilter === 'labels' && tasksStore.activeLabel">
              🏷️ {{ tasksStore.activeLabel }}
            </template>
            <template v-else>{{ activeFilterMeta.label }}</template>
          </h2>
          <p class="hint">
            <template v-if="tasksStore.viewMode === 'project' && selectedProject">
              {{ selectedProject.description || '项目任务与 Section 管理' }}
            </template>
            <template v-else>{{ activeFilterMeta.hint }}</template>
          </p>
        </div>
        <div class="head-actions">
          <button class="btn-refresh" :disabled="tasksStore.loading" @click="load">
            {{ tasksStore.loading ? '…' : '刷新' }}
          </button>
          <button
            v-if="tasksStore.viewMode === 'project' && selectedProject"
            class="btn-edit-head"
            @click="openEditProject(selectedProject)"
          >
            编辑项目
          </button>
        </div>
      </header>

      <p v-if="tasksStore.error" class="error">{{ tasksStore.error }}</p>
      <p v-if="settings.sidecarStatus !== 'running'" class="warn">Sidecar 未运行</p>

      <!-- 筛选视图 -->
      <template v-if="tasksStore.viewMode === 'filter'">
        <div v-if="tasksStore.activeFilter === 'labels' && !tasksStore.activeLabel" class="labels-panel">
          <h3>全部标签</h3>
          <ul class="label-list">
            <li v-for="[tag, count] in labelMap" :key="tag" @click="pickLabel(tag)">
              <span class="tag-chip">{{ tag }}</span>
              <span class="tag-count">{{ count }}</span>
            </li>
            <li v-if="!labelMap.size" class="empty">暂无标签</li>
          </ul>
        </div>

        <template v-else>
          <div class="inline-add">
            <input
              v-model="newTodoTitle"
              placeholder="添加任务…"
              @keydown.enter="addTodo"
            />
            <AppDatePicker v-model="newTodoDue" mode="datetime" placeholder="截止" />
            <button @click="addTodo">+ Add Task</button>
            <button class="btn-detail" title="详细表单" @click="openCreateTask">⋯</button>
          </div>

          <ul class="task-list">
            <li
              v-for="t in filteredTasks"
              :key="t.id"
              :class="{ done: t.completed }"
              @click="openEditTask(t)"
            >
              <input type="checkbox" :checked="t.completed" @click.stop @change="toggleTodo(t)" />
              <div class="task-body">
                <div class="task-title">{{ t.title }}</div>
                <div class="task-meta">
                  <span class="due">{{ formatDueShort(t.due_date) }}</span>
                  <span v-if="t.priority !== 'normal'" class="tag pri">{{ t.priority }}</span>
                  <span v-for="tag in t.tags ?? []" :key="tag" class="tag">{{ tag }}</span>
                  <span v-if="t.project_id && t.project_id !== inboxProjectId" class="tag proj">
                    P#{{ t.project_id }}
                  </span>
                </div>
              </div>
              <button class="btn-del" @click.stop="removeTodo(t.id)">×</button>
            </li>
            <li v-if="!filteredTasks.length" class="empty">暂无任务</li>
          </ul>
        </template>
      </template>

      <!-- 项目视图 -->
      <template v-else-if="selectedProject">
        <div class="project-toolbar">
          <select
            :value="selectedProject.status"
            @change="tasksStore.updateProjectStatus(settings.sidecarPort, selectedProject.id, ($event.target as HTMLSelectElement).value)"
          >
            <option value="planning">规划中</option>
            <option value="active">进行中</option>
            <option value="on_hold">暂停</option>
            <option value="completed">已完成</option>
            <option value="archived">已归档</option>
          </select>
          <div class="progress-wrap">
            <div
              class="progress-bar"
              :style="{ width: `${progressPercent(selectedProject.stats)}%` }"
            />
          </div>
          <span class="progress-text">
            {{ selectedProject.stats?.completed ?? 0 }}/{{ selectedProject.stats?.total ?? 0 }}
          </span>
        </div>

        <div class="project-layout">
          <aside class="section-nav">
            <div class="section-nav-head">
              <span>Sections</span>
              <button class="icon-btn" title="新建 Section" @click="openCreateSection">+</button>
            </div>
            <button
              :class="{ active: tasksStore.selectedSectionId === null }"
              @click="pickSection(null)"
            >
              全部
            </button>
            <button
              :class="{ active: tasksStore.selectedSectionId === UNSECTIONED_SECTION }"
              @click="pickSection(UNSECTIONED_SECTION)"
            >
              无section
              <small>{{ projectTasksUnsectioned.length }}</small>
            </button>
            <div
              v-for="s in tasksStore.sections"
              :key="s.id"
              class="section-nav-item"
              :class="{ active: s.id === tasksStore.selectedSectionId }"
              @click="pickSection(s.id)"
            >
              <span class="section-nav-name">{{ s.name }}</span>
              <span class="section-nav-meta">
                <small>{{ s.stats?.completed ?? 0 }}/{{ s.stats?.total ?? 0 }}</small>
                <button class="btn-edit" title="编辑 Section" @click="openEditSection(s, $event)">✎</button>
              </span>
            </div>
          </aside>

          <section class="project-tasks">
            <div class="inline-add">
              <input v-model="newTodoTitle" placeholder="添加项目任务…" @keydown.enter="addTodo" />
              <AppDatePicker v-model="newTodoDue" mode="datetime" placeholder="截止" />
              <button @click="addTodo">+ Add Task</button>
              <button class="btn-detail" @click="openCreateTask">⋯</button>
            </div>

            <template v-if="tasksStore.selectedSectionId === null">
              <h3 class="section-title">无section</h3>
              <ul class="task-list">
                <li
                  v-for="t in projectTasksUnsectioned"
                  :key="t.id"
                  :class="{ done: t.completed }"
                  @click="openEditTask(t)"
                >
                  <input type="checkbox" :checked="t.completed" @click.stop @change="toggleTodo(t)" />
                  <div class="task-body">
                    <div class="task-title">{{ t.title }}</div>
                    <div class="task-meta">
                      <span class="due">{{ formatDueShort(t.due_date) }}</span>
                      <span v-for="tag in t.tags ?? []" :key="tag" class="tag">{{ tag }}</span>
                    </div>
                  </div>
                  <button class="btn-del" @click.stop="removeTodo(t.id)">×</button>
                </li>
                <li v-if="!projectTasksUnsectioned.length" class="empty">暂无任务</li>
              </ul>
              <div v-for="s in tasksStore.sections" :key="s.id" class="section-block">
                <h3 class="section-title">
                  {{ s.name }}
                  <span class="badge">{{ statusLabel(s.status) }}</span>
                  <span class="section-stat">
                    {{ s.stats?.completed ?? 0 }}/{{ s.stats?.total ?? 0 }}
                  </span>
                  <button class="btn-edit-inline" title="编辑 Section" @click.stop="openEditSection(s)">✎</button>
                </h3>
                <p v-if="s.goals" class="section-goals">{{ s.goals }}</p>
                <ul class="task-list">
                  <li
                    v-for="t in tasksForSection(s.id)"
                    :key="t.id"
                    :class="{ done: t.completed }"
                    @click="openEditTask(t)"
                  >
                    <input type="checkbox" :checked="t.completed" @click.stop @change="toggleTodo(t)" />
                    <div class="task-body">
                      <div class="task-title">{{ t.title }}</div>
                      <div class="task-meta">
                        <span class="due">{{ formatDueShort(t.due_date) }}</span>
                        <span v-for="tag in t.tags ?? []" :key="tag" class="tag">{{ tag }}</span>
                      </div>
                    </div>
                    <button class="btn-del" @click.stop="removeTodo(t.id)">×</button>
                  </li>
                  <li v-if="!tasksForSection(s.id).length" class="empty">暂无任务</li>
                </ul>
              </div>
            </template>

            <template v-else-if="tasksStore.selectedSectionId === UNSECTIONED_SECTION">
              <h3 class="section-title">无section</h3>
              <ul class="task-list">
                <li
                  v-for="t in projectTasksUnsectioned"
                  :key="t.id"
                  :class="{ done: t.completed }"
                  @click="openEditTask(t)"
                >
                  <input type="checkbox" :checked="t.completed" @click.stop @change="toggleTodo(t)" />
                  <div class="task-body">
                    <div class="task-title">{{ t.title }}</div>
                    <div class="task-meta">
                      <span class="due">{{ formatDueShort(t.due_date) }}</span>
                      <span v-for="tag in t.tags ?? []" :key="tag" class="tag">{{ tag }}</span>
                    </div>
                  </div>
                  <button class="btn-del" @click.stop="removeTodo(t.id)">×</button>
                </li>
                <li v-if="!projectTasksUnsectioned.length" class="empty">暂无任务</li>
              </ul>
            </template>

            <template v-else-if="selectedSection">
              <div class="section-head">
                <h3 class="section-title">{{ selectedSection.name }}</h3>
                <button class="btn-edit-head" @click="openEditSection(selectedSection)">编辑 Section</button>
              </div>
              <p v-if="selectedSection.goals" class="section-goals">{{ selectedSection.goals }}</p>
              <ul class="task-list">
                <li
                  v-for="t in tasksForSection(selectedSection.id)"
                  :key="t.id"
                  :class="{ done: t.completed }"
                  @click="openEditTask(t)"
                >
                  <input type="checkbox" :checked="t.completed" @click.stop @change="toggleTodo(t)" />
                  <div class="task-body">
                    <div class="task-title">{{ t.title }}</div>
                    <div class="task-meta">
                      <span class="due">{{ formatDueShort(t.due_date) }}</span>
                      <span v-for="tag in t.tags ?? []" :key="tag" class="tag">{{ tag }}</span>
                    </div>
                  </div>
                  <button class="btn-del" @click.stop="removeTodo(t.id)">×</button>
                </li>
                <li v-if="!tasksForSection(selectedSection.id).length" class="empty">暂无任务</li>
              </ul>
              <div class="summary-block">
                <h4>每日总结</h4>
                <div class="summary-form">
                  <AppDatePicker v-model="summaryDate" mode="date" placeholder="日期" />
                  <input v-model="summaryProgress" placeholder="进度" />
                  <input v-model="summaryRisks" placeholder="风险" />
                  <input v-model="summaryChallenges" placeholder="挑战" />
                  <button @click="saveSummary">保存</button>
                </div>
                <ul v-if="tasksStore.sectionSummaries.length" class="summary-list">
                  <li v-for="s in tasksStore.sectionSummaries" :key="s.id">
                    <strong>{{ s.summary_date }}</strong>
                    <span v-if="s.progress"> · {{ s.progress }}</span>
                  </li>
                </ul>
              </div>
            </template>
          </section>
        </div>
      </template>
    </main>

    <TaskEditDialog
      :open="taskDialogOpen"
      :mode="taskDialogMode"
      :todo="editingTodo"
      :projects="tasksStore.projects"
      :sections="tasksStore.sections"
      :inbox-project-id="inboxProjectId"
      :available-labels="availableLabels"
      :default-project-id="tasksStore.viewMode === 'project' ? tasksStore.selectedProjectId : inboxProjectId"
      :default-section-id="
        tasksStore.selectedSectionId === UNSECTIONED_SECTION ? null : tasksStore.selectedSectionId
      "
      @project-change="onTaskDialogProjectChange"
      @save="saveTask"
      @cancel="taskDialogOpen = false"
    />

    <ProjectEditDialog
      :open="projectDialogOpen"
      :mode="projectDialogMode"
      :project="editingProject"
      @save="saveProject"
      @cancel="projectDialogOpen = false"
    />

    <SectionEditDialog
      :open="sectionDialogOpen"
      :mode="sectionDialogMode"
      :section="editingSection"
      @save="saveSection"
      @cancel="sectionDialogOpen = false"
    />
  </div>
</template>

<style scoped>
.task-hub {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: var(--bg-app);
}

.sidebar {
  width: 240px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  background: var(--bg-sidebar, var(--bg-panel));
  padding: 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.filter-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: 10px;
  cursor: pointer;
  color: var(--text-on-accent);
  text-align: left;
  min-height: 72px;
  transition: outline-color 0.15s ease, transform 0.15s ease;
}

.filter-card:hover {
  transform: translateY(-1px);
}

.filter-card.active {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.filter-inbox {
  background: linear-gradient(135deg, var(--accent), var(--accent-hover));
}

.filter-today {
  background: linear-gradient(
    135deg,
    var(--success),
    color-mix(in srgb, var(--success) 62%, var(--bg-app))
  );
}

.filter-scheduled {
  background: linear-gradient(
    135deg,
    var(--tool-mcp),
    color-mix(in srgb, var(--tool-mcp) 58%, var(--accent-hover))
  );
}

.filter-pinned {
  background: linear-gradient(135deg, var(--danger), var(--danger-hover));
}

.filter-labels {
  background: linear-gradient(
    135deg,
    var(--warning),
    color-mix(in srgb, var(--warning) 62%, var(--bg-app))
  );
}

.filter-completed {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--warning) 50%, var(--success)),
    var(--warning)
  );
}

.filter-icon { font-size: 18px; }
.filter-label { font-size: 13px; font-weight: 600; }
.filter-count {
  position: absolute;
  top: 8px;
  right: 8px;
  background: color-mix(in srgb, var(--bg-app) 42%, transparent);
  border-radius: 10px;
  padding: 1px 7px;
  font-size: 11px;
}

.projects-block {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.projects-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.icon-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 16px;
}

.project-add-input {
  width: 100%;
  background: var(--bg-code);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 12px;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.project-list {
  list-style: none;
  overflow-y: auto;
  flex: 1;
}

.project-list li {
  display: flex;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
}

.project-list li:hover { background: var(--bg-hover); }
.project-list li.active {
  background: var(--choice-active-bg);
  box-shadow: inset 0 0 0 1px var(--choice-active-border);
}
.proj-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.proj-meta { color: var(--text-muted); font-size: 11px; }

.btn-edit {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  padding: 0 4px;
  opacity: 0;
}

.project-list li:hover .btn-edit {
  opacity: 1;
}

.main-panel {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  min-width: 0;
  background: var(--bg-app);
}

.main-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 8px;
  flex-wrap: wrap;
}

.head-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.btn-edit-head {
  background: var(--btn-secondary-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-primary);
}

.main-head h2 { margin: 0; font-size: 20px; }
.hint { margin: 4px 0 0; color: var(--text-muted); font-size: 13px; }

.btn-refresh {
  background: var(--btn-secondary-bg);
  border: none;
  border-radius: 6px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-primary);
}

.error { color: var(--danger); font-size: 13px; }
.warn { color: var(--text-highlight); font-size: 13px; }

.inline-add {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  align-items: center;
}

.inline-add :deep(.app-date-picker) {
  width: 180px;
  flex-shrink: 0;
}

.inline-add input {
  flex: 1;
  background: var(--bg-code);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-primary);
}

.inline-add :deep(.app-date-picker input),
.inline-add :deep(.dp__input) {
  background: var(--bg-input);
  border-color: var(--border);
  color: var(--text-primary);
}

.inline-add button {
  background: var(--accent);
  color: var(--text-on-accent);
  border: none;
  border-radius: 8px;
  padding: 0 16px;
  cursor: pointer;
  white-space: nowrap;
}

.inline-add button:hover {
  background: var(--accent-hover);
}

.btn-detail {
  background: var(--btn-secondary-bg) !important;
  color: var(--text-primary) !important;
  padding: 0 12px !important;
}

.task-list { list-style: none; }

.task-list li {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  margin-bottom: 8px;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 10px;
  cursor: pointer;
}

.task-list li:hover {
  background: var(--bg-hover);
  border-color: color-mix(in srgb, var(--accent) 35%, var(--border));
}

.task-list li.done {
  opacity: 0.65;
  border-left-color: var(--text-muted);
}

.task-list li.done .task-title {
  text-decoration: line-through;
  color: var(--text-muted);
}

.task-body { flex: 1; min-width: 0; }
.task-title { font-size: 14px; font-weight: 500; }
.task-meta { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }

.due { font-size: 11px; color: var(--text-muted); }
.tag {
  font-size: 10px;
  background: color-mix(in srgb, var(--border) 70%, var(--bg-panel));
  color: var(--text-secondary);
  padding: 2px 6px;
  border-radius: 4px;
}
.tag.pri { color: var(--text-highlight); background: var(--warning-muted); }
.tag.proj {
  color: var(--accent);
  background: var(--accent-muted);
}

.btn-del {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 18px;
}

.empty { color: var(--text-muted); font-size: 13px; padding: 12px 4px; }

.labels-panel h3 { font-size: 14px; margin-bottom: 12px; }
.label-list { list-style: none; }
.label-list li {
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
}
.label-list li:hover { background: var(--bg-hover); }
.tag-chip {
  background: var(--accent-muted);
  color: var(--accent);
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 13px;
}

.project-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.project-toolbar select {
  background: var(--bg-code);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  color: var(--text-primary);
}

.progress-wrap {
  flex: 1;
  height: 6px;
  background: var(--border);
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar { height: 100%; background: var(--accent); }
.progress-text { font-size: 12px; color: var(--text-muted); }

.project-layout {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 16px;
  min-height: 300px;
}

.section-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-nav-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 4px;
  padding: 0 2px;
}

.section-nav button,
.section-nav-item {
  text-align: left;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
  color: var(--text-primary);
  font-size: 12px;
}

.section-nav-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
}

.section-nav-item.active,
.section-nav button.active {
  background: var(--choice-active-bg);
  border-color: var(--choice-active-border);
}

.section-nav-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.section-nav-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.section-nav-meta .btn-edit {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 11px;
  padding: 0 2px;
  opacity: 0;
}

.section-nav-item:hover .btn-edit {
  opacity: 1;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 16px 0 8px;
}

.section-head .section-title {
  margin: 0;
}

.btn-edit-inline {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  margin-left: auto;
  padding: 0 4px;
}

.section-title {
  font-size: 14px;
  margin: 16px 0 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-goals { font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; }
.badge { font-size: 10px; color: var(--accent); }
.section-stat { font-size: 11px; color: var(--text-muted); }
.section-block { margin-bottom: 20px; }

.summary-block {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.summary-form {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.summary-form input {
  flex: 1;
  min-width: 100px;
  background: var(--bg-code);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 12px;
  color: var(--text-primary);
}

.summary-list { list-style: none; font-size: 12px; }
</style>
