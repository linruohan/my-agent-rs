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
      <span v-if="settings.lastTokenUsage?.total_tokens" class="status-sep">·</span>
      <span v-if="settings.lastTokenUsage?.total_tokens" title="上轮 Token 用量">
        {{ settings.lastTokenUsage.total_tokens }} tok
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
  color: var(--text-muted);
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
  background: var(--success);
}

.status-dot.err {
  background: var(--danger);
}

.status-text {
  color: var(--text-muted);
}

.status-sep {
  color: var(--text-muted);
}

.sidecar.running {
  color: var(--success);
}

.sidecar.error {
  color: var(--danger);
}

.sidecar.starting {
  color: var(--warning);
}

.provider-tag {
  color: var(--text-muted);
  background: var(--bg-hover);
  padding: 2px 8px;
  border-radius: 4px;
}

.version {
  color: var(--text-muted);
}
</style>
