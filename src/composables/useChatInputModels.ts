import { computed, onMounted, ref } from 'vue';
import { useSettingsStore } from '@/stores/settings';
import { buildLlmConfigPayload, isUserCustomProviderId } from '@/utils/llmConfig';
import { fetchOpenAiCompatibleModels } from '@/utils/providerModels';
import { sidecarJson } from '@/utils/sidecarFetch';
import { isTauriEnv } from '@/utils/tauri';

export interface ProviderInfo {
  id: string;
  label: string;
  type: string;
  model: string;
  base_url?: string;
  is_custom?: boolean;
}

export interface ModelTestResult {
  ok: boolean;
  status_code: number;
}

export interface ModelOption {
  id: string;
  provider: string;
  providerLabel: string;
  model: string;
  label: string;
  test?: ModelTestResult | null;
  testing?: boolean;
}

export interface ModelGroup {
  provider: string;
  providerLabel: string;
  isPrimary: boolean;
  models: ModelOption[];
  loading?: boolean;
  testing?: boolean;
}

export function useChatInputModels() {
  const settings = useSettingsStore();
  const providerList = ref<ProviderInfo[]>([]);
  const modelsByProvider = ref<Record<string, string[]>>({});
  const testsByProvider = ref<Record<string, Record<string, ModelTestResult>>>({});
  const loadingProviders = ref<Set<string>>(new Set());
  const testingProviders = ref<Set<string>>(new Set());
  const loading = ref(false);

  async function fetchProviders() {
    loading.value = true;
    try {
      const base = `http://127.0.0.1:${settings.sidecarPort}`;
      const resp = await fetch(`${base}/providers`);
      if (resp.ok) {
        const data = (await resp.json()) as { providers?: ProviderInfo[] };
        providerList.value = data.providers || [];
      }
    } catch {
      providerList.value = [];
    } finally {
      loading.value = false;
    }
  }

  async function getStoredApiKey(providerId: string): Promise<string | null> {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      return await invoke<string>('get_api_key', { provider: providerId });
    } catch {
      return null;
    }
  }

  function resolveCustomBaseUrl(providerId: string, providerInfo?: ProviderInfo): string {
    const fromList = providerInfo?.base_url?.trim();
    if (fromList) return fromList;
    const entry = settings.customProviders.find((e) => e.id === providerId);
    if (entry?.baseUrl.trim()) return entry.baseUrl.trim();
    if (providerId === 'custom') return settings.customBaseUrl.trim();
    return '';
  }

  function isCustomProvider(providerId: string, providerInfo?: ProviderInfo): boolean {
    return Boolean(providerInfo?.is_custom) || isUserCustomProviderId(providerId);
  }

  async function fetchCustomProviderModels(
    providerId: string,
    providerInfo: ProviderInfo | undefined,
    test: boolean
  ): Promise<{ models: string[]; tests?: Record<string, ModelTestResult> } | null> {
    const baseUrl = resolveCustomBaseUrl(providerId, providerInfo);
    const apiKey = await getStoredApiKey(providerId);
    if (!baseUrl || !apiKey) return null;

    try {
      const models = await fetchOpenAiCompatibleModels(baseUrl, apiKey);
      return { models };
    } catch {
      if (!test && settings.sidecarStatus === 'running') {
        try {
          const resp = await fetch(
            `http://127.0.0.1:${settings.sidecarPort}/providers/${encodeURIComponent(providerId)}/models`
          );
          if (resp.ok) {
            const data = (await resp.json()) as { models?: string[] };
            return { models: data.models || [] };
          }
        } catch {
          /* ignore */
        }
      }
      return null;
    }
  }

  function applyProviderModels(
    providerId: string,
    models: string[],
    tests?: Record<string, ModelTestResult>
  ) {
    modelsByProvider.value = {
      ...modelsByProvider.value,
      [providerId]: models,
    };
    if (tests) {
      testsByProvider.value = {
        ...testsByProvider.value,
        [providerId]: tests,
      };
    }
  }

  async function fetchProviderModels(providerId: string, options: { priority?: boolean; test?: boolean } = {}) {
    const { priority = false, test = false } = options;
    if (modelsByProvider.value[providerId]?.length && !priority && !test) return;

    if (test) {
      testingProviders.value = new Set([...testingProviders.value, providerId]);
    } else {
      loadingProviders.value = new Set([...loadingProviders.value, providerId]);
    }

    const providerInfo = providerList.value.find((p) => p.id === providerId);

    try {
      if (isCustomProvider(providerId, providerInfo)) {
        const preview = await fetchCustomProviderModels(providerId, providerInfo, test);
        if (preview?.models?.length) {
          applyProviderModels(providerId, preview.models, preview.tests);
          return;
        }
      }

      const base = `http://127.0.0.1:${settings.sidecarPort}`;
      const url = `${base}/providers/${encodeURIComponent(providerId)}/models${test ? '?test=true' : ''}`;
      const resp = await fetch(url);
      if (resp.ok) {
        const data = (await resp.json()) as {
          models?: string[];
          tests?: Record<string, ModelTestResult>;
          source?: string;
        };
        let models = data.models || [];

        if (
          isCustomProvider(providerId, providerInfo) &&
          models.length <= 1 &&
          data.source !== 'api'
        ) {
          const preview = await fetchCustomProviderModels(providerId, providerInfo, test);
          if (preview?.models?.length) {
            models = preview.models;
            applyProviderModels(providerId, models, preview.tests ?? data.tests);
            return;
          }
        }

        applyProviderModels(providerId, models, data.tests);
      }
    } catch {
      const fallback = providerList.value.find((p) => p.id === providerId)?.model;
      if (fallback) {
        modelsByProvider.value = { ...modelsByProvider.value, [providerId]: [fallback] };
      }
    } finally {
      const loadingNext = new Set(loadingProviders.value);
      loadingNext.delete(providerId);
      loadingProviders.value = loadingNext;
      const testingNext = new Set(testingProviders.value);
      testingNext.delete(providerId);
      testingProviders.value = testingNext;
    }
  }

  async function refreshModels() {
    await fetchProviders();
    const current = settings.provider;
    await fetchProviderModels(current, { priority: true, test: false });
    void fetchProviderModels(current, { priority: true, test: true });
    const others = providerList.value.map((p) => p.id).filter((id) => id !== current);
    await Promise.all(others.map((id) => fetchProviderModels(id)));
  }

  async function openModelMenu() {
    const current = settings.provider;
    await fetchProviders();
    await fetchProviderModels(current, { priority: true, test: false });
    void fetchProviderModels(current, { priority: true, test: true });
    void Promise.all(
      providerList.value
        .map((p) => p.id)
        .filter((id) => id !== current)
        .map((id) => fetchProviderModels(id))
    );
  }

  function buildOptionsForProvider(p: ProviderInfo): ModelOption[] {
    const models = modelsByProvider.value[p.id];
    const tests = testsByProvider.value[p.id];
    const isTesting = testingProviders.value.has(p.id);
    const selected = settings.getSelectedModel(p.id);
    const defaultModel = p.model;
    const modelNames =
      models && models.length
        ? models
        : selected
          ? [selected]
          : defaultModel
            ? [defaultModel]
            : [];

    return modelNames.map((m) => ({
      id: `${p.id}:${m}`,
      provider: p.id,
      providerLabel: p.label || p.id,
      model: m,
      label: m,
      test: tests?.[m] ?? null,
      testing: isTesting && !tests?.[m],
    }));
  }

  const modelGroups = computed<ModelGroup[]>(() => {
    const list =
      providerList.value.length > 0
        ? providerList.value
        : [{ id: settings.provider, label: settings.provider, type: '', model: '' }];

    const current = settings.provider;
    const ordered = [
      ...list.filter((p) => p.id === current),
      ...list.filter((p) => p.id !== current),
    ];

    return ordered.map((p) => ({
      provider: p.id,
      providerLabel: p.label || p.id,
      isPrimary: p.id === current,
      loading: loadingProviders.value.has(p.id),
      testing: testingProviders.value.has(p.id),
      models: buildOptionsForProvider(p),
    }));
  });

  const flatModelOptions = computed(() => modelGroups.value.flatMap((g) => g.models));

  const currentModelLabel = computed(() => {
    const selected = settings.getSelectedModel();
    if (selected) return selected;
    const p = providerList.value.find((item) => item.id === settings.provider);
    return p?.model || settings.provider;
  });

  function isOptionActive(option: ModelOption): boolean {
    if (settings.provider !== option.provider) return false;
    const selected = settings.getSelectedModel(option.provider);
    return (selected || currentModelLabel.value) === option.model;
  }

  function formatTestStatus(option: ModelOption): string {
    if (option.testing) return '测试中…';
    if (!option.test) return '';
    if (option.test.ok) return `${option.test.status_code} ok`;
    const code = option.test.status_code || 0;
    return `${code} fail`;
  }

  function isTestOk(option: ModelOption): boolean | null {
    if (option.testing) return null;
    if (!option.test) return null;
    return option.test.ok;
  }

  async function persistModelSelection() {
    const payload = buildLlmConfigPayload(settings);

    if (isTauriEnv()) {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('store_llm_user_config', { config: payload });
      if (settings.sidecarStatus === 'running') {
        try {
          await sidecarJson('/config/llm', {
            method: 'PUT',
            body: JSON.stringify(payload),
          });
        } catch {
          /* 本地 yaml 已写入，Sidecar 下次重启会加载 */
        }
      }
      return;
    }

    if (settings.sidecarStatus !== 'running') return;
    await sidecarJson('/config/llm', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  function selectModel(option: ModelOption) {
    settings.provider = option.provider;
    settings.setSelectedModel(option.provider, option.model);
    void persistModelSelection();
  }

  function filterModelGroups(query: string): ModelGroup[] {
    const q = query.trim().toLowerCase();
    if (!q) return modelGroups.value;

    return modelGroups.value
      .map((group) => {
        const providerMatch =
          group.provider.toLowerCase().includes(q) ||
          group.providerLabel.toLowerCase().includes(q);
        const models = group.models.filter(
          (o) =>
            providerMatch ||
            o.label.toLowerCase().includes(q) ||
            o.model.toLowerCase().includes(q)
        );
        return models.length ? { ...group, models } : null;
      })
      .filter((g): g is ModelGroup => g !== null);
  }

  function filterModels(query: string): ModelOption[] {
    return filterModelGroups(query).flatMap((g) => g.models);
  }

  onMounted(() => {
    void fetchProviders();
  });

  return {
    modelGroups,
    flatModelOptions,
    currentModelLabel,
    loading,
    fetchProviders,
    fetchProviderModels,
    refreshModels,
    openModelMenu,
    selectModel,
    filterModels,
    filterModelGroups,
    isOptionActive,
    formatTestStatus,
    isTestOk,
  };
}
