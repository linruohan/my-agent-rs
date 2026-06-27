import { ref, watch } from 'vue';
import { defineStore } from 'pinia';

const STORAGE_KEY = 'pa-agent-settings';

type StoredSettings = {
  provider: string;
  temperature: number;
  customBaseUrl: string;
  customModel: string;
};

function loadStored(): Partial<StoredSettings> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveStored(data: StoredSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

export const useSettingsStore = defineStore('settings', () => {
  const stored = loadStored();
  const sidecarPort = ref(Number(import.meta.env.VITE_SIDECAR_PORT) || 8765);
  const wsConnected = ref(false);
  const sidecarStatus = ref<'stopped' | 'starting' | 'running' | 'error'>('stopped');
  const provider = ref(stored.provider ?? 'deepseek');
  const temperature = ref(stored.temperature ?? 0.7);
  const customBaseUrl = ref(stored.customBaseUrl ?? '');
  const customModel = ref(stored.customModel ?? '');

  watch([provider, temperature, customBaseUrl, customModel], () => {
    saveStored({
      provider: provider.value,
      temperature: temperature.value,
      customBaseUrl: customBaseUrl.value,
      customModel: customModel.value,
    });
  });

  function setSidecarPort(port: number) {
    sidecarPort.value = port;
  }

  function setWsConnected(connected: boolean) {
    wsConnected.value = connected;
  }

  function setSidecarStatus(status: typeof sidecarStatus.value) {
    sidecarStatus.value = status;
  }

  function applyLlmConfig(cfg: {
    default_provider?: string;
    custom?: { base_url?: string; model?: string };
  }) {
    if (cfg.default_provider) {
      provider.value = cfg.default_provider;
    }
    if (cfg.custom?.base_url) {
      customBaseUrl.value = cfg.custom.base_url;
    }
    if (cfg.custom?.model) {
      customModel.value = cfg.custom.model;
    }
  }

  return {
    sidecarPort,
    wsConnected,
    sidecarStatus,
    provider,
    temperature,
    customBaseUrl,
    customModel,
    setSidecarPort,
    setWsConnected,
    setSidecarStatus,
    applyLlmConfig,
  };
});
