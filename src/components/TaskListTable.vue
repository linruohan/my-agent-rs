<script setup lang="ts">
import type { TodoItem } from '@/stores/tasks';
import TaskListRow from '@/components/TaskListRow.vue';

defineProps<{
  todos: TodoItem[];
  labelColors: Map<string, string>;
}>();

const emit = defineEmits<{
  toggle: [todo: TodoItem];
  edit: [todo: TodoItem];
  remove: [id: number];
}>();
</script>

<template>
  <div class="task-table">
    <div class="task-table-head">
      <span class="col-check" />
      <span class="col-due">截止</span>
      <span class="col-title">任务</span>
      <span class="col-tags">标签</span>
      <span class="col-owner">负责人</span>
      <span class="col-remind">提醒</span>
      <span class="col-status">状态</span>
      <span class="col-actions" />
    </div>
    <ul class="task-list">
      <TaskListRow
        v-for="t in todos"
        :key="t.id"
        :todo="t"
        :label-colors="labelColors"
        @toggle="emit('toggle', t)"
        @edit="emit('edit', t)"
        @remove="emit('remove', t.id)"
      />
      <li v-if="!todos.length" class="empty">暂无任务</li>
    </ul>
  </div>
</template>

<style scoped>
.task-table {
  width: 100%;
}

.task-table-head {
  display: grid;
  grid-template-columns: 28px 72px minmax(120px, 1.6fr) minmax(100px, 1.2fr) 72px 72px 64px 64px;
  gap: 8px;
  padding: 0 12px 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.task-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.empty {
  color: var(--text-muted);
  font-size: 13px;
  padding: 12px 4px;
}

@media (max-width: 900px) {
  .task-table-head {
    display: none;
  }
}
</style>
