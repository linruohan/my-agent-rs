<script setup lang="ts">
import { computed } from 'vue';
import { useSettingsStore } from '@/stores/settings';
import { openExternalUrl } from '@/utils/nativeOpen';
import { formatToolContent } from '@/utils/formatToolContent';
import { formatArgsForDisplay } from '@/utils/formatToolArgs';

const props = defineProps<{
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
const displayContent = computed(() =>
  formatToolContent(props.name, props.content ?? '', settings.appearance.toolCallDisplay)
);

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
    <div class="header" :class="{ 'no-body': compact && !showTechnical && !displayContent && !citations?.length }">
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
      <code>{{ formatArgsForDisplay(args) }}</code>
    </div>
    <div v-if="displayContent" class="content">{{ displayContent }}</div>
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
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
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
  overflow: auto;
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
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
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
  flex: 1;
  min-width: 0;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.spinner {
  margin-left: auto;
}

.args {
  background: var(--bg-input);
  border-radius: 4px;
  padding: 8px;
  margin-bottom: 8px;
  max-width: 100%;
  min-width: 0;
  overflow: auto;
  max-height: 160px;
}

.args code {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.content {
  color: var(--text-secondary);
  line-height: 1.4;
  min-width: 0;
  max-width: 100%;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  overflow: auto;
  max-height: 160px;
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
