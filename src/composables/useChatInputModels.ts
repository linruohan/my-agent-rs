import { computed, onMounted, ref } from 'vue';
import { useSettingsStore } from '@/stores/settings';

export interface ModelOption {
  id: string;
  provider: string;
  model: string;
  label: string;
}

const PROVIDER_MODELS: Record<string, string> = {
  deepseek: 'deepseek-chat',
  openai: 'gpt-4o',
  anthropic: 'claude-sonnet-4-20250514',
  qwen: 'qwen-plus',
  ollama: 'qwen2.5:7b',
};

export function useChatInputModels() {
  const settings = useSettingsStore();
  const ollamaModels = ref<string[]>([]);
  const providers = ref<string[]>([]);
  const loading = ref(false);

  const modelOptions = computed<ModelOption[]>(() => {
    const opts: ModelOption[] = [];
    for (const p of providers.value.length ? providers.value : Object.keys(PROVIDER_MODELS)) {
      if (p === 'ollama') {
        const models = ollamaModels.value.length ? ollamaModels.value : [PROVIDER_MODELS.ollama];
        for (const m of models) {
          opts.push({
            id: `ollama:${m}`,
            provider: 'ollama',
            model: m,
            label: m,
          });
        }
        continue;
      }
      if (p === 'custom') {
        const m = settings.customModel.trim() || 'custom-model';
        opts.push({ id: `custom:${m}`, provider: 'custom', model: m, label: m });
        continue;
      }
      const model = PROVIDER_MODELS[p] || p;
      opts.push({ id: `${p}:${model}`, provider: p, model, label: model });
    }
    return opts;
  });

  const currentModelLabel = computed(() => {
    if (settings.provider === 'custom') {
      return settings.customModel.trim() || 'custom-model';
    }
    if (settings.provider === 'ollama') {
      const cur = modelOptions.value.find(
        (o) => o.provider === 'ollama' && o.model === (settings.customModel || PROVIDER_MODELS.ollama)
      );
      return cur?.label || PROVIDER_MODELS.ollama;
    }
    const opt = modelOptions.value.find((o) => o.provider === settings.provider);
    return opt?.label || settings.provider;
  });

  async function fetchProviders() {
    loading.value = true;
    try {
      const base = `http://127.0.0.1:${settings.sidecarPort}`;
      const resp = await fetch(`${base}/providers`);
      if (resp.ok) {
        const data = (await resp.json()) as { providers?: string[] };
        providers.value = data.providers || [];
      }
    } catch {
      providers.value = Object.keys(PROVIDER_MODELS).concat(['custom']);
    } finally {
      loading.value = false;
    }
  }

  async function fetchOllamaModels() {
    try {
      const resp = await fetch('http://localhost:11434/api/tags');
      if (!resp.ok) return;
      const data = (await resp.json()) as { models?: Array<{ name: string }> };
      ollamaModels.value = (data.models || []).map((m) => m.name);
    } catch {
      ollamaModels.value = [];
    }
  }

  function selectModel(option: ModelOption) {
    settings.provider = option.provider;
    if (option.provider === 'custom' || option.provider === 'ollama') {
      settings.customModel = option.model;
    }
  }

  function filterModels(query: string): ModelOption[] {
    const q = query.trim().toLowerCase();
    if (!q) return modelOptions.value;
    return modelOptions.value.filter(
      (o) =>
        o.label.toLowerCase().includes(q) ||
        o.provider.toLowerCase().includes(q) ||
        o.model.toLowerCase().includes(q)
    );
  }

  onMounted(() => {
    void fetchProviders();
    void fetchOllamaModels();
  });

  return {
    modelOptions,
    currentModelLabel,
    loading,
    fetchProviders,
    fetchOllamaModels,
    selectModel,
    filterModels,
  };
}
