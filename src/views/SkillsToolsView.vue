<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useSettingsStore } from '@/stores/settings';
import {
  loadToolsConfigFromSidecar,
  saveToolsConfigToSidecar,
  type ConfigurableTool,
} from '@/utils/toolsConfig';

const settings = useSettingsStore();
const tools = ref<ConfigurableTool[]>([]);
const loading = ref(true);
const saving = ref(false);
const message = ref('');

async function load() {
  loading.value = true;
  message.value = '';
  try {
    const data = await loadToolsConfigFromSidecar(settings.sidecarPort);
    tools.value = data?.tools ?? [];
  } catch {
    tools.value = [];
  } finally {
    loading.value = false;
  }
}

async function toggleTool(tool: ConfigurableTool, enabled: boolean) {
  tools.value = tools.value.map((t) => (t.name === tool.name ? { ...t, enabled } : t));
  saving.value = true;
  message.value = '';
  try {
    const data = await saveToolsConfigToSidecar(settings.sidecarPort, tools.value);
    tools.value = data.tools ?? tools.value;
    message.value = `${tool.name} 已${enabled ? '启用' : '禁用'}`;
  } catch (e) {
    tools.value = tools.value.map((t) =>
      t.name === tool.name ? { ...t, enabled: !enabled } : t
    );
    message.value = `保存失败: ${e instanceof Error ? e.message : String(e)}`;
  } finally {
    saving.value = false;
  }
}

onMounted(() => void load());
</script>

<template>
  <div class="skills-view">
    <header>
      <h2>技能与工具</h2>
      <p class="hint">Sidecar 已注册的工具与 MCP 能力</p>
      <div class="header-actions">
        <button type="button" class="btn-refresh" :disabled="loading || saving" @click="load">
          刷新
        </button>
        <span v-if="message" class="status-msg">{{ message }}</span>
      </div>
    </header>

    <div v-if="loading" class="status">加载中…</div>
    <div v-else-if="!tools.length" class="status">暂无工具，请确认 Sidecar 已启动</div>
    <ul v-else class="tool-grid">
      <li v-for="t in tools" :key="t.name" :class="{ disabled: t.enabled === false }">
        <div class="tool-head">
          <div class="tool-name">{{ t.name }}</div>
          <label class="tool-switch">
            <input
              type="checkbox"
              :checked="t.enabled !== false"
              :disabled="saving"
              @change="toggleTool(t, ($event.target as HTMLInputElement).checked)"
            />
            <span class="switch-label">{{ t.enabled !== false ? '已启用' : '已禁用' }}</span>
          </label>
        </div>
        <div v-if="t.category" class="tool-cat">{{ t.category }}</div>
        <p v-if="t.description" class="tool-desc">{{ t.description }}</p>
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
  color: var(--text-muted);
  font-size: 13px;
  margin-bottom: 12px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-msg {
  font-size: 13px;
  color: var(--text-secondary);
}

.btn-refresh {
  background: var(--bg-hover);
  border: 1px solid var(--border);
  color: var(--text-primary);
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
}

.btn-refresh:hover:not(:disabled) {
  background: var(--bg-hover);
}

.btn-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.status {
  color: var(--text-muted);
  font-size: 14px;
}

.tool-grid {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.tool-grid li {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
}

.tool-grid li.disabled {
  opacity: 0.55;
}

.tool-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}

.tool-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.tool-switch {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-muted);
  cursor: pointer;
  flex-shrink: 0;
}

.tool-switch input {
  cursor: pointer;
}

.tool-cat {
  font-size: 11px;
  color: var(--accent);
  margin-bottom: 6px;
}

.tool-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}
</style>
