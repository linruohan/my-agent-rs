import { ref, watch } from 'vue';
import { defineStore } from 'pinia';
import {
  DEFAULT_APPEARANCE,
  type ColorMode,
  type InlinePreviewMode,
  type ToolCallDisplayMode,
} from '@/utils/themes';
import { isTauriEnv } from '@/utils/tauri';
import { mapCustomProvidersFromApi, isUserCustomProviderId } from '@/utils/llmConfig';
import { syncWorkspaceToSidecar } from '@/utils/workspaceConfig';

const STORAGE_KEY = 'pa-agent-settings';
const WORKSPACE_KEY = 'pa-workspace-path';

export interface CustomProviderEntry {
  id: string;
  name: string;
  baseUrl: string;
  model: string;
}

type StoredSettings = {
  provider: string;
  temperature: number;
  customBaseUrl: string;
  customModel: string;
  customProviders: CustomProviderEntry[];
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
  maxTokens: number;
  searchBackend: string;
  conversationPrefs: {
    maxHistoryMessages: number;
    autoTitle: boolean;
  };
  memoryPrefs: {
    autoLearn: boolean;
    historyRecall: boolean;
    historySimilarityMin: number;
    historyMaxAgeDays: number;
  };
  notificationPrefs: {
    desktopEnabled: boolean;
    soundEnabled: boolean;
  };
  lastTokenUsage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null;
  appearance: {
    uiLanguage: string;
    colorMode: ColorMode;
    themeId: string;
    windowTransparency: number;
    toolCallDisplay: ToolCallDisplayMode;
    inlinePreview: InlinePreviewMode;
  };
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
  const sidecarStatus = ref<'stopped' | 'starting' | 'running' | 'error'>(
    isTauriEnv() ? 'starting' : 'stopped'
  );
  const provider = ref(stored.provider ?? 'deepseek');
  const temperature = ref(stored.temperature ?? 0.7);
  const customBaseUrl = ref(stored.customBaseUrl ?? '');
  const customModel = ref(stored.customModel ?? '');
  const customProviders = ref<CustomProviderEntry[]>(stored.customProviders ?? []);
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
  const maxTokens = ref(stored.maxTokens ?? 4096);
  const searchBackend = ref(stored.searchBackend ?? '');
  const conversationPrefs = ref(
    stored.conversationPrefs ?? { maxHistoryMessages: 50, autoTitle: true }
  );
  const memoryPrefs = ref(
    stored.memoryPrefs ?? {
      autoLearn: false,
      historyRecall: true,
      historySimilarityMin: 0.72,
      historyMaxAgeDays: 90,
    }
  );
  const notificationPrefs = ref(
    stored.notificationPrefs ?? { desktopEnabled: true, soundEnabled: false }
  );
  const appearance = ref({
    ...DEFAULT_APPEARANCE,
    ...stored.appearance,
  });
  const lastTurnDurationMs = ref<number | null>(null);
  const lastTokenUsage = ref<StoredSettings['lastTokenUsage']>(
    stored.lastTokenUsage ?? null
  );

  watch(
    [
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
      lastTokenUsage,
      appearance,
    ],
    () => {
      saveStored({
        provider: provider.value,
        temperature: temperature.value,
        customBaseUrl: customBaseUrl.value,
        customModel: customModel.value,
        customProviders: customProviders.value.map((e) => ({ ...e })),
        providerModels: { ...providerModels.value },
        workspacePath: workspacePath.value,
        toolKeys: { ...toolKeys.value },
        projectPrefs: { ...projectPrefs.value },
        taskPrefs: { ...taskPrefs.value },
        hitlTimeoutSec: hitlTimeoutSec.value,
        maxTokens: maxTokens.value,
        searchBackend: searchBackend.value,
        conversationPrefs: { ...conversationPrefs.value },
        memoryPrefs: { ...memoryPrefs.value },
        notificationPrefs: { ...notificationPrefs.value },
        lastTokenUsage: lastTokenUsage.value ? { ...lastTokenUsage.value } : null,
        appearance: { ...appearance.value },
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

  function setLastTokenUsage(usage: StoredSettings['lastTokenUsage']) {
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
  }

  return {
    sidecarPort,
    wsConnected,
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
    setSidecarStatus,
    setLastTurnDuration,
    setLastTokenUsage,
    getSelectedModel,
    setSelectedModel,
    setWorkspacePath,
    applyLlmConfig,
  };
});
