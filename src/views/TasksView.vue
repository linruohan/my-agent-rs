<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useTasksStore } from '@/stores/tasks';
import { useSettingsStore } from '@/stores/settings';

const tasksStore = useTasksStore();
const settings = useSettingsStore();

const newTodoTitle = ref('');
const newProjectName = ref('');
const newSectionName = ref('');
const newSectionGoals = ref('');
const newTodoDue = ref('');
const showCompleted = ref(true);
const docTitle = ref('');
const docPath = ref('');
const docNote = ref('');
const summaryDate = ref('');
const summaryProgress = ref('');
const summaryRisks = ref('');
const summaryChallenges = ref('');

const PROJECT_STATUSES = ['planning', 'active', 'on_hold', 'completed', 'archived'] as const;

const visibleProjects = computed(() =>
  tasksStore.projects.filter((p) => !p.is_inbox)
);

const selectedProject = computed(() => {
  if (tasksStore.selectedProjectId == null) return tasksStore.inbox;
  return (
    tasksStore.projects.find((p) => p.id === tasksStore.selectedProjectId) ??
    tasksStore.inbox
  );
});

const selectedSection = computed(() =>
  tasksStore.sections.find((s) => s.id === tasksStore.selectedSectionId) ?? null
);

const isInboxView = computed(
  () => tasksStore.selectedProjectId != null && selectedProject.value?.is_inbox
);

const filteredTodos = computed(() => {
  let list = tasksStore.todos;
  if (!showCompleted.value) list = list.filter((t) => !t.completed);
  return list;
});

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

async function selectInbox() {
  const inbox = tasksStore.inbox;
  if (!inbox) return;
  tasksStore.selectProject(inbox.id);
  tasksStore.sectionSummaries = [];
  await tasksStore.refresh(settings.sidecarPort);
}

async function selectProject(id: number) {
  tasksStore.selectProject(id);
  tasksStore.lastDocMessage = '';
  try {
    await tasksStore.fetchProjectDetail(settings.sidecarPort, id);
    await tasksStore.refresh(settings.sidecarPort);
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function selectSection(id: number | null) {
  tasksStore.selectSection(id);
  if (id != null) {
    try {
      await tasksStore.fetchSectionDetail(settings.sidecarPort, id);
    } catch (e) {
      tasksStore.error = e instanceof Error ? e.message : String(e);
    }
  } else {
    tasksStore.sectionSummaries = [];
  }
  await tasksStore.refresh(settings.sidecarPort);
}

async function changeProjectStatus(status: string) {
  const id = tasksStore.selectedProjectId;
  if (id == null || selectedProject.value?.is_inbox) return;
  try {
    await tasksStore.updateProjectStatus(settings.sidecarPort, id, status);
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function removeTodo(todoId: number) {
  if (!confirm(`删除任务 #${todoId}？`)) return;
  try {
    await tasksStore.deleteTodo(settings.sidecarPort, todoId);
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
      section_id: tasksStore.selectedSectionId ?? undefined,
      due_date: newTodoDue.value,
    });
    newTodoTitle.value = '';
    newTodoDue.value = '';
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function addProject() {
  const name = newProjectName.value.trim();
  if (!name) return;
  try {
    await tasksStore.createProject(settings.sidecarPort, name);
    newProjectName.value = '';
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function addSection() {
  const id = tasksStore.selectedProjectId;
  const name = newSectionName.value.trim();
  if (id == null || selectedProject.value?.is_inbox || !name) return;
  try {
    await tasksStore.createSection(settings.sidecarPort, id, {
      name,
      goals: newSectionGoals.value.trim(),
    });
    newSectionName.value = '';
    newSectionGoals.value = '';
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
  }
}

async function saveSummary() {
  const sid = tasksStore.selectedSectionId;
  const date = summaryDate.value.trim();
  if (sid == null || !date) return;
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

async function addProjectDoc() {
  const id = tasksStore.selectedProjectId;
  const title = docTitle.value.trim();
  if (id == null || selectedProject.value?.is_inbox || !title) return;
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
      <h2>项目 · Section · 任务</h2>
      <p class="hint">Project → Section（里程碑）→ Task；无 Section 的临时任务在 Inbox</p>
      <button class="btn-refresh" :disabled="tasksStore.loading" @click="load">
        {{ tasksStore.loading ? '加载中…' : '刷新' }}
      </button>
    </header>

    <p v-if="tasksStore.error" class="error">{{ tasksStore.error }}</p>
    <p v-if="settings.sidecarStatus !== 'running'" class="warn">
      Sidecar 未运行，无法加载任务数据
    </p>

    <div class="layout">
      <!-- 项目 -->
      <aside class="panel projects-panel">
        <div class="panel-head">
          <h3>项目</h3>
          <div class="inline-add">
            <input v-model="newProjectName" placeholder="新项目名称" @keydown.enter="addProject" />
            <button @click="addProject">+</button>
          </div>
        </div>
        <ul class="list">
          <li
            :class="{ active: isInboxView }"
            @click="selectInbox"
          >
            <span class="name">📥 Inbox</span>
            <span class="meta">临时任务</span>
          </li>
          <li
            v-for="p in visibleProjects"
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
            <div class="meta">{{ p.stats?.completed ?? 0 }}/{{ p.stats?.total ?? 0 }} 任务</div>
          </li>
        </ul>
      </aside>

      <!-- Section -->
      <aside class="panel sections-panel">
        <div class="panel-head">
          <h3>Sections</h3>
          <template v-if="selectedProject && !selectedProject.is_inbox">
            <div class="inline-add">
              <input v-model="newSectionName" placeholder="如 R13B100" @keydown.enter="addSection" />
              <button @click="addSection">+</button>
            </div>
            <input v-model="newSectionGoals" class="goals-input" placeholder="主要目标…" />
          </template>
        </div>
        <ul v-if="selectedProject && !selectedProject.is_inbox" class="list">
          <li
            :class="{ active: tasksStore.selectedSectionId === null }"
            @click="selectSection(null)"
          >
            <span class="name">全部 Section</span>
          </li>
          <li
            v-for="s in tasksStore.sections"
            :key="s.id"
            :class="{ active: s.id === tasksStore.selectedSectionId }"
            @click="selectSection(s.id)"
          >
            <div class="row">
              <span class="name">{{ s.name }}</span>
              <span class="badge">{{ statusLabel(s.status) }}</span>
            </div>
            <div class="meta">
              {{ s.stats?.completed ?? 0 }}/{{ s.stats?.total ?? 0 }}
              <span v-if="s.owner"> · @{{ s.owner }}</span>
            </div>
            <div v-if="s.goals" class="goals-preview">{{ s.goals }}</div>
          </li>
          <li v-if="!tasksStore.sections.length" class="empty">暂无 Section</li>
        </ul>
        <p v-else class="empty">选择项目以管理 Section</p>
      </aside>

      <!-- 任务 -->
      <section class="panel todos-panel">
        <div class="panel-head">
          <h3>
            <template v-if="selectedSection">{{ selectedSection.name }}</template>
            <template v-else-if="isInboxView">Inbox 临时任务</template>
            <template v-else-if="selectedProject">{{ selectedProject.name }}</template>
            <template v-else>任务</template>
          </h3>
          <label class="toggle">
            <input v-model="showCompleted" type="checkbox" />
            显示已完成
          </label>
        </div>

        <div class="inline-add">
          <input v-model="newTodoTitle" placeholder="添加任务…" @keydown.enter="addTodo" />
          <input v-model="newTodoDue" type="datetime-local" title="截止" />
          <button @click="addTodo">添加</button>
        </div>

        <ul class="todo-list">
          <li v-for="t in filteredTodos" :key="t.id" :class="{ done: t.completed }">
            <input type="checkbox" :checked="t.completed" @change="toggleTodo(t.id)" />
            <div class="todo-body">
              <span class="title">#{{ t.id }} {{ t.title }}</span>
              <span class="tags">
                <span class="tag priority">{{ t.priority }}</span>
                <span v-if="t.section_id" class="tag">S#{{ t.section_id }}</span>
                <span v-if="t.due_date" class="tag due">{{ t.due_date }}</span>
              </span>
            </div>
            <button class="btn-del" @click="removeTodo(t.id)">×</button>
          </li>
          <li v-if="!filteredTodos.length" class="empty">暂无任务</li>
        </ul>

        <!-- Section 每日总结 -->
        <section v-if="selectedSection" class="sub-section">
          <h4>每日总结</h4>
          <div class="summary-form">
            <input v-model="summaryDate" type="date" />
            <input v-model="summaryProgress" placeholder="进度" />
            <input v-model="summaryRisks" placeholder="风险" />
            <input v-model="summaryChallenges" placeholder="挑战" />
            <button @click="saveSummary">保存</button>
          </div>
          <ul v-if="tasksStore.sectionSummaries.length" class="summary-list">
            <li v-for="s in tasksStore.sectionSummaries" :key="s.id">
              <strong>{{ s.summary_date }}</strong>
              <span v-if="s.progress"> 进度: {{ s.progress }}</span>
              <span v-if="s.risks"> 风险: {{ s.risks }}</span>
              <span v-if="s.challenges"> 挑战: {{ s.challenges }}</span>
            </li>
          </ul>
        </section>

        <!-- 项目文档 -->
        <section v-if="selectedProject && !selectedProject.is_inbox" class="sub-section">
          <h4>项目文档</h4>
          <div class="doc-form">
            <input v-model="docTitle" placeholder="文档标题" />
            <input v-model="docPath" placeholder="工作区路径" />
            <textarea v-model="docNote" placeholder="备注" rows="2" />
            <button @click="addProjectDoc">添加</button>
          </div>
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

.error { color: var(--danger); font-size: 13px; }
.warn { color: var(--text-highlight); font-size: 13px; }

.layout {
  display: grid;
  grid-template-columns: 220px 240px 1fr;
  gap: 12px;
  min-height: 400px;
}

.panel {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.panel-head h3 {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 8px;
}

.inline-add {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}

.inline-add input,
.goals-input,
.summary-form input,
.doc-form input,
.doc-form textarea {
  flex: 1;
  background: var(--bg-code);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  padding: 6px 10px;
  font-size: 12px;
}

.goals-input { width: 100%; margin-bottom: 8px; }

.inline-add button {
  background: var(--accent);
  color: var(--text-on-accent);
  border: none;
  border-radius: 6px;
  padding: 0 10px;
  cursor: pointer;
}

.list, .todo-list {
  list-style: none;
  overflow-y: auto;
  flex: 1;
}

.list li {
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
}

.list li:hover { background: var(--bg-hover); }
.list li.active {
  background: var(--accent-subtle);
  border-color: var(--user-bubble);
}

.row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

.badge { font-size: 10px; color: var(--text-link); }
.meta { font-size: 11px; color: var(--text-muted); margin-top: 4px; }
.goals-preview { font-size: 11px; color: var(--text-secondary); margin-top: 2px; }

.progress-wrap {
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  margin: 4px 0;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--accent);
}

.todo-list li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 4px;
  border-bottom: 1px solid var(--bg-hover);
  font-size: 13px;
}

.todo-list li.done .title {
  text-decoration: line-through;
  color: var(--text-muted);
}

.todo-body { flex: 1; min-width: 0; }

.tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }

.tag {
  font-size: 10px;
  background: var(--border);
  color: var(--text-secondary);
  padding: 2px 6px;
  border-radius: 4px;
}

.empty { color: var(--text-muted); font-size: 12px; padding: 8px; cursor: default; }

.btn-del {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 18px;
}

.sub-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.sub-section h4 {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.summary-form {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.summary-list { font-size: 12px; list-style: none; }
.summary-list li { padding: 4px 0; border-bottom: 1px solid var(--bg-hover); }

.toggle {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>
