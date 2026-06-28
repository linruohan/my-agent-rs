import {
  DEFAULT_APPEARANCE,
  type ColorMode,
  type InlinePreviewMode,
  type ToolCallDisplayMode,
} from '@/utils/themes';

/** Fields persisted in localStorage (UI-only). Sidecar-backed settings live in YAML on the server. */
export type LocalPersistedSettings = {
  appearance: {
    uiLanguage: string;
    colorMode: ColorMode;
    themeId: string;
    windowTransparency: number;
    toolCallDisplay: ToolCallDisplayMode;
    inlinePreview: InlinePreviewMode;
  };
  projectPrefs: {
    defaultStatus: string;
    autoIndexDocs: boolean;
  };
  taskPrefs: {
    defaultPriority: string;
    showCompleted: boolean;
    defaultRemindHours: number;
  };
  toolKeys: Record<string, string>;
  lastTokenUsage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null;
};

const STORAGE_KEY = 'pa-agent-settings';

/** Legacy blob keys that are now owned by Sidecar (user_settings.yaml / llm_user.yaml / workspace). */
const LEGACY_SIDECAR_FIELD_KEYS = [
  'provider',
  'temperature',
  'customBaseUrl',
  'customModel',
  'customProviders',
  'providerModels',
  'workspacePath',
  'hitlTimeoutSec',
  'maxTokens',
  'searchBackend',
  'conversationPrefs',
  'memoryPrefs',
  'notificationPrefs',
] as const;

export function defaultLocalSettings(): LocalPersistedSettings {
  return {
    appearance: { ...DEFAULT_APPEARANCE },
    projectPrefs: { defaultStatus: 'active', autoIndexDocs: true },
    taskPrefs: { defaultPriority: 'medium', showCompleted: true, defaultRemindHours: 0 },
    toolKeys: {},
    lastTokenUsage: null,
  };
}

function stripLegacySidecarFields(raw: Record<string, unknown>): Record<string, unknown> {
  const next = { ...raw };
  for (const key of LEGACY_SIDECAR_FIELD_KEYS) {
    delete next[key];
  }
  return next;
}

export function loadLocalSettings(): LocalPersistedSettings {
  const defaults = defaultLocalSettings();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const cleaned = stripLegacySidecarFields(parsed);
    const hadLegacy = LEGACY_SIDECAR_FIELD_KEYS.some((k) => k in parsed);
    if (hadLegacy) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...defaults, ...cleaned }));
    }
    return {
      appearance: {
        ...defaults.appearance,
        ...(cleaned.appearance as LocalPersistedSettings['appearance'] | undefined),
      },
      projectPrefs: {
        ...defaults.projectPrefs,
        ...(cleaned.projectPrefs as LocalPersistedSettings['projectPrefs'] | undefined),
      },
      taskPrefs: {
        ...defaults.taskPrefs,
        ...(cleaned.taskPrefs as LocalPersistedSettings['taskPrefs'] | undefined),
      },
      toolKeys: (cleaned.toolKeys as Record<string, string>) ?? defaults.toolKeys,
      lastTokenUsage:
        (cleaned.lastTokenUsage as LocalPersistedSettings['lastTokenUsage']) ??
        defaults.lastTokenUsage,
    };
  } catch {
    return defaults;
  }
}

export function saveLocalSettings(data: LocalPersistedSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

/** Remove Sidecar-owned keys after a successful settings save (idempotent). */
export function purgeLegacySidecarFieldsFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    if (!LEGACY_SIDECAR_FIELD_KEYS.some((k) => k in parsed)) return;
    const local = loadLocalSettings();
    saveLocalSettings(local);
  } catch {
    /* ignore */
  }
}
