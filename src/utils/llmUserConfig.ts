import type { useSettingsStore } from '@/stores/settings';
import { parseResponseError, sidecarBaseUrl } from '@/utils/sidecarFetch';
import { purgeLegacySidecarFieldsFromStorage } from '@/utils/settingsStorage';

export type LlmUserConfigPayload = {
  default_provider?: string;
  custom?: { base_url?: string; model?: string; name?: string };
  custom_providers?: Array<{ id?: string; name?: string; base_url?: string; model?: string }>;
  provider_models?: Record<string, string>;
};

type SettingsStore = ReturnType<typeof useSettingsStore>;

export async function loadLlmConfigFromSidecar(port: number): Promise<LlmUserConfigPayload | null> {
  try {
    const resp = await fetch(`${sidecarBaseUrl(port)}/config/llm`);
    if (!resp.ok) return null;
    return (await resp.json()) as LlmUserConfigPayload;
  } catch {
    return null;
  }
}

let llmConfigHydrated = false;

export async function hydrateLlmConfigFromSidecar(port: number): Promise<boolean> {
  if (llmConfigHydrated || !port) return false;
  const cfg = await loadLlmConfigFromSidecar(port);
  if (!cfg) return false;
  llmConfigHydrated = true;
  const { useSettingsStore } = await import('@/stores/settings');
  useSettingsStore().applyLlmConfig(cfg);
  return true;
}

export function resetLlmConfigHydration() {
  llmConfigHydrated = false;
}

export async function syncLlmConfigToSidecar(store: SettingsStore): Promise<void> {
  const { buildLlmConfigPayload } = await import('@/utils/llmConfig');
  const payload = buildLlmConfigPayload(store);
  const resp = await fetch(`${sidecarBaseUrl(store.sidecarPort)}/config/llm`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    throw new Error(await parseResponseError(resp));
  }
  purgeLegacySidecarFieldsFromStorage();
}
