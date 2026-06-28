import { ref, watch } from 'vue';
import { defineStore } from 'pinia';

const STORAGE_KEY = 'pa-agent-settings';
const WORKSPACE_KEY = 'pa-workspace-path';

type StoredSettings = {
  provider: string;
  temperature: number;
  customBaseUrl: string;
  customModel: string;
  providerModels: Record<string, string>;
  workspacePath: string;
  toolKeys: Record<string, string>;
  projectPrefs: {
    defaultStatus: string;
    autoIndexDocs: boolean;
  };
  taskPrefs: {
    defaultPriority: string;
    showCompleted: boolean;
    defaultRemindHours: number;
  };
  hitlTimeoutSec: number;
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
  const providerModels = ref<Record<string, string>>(stored.providerModels ?? {});
  const workspacePath = ref(stored.workspacePath ?? localStorage.getItem(WORKSPACE_KEY) ?? '~/AssistantWorkspace');
  const toolKeys = ref<Record<string, string>>(stored.toolKeys ?? {});
  const projectPrefs = ref(
    stored.projectPrefs ?? { defaultStatus: 'active', autoIndexDocs: true }
  );
  const taskPrefs = ref(
    stored.taskPrefs ?? { defaultPriority: 'medium', showCompleted: true, defaultRemindHours: 0 }
  );
  const hitlTimeoutSec = ref(stored.hitlTimeoutSec ?? 300);
  const lastTurnDurationMs = ref<number | null>(null);

  watch(
    [provider, temperature, customBaseUrl, customModel, providerModels, workspacePath, toolKeys, projectPrefs, taskPrefs, hitlTimeoutSec],
    () => {
      saveStored({
        provider: provider.value,
        temperature: temperature.value,
        customBaseUrl: customBaseUrl.value,
        customModel: customModel.value,
        providerModels: { ...providerModels.value },
        workspacePath: workspacePath.value,
        toolKeys: { ...toolKeys.value },
        projectPrefs: { ...projectPrefs.value },
        taskPrefs: { ...taskPrefs.value },
        hitlTimeoutSec: hitlTimeoutSec.value,
      });
      localStorage.setItem(WORKSPACE_KEY, workspacePath.value);
    },
    { deep: true }
  );

  function setSidecarPort(port: number) {
    sidecarPort.value = port;
  }

  function setWsConnected(connected: boolean) {
    wsConnected.value = connected;
  }

  function setSidecarStatus(status: typeof sidecarStatus.value) {
    sidecarStatus.value = status;
  }

  function setLastTurnDuration(ms: number | null) {
    lastTurnDurationMs.value = ms;
  }

  function getSelectedModel(providerName?: string): string | undefined {
    const p = providerName ?? provider.value;
    if (p === 'custom') return customModel.value.trim() || undefined;
    if (p === 'ollama') return customModel.value.trim() || undefined;
    return providerModels.value[p];
  }

  function setSelectedModel(providerName: string, model: string) {
    if (providerName === 'custom' || providerName === 'ollama') {
      customModel.value = model;
    } else {
      providerModels.value = { ...providerModels.value, [providerName]: model };
    }
  }

  function applyLlmConfig(cfg: {
    default_provider?: string;
    custom?: { base_url?: string; model?: string };
    provider_models?: Record<string, string>;
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
    if (cfg.provider_models) {
      providerModels.value = { ...providerModels.value, ...cfg.provider_models };
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
    providerModels,
    workspacePath,
    toolKeys,
    projectPrefs,
    taskPrefs,
    hitlTimeoutSec,
    lastTurnDurationMs,
    setSidecarPort,
    setWsConnected,
    setSidecarStatus,
    setLastTurnDuration,
    getSelectedModel,
    setSelectedModel,
    applyLlmConfig,
  };
});
