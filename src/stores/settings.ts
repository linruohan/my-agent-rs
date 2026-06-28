import { ref, watch } from 'vue';
import { defineStore } from 'pinia';
import {
  type ColorMode,
  type InlinePreviewMode,
  type ToolCallDisplayMode,
} from '@/utils/themes';
import { isTauriEnv } from '@/utils/tauri';
import { mapCustomProvidersFromApi, isUserCustomProviderId } from '@/utils/llmConfig';
import { syncWorkspaceToSidecar } from '@/utils/workspaceConfig';
import { defaultLocalSettings, loadLocalSettings, saveLocalSettings } from '@/utils/settingsStorage';

export interface CustomProviderEntry {
  id: string;
  name: string;
  baseUrl: string;
  model: string;
}

export const useSettingsStore = defineStore('settings', () => {
  const local = loadLocalSettings();
  const sidecarPort = ref(Number(import.meta.env.VITE_SIDECAR_PORT) || 8765);
  const wsConnected = ref(false);
  const wsReadOnly = ref(false);
  const sidecarStatus = ref<'stopped' | 'starting' | 'running' | 'error'>(
    isTauriEnv() ? 'starting' : 'stopped'
  );

  // Sidecar-backed runtime settings (defaults until hydrate from Sidecar)
  const provider = ref('deepseek');
  const temperature = ref(0.7);
  const customBaseUrl = ref('');
  const customModel = ref('');
  const customProviders = ref<CustomProviderEntry[]>([]);
  const providerModels = ref<Record<string, string>>({});
  const workspacePath = ref('~/AssistantWorkspace');
  const hitlTimeoutSec = ref(300);
  const maxTokens = ref(4096);
  const searchBackend = ref('');
  const conversationPrefs = ref({ maxHistoryMessages: 50, autoTitle: true });
  const memoryPrefs = ref({
    autoLearn: false,
    historyRecall: true,
    historySimilarityMin: 0.72,
    historyMaxAgeDays: 90,
  });
  const notificationPrefs = ref({ desktopEnabled: true, soundEnabled: false });

  // Local UI-only settings (persisted in localStorage)
  const toolKeys = ref<Record<string, string>>(local.toolKeys);
  const projectPrefs = ref(local.projectPrefs);
  const taskPrefs = ref(local.taskPrefs);
  const appearance = ref(local.appearance);
  const lastTurnDurationMs = ref<number | null>(null);
  const lastTokenUsage = ref(local.lastTokenUsage);

  watch(
    [toolKeys, projectPrefs, taskPrefs, lastTokenUsage, appearance],
    () => {
      saveLocalSettings({
        toolKeys: { ...toolKeys.value },
        projectPrefs: { ...projectPrefs.value },
        taskPrefs: { ...taskPrefs.value },
        lastTokenUsage: lastTokenUsage.value ? { ...lastTokenUsage.value } : null,
        appearance: { ...appearance.value },
      });
    },
    { deep: true }
  );

  function setSidecarPort(port: number) {
    sidecarPort.value = port;
  }

  function setWsConnected(connected: boolean) {
    wsConnected.value = connected;
  }

  function setWsReadOnly(readOnly: boolean) {
    wsReadOnly.value = readOnly;
  }

  function setSidecarStatus(status: typeof sidecarStatus.value) {
    sidecarStatus.value = status;
  }

  function setLastTokenUsage(usage: typeof lastTokenUsage.value) {
    lastTokenUsage.value = usage;
  }

  function setLastTurnDuration(ms: number | null) {
    lastTurnDurationMs.value = ms;
  }

  function getSelectedModel(providerName?: string): string | undefined {
    const p = providerName ?? provider.value;
    if (isUserCustomProviderId(p)) {
      if (p === 'custom') {
        return customModel.value.trim() || undefined;
      }
      const entry = customProviders.value.find((e) => e.id === p);
      if (entry?.model.trim()) return entry.model.trim();
    }
    if (p === 'ollama') return customModel.value.trim() || undefined;
    return providerModels.value[p];
  }

  function setSelectedModel(providerName: string, model: string) {
    if (isUserCustomProviderId(providerName)) {
      if (providerName === 'custom') {
        customModel.value = model;
      } else {
        const idx = customProviders.value.findIndex((e) => e.id === providerName);
        if (idx >= 0) {
          customProviders.value[idx] = { ...customProviders.value[idx], model };
        }
        providerModels.value = { ...providerModels.value, [providerName]: model };
      }
    } else if (providerName === 'ollama') {
      customModel.value = model;
    } else {
      providerModels.value = { ...providerModels.value, [providerName]: model };
    }
  }

  function setWorkspacePath(path: string) {
    workspacePath.value = path;
    void syncWorkspaceToSidecar(path, sidecarPort.value);
  }

  function applyLlmConfig(cfg: {
    default_provider?: string;
    custom?: { base_url?: string; model?: string; name?: string };
    custom_providers?: Array<{ id?: string; name?: string; base_url?: string; model?: string }>;
    provider_models?: Record<string, string>;
  }) {
    if (cfg.default_provider) {
      provider.value = cfg.default_provider;
    }
    const fromList = mapCustomProvidersFromApi(cfg.custom_providers);
    if (fromList.length) {
      customProviders.value = fromList;
    } else if (cfg.custom?.base_url && cfg.custom?.model) {
      customProviders.value = [
        {
          id: 'custom',
          name: cfg.custom.name?.trim() || '自定义网关',
          baseUrl: cfg.custom.base_url,
          model: cfg.custom.model,
        },
      ];
      customBaseUrl.value = cfg.custom.base_url;
      customModel.value = cfg.custom.model;
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
    reconcileStaleCustomProvider();
  }

  function reconcileStaleCustomProvider() {
    if (provider.value !== 'custom') return;
    if (customProviders.value.some((e) => e.id === 'custom')) return;
    const first = customProviders.value[0];
    if (first?.id) provider.value = first.id;
  }

  function resetLocalUiSettings() {
    const defaults = defaultLocalSettings();
    toolKeys.value = defaults.toolKeys;
    projectPrefs.value = defaults.projectPrefs;
    taskPrefs.value = defaults.taskPrefs;
    appearance.value = defaults.appearance;
    lastTokenUsage.value = defaults.lastTokenUsage;
  }

  return {
    sidecarPort,
    wsConnected,
    wsReadOnly,
    sidecarStatus,
    provider,
    temperature,
    customBaseUrl,
    customModel,
    customProviders,
    providerModels,
    workspacePath,
    toolKeys,
    projectPrefs,
    taskPrefs,
    hitlTimeoutSec,
    maxTokens,
    searchBackend,
    conversationPrefs,
    memoryPrefs,
    notificationPrefs,
    appearance,
    lastTurnDurationMs,
    lastTokenUsage,
    setSidecarPort,
    setWsConnected,
    setWsReadOnly,
    setSidecarStatus,
    setLastTurnDuration,
    setLastTokenUsage,
    getSelectedModel,
    setSelectedModel,
    setWorkspacePath,
    applyLlmConfig,
    resetLocalUiSettings,
  };
});

export type {
  ColorMode,
  InlinePreviewMode,
  ToolCallDisplayMode,
};
