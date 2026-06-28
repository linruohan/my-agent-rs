<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useTasksStore } from '@/stores/tasks';
import { useSettingsStore } from '@/stores/settings';

const tasksStore = useTasksStore();
const settings = useSettingsStore();

const newTodoTitle = ref('');
const newProjectName = ref('');
const newTodoDue = ref('');
const newTodoRemind = ref('');
const newProjectDue = ref('');
const newProjectRemind = ref('');
const projectRemindInput = ref('');
const showCompleted = ref(true);
const docTitle = ref('');
const docPath = ref('');
const docNote = ref('');

const PROJECT_STATUSES = ['planning', 'active', 'on_hold', 'completed', 'archived'] as const;

const filteredTodos = computed(() =>
  showCompleted.value
    ? tasksStore.todos
    : tasksStore.todos.filter((t) => !t.completed)
);

const selectedProject = computed(() =>
  tasksStore.projects.find((p) => p.id === tasksStore.selectedProjectId) ?? null
);

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

function formatRemindTime(iso: string) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

async function load() {
  if (settings.sidecarStatus !== 'running') return;
  await tasksStore.refresh(settings.sidecarPort);
}

async function selectProject(id: number | null) {
  tasksStore.selectProject(id);
  tasksStore.lastDocMessage = '';
  await tasksStore.fetchTodos(settings.sidecarPort, id);
  if (id != null) {
    try {
      await tasksStore.fetchProjectDetail(settings.sidecarPort, id);
    } catch (e) {
      tasksStore.error = e instanceof Error ? e.message : String(e);
    }
  } else {
    tasksStore.projectDocs = [];
  }
}

async function changeProjectStatus(status: string) {
  const id = tasksStore.selectedProjectId;
  if (id == null) return;
  try {
    await tasksStore.updateProjectStatus(settings.sidecarPort, id, status);
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function removeTodo(todoId: number) {
  if (!confirm(`删除待办 #${todoId}？`)) return;
  try {
    await tasksStore.deleteTodo(settings.sidecarPort, todoId);
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function addProjectDoc() {
  const id = tasksStore.selectedProjectId;
  const title = docTitle.value.trim();
  if (id == null || !title) return;
  try {
    await tasksStore.addProjectDoc(settings.sidecarPort, id, {
      title,
      file_path: docPath.value.trim(),
      note: docNote.value.trim(),
    });
    docTitle.value = '';
    docPath.value = '';
    docNote.value = '';
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function toggleTodo(todoId: number) {
  const todo = tasksStore.todos.find((t) => t.id === todoId);
  if (!todo) return;
  try {
    await tasksStore.toggleTodoComplete(settings.sidecarPort, todo);
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function addTodo() {
  const title = newTodoTitle.value.trim();
  if (!title) return;
  try {
    await tasksStore.createTodo(settings.sidecarPort, {
      title,
      project_id: tasksStore.selectedProjectId ?? undefined,
      due_date: newTodoDue.value,
      remind_at: newTodoRemind.value || newTodoDue.value,
    });
    newTodoTitle.value = '';
    newTodoDue.value = '';
    newTodoRemind.value = '';
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function addProject() {
  const name = newProjectName.value.trim();
  if (!name) return;
  try {
    await tasksStore.createProject(
      settings.sidecarPort,
      name,
      '',
      newProjectDue.value,
      newProjectRemind.value || newProjectDue.value
    );
    newProjectName.value = '';
    newProjectDue.value = '';
    newProjectRemind.value = '';
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function saveProjectReminder() {
  const id = tasksStore.selectedProjectId;
  if (id == null) return;
  try {
    await tasksStore.setProjectReminder(
      settings.sidecarPort,
      id,
      projectRemindInput.value
    );
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
  <div class="tasks-view">
    <header>
      <h2>任务与项目</h2>
      <p class="hint">与 Agent 工具共享数据；项目文档添加时会自动索引到知识库</p>
      <button class="btn-refresh" :disabled="tasksStore.loading" @click="load">
        {{ tasksStore.loading ? '加载中…' : '刷新' }}
      </button>
    </header>

    <p v-if="tasksStore.error" class="error">{{ tasksStore.error }}</p>
    <p v-if="settings.sidecarStatus !== 'running'" class="warn">
      Sidecar 未运行，无法加载任务数据
    </p>

    <section v-if="tasksStore.reminders.length" class="reminders-banner">
      <h3>即将提醒</h3>
      <ul>
        <li v-for="r in tasksStore.reminders.slice(0, 5)" :key="r.job_id">
          <span class="remind-time">{{ formatRemindTime(r.run_at) }}</span>
          {{ r.title }}: {{ r.message }}
        </li>
      </ul>
    </section>

    <div class="layout">
      <aside class="projects-panel">
        <div class="panel-head">
          <h3>项目</h3>
          <div class="inline-add">
            <input v-model="newProjectName" placeholder="新项目名称" @keydown.enter="addProject" />
            <button @click="addProject">+</button>
          </div>
          <div class="datetime-row">
            <input v-model="newProjectDue" type="datetime-local" title="项目截止" />
            <input v-model="newProjectRemind" type="datetime-local" title="提醒时间（默认同截止）" />
          </div>
        </div>
        <ul class="project-list">
          <li
            :class="{ active: tasksStore.selectedProjectId === null }"
            @click="selectProject(null)"
          >
            <span class="name">全部待办</span>
          </li>
          <li
            v-for="p in tasksStore.projects"
            :key="p.id"
            :class="{ active: p.id === tasksStore.selectedProjectId }"
            @click="selectProject(p.id)"
          >
            <div class="row">
              <span class="name">#{{ p.id }} {{ p.name }}</span>
              <span class="badge">{{ statusLabel(p.status) }}</span>
            </div>
            <div class="progress-wrap">
              <div class="progress-bar" :style="{ width: `${progressPercent(p.stats)}%` }" />
            </div>
            <div class="meta">
              {{ p.stats?.completed ?? 0 }}/{{ p.stats?.total ?? 0 }} 任务
              <span v-if="p.doc_count"> · {{ p.doc_count }} 文档</span>
            </div>
          </li>
          <li v-if="!tasksStore.projects.length" class="empty">暂无项目，可通过对话或上方输入创建</li>
        </ul>
      </aside>

      <section class="todos-panel">
        <div class="panel-head">
          <h3>
            {{ selectedProject ? selectedProject.name : '全部待办' }}
          </h3>
          <div v-if="selectedProject" class="status-row">
            <select
              :value="selectedProject.status"
              @change="changeProjectStatus(($event.target as HTMLSelectElement).value)"
            >
              <option v-for="s in PROJECT_STATUSES" :key="s" :value="s">
                {{ statusLabel(s) }}
              </option>
            </select>
          </div>
          <div v-if="selectedProject" class="datetime-row">
            <input
              v-model="projectRemindInput"
              type="datetime-local"
              title="项目提醒时间"
            />
            <button class="btn-small" @click="saveProjectReminder">更新提醒</button>
          </div>
          <label class="toggle">
            <input v-model="showCompleted" type="checkbox" />
            显示已完成
          </label>
        </div>

        <div class="inline-add todo-add">
          <input
            v-model="newTodoTitle"
            placeholder="快速添加待办…"
            @keydown.enter="addTodo"
          />
          <button @click="addTodo">添加</button>
        </div>
        <div class="datetime-row">
          <input v-model="newTodoDue" type="datetime-local" title="截止日期" />
          <input v-model="newTodoRemind" type="datetime-local" title="提醒时间（默认同截止）" />
        </div>

        <ul class="todo-list">
          <li v-for="t in filteredTodos" :key="t.id" :class="{ done: t.completed }">
            <input
              type="checkbox"
              :checked="t.completed"
              @change="toggleTodo(t.id)"
            />
            <div class="todo-body">
              <span class="title">#{{ t.id }} {{ t.title }}</span>
              <span class="tags">
                <span class="tag priority">{{ t.priority }}</span>
                <span v-if="t.project_id" class="tag">项目 #{{ t.project_id }}</span>
                <span v-if="t.due_date" class="tag due">截止 {{ t.due_date }}</span>
              </span>
            </div>
            <button class="btn-del" title="删除" @click="removeTodo(t.id)">×</button>
          </li>
          <li v-if="!filteredTodos.length" class="empty">暂无待办</li>
        </ul>

        <section v-if="selectedProject" class="docs-section">
          <h4>项目文档</h4>
          <div class="doc-form">
            <input v-model="docTitle" placeholder="文档标题" />
            <input v-model="docPath" placeholder="工作区相对路径，如 docs/spec.md" />
            <textarea v-model="docNote" placeholder="备注（可选，将索引到 RAG）" rows="2" />
            <button @click="addProjectDoc">添加并索引</button>
          </div>
          <p v-if="tasksStore.lastDocMessage" class="doc-msg">{{ tasksStore.lastDocMessage }}</p>
          <ul v-if="tasksStore.projectDocs.length" class="doc-list">
            <li v-for="d in tasksStore.projectDocs" :key="d.id">
              <strong>#{{ d.id }} {{ d.title }}</strong>
              <span v-if="d.file_path" class="doc-path">{{ d.file_path }}</span>
            </li>
          </ul>
        </section>
      </section>
    </div>
  </div>
</template>

<style scoped>
.tasks-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 16px;
}

header h2 {
  font-size: 18px;
  margin: 0;
}

.hint {
  flex: 1;
  color: var(--text-muted);
  font-size: 13px;
  margin: 0;
}

.btn-refresh {
  background: var(--btn-secondary-bg);
  color: var(--text-primary);
  border: none;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}

.error {
  color: var(--danger);
  font-size: 13px;
  margin-bottom: 12px;
}

.warn {
  color: var(--text-highlight);
  font-size: 13px;
  margin-bottom: 12px;
}

.reminders-banner {
  background: var(--accent-subtle)33;
  border: 1px solid var(--user-bubble)44;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
}

.reminders-banner h3 {
  font-size: 13px;
  color: var(--text-link);
  margin: 0 0 8px;
}

.reminders-banner ul {
  list-style: none;
  font-size: 12px;
  color: var(--text-secondary);
}

.reminders-banner li {
  padding: 4px 0;
}

.remind-time {
  color: var(--text-highlight);
  margin-right: 8px;
}

.datetime-row {
  display: flex;
  gap: 6px;
  margin-top: 6px;
  flex-wrap: wrap;
}

.datetime-row input {
  flex: 1;
  min-width: 140px;
  background: var(--bg-code);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  padding: 4px 8px;
  font-size: 11px;
}

.btn-small {
  background: var(--btn-secondary-bg);
  color: var(--text-primary);
  border: none;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 11px;
}

.layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  min-height: 400px;
}

.projects-panel,
.todos-panel {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.panel-head {
  margin-bottom: 10px;
}

.panel-head h3 {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 8px;
}

.inline-add {
  display: flex;
  gap: 6px;
}

.inline-add input {
  flex: 1;
  background: var(--bg-code);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  padding: 6px 10px;
  font-size: 13px;
}

.inline-add button {
  background: var(--accent);
  color: var(--text-on-accent);
  border: none;
  border-radius: 6px;
  padding: 0 10px;
  cursor: pointer;
}

.project-list,
.todo-list {
  list-style: none;
  overflow-y: auto;
  flex: 1;
}

.project-list li {
  padding: 10px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
}

.project-list li:hover {
  background: var(--bg-hover);
}

.project-list li.active {
  background: var(--accent-subtle);
  border-color: var(--user-bubble);
}

.row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

.badge {
  font-size: 10px;
  color: var(--text-link);
  white-space: nowrap;
}

.progress-wrap {
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  margin: 6px 0 4px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--accent);
  transition: width 0.2s;
}

.meta {
  font-size: 11px;
  color: var(--text-muted);
}

.todo-add {
  margin-bottom: 12px;
}

.toggle {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
}

.todo-list li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 4px;
  border-bottom: 1px solid var(--bg-hover);
  font-size: 13px;
}

.todo-list li.done .title {
  text-decoration: line-through;
  color: var(--text-muted);
}

.todo-body {
  flex: 1;
  min-width: 0;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.tag {
  font-size: 10px;
  background: var(--border);
  color: var(--text-secondary);
  padding: 2px 6px;
  border-radius: 4px;
}

.tag.priority {
  color: var(--text-highlight);
}

.tag.due {
  color: var(--text-link);
}

.empty {
  color: var(--text-muted);
  font-size: 12px;
  padding: 12px 4px;
  cursor: default;
}

.status-row select {
  background: var(--bg-code);
  border: 1px solid var(--border);
  color: var(--text-primary);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  margin-bottom: 8px;
}

.btn-del {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 18px;
  padding: 0 4px;
}

.btn-del:hover {
  color: var(--danger);
}

.docs-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.docs-section h4 {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.doc-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}

.doc-form input,
.doc-form textarea {
  background: var(--bg-code);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  padding: 6px 10px;
  font-size: 12px;
}

.doc-form button {
  align-self: flex-start;
  background: var(--btn-secondary-bg);
  color: var(--text-primary);
  border: none;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}

.doc-msg {
  font-size: 12px;
  color: var(--success);
  margin-bottom: 8px;
}

.doc-list {
  list-style: none;
  font-size: 12px;
}

.doc-list li {
  padding: 6px 0;
  border-bottom: 1px solid var(--bg-hover);
}

.doc-path {
  display: block;
  color: var(--text-muted);
  font-size: 11px;
}
</style>
