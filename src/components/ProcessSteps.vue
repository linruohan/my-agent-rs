<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useSessionStore } from '@/stores/session';
import ToolCallCard from '@/components/ToolCallCard.vue';
import { formatDuration } from '@/utils/formatDuration';
import type { Message } from '@/types';

const props = defineProps<{
  tools: Message[];
  durationMs?: number;
  inProgress?: boolean;
  defaultExpanded?: boolean;
}>();

const sessionStore = useSessionStore();
const expanded = ref(props.defaultExpanded ?? false);

watch(
  () => props.defaultExpanded,
  (next) => {
    if (next !== undefined) expanded.value = next;
  }
);

watch(
  () => props.inProgress,
  (active, wasActive) => {
    if (wasActive && !active) expanded.value = false;
  }
);

const summary = computed(() => {
  const n = props.tools.length;
  if (props.inProgress) {
    return n ? `正在处理 ${n} 个步骤…` : '正在处理…';
  }
  if (props.durationMs != null) {
    const time = formatDuration(props.durationMs);
    return n ? `执行了 ${n} 个步骤 · ${time}` : time;
  }
  return n ? `执行了 ${n} 个步骤` : '';
});

function toolStatus(toolMsg: Message): 'running' | 'done' | undefined {
  const tc = sessionStore.pendingToolCalls.get(toolMsg.id);
  if (tc?.status === 'running') return 'running';
  return undefined;
}

function toggle() {
  expanded.value = !expanded.value;
}
</script>

<template>
  <div class="process-steps">
    <button type="button" class="process-header" @click="toggle">
      <span class="chevron" :class="{ expanded }">▾</span>
      <span class="summary">{{ summary }}</span>
    </button>
    <div v-show="expanded" class="process-body">
      <ToolCallCard
        v-for="tool in tools"
        :key="tool.id"
        compact
        :name="tool.toolName || ''"
        :category="tool.category"
        :content="tool.content"
        :args="sessionStore.pendingToolCalls.get(tool.id)?.args"
        :citations="tool.citations"
        :status="toolStatus(tool)"
      />
    </div>
  </div>
</template>

<style scoped>
.process-steps {
  width: 100%;
  min-width: 0;
  max-width: 100%;
}

.process-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  font-size: 13px;
  font-family: inherit;
  text-align: left;
  min-width: 0;
  max-width: 100%;
}

.process-header:hover {
  color: var(--text-secondary);
}

.chevron {
  display: inline-block;
  font-size: 11px;
  line-height: 1;
  transition: transform 0.2s ease;
  transform: rotate(-90deg);
}

.chevron.expanded {
  transform: rotate(0deg);
}

.summary {
  line-height: 1.4;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.process-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 4px 0 10px;
  padding: 4px 0 4px 12px;
  border-left: 2px solid var(--border);
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
}
</style>
