<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useSettingsStore } from '@/stores/settings';

const settings = useSettingsStore();
const tools = ref<Array<{ name: string; description?: string; enabled?: boolean; category?: string }>>([]);
const loading = ref(true);

async function load() {
  loading.value = true;
  try {
    const base = `http://127.0.0.1:${settings.sidecarPort}`;
    const resp = await fetch(`${base}/bootstrap`);
    if (!resp.ok) return;
    const data = (await resp.json()) as {
      tools?: { tools?: Array<{ name: string; description?: string; enabled?: boolean; category?: string }> };
    };
    tools.value = data.tools?.tools || [];
  } catch {
    tools.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(() => void load());
</script>

<template>
  <div class="skills-view">
    <header>
      <h2>技能与工具</h2>
      <p class="hint">Sidecar 已注册的工具与 MCP 能力</p>
      <button type="button" class="btn-refresh" @click="load">刷新</button>
    </header>

    <div v-if="loading" class="status">加载中…</div>
    <div v-else-if="!tools.length" class="status">暂无工具，请确认 Sidecar 已启动</div>
    <ul v-else class="tool-grid">
      <li v-for="t in tools" :key="t.name" :class="{ disabled: t.enabled === false }">
        <div class="tool-name">{{ t.name }}</div>
        <div v-if="t.category" class="tool-cat">{{ t.category }}</div>
        <p v-if="t.description" class="tool-desc">{{ t.description }}</p>
        <span class="tool-status">{{ t.enabled ? '已启用' : '已禁用' }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.skills-view {
  flex: 1;
  overflow-y: auto;
  padding: 32px 40px;
}

header {
  margin-bottom: 24px;
}

header h2 {
  font-size: 20px;
  margin-bottom: 4px;
}

.hint {
  color: #71717a;
  font-size: 13px;
  margin-bottom: 12px;
}

.btn-refresh {
  background: #1f2128;
  border: 1px solid #2a2d35;
  color: #e4e4e7;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
}

.btn-refresh:hover {
  background: #252830;
}

.status {
  color: #71717a;
  font-size: 14px;
}

.tool-grid {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.tool-grid li {
  background: #16181d;
  border: 1px solid #2a2d35;
  border-radius: 12px;
  padding: 16px;
}

.tool-grid li.disabled {
  opacity: 0.55;
}

.tool-name {
  font-size: 14px;
  font-weight: 600;
  color: #e4e4e7;
  margin-bottom: 4px;
}

.tool-cat {
  font-size: 11px;
  color: #3b82f6;
  margin-bottom: 6px;
}

.tool-desc {
  font-size: 12px;
  color: #a1a1aa;
  margin: 0 0 8px;
  line-height: 1.5;
}

.tool-status {
  font-size: 11px;
  color: #71717a;
}
</style>
