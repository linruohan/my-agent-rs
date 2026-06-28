<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useTasksStore } from '@/stores/tasks';
import { useSettingsStore } from '@/stores/settings';

const tasksStore = useTasksStore();
const settings = useSettingsStore();

const newProjectName = ref('');
const newProjectDue = ref('');
const newProjectRemind = ref('');
const projectRemindInput = ref('');
const docTitle = ref('');
const docPath = ref('');
const docNote = ref('');

const PROJECT_STATUSES = ['planning', 'active', 'on_hold', 'completed', 'archived'] as const;

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

async function selectProject(id: number) {
  tasksStore.selectProject(id);
  tasksStore.lastDocMessage = '';
  try {
    await tasksStore.fetchProjectDetail(settings.sidecarPort, id);
  } catch (e) {
    tasksStore.error = e instanceof Error ? e.message : String(e);
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

async function addProject() {
  const name = newProjectName.value.trim();
  if (!name) return;
  try {
    await tasksStore.createProjectLegacy(
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
    await tasksStore.setProjectReminder(settings.sidecarPort, id, projectRemindInput.value);
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
  <div class="projects-view">
    <header>
      <h2>项目管理</h2>
      <p class="hint">管理项目进度、状态与文档；文档添加时可自动索引到知识库</p>
      <button class="btn-refresh" :disabled="tasksStore.loading" @click="load">
        {{ tasksStore.loading ? '加载中…' : '刷新' }}
      </button>
    </header>

    <p v-if="tasksStore.error" class="error">{{ tasksStore.error }}</p>
    <p v-if="settings.sidecarStatus !== 'running'" class="warn">Sidecar 未运行，无法加载项目数据</p>

    <div class="layout">
      <aside class="list-panel">
        <div class="panel-head">
          <h3>项目列表</h3>
          <div class="inline-add">
            <input v-model="newProjectName" placeholder="新项目名称" @keydown.enter="addProject" />
            <button @click="addProject">+</button>
          </div>
          <div class="datetime-row">
            <input v-model="newProjectDue" type="datetime-local" title="项目截止" />
            <input v-model="newProjectRemind" type="datetime-local" title="提醒时间" />
          </div>
        </div>
        <ul class="project-list">
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
          <li v-if="!tasksStore.projects.length" class="empty">暂无项目</li>
        </ul>
      </aside>

      <section class="detail-panel">
        <template v-if="selectedProject">
          <h3>{{ selectedProject.name }}</h3>
          <div class="status-row">
            <label>状态</label>
            <select
              :value="selectedProject.status"
              @change="changeProjectStatus(($event.target as HTMLSelectElement).value)"
            >
              <option v-for="s in PROJECT_STATUSES" :key="s" :value="s">
                {{ statusLabel(s) }}
              </option>
            </select>
          </div>
          <div class="datetime-row">
            <input v-model="projectRemindInput" type="datetime-local" title="项目提醒" />
            <button class="btn-small" @click="saveProjectReminder">更新提醒</button>
          </div>
          <p v-if="selectedProject.remind_at" class="meta-line">
            当前提醒：{{ formatRemindTime(selectedProject.remind_at) }}
          </p>

          <section class="docs-section">
            <h4>项目文档</h4>
            <div class="doc-form">
              <input v-model="docTitle" placeholder="文档标题" />
              <input v-model="docPath" placeholder="工作区相对路径，如 docs/spec.md" />
              <textarea v-model="docNote" placeholder="备注（可选）" rows="2" />
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
        </template>
        <p v-else class="empty-detail">请从左侧选择一个项目查看详情</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.projects-view {
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
}

.warn {
  color: var(--text-highlight);
  font-size: 13px;
}

.layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
  min-height: 400px;
}

.list-panel,
.detail-panel {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
}

.panel-head h3,
.detail-panel h3 {
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

.project-list {
  list-style: none;
  overflow-y: auto;
  max-height: 520px;
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
}

.meta,
.meta-line {
  font-size: 11px;
  color: var(--text-muted);
}

.status-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.status-row label {
  font-size: 13px;
  color: var(--text-secondary);
}

.status-row select {
  background: var(--bg-code);
  border: 1px solid var(--border);
  color: var(--text-primary);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
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

.empty,
.empty-detail {
  color: var(--text-muted);
  font-size: 13px;
  padding: 12px;
}

.docs-section {
  margin-top: 20px;
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
