<script setup lang="ts">
defineProps<{
  name: string;
  category?: string;
  content?: string;
  args?: Record<string, unknown>;
  status?: 'running' | 'done' | 'error';
  citations?: Array<{ title: string; url: string }>;
}>();

const categoryLabels: Record<string, string> = {
  capability: '通用能力',
  business: '助理事务',
  mcp: 'MCP 扩展',
};

const categoryColors: Record<string, string> = {
  capability: '#3b82f6',
  business: '#10b981',
  mcp: '#8b5cf6',
};
</script>

<template>
  <div class="tool-card">
    <div class="header">
      <span
        class="badge"
        :style="{ background: categoryColors[category || 'capability'] || '#71717a' }"
      >
        {{ categoryLabels[category || 'capability'] || category }}
      </span>
      <span class="name">{{ name }}</span>
      <span v-if="status === 'running'" class="spinner">⏳</span>
    </div>
    <div v-if="args && Object.keys(args).length" class="args">
      <code>{{ JSON.stringify(args, null, 2) }}</code>
    </div>
    <div v-if="content" class="content">{{ content }}</div>
    <ul v-if="citations?.length" class="citations">
      <li v-for="(c, i) in citations" :key="i">
        <a :href="c.url" target="_blank" rel="noopener">{{ c.title || c.url }}</a>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.tool-card {
  background: #16181d;
  border: 1px solid #2a2d35;
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
  color: white;
  font-weight: 500;
}

.name {
  font-weight: 600;
  color: #e4e4e7;
}

.spinner {
  margin-left: auto;
}

.args {
  background: #0f1117;
  border-radius: 4px;
  padding: 8px;
  margin-bottom: 8px;
  overflow-x: auto;
}

.args code {
  font-size: 11px;
  color: #a1a1aa;
}

.content {
  color: #a1a1aa;
  line-height: 1.4;
}

.citations {
  margin-top: 8px;
  padding-left: 16px;
}

.citations a {
  color: #3b82f6;
  font-size: 12px;
}
</style>
