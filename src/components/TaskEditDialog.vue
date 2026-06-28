<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { ProjectItem, SectionItem, TodoItem } from '@/stores/tasks';
import AppDatePicker from '@/components/AppDatePicker.vue';

export type TaskFormPayload = {
  title: string;
  description: string;
  due_date: string;
  remind_at: string;
  priority: string;
  tags: string[];
  project_id: number | null;
  section_id: number | null;
  pinned: boolean;
};

const props = defineProps<{
  open: boolean;
  mode: 'create' | 'edit';
  todo?: TodoItem | null;
  projects: ProjectItem[];
  sections: SectionItem[];
  inboxProjectId: number | null;
  availableLabels: string[];
  defaultProjectId?: number | null;
  defaultSectionId?: number | null;
}>();

const emit = defineEmits<{
  save: [payload: TaskFormPayload];
  cancel: [];
  'project-change': [projectId: number | null];
}>();

const title = ref('');
const description = ref('');
const dueDate = ref('');
const remindAt = ref('');
const priority = ref('normal');
const selectedTags = ref<string[]>([]);
const customTag = ref('');
const projectId = ref<number | null>(null);
const sectionId = ref<number | null>(null);
const pinned = ref(false);
const dialogError = ref('');

const dialogTitle = computed(() => (props.mode === 'create' ? 'New Item' : 'Edit Item'));
const submitLabel = computed(() => (props.mode === 'create' ? 'Add' : 'Save'));

const locationLabel = computed(() => {
  if (projectId.value == null || projectId.value === props.inboxProjectId) {
    return 'Inbox → 无section';
  }
  const proj = props.projects.find((p) => p.id === projectId.value);
  const sec = props.sections.find((s) => s.id === sectionId.value);
  const projName = proj?.name ?? `Project #${projectId.value}`;
  const secName = sec?.name ?? '无section';
  return `${projName} → ${secName}`;
});

const sectionOptions = computed(() =>
  props.sections.filter((s) => s.project_id === projectId.value)
);

const allLabelOptions = computed(() => {
  const set = new Set([...props.availableLabels, ...selectedTags.value]);
  return [...set].sort((a, b) => a.localeCompare(b, 'zh-CN'));
});

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return;
    dialogError.value = '';
    customTag.value = '';
    if (props.mode === 'edit' && props.todo) {
      const t = props.todo;
      title.value = t.title;
      description.value = t.description ?? '';
      dueDate.value = t.due_date ?? '';
      remindAt.value = t.remind_at ?? '';
      priority.value = t.priority || 'normal';
      selectedTags.value = [...(t.tags ?? [])];
      pinned.value = t.priority === 'high' || (t.tags ?? []).includes('pinned');
      projectId.value = t.project_id ?? props.inboxProjectId;
      sectionId.value =
        projectId.value === props.inboxProjectId ? null : (t.section_id ?? null);
    } else {
      title.value = '';
      description.value = '';
      dueDate.value = '';
      remindAt.value = '';
      priority.value = 'normal';
      selectedTags.value = [];
      pinned.value = false;
      projectId.value = props.defaultProjectId ?? props.inboxProjectId;
      sectionId.value = props.defaultSectionId ?? null;
    }
  }
);

function toggleTag(tag: string) {
  const idx = selectedTags.value.indexOf(tag);
  if (idx >= 0) selectedTags.value.splice(idx, 1);
  else selectedTags.value.push(tag);
}

function addCustomTag() {
  const tag = customTag.value.trim();
  if (!tag) return;
  if (!selectedTags.value.includes(tag)) selectedTags.value.push(tag);
  customTag.value = '';
}

function onProjectChange() {
  if (sectionId.value != null) {
    const sec = props.sections.find((s) => s.id === sectionId.value);
    if (!sec || sec.project_id !== projectId.value) sectionId.value = null;
  }
  emit('project-change', projectId.value);
}

function submit() {
  dialogError.value = '';
  if (!title.value.trim()) {
    dialogError.value = '请填写任务名称';
    return;
  }
  const tags = [...selectedTags.value.filter((t) => t !== 'pinned')];
  if (pinned.value && !tags.includes('pinned')) tags.push('pinned');
  const pri = pinned.value ? 'high' : priority.value;
  emit('save', {
    title: title.value.trim(),
    description: description.value.trim(),
    due_date: dueDate.value,
    remind_at: remindAt.value,
    priority: pri,
    tags,
    project_id: projectId.value,
    section_id: sectionId.value,
    pinned: pinned.value,
  });
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('cancel');
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="overlay" @click.self="emit('cancel')">
      <div class="dialog" role="dialog" aria-modal="true" @keydown="onKeydown">
        <header class="dialog-header">
          <h3>{{ dialogTitle }}</h3>
          <button type="button" class="btn-close" aria-label="关闭" @click="emit('cancel')">×</button>
        </header>

        <div class="dialog-body">
          <div class="task-card">
            <div class="title-row">
              <span class="check-icon">☐</span>
              <input v-model="title" type="text" class="title-input" placeholder="Task name…" />
              <button
                type="button"
                class="pin-btn"
                :class="{ active: pinned }"
                title="置顶"
                @click="pinned = !pinned"
              >
                📌
              </button>
            </div>

            <textarea
              v-model="description"
              class="desc-input"
              placeholder="Add description…"
              rows="3"
            />

            <div v-if="allLabelOptions.length" class="tags-row">
              <label v-for="tag in allLabelOptions" :key="tag" class="tag-check">
                <input
                  type="checkbox"
                  :checked="selectedTags.includes(tag)"
                  @change="toggleTag(tag)"
                />
                {{ tag }}
              </label>
            </div>

            <div class="tag-add">
              <input
                v-model="customTag"
                type="text"
                placeholder="新标签…"
                @keydown.enter.prevent="addCustomTag"
              />
              <button type="button" class="btn-mini" @click="addCustomTag">+</button>
            </div>

            <div class="location">{{ locationLabel }}</div>

            <div class="meta-row">
              <div class="field-inline">
                <label>项目</label>
                <select v-model="projectId" @change="onProjectChange">
                  <option :value="inboxProjectId">Inbox</option>
                  <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
              </div>
              <div class="field-inline">
                <label>Section</label>
                <select v-model="sectionId" :disabled="!projectId || projectId === inboxProjectId">
                  <option :value="null">无section</option>
                  <option v-for="s in sectionOptions" :key="s.id" :value="s.id">{{ s.name }}</option>
                </select>
              </div>
            </div>

            <div class="action-bar">
              <div class="schedule-block">
                <span class="action-label">📅 Schedule</span>
                <AppDatePicker v-model="dueDate" mode="datetime" placeholder="截止日期" />
              </div>
              <div class="schedule-block">
                <span class="action-label">⏰ Remind</span>
                <AppDatePicker v-model="remindAt" mode="datetime" placeholder="提醒时间" />
              </div>
              <div class="field-inline pri-field">
                <label>优先级</label>
                <select v-model="priority" :disabled="pinned">
                  <option value="low">低</option>
                  <option value="normal">普通</option>
                  <option value="high">高</option>
                </select>
              </div>
            </div>
          </div>

          <p v-if="dialogError" class="error">{{ dialogError }}</p>
        </div>

        <footer class="dialog-footer">
          <button type="button" class="btn-cancel" @click="emit('cancel')">Cancel</button>
          <button type="button" class="btn-primary" @click="submit">{{ submitLabel }}</button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 24px;
}

.dialog {
  width: 100%;
  max-width: 560px;
  background: var(--bg-popover);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 16px 48px var(--shadow-color);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}

.dialog-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.btn-close {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 22px;
  cursor: pointer;
  line-height: 1;
}

.dialog-body {
  padding: 16px;
}

.task-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  background: var(--bg-panel);
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.check-icon {
  color: var(--text-muted);
  font-size: 16px;
}

.title-input {
  flex: 1;
  background: transparent;
  border: none;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  outline: none;
}

.pin-btn {
  background: none;
  border: none;
  cursor: pointer;
  opacity: 0.4;
  font-size: 16px;
}

.pin-btn.active {
  opacity: 1;
}

.desc-input {
  width: 100%;
  box-sizing: border-box;
  background: transparent;
  border: none;
  resize: vertical;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 10px;
  outline: none;
  font-family: inherit;
}

.tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-bottom: 8px;
}

.tag-check {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

.tag-add {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}

.tag-add input {
  flex: 1;
  background: var(--bg-code);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  color: var(--text-primary);
}

.btn-mini {
  background: var(--btn-secondary-bg);
  border: none;
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 14px;
}

.location {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.meta-row {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}

.field-inline {
  flex: 1;
}

.field-inline label {
  display: block;
  font-size: 10px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.field-inline select {
  width: 100%;
  background: var(--bg-code);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 12px;
  color: var(--text-primary);
}

.action-bar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}

.schedule-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.action-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.pri-field select:disabled {
  opacity: 0.5;
}

.error {
  font-size: 12px;
  color: var(--danger);
  margin: 8px 0 0;
}

.dialog-footer {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

.btn-cancel {
  background: var(--btn-secondary-bg);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
}

.btn-primary {
  background: var(--accent);
  color: var(--text-on-accent);
  border: none;
  border-radius: 8px;
  padding: 10px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
}
</style>
