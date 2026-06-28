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

const dialogTitle = computed(() => (props.mode === 'create' ? '新建任务' : '编辑任务'));
const submitLabel = computed(() => (props.mode === 'create' ? '添加' : '保存'));

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
          <div class="field">
            <label>任务名称</label>
            <div class="title-row">
              <input
                v-model="title"
                type="text"
                class="control"
                placeholder="输入任务名称…"
              />
              <button
                type="button"
                class="pin-btn"
                :class="{ active: pinned }"
                title="置顶"
                aria-label="置顶"
                @click="pinned = !pinned"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                  <path d="M9.5 1.5 8 0 6.5 1.5v4.1L2.2 9.8l-.7.7 1.4 1.4.7-.7 2.8-2.8V14h2v-5.8l2.8 2.8.7.7 1.4-1.4-.7-.7-4.3-4.2V1.5z" />
                </svg>
              </button>
            </div>
          </div>

          <div class="field">
            <label>描述</label>
            <textarea
              v-model="description"
              class="control textarea"
              placeholder="添加描述（可选）"
              rows="3"
            />
          </div>

          <div v-if="allLabelOptions.length" class="field">
            <label>标签</label>
            <div class="tag-chips">
              <button
                v-for="tag in allLabelOptions"
                :key="tag"
                type="button"
                class="tag-chip"
                :class="{ active: selectedTags.includes(tag) }"
                @click="toggleTag(tag)"
              >
                {{ tag }}
              </button>
            </div>
          </div>

          <div class="field">
            <label>新标签</label>
            <div class="tag-add">
              <input
                v-model="customTag"
                type="text"
                class="control"
                placeholder="输入后按 Enter 或点击添加"
                @keydown.enter.prevent="addCustomTag"
              />
              <button type="button" class="btn-secondary" @click="addCustomTag">添加</button>
            </div>
          </div>

          <div class="field-row">
            <div class="field">
              <label>项目</label>
              <select v-model="projectId" class="control" @change="onProjectChange">
                <option :value="inboxProjectId">Inbox</option>
                <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </div>
            <div class="field">
              <label>Section</label>
              <select
                v-model="sectionId"
                class="control"
                :disabled="!projectId || projectId === inboxProjectId"
              >
                <option :value="null">无 section</option>
                <option v-for="s in sectionOptions" :key="s.id" :value="s.id">{{ s.name }}</option>
              </select>
            </div>
          </div>

          <div class="field-row field-row-3">
            <div class="field">
              <label>截止日期</label>
              <AppDatePicker v-model="dueDate" mode="datetime" placeholder="选择日期时间" />
            </div>
            <div class="field">
              <label>提醒时间</label>
              <AppDatePicker v-model="remindAt" mode="datetime" placeholder="选择提醒时间" />
            </div>
            <div class="field">
              <label>优先级</label>
              <select v-model="priority" class="control" :disabled="pinned">
                <option value="low">低</option>
                <option value="normal">普通</option>
                <option value="high">高</option>
              </select>
            </div>
          </div>

          <p v-if="dialogError" class="error">{{ dialogError }}</p>
        </div>

        <footer class="dialog-footer">
          <button type="button" class="btn-cancel" @click="emit('cancel')">取消</button>
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
  background: var(--overlay-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 24px;
}

.dialog {
  width: 100%;
  max-width: 520px;
  background: var(--bg-popover);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 16px 48px var(--shadow-color);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
}

.dialog-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.btn-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 8px;
  color: var(--text-muted);
  font-size: 22px;
  cursor: pointer;
  line-height: 1;
}

.btn-close:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.dialog-body {
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.field label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.field-row-3 {
  grid-template-columns: 1fr 1fr 1fr;
}

.control {
  width: 100%;
  box-sizing: border-box;
  background: var(--bg-input, var(--bg-code));
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  padding: 8px 12px;
  font-size: 13px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s ease;
}

.control::placeholder {
  color: var(--text-muted);
}

.control:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--accent) 35%, var(--border));
}

.control:focus {
  border-color: var(--accent);
}

.control:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.textarea {
  resize: vertical;
  min-height: 72px;
  line-height: 1.5;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-row .control {
  flex: 1;
  min-width: 0;
}

.pin-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-input, var(--bg-code));
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-muted);
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.pin-btn:hover {
  background: var(--bg-hover);
  color: var(--text-secondary);
}

.pin-btn.active {
  background: var(--accent-subtle);
  border-color: color-mix(in srgb, var(--accent) 45%, var(--border));
  color: var(--accent);
}

.tag-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-chip {
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg-input, var(--bg-code));
  color: var(--text-secondary);
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.tag-chip:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.tag-chip.active {
  background: var(--accent-subtle);
  border-color: color-mix(in srgb, var(--accent) 50%, var(--border));
  color: var(--accent);
}

.tag-add {
  display: flex;
  gap: 8px;
  align-items: center;
}

.tag-add .control {
  flex: 1;
  min-width: 0;
}

.btn-secondary {
  flex-shrink: 0;
  background: var(--btn-secondary-bg);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
}

.btn-secondary:hover {
  background: var(--bg-hover);
}

.field :deep(.app-date-picker) {
  width: 100%;
}

.field :deep(.app-date-picker .dp--input) {
  width: 100%;
  box-sizing: border-box;
}

.error {
  font-size: 12px;
  color: var(--danger);
  margin: 0;
}

.dialog-footer {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px 18px;
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

.btn-cancel:hover {
  background: var(--bg-hover);
}

.btn-primary {
  background: var(--accent);
  color: var(--text-on-accent);
  border: none;
  border-radius: 8px;
  padding: 10px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
}

.btn-primary:hover {
  background: var(--accent-hover, var(--accent));
}

@media (max-width: 560px) {
  .field-row,
  .field-row-3 {
    grid-template-columns: 1fr;
  }
}
</style>
