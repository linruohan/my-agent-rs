<script setup lang="ts">
import { computed } from 'vue';
import { useSettingsStore } from '@/stores/settings';

const settings = useSettingsStore();

const visible = computed(
  () =>
    settings.sidecarStatus === 'starting' ||
    settings.sidecarStatus === 'error' ||
    (settings.sidecarStatus === 'running' && !settings.wsConnected)
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
  background: #16181d;
  border: 1px solid #2a2d35;
  border-radius: 12px;
}

.spinner {
  width: 36px;
  height: 36px;
  margin: 0 auto 16px;
  border: 3px solid #2a2d35;
  border-top-color: #3b82f6;
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
  color: #e4e4e7;
}

p {
  font-size: 13px;
  color: #71717a;
  line-height: 1.5;
}

.port {
  margin-top: 8px;
  color: #a1a1aa;
}

.retry {
  margin-top: 16px;
  background: #3b82f6;
  color: white;
  border: none;
  padding: 8px 20px;
  border-radius: 6px;
  cursor: pointer;
}
</style>
