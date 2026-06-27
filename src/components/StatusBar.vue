<script setup lang="ts">
import { useSettingsStore } from '@/stores/settings';

const settings = useSettingsStore();
</script>

<template>
  <footer class="status-bar">
    <span>Provider: {{ settings.provider }}</span>
    <span :class="['ws', settings.wsConnected ? 'connected' : 'disconnected']">
      WebSocket: {{ settings.wsConnected ? '已连接' : '未连接' }}
    </span>
    <span :class="['sidecar', settings.sidecarStatus]">
      Sidecar: {{ settings.sidecarStatus }}
      <template v-if="settings.sidecarPort"> (port {{ settings.sidecarPort }})</template>
    </span>
  </footer>
</template>

<style scoped>
.status-bar {
  display: flex;
  gap: 24px;
  padding: 8px 16px;
  background: #16181d;
  border-top: 1px solid #2a2d35;
  font-size: 11px;
  color: #71717a;
}

.ws.connected {
  color: #10b981;
}

.ws.disconnected {
  color: #ef4444;
}

.sidecar.error {
  color: #ef4444;
}

.sidecar.starting {
  color: #f59e0b;
}
</style>
