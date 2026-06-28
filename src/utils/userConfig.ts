import type { useSettingsStore } from '@/stores/settings';
import { parseResponseError, sidecarBaseUrl } from '@/utils/sidecarFetch';
import { purgeLegacySidecarFieldsFromStorage } from '@/utils/settingsStorage';

export type UserAppConfig = {
  hitl?: {
    timeout_sec?: number;
    on_timeout?: string;
    notify_before_sec?: number;
  };
  llm?: {
    temperature?: number;
    max_tokens?: number;
  };
  web_search?: {
    backend?: string;
  };
  conversation?: {
    max_history_messages?: number;
    auto_title?: boolean;
  };
  memory?: {
    auto_learn?: boolean;
    history_recall?: boolean;
    history_similarity_min?: number;
    history_max_age_days?: number;
  };
  notifications?: {
    desktop_enabled?: boolean;
    sound_enabled?: boolean;
  };
};

type SettingsStore = ReturnType<typeof useSettingsStore>;

export async function loadUserConfigFromSidecar(port: number): Promise<UserAppConfig | null> {
  try {
    const resp = await fetch(`${sidecarBaseUrl(port)}/config/user`);
    if (!resp.ok) return null;
    return (await resp.json()) as UserAppConfig;
  } catch {
    return null;
  }
}

export function buildUserConfigPayload(store: SettingsStore): UserAppConfig {
  return {
    hitl: {
      timeout_sec: store.hitlTimeoutSec,
      on_timeout: 'reject',
      notify_before_sec: 30,
    },
    llm: {
      temperature: store.temperature,
      max_tokens: store.maxTokens,
    },
    web_search: {
      backend: store.searchBackend,
    },
    conversation: {
      max_history_messages: store.conversationPrefs.maxHistoryMessages,
      auto_title: store.conversationPrefs.autoTitle,
    },
    memory: {
      auto_learn: store.memoryPrefs.autoLearn,
      history_recall: store.memoryPrefs.historyRecall,
      history_similarity_min: store.memoryPrefs.historySimilarityMin,
      history_max_age_days: store.memoryPrefs.historyMaxAgeDays,
    },
    notifications: {
      desktop_enabled: store.notificationPrefs.desktopEnabled,
      sound_enabled: store.notificationPrefs.soundEnabled,
    },
  };
}

export async function syncUserConfigToSidecar(store: SettingsStore): Promise<void> {
  const payload = buildUserConfigPayload(store);
  const memory = payload.memory;
  if (memory?.history_max_age_days != null) {
    memory.history_max_age_days = Math.min(
      36500,
      Math.max(1, Math.round(memory.history_max_age_days))
    );
  }
  if (memory?.history_similarity_min != null) {
    memory.history_similarity_min = Math.min(
      1,
      Math.max(0.5, Number(memory.history_similarity_min))
    );
  }

  const resp = await fetch(`${sidecarBaseUrl(store.sidecarPort)}/config/user`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    throw new Error(await parseResponseError(resp));
  }
  purgeLegacySidecarFieldsFromStorage();
}

export function applyUserConfigToStore(store: SettingsStore, cfg: UserAppConfig) {
  if (cfg.hitl?.timeout_sec != null) store.hitlTimeoutSec = cfg.hitl.timeout_sec;
  if (cfg.llm?.temperature != null) store.temperature = cfg.llm.temperature;
  if (cfg.llm?.max_tokens != null) store.maxTokens = cfg.llm.max_tokens;
  if (cfg.web_search?.backend != null) store.searchBackend = cfg.web_search.backend;
  if (cfg.conversation) {
    if (cfg.conversation.max_history_messages != null) {
      store.conversationPrefs.maxHistoryMessages = cfg.conversation.max_history_messages;
    }
    if (cfg.conversation.auto_title != null) {
      store.conversationPrefs.autoTitle = cfg.conversation.auto_title;
    }
  }
  if (cfg.memory?.auto_learn != null) store.memoryPrefs.autoLearn = cfg.memory.auto_learn;
  if (cfg.memory?.history_recall != null) {
    store.memoryPrefs.historyRecall = cfg.memory.history_recall;
  }
  if (cfg.memory?.history_similarity_min != null) {
    store.memoryPrefs.historySimilarityMin = cfg.memory.history_similarity_min;
  }
  if (cfg.memory?.history_max_age_days != null) {
    store.memoryPrefs.historyMaxAgeDays = cfg.memory.history_max_age_days;
  }
  if (cfg.notifications) {
    if (cfg.notifications.desktop_enabled != null) {
      store.notificationPrefs.desktopEnabled = cfg.notifications.desktop_enabled;
    }
    if (cfg.notifications.sound_enabled != null) {
      store.notificationPrefs.soundEnabled = cfg.notifications.sound_enabled;
    }
  }
}

let userConfigHydrated = false;

/** Load Sidecar user_settings.yaml into Pinia once per session (Sidecar is source of truth). */
export async function hydrateUserConfigFromSidecar(port: number): Promise<boolean> {
  if (userConfigHydrated || !port) return false;
  const cfg = await loadUserConfigFromSidecar(port);
  if (!cfg) return false;
  userConfigHydrated = true;
  const { useSettingsStore } = await import('@/stores/settings');
  applyUserConfigToStore(useSettingsStore(), cfg);
  return true;
}

/** Reset hydration flag (tests or Sidecar restart). */
export function resetUserConfigHydration() {
  userConfigHydrated = false;
}
