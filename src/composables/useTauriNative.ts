import { onMounted, onUnmounted } from 'vue';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import { useSettingsStore } from '@/stores/settings';
import { useAgentWs } from '@/composables/useAgentWs';
import { isTauriEnv } from '@/utils/tauri';
import { logStartupMilestone } from '@/utils/startupTiming';

type SidecarStatus = 'stopped' | 'starting' | 'running' | 'error';

function normalizeStatus(raw: unknown): SidecarStatus {
  if (typeof raw === 'string') {
    if (raw === 'stopped' || raw === 'starting' || raw === 'running' || raw === 'error') {
      return raw;
    }
  }
  return 'stopped';
}

export function useTauriNative() {
  const settings = useSettingsStore();
  const { connect, disconnect } = useAgentWs();
  let unlisteners: UnlistenFn[] = [];
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  async function pollStatus() {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const result = await invoke<[unknown, number | null]>('get_sidecar_status');
      const status = normalizeStatus(result[0]);
      const port = result[1];

      settings.setSidecarStatus(status);
      if (port && port !== settings.sidecarPort) {
        disconnect();
        settings.setSidecarPort(port);
      }
      if (status === 'running' && port) {
        logStartupMilestone('Sidecar running', { port });
        connect();
        if (pollTimer) {
          clearInterval(pollTimer);
          pollTimer = null;
        }
      }
    } catch {
      /* ignore poll errors */
    }
  }

  async function setup() {
    if (!isTauriEnv()) {
      connect();
      return;
    }

    settings.setSidecarStatus('starting');

    try {
      unlisteners.push(
        await listen<number>('sidecar-port', (e) => {
          disconnect();
          settings.setSidecarPort(e.payload);
          settings.setSidecarStatus('running');
          connect();
        })
      );

      unlisteners.push(
        await listen<unknown>('sidecar-status', (e) => {
          const status = normalizeStatus(e.payload);
          settings.setSidecarStatus(status);
          if (status === 'running') {
            connect();
          }
        })
      );

      await pollStatus();

      pollTimer = setInterval(async () => {
        if (settings.sidecarStatus === 'running' && settings.wsConnected) {
          if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
          }
          return;
        }
        await pollStatus();
      }, 1500);
    } catch (err) {
      console.error('Tauri native setup failed:', err);
      settings.setSidecarStatus('error');
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
