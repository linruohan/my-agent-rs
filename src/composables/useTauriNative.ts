import { onMounted, onUnmounted } from 'vue';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import { useSettingsStore } from '@/stores/settings';
import { useAgentWs } from '@/composables/useAgentWs';

export function useTauriNative() {
  const settings = useSettingsStore();
  const { connect, disconnect } = useAgentWs();
  let unlisteners: UnlistenFn[] = [];
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  async function setup() {
    try {
      const { invoke } = await import('@tauri-apps/api/core');

      unlisteners.push(
        await listen<number>('sidecar-port', (e) => {
          disconnect();
          settings.setSidecarPort(e.payload);
          settings.setSidecarStatus('running');
          connect();
        })
      );

      unlisteners.push(
        await listen<string>('sidecar-status', (e) => {
          settings.setSidecarStatus(e.payload as typeof settings.sidecarStatus);
          if (e.payload === 'running') {
            connect();
          }
        })
      );

      pollTimer = setInterval(async () => {
        if (settings.sidecarStatus === 'running' && settings.wsConnected) {
          if (pollTimer) clearInterval(pollTimer);
          return;
        }
        try {
          const [status, port] = await invoke<[string, number | null]>('get_sidecar_status');
          settings.setSidecarStatus(status as typeof settings.sidecarStatus);
          if (port && port !== settings.sidecarPort) {
            disconnect();
            settings.setSidecarPort(port);
          }
          if (status === 'running' && port) {
            connect();
            if (pollTimer) clearInterval(pollTimer);
          }
        } catch {
          /* ignore poll errors */
        }
      }, 1500);

      const [status, port] = await invoke<[string, number | null]>('get_sidecar_status');
      settings.setSidecarStatus(status as typeof settings.sidecarStatus);
      if (port) {
        settings.setSidecarPort(port);
      }
      if (status === 'running' && port) {
        connect();
      }
    } catch {
      connect();
    }
  }

  onMounted(() => {
    setup();
  });

  onUnmounted(() => {
    if (pollTimer) clearInterval(pollTimer);
    unlisteners.forEach((fn) => fn());
  });

  return { setup };
}
