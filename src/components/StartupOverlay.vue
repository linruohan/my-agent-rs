<script setup lang="ts">
import { computed } from 'vue';
import { useSettingsStore } from '@/stores/settings';
import { isTauriEnv } from '@/utils/tauri';

const settings = useSettingsStore();
const inTauri = isTauriEnv();

const visible = computed(
  () =>
    inTauri &&
    (settings.sidecarStatus === 'starting' ||
      settings.sidecarStatus === 'error' ||
      (settings.sidecarStatus === 'running' && !settings.wsConnected))
);

const title = computed(() => {
  if (settings.sidecarStatus === 'error') return 'Sidecar 启动失败';
  if (settings.sidecarStatus === 'starting') return '正在启动 Agent 服务…';
  return '正在连接 WebSocket…';
});

const hint = computed(() => {
  if (settings.sidecarStatus === 'error') {
    return '请检查 Sidecar 日志，或点击下方重试。';
  }
  if (settings.sidecarStatus === 'starting') {
    return '首次启动可能需数秒（加载模型与工具）。';
  }
  return 'Sidecar 已就绪，正在建立会话连接。';
});

async function retry() {
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    settings.setSidecarStatus('starting');
    await invoke<number>('restart_sidecar');
  } catch {
    /* web dev fallback */
    settings.setSidecarStatus('running');
  }
}
</script>

<template>
  <div v-if="visible" class="overlay">
    <div class="card">
      <div class="spinner" />
      <h3>{{ title }}</h3>
      <p>{{ hint }}</p>
      <p v-if="settings.sidecarPort" class="port">端口 {{ settings.sidecarPort }}</p>
      <button v-if="settings.sidecarStatus === 'error'" class="retry" @click="retry">
        重试启动
      </button>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(9, 9, 11, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.card {
  text-align: center;
  max-width: 360px;
  padding: 32px;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 12px;
}

.spinner {
  width: 36px;
  height: 36px;
  margin: 0 auto 16px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

h3 {
  font-size: 16px;
  margin-bottom: 8px;
  color: var(--text-primary);
}

p {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}

.port {
  margin-top: 8px;
  color: var(--text-secondary);
}

.retry {
  margin-top: 16px;
  background: var(--accent);
  color: var(--text-on-accent);
  border: none;
  padding: 8px 20px;
  border-radius: 6px;
  cursor: pointer;
}
</style>
