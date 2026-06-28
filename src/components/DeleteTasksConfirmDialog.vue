<script setup lang="ts">
import { computed } from 'vue';
import type { TodoItem } from '@/stores/tasks';
import {
  deleteHintFor,
  priorityLabel,
  type DeleteTargetKind,
} from '@/utils/deleteConfirm';

const props = defineProps<{
  open: boolean;
  kind: DeleteTargetKind;
  targetName: string;
  incomplete: TodoItem[];
  completed: TodoItem[];
}>();

const emit = defineEmits<{
  confirm: [];
  cancel: [];
}>();

const hasIncomplete = computed(() => props.incomplete.length > 0);
const hasTasks = computed(() => props.incomplete.length + props.completed.length > 0);

const dialogTitle = computed(() => {
  const name = props.targetName;
  if (props.kind === 'task') {
    return hasIncomplete.value ? '删除任务 - 尚未完成' : '删除任务 - 已完成';
  }
  const label = props.kind === 'project' ? '项目' : 'Section';
  if (hasIncomplete.value) return `删除${label}「${name}」- 存在未完成任务`;
  if (hasTasks.value) return `删除${label}「${name}」- 所有任务已完成`;
  return `删除${label}「${name}」`;
});

const summaryText = computed(() => {
  if (hasIncomplete.value) {
    return `共 ${props.incomplete.length + props.completed.length} 个任务，其中 ${props.incomplete.length} 个尚未完成。`;
  }
  if (hasTasks.value) {
    return `共 ${props.completed.length} 个任务，已全部完成。`;
  }
  return '无关联任务。';
});

const hintText = computed(() => deleteHintFor(props.kind));

function formatDue(due: string): string {
  const trimmed = due?.trim();
  return trimmed || '无截止日期';
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="overlay" @click.self="emit('cancel')">
      <div class="dialog" role="alertdialog" aria-modal="true">
        <header class="dialog-header">
          <h3>{{ dialogTitle }}</h3>
          <button type="button" class="btn-close" aria-label="关闭" @click="emit('cancel')">×</button>
        </header>

        <div class="dialog-body">
          <p class="summary" :class="{ warn: hasIncomplete }">{{ summaryText }}</p>
          <p class="hint">{{ hintText }}</p>

          <section v-if="hasIncomplete" class="task-block">
            <h4>未完成任务</h4>
            <ul class="task-list incomplete">
              <li v-for="task in incomplete" :key="task.id">
                <span class="status-dot" aria-hidden="true" />
                <div class="task-info">
                  <span class="task-title">{{ task.title }}</span>
                  <span class="task-meta">
                    {{ formatDue(task.due_date) }} · 优先级 {{ priorityLabel(task.priority) }}
                  </span>
                </div>
              </li>
            </ul>
          </section>

          <section v-if="!hasIncomplete && completed.length" class="task-block">
            <h4>已完成任务</h4>
            <ul class="task-list completed">
              <li v-for="task in completed" :key="task.id">
                <span class="status-dot done" aria-hidden="true">✓</span>
                <div class="task-info">
                  <span class="task-title">{{ task.title }}</span>
                  <span class="task-meta">
                    {{ formatDue(task.due_date) }} · 优先级 {{ priorityLabel(task.priority) }}
                  </span>
                </div>
              </li>
            </ul>
          </section>

          <section v-if="hasIncomplete && completed.length" class="task-block muted">
            <h4>已完成任务（{{ completed.length }}）</h4>
            <ul class="task-list completed compact">
              <li v-for="task in completed" :key="task.id">
                <span class="status-dot done" aria-hidden="true">✓</span>
                <span class="task-title">{{ task.title }}</span>
              </li>
            </ul>
          </section>

          <p class="confirm-ask">确认要删除吗？</p>
        </div>

        <footer class="dialog-footer">
          <button type="button" class="btn-cancel" @click="emit('cancel')">取消</button>
          <button type="button" class="btn-danger" @click="emit('confirm')">确认删除</button>
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
  z-index: 2100;
  padding: 24px;
}

.dialog {
  width: 100%;
  max-width: 480px;
  max-height: min(80vh, 640px);
  display: flex;
  flex-direction: column;
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
  flex-shrink: 0;
}

.dialog-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.btn-close {
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  padding: 0 4px;
}

.dialog-body {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.summary {
  margin: 0 0 8px;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.summary.warn {
  color: var(--warning, #d97706);
}

.hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}

.task-block {
  margin-bottom: 16px;
}

.task-block.muted h4 {
  color: var(--text-muted);
}

.task-block h4 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.task-list {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.task-list li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
}

.task-list li:last-child {
  border-bottom: none;
}

.task-list.incomplete li {
  background: rgba(217, 119, 6, 0.06);
}

.task-list.completed li {
  background: rgba(34, 197, 94, 0.05);
}

.task-list.compact li {
  padding: 8px 12px;
}

.status-dot {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  margin-top: 2px;
  border-radius: 50%;
  border: 2px solid var(--warning, #d97706);
  background: transparent;
}

.status-dot.done {
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: var(--success, #22c55e);
  color: var(--text-on-accent, #fff);
  font-size: 10px;
  font-weight: 700;
}

.task-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.task-title {
  font-size: 14px;
  color: var(--text-primary);
  word-break: break-word;
}

.task-meta {
  font-size: 12px;
  color: var(--text-muted);
}

.confirm-ask {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.btn-cancel {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  background: var(--btn-secondary-bg, transparent);
  color: var(--text-primary);
}

.btn-danger {
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  background: var(--danger, #ef4444);
  color: var(--text-on-accent, #fff);
}

.btn-danger:hover {
  opacity: 0.9;
}
</style>
