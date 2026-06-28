<script setup lang="ts">
import { computed } from 'vue';
import { useSettingsStore } from '@/stores/settings';

const settings = useSettingsStore();
const appVersion = '0.1.0';

const modelLabel = computed(() => {
  const selected = settings.getSelectedModel();
  if (selected) return selected;
  if (settings.provider === 'custom') return settings.customModel || 'custom';
  return '';
});
</script>

<template>
  <footer class="status-bar">
    <div class="status-left">
      <span :class="['status-dot', settings.wsConnected ? 'ok' : 'err']" title="WebSocket" />
      <span class="status-text">
        {{ settings.wsConnected ? '已连接' : '未连接' }}
      </span>
      <span class="status-sep">·</span>
      <span :class="['sidecar', settings.sidecarStatus]">
        Sidecar {{ settings.sidecarStatus }}
      </span>
      <span v-if="settings.lastTurnDurationMs != null" class="status-sep">·</span>
      <span v-if="settings.lastTurnDurationMs != null">
        {{ settings.lastTurnDurationMs }}ms
      </span>
    </div>
    <div class="status-right">
      <span class="provider-tag">
        {{ settings.provider }}<template v-if="modelLabel"> / {{ modelLabel }}</template>
      </span>
      <span class="version"># v{{ appVersion }}</span>
    </div>
  </footer>
</template>

<style scoped>
.status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 20px;
  background: var(--bg-sidebar);
  border-top: 1px solid var(--border);
  font-size: 11px;
  color: #52525b;
  flex-shrink: 0;
}

.status-left,
.status-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.ok {
  background: #10b981;
}

.status-dot.err {
  background: #ef4444;
}

.status-text {
  color: #71717a;
}

.status-sep {
  color: #3f3f46;
}

.sidecar.running {
  color: #10b981;
}

.sidecar.error {
  color: #ef4444;
}

.sidecar.starting {
  color: #f59e0b;
}

.provider-tag {
  color: #71717a;
  background: #1f2128;
  padding: 2px 8px;
  border-radius: 4px;
}

.version {
  color: #52525b;
}
</style>
