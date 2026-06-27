import { ref } from 'vue';
import { defineStore } from 'pinia';

export const useSettingsStore = defineStore('settings', () => {
  const sidecarPort = ref(Number(import.meta.env.VITE_SIDECAR_PORT) || 8765);
  const wsConnected = ref(false);
  const sidecarStatus = ref<'stopped' | 'starting' | 'running' | 'error'>('stopped');
  const provider = ref('deepseek');
  const temperature = ref(0.7);

  function setSidecarPort(port: number) {
    sidecarPort.value = port;
  }

  function setWsConnected(connected: boolean) {
    wsConnected.value = connected;
  }

  function setSidecarStatus(status: typeof sidecarStatus.value) {
    sidecarStatus.value = status;
  }

  return {
    sidecarPort,
    wsConnected,
    sidecarStatus,
    provider,
    temperature,
    setSidecarPort,
    setWsConnected,
    setSidecarStatus,
  };
});
