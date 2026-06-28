import { ref } from 'vue';
import { defineStore } from 'pinia';
import { fetchMemorySummaryRest } from '@/utils/sidecarConfig';
import { getMemoryRest, setMemoryRest } from '@/utils/sidecarMemory';
import { useSettingsStore } from '@/stores/settings';

export type MemorySummary = {
  preferences: Record<string, unknown>;
  history_stats: { total_entries: number; total_hits: number };
};

export const useMemoryStore = defineStore('memory', () => {
  const summary = ref<MemorySummary | null>(null);
  const prefsJson = ref('');
  const prefsDirty = ref(false);
  const prefsError = ref('');

  function markPrefsEdited(json: string) {
    prefsJson.value = json;
    prefsDirty.value = true;
  }

  async function refreshSummary(port?: number) {
    const settings = useSettingsStore();
    const p = port ?? settings.sidecarPort;
    if (settings.sidecarStatus !== 'running' || !p) {
      summary.value = null;
      return;
    }
    try {
      const data = await fetchMemorySummaryRest(p);
      if (!data) throw new Error('memory summary unavailable');
      summary.value = {
        preferences: (data.preferences as Record<string, unknown>) ?? {},
        history_stats: data.history_stats ?? { total_entries: 0, total_hits: 0 },
      };
    } catch {
      summary.value = null;
    }
  }

  async function refreshPreferences(port?: number, force = false) {
    prefsError.value = '';
    const settings = useSettingsStore();
    const p = port ?? settings.sidecarPort;
    if (settings.sidecarStatus !== 'running' || !p) {
      prefsJson.value = '';
      prefsDirty.value = false;
      return;
    }
    if (prefsDirty.value && !force) return;
    try {
      const prefs = await getMemoryRest(p, 'user', 'preferences');
      prefsJson.value =
        prefs && Object.keys(prefs).length ? JSON.stringify(prefs, null, 2) : '{\n}';
      prefsDirty.value = false;
    } catch (e) {
      prefsJson.value = '';
      prefsError.value = e instanceof Error ? e.message : String(e);
    }
  }

  /** After each chat turn: refresh summary; sync prefs JSON unless user is editing. */
  async function refreshAfterConversationTurn(port?: number) {
    await refreshSummary(port);
    await refreshPreferences(port);
  }

  async function savePreferences(port?: number): Promise<void> {
    prefsError.value = '';
    const settings = useSettingsStore();
    const p = port ?? settings.sidecarPort;
    if (settings.sidecarStatus !== 'running' || !p) {
      throw new Error('Sidecar 未运行');
    }
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(prefsJson.value || '{}') as Record<string, unknown>;
      if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
        throw new Error('偏好须为 JSON 对象');
      }
    } catch (e) {
      prefsError.value = e instanceof Error ? e.message : String(e);
      throw new Error('JSON 格式无效');
    }
    await setMemoryRest(p, 'user', 'preferences', parsed);
    await refreshSummary(p);
    await refreshPreferences(p, true);
  }

  return {
    summary,
    prefsJson,
    prefsDirty,
    prefsError,
    markPrefsEdited,
    refreshSummary,
    refreshPreferences,
    refreshAfterConversationTurn,
    savePreferences,
  };
});
