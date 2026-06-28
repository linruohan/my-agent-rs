<script setup lang="ts">
import { ref } from 'vue';
import type { TodoItem } from '@/stores/tasks';
import { colorForLabel, labelChipStyle } from '@/utils/labelColors';
import {
  attachmentSummary,
  formatDueColumn,
  formatRemindColumn,
  hasTaskDetails,
  todoStatusLabel,
} from '@/utils/taskDisplay';

const props = defineProps<{
  todo: TodoItem;
  labelColors: Map<string, string>;
}>();

const emit = defineEmits<{
  toggle: [];
  edit: [];
  remove: [];
}>();

const detailOpen = ref(false);

function toggleDetail(e: Event) {
  e.stopPropagation();
  if (!hasTaskDetails(props.todo)) {
    emit('edit');
    return;
  }
  detailOpen.value = !detailOpen.value;
}
</script>

<template>
  <li :class="{ done: todo.completed, 'detail-open': detailOpen }" @click="emit('edit')">
    <input
      type="checkbox"
      class="col-check"
      :checked="todo.completed"
      @click.stop
      @change="emit('toggle')"
    />

    <span class="col-due" :title="todo.due_date || ''">{{ formatDueColumn(todo.due_date) }}</span>

    <span class="col-title" :title="todo.title">{{ todo.title }}</span>

    <div class="col-tags">
      <span
        v-for="tag in todo.tags ?? []"
        :key="tag"
        class="label-chip"
        :style="labelChipStyle(colorForLabel(tag, labelColors))"
      >
        {{ tag }}
      </span>
      <span v-if="!(todo.tags?.length)" class="muted">—</span>
    </div>

    <span class="col-owner" :title="todo.owner || ''">{{ todo.owner?.trim() || '—' }}</span>

    <span class="col-remind" :title="todo.remind_at || ''">{{ formatRemindColumn(todo.remind_at ?? '') }}</span>

    <span class="col-status">{{ todoStatusLabel(todo) }}</span>

    <div class="col-actions" @click.stop>
      <button
        type="button"
        class="btn-more"
        :title="hasTaskDetails(todo) ? '查看详情' : '编辑任务'"
        @click="toggleDetail"
      >
        ⋯
      </button>
      <button type="button" class="btn-del" title="删除" @click="emit('remove')">×</button>
    </div>

    <div v-if="detailOpen && hasTaskDetails(todo)" class="task-detail" @click.stop>
      <pre class="detail-text">{{ attachmentSummary(todo) }}</pre>
    </div>
  </li>
</template>

<style scoped>
li {
  display: grid;
  grid-template-columns: 28px 72px minmax(120px, 1.6fr) minmax(100px, 1.2fr) 72px 72px 64px 64px;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  margin-bottom: 6px;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
}

li.detail-open {
  grid-template-rows: auto auto;
}

li:hover {
  background: var(--bg-hover);
  border-color: color-mix(in srgb, var(--accent) 35%, var(--border));
}

li.done {
  opacity: 0.65;
  border-left-color: var(--text-muted);
}

li.done .col-title {
  text-decoration: line-through;
  color: var(--text-muted);
}

.col-check {
  margin: 0;
  cursor: pointer;
}

.col-due,
.col-owner,
.col-remind,
.col-status {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.col-title {
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  min-width: 0;
}

.label-chip {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 4px;
  white-space: nowrap;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.muted {
  color: var(--text-muted);
  font-size: 12px;
}

.col-status {
  font-size: 11px;
}

.col-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
}

.btn-more,
.btn-del {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  padding: 2px 4px;
  border-radius: 4px;
}

.btn-more:hover,
.btn-del:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.task-detail {
  grid-column: 1 / -1;
  margin-top: 4px;
  padding: 10px 12px;
  background: var(--bg-code);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.detail-text {
  margin: 0;
  font-family: inherit;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 900px) {
  li {
    grid-template-columns: 28px 64px 1fr 64px;
    grid-template-areas:
      'check due title actions'
      'check tags tags actions'
      'check owner remind status';
  }

  .col-check { grid-area: check; }
  .col-due { grid-area: due; }
  .col-title { grid-area: title; }
  .col-tags { grid-area: tags; }
  .col-owner { grid-area: owner; }
  .col-remind { grid-area: remind; }
  .col-status { grid-area: status; }
  .col-actions { grid-area: actions; }

  .task-detail {
    grid-column: 1 / -1;
  }
}
</style>
