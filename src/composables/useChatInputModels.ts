import { computed, onMounted, ref } from 'vue';
import { useSettingsStore } from '@/stores/settings';

export interface ProviderInfo {
  id: string;
  label: string;
  type: string;
  model: string;
  base_url?: string;
}

export interface ModelOption {
  id: string;
  provider: string;
  providerLabel: string;
  model: string;
  label: string;
}

export interface ModelGroup {
  provider: string;
  providerLabel: string;
  isPrimary: boolean;
  models: ModelOption[];
  loading?: boolean;
}

export function useChatInputModels() {
  const settings = useSettingsStore();
  const providerList = ref<ProviderInfo[]>([]);
  const modelsByProvider = ref<Record<string, string[]>>({});
  const loadingProviders = ref<Set<string>>(new Set());
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

  async function fetchProviderModels(providerId: string, priority = false) {
    if (modelsByProvider.value[providerId]?.length && !priority) return;
    loadingProviders.value = new Set([...loadingProviders.value, providerId]);
    try {
      const base = `http://127.0.0.1:${settings.sidecarPort}`;
      const resp = await fetch(`${base}/providers/${encodeURIComponent(providerId)}/models`);
      if (resp.ok) {
        const data = (await resp.json()) as { models?: string[] };
        modelsByProvider.value = {
          ...modelsByProvider.value,
          [providerId]: data.models || [],
        };
      }
    } catch {
      const fallback = providerList.value.find((p) => p.id === providerId)?.model;
      if (fallback) {
        modelsByProvider.value = { ...modelsByProvider.value, [providerId]: [fallback] };
      }
    } finally {
      const next = new Set(loadingProviders.value);
      next.delete(providerId);
      loadingProviders.value = next;
    }
  }

  async function refreshModels() {
    await fetchProviders();
    const current = settings.provider;
    await fetchProviderModels(current, true);
    const others = providerList.value.map((p) => p.id).filter((id) => id !== current);
    await Promise.all(others.map((id) => fetchProviderModels(id)));
  }

  async function openModelMenu() {
    const current = settings.provider;
    await fetchProviders();
    await fetchProviderModels(current, true);
    void Promise.all(
      providerList.value
        .map((p) => p.id)
        .filter((id) => id !== current)
        .map((id) => fetchProviderModels(id))
    );
  }

  function buildOptionsForProvider(p: ProviderInfo): ModelOption[] {
    const models = modelsByProvider.value[p.id];
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

  async function persistModelSelection() {
    const payload = {
      default_provider: settings.provider,
      custom:
        settings.provider === 'custom'
          ? {
              base_url: settings.customBaseUrl.trim(),
              model: settings.customModel.trim(),
            }
          : undefined,
      provider_models: { ...settings.providerModels },
    };
    if (settings.provider === 'ollama' && settings.customModel.trim()) {
      payload.provider_models = {
        ...payload.provider_models,
        ollama: settings.customModel.trim(),
      };
    }

    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('store_llm_user_config', { config: payload });
      return;
    } catch {
      /* fall through */
    }

    const base = `http://127.0.0.1:${settings.sidecarPort}`;
    await fetch(`${base}/config/llm`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
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
  };
}
