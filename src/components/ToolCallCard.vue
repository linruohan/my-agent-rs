<script setup lang="ts">
import { computed } from 'vue';
import { useSettingsStore } from '@/stores/settings';
import { openExternalUrl } from '@/utils/nativeOpen';

defineProps<{
  name: string;
  category?: string;
  content?: string;
  args?: Record<string, unknown>;
  status?: 'running' | 'done' | 'error';
  citations?: Array<{ title: string; url: string }>;
  compact?: boolean;
}>();

const settings = useSettingsStore();
const showTechnical = computed(() => settings.appearance.toolCallDisplay === 'technical');

const categoryLabels: Record<string, string> = {
  capability: '通用能力',
  business: '助理事务',
  mcp: 'MCP 扩展',
};

const categoryColors: Record<string, string> = {
  capability: 'var(--accent)',
  business: 'var(--success)',
  mcp: 'var(--tool-mcp)',
};

async function onCitationClick(e: MouseEvent, url: string) {
  e.preventDefault();
  await openExternalUrl(url);
}
</script>

<template>
  <div class="tool-card" :class="{ compact }">
    <div class="header" :class="{ 'no-body': compact && !showTechnical && !content && !citations?.length }">
      <span
        class="badge"
        :style="{ background: categoryColors[category || 'capability'] || 'var(--text-muted)' }"
      >
        {{ categoryLabels[category || 'capability'] || category }}
      </span>
      <span class="name">{{ name }}</span>
      <span v-if="status === 'running'" class="spinner">⏳</span>
    </div>
    <div v-if="showTechnical && args && Object.keys(args).length" class="args">
      <code>{{ JSON.stringify(args, null, 2) }}</code>
    </div>
    <div v-if="content" class="content">{{ content }}</div>
    <ul v-if="citations?.length" class="citations">
      <li v-for="(c, i) in citations" :key="i">
        <a href="#" @click="onCitationClick($event, c.url)">{{ c.title || c.url }}</a>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.tool-card.compact {
  padding: 8px 10px;
  font-size: 12px;
  background: var(--bg-panel);
}

.tool-card.compact .header {
  margin-bottom: 0;
}

.tool-card.compact .header.no-body {
  margin-bottom: 0;
}

.tool-card.compact .header:not(.no-body) {
  margin-bottom: 6px;
}

.tool-card.compact .content {
  font-size: 11px;
  max-height: 120px;
  overflow-y: auto;
}

.tool-card.compact .badge {
  font-size: 9px;
  padding: 1px 5px;
}

.tool-card.compact .name {
  font-size: 12px;
}

.tool-card {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  font-size: 13px;
}

.header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--text-on-accent);
  font-weight: 500;
}

.name {
  font-weight: 600;
  color: var(--text-primary);
}

.spinner {
  margin-left: auto;
}

.args {
  background: var(--bg-input);
  border-radius: 4px;
  padding: 8px;
  margin-bottom: 8px;
  overflow-x: auto;
}

.args code {
  font-size: 11px;
  color: var(--text-secondary);
}

.content {
  color: var(--text-secondary);
  line-height: 1.4;
}

.citations {
  margin-top: 8px;
  padding-left: 16px;
}

.citations a {
  color: var(--accent);
  font-size: 12px;
  cursor: pointer;
  text-decoration: none;
}

.citations a:hover {
  text-decoration: underline;
}
</style>
