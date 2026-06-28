<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { ProjectItem } from '@/stores/tasks';
import AppDatePicker from '@/components/AppDatePicker.vue';

export type ProjectFormPayload = {
  name: string;
  description: string;
  status: string;
  start_at: string;
  end_at: string;
  owner: string;
  remind_at: string;
};

const PROJECT_COLORS = [
  '#fca5a5', '#fdba74', '#fde047', '#bef264', '#86efac', '#5eead4',
  '#67e8f9', '#93c5fd', '#a5b4fc', '#c4b5fd', '#f0abfc', '#fda4af',
  '#e5e7eb', '#d1d5db', '#9ca3af', '#78716c', '#57534e', '#44403c',
  '#fecdd3', '#fed7aa', '#fef08a',
];

const props = defineProps<{
  open: boolean;
  mode: 'create' | 'edit';
  project?: ProjectItem | null;
}>();

const emit = defineEmits<{
  save: [payload: ProjectFormPayload];
  cancel: [];
  delete: [];
}>();

const name = ref('');
const description = ref('');
const status = ref('active');
const startAt = ref('');
const endAt = ref('');
const owner = ref('');
const remindAt = ref('');
const accentColor = ref(PROJECT_COLORS[7]);
const dialogError = ref('');

const dialogTitle = computed(() => (props.mode === 'create' ? 'New Project' : 'Edit Project'));
const submitLabel = computed(() => (props.mode === 'create' ? 'Add' : 'Save'));

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return;
    dialogError.value = '';
    if (props.mode === 'edit' && props.project) {
      const p = props.project;
      name.value = p.name;
      description.value = p.description ?? '';
      status.value = p.status || 'active';
      startAt.value = p.start_at ?? '';
      endAt.value = p.end_at ?? p.due_date ?? '';
      owner.value = p.owner ?? '';
      remindAt.value = p.remind_at ?? '';
    } else {
      name.value = '';
      description.value = '';
      status.value = 'active';
      startAt.value = '';
      endAt.value = '';
      owner.value = '';
      remindAt.value = '';
      accentColor.value = PROJECT_COLORS[7];
    }
  }
);

function submit() {
  dialogError.value = '';
  if (!name.value.trim()) {
    dialogError.value = '请填写项目名称';
    return;
  }
  emit('save', {
    name: name.value.trim(),
    description: description.value.trim(),
    status: status.value,
    start_at: startAt.value,
    end_at: endAt.value,
    owner: owner.value.trim(),
    remind_at: remindAt.value,
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
            <input v-model="name" type="text" placeholder="Project Name" />
          </div>

          <div class="field">
            <textarea v-model="description" placeholder="项目描述（可选）" rows="2" />
          </div>

          <div v-if="mode === 'edit'" class="field">
            <label>状态</label>
            <select v-model="status">
              <option value="planning">规划中</option>
              <option value="active">进行中</option>
              <option value="on_hold">暂停</option>
              <option value="completed">已完成</option>
              <option value="archived">已归档</option>
            </select>
          </div>

          <div class="color-section">
            <div class="color-preview" :style="{ background: accentColor }" />
            <div class="color-grid">
              <button
                v-for="c in PROJECT_COLORS"
                :key="c"
                type="button"
                class="color-swatch"
                :class="{ active: c === accentColor }"
                :style="{ background: c }"
                :aria-label="c"
                @click="accentColor = c"
              />
            </div>
          </div>

          <div class="field">
            <label>开始日期</label>
            <AppDatePicker v-model="startAt" mode="date" placeholder="开始日期" />
          </div>

          <div class="field">
            <label>截止日期</label>
            <AppDatePicker v-model="endAt" mode="date" placeholder="截止日期" />
          </div>

          <div class="field">
            <label>提醒</label>
            <AppDatePicker v-model="remindAt" mode="datetime" placeholder="提醒时间" />
          </div>

          <div class="field">
            <label>负责人</label>
            <input v-model="owner" type="text" placeholder="Owner" />
          </div>

          <p v-if="dialogError" class="error">{{ dialogError }}</p>
        </div>

        <footer class="dialog-footer" :class="{ 'with-delete': mode === 'edit' }">
          <button
            v-if="mode === 'edit'"
            type="button"
            class="btn-danger"
            @click="emit('delete')"
          >
            删除项目
          </button>
          <div class="footer-actions">
            <button type="button" class="btn-cancel" @click="emit('cancel')">Cancel</button>
            <button type="button" class="btn-primary" @click="submit">{{ submitLabel }}</button>
          </div>
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
  max-width: 480px;
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

.field {
  margin-bottom: 14px;
}

.field label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 6px;
}

.field input,
.field textarea,
.field select {
  width: 100%;
  box-sizing: border-box;
  background: var(--bg-input, var(--bg-code));
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  padding: 8px 12px;
  font-size: 13px;
  font-family: inherit;
}

.color-section {
  display: flex;
  gap: 12px;
  padding: 12px;
  margin-bottom: 14px;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 10px;
}

.color-preview {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  flex-shrink: 0;
}

.color-grid {
  display: grid;
  grid-template-columns: repeat(10, 1fr);
  gap: 6px;
  flex: 1;
}

.color-swatch {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  padding: 0;
}

.color-swatch.active {
  border-color: var(--text-primary);
  box-shadow: 0 0 0 2px var(--bg-popover);
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

.dialog-footer.with-delete {
  grid-template-columns: auto 1fr;
  align-items: center;
}

.footer-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.btn-danger {
  background: transparent;
  color: var(--danger);
  border: 1px solid color-mix(in srgb, var(--danger) 40%, transparent);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
}

.btn-danger:hover {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
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
