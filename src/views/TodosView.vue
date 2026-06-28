<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useTasksStore } from '@/stores/tasks';
import { useSettingsStore } from '@/stores/settings';

const tasksStore = useTasksStore();
const settings = useSettingsStore();

const newTodoTitle = ref('');
const newTodoDue = ref('');
const newTodoRemind = ref('');
const filterProjectId = ref<number | ''>('');

const showCompleted = computed({
  get: () => settings.taskPrefs.showCompleted,
  set: (v: boolean) => {
    settings.taskPrefs.showCompleted = v;
  },
});

const filteredTodos = computed(() => {
  let list = showCompleted.value
    ? tasksStore.todos
    : tasksStore.todos.filter((t) => !t.completed);
  if (filterProjectId.value !== '') {
    list = list.filter((t) => t.project_id === filterProjectId.value);
  }
  return list;
});

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
  if (filterProjectId.value !== '') {
    await tasksStore.fetchTodos(settings.sidecarPort, filterProjectId.value as number);
  } else {
    await tasksStore.fetchTodos(settings.sidecarPort, null);
  }
}

async function onFilterChange() {
  const id = filterProjectId.value === '' ? null : (filterProjectId.value as number);
  tasksStore.selectProject(id);
  await tasksStore.fetchTodos(settings.sidecarPort, id);
}

async function removeTodo(todoId: number) {
  if (!confirm(`删除待办 #${todoId}？`)) return;
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
  const projectId = filterProjectId.value === '' ? undefined : (filterProjectId.value as number);
  try {
    await tasksStore.createTodo(settings.sidecarPort, {
      title,
      project_id: projectId,
      due_date: newTodoDue.value,
      remind_at: newTodoRemind.value || newTodoDue.value,
      priority: settings.taskPrefs.defaultPriority,
    });
    newTodoTitle.value = '';
    newTodoDue.value = '';
    newTodoRemind.value = '';
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
      <h2>任务管理</h2>
      <p class="hint">管理待办事项与提醒，可与项目关联</p>
      <button class="btn-refresh" :disabled="tasksStore.loading" @click="load">
        {{ tasksStore.loading ? '加载中…' : '刷新' }}
      </button>
    </header>

    <p v-if="tasksStore.error" class="error">{{ tasksStore.error }}</p>
    <p v-if="settings.sidecarStatus !== 'running'" class="warn">Sidecar 未运行，无法加载任务数据</p>

    <section v-if="tasksStore.reminders.length" class="reminders-banner">
      <h3>即将提醒</h3>
      <ul>
        <li v-for="r in tasksStore.reminders.slice(0, 5)" :key="r.job_id">
          <span class="remind-time">{{ formatRemindTime(r.run_at) }}</span>
          {{ r.title }}: {{ r.message }}
        </li>
      </ul>
    </section>

    <div class="panel">
      <div class="panel-head">
        <div class="filter-row">
          <label>所属项目</label>
          <select v-model="filterProjectId" @change="onFilterChange">
            <option value="">全部待办</option>
            <option v-for="p in tasksStore.projects" :key="p.id" :value="p.id">
              #{{ p.id }} {{ p.name }}
            </option>
          </select>
        </div>
        <label class="toggle">
          <input v-model="showCompleted" type="checkbox" />
          显示已完成
        </label>
      </div>

      <div class="inline-add">
        <input v-model="newTodoTitle" placeholder="快速添加待办…" @keydown.enter="addTodo" />
        <button @click="addTodo">添加</button>
      </div>
      <div class="datetime-row">
        <input v-model="newTodoDue" type="datetime-local" title="截止日期" />
        <input v-model="newTodoRemind" type="datetime-local" title="提醒时间" />
      </div>

      <ul class="todo-list">
        <li v-for="t in filteredTodos" :key="t.id" :class="{ done: t.completed }">
          <input type="checkbox" :checked="t.completed" @change="toggleTodo(t.id)" />
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
}

.warn {
  color: var(--text-highlight);
  font-size: 13px;
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

.remind-time {
  color: var(--text-highlight);
  margin-right: 8px;
}

.panel {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
}

.panel-head {
  margin-bottom: 12px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.filter-row label {
  font-size: 13px;
  color: var(--text-secondary);
}

.filter-row select {
  flex: 1;
  background: var(--bg-code);
  border: 1px solid var(--border);
  color: var(--text-primary);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
}

.toggle {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
}

.inline-add {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
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
  padding: 0 12px;
  cursor: pointer;
}

.datetime-row {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
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

.todo-list {
  list-style: none;
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

.btn-del {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 18px;
}

.btn-del:hover {
  color: var(--danger);
}

.empty {
  color: var(--text-muted);
  font-size: 12px;
  padding: 12px;
}
</style>
