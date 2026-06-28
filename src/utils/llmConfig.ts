import type { CustomProviderEntry } from '@/stores/settings';

export function isUserCustomProviderId(id: string): boolean {
  return id === 'custom' || id.startsWith('custom_');
}

export function slugProviderId(name: string): string {
  const base = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '');
  return `custom_${base || 'gateway'}_${Date.now().toString(36).slice(-4)}`;
}

export function buildLlmConfigPayload(settings: {
  provider: string;
  customProviders: CustomProviderEntry[];
  providerModels: Record<string, string>;
  customModel: string;
}) {
  const custom_providers = settings.customProviders
    .map((e) => ({
      id: e.id,
      name: e.name.trim(),
      base_url: e.baseUrl.trim(),
      model: e.model.trim(),
    }))
    .filter((e) => e.id && e.name && e.base_url && e.model);

  const provider_models = { ...settings.providerModels };
  if (settings.provider === 'ollama' && settings.customModel.trim()) {
    provider_models.ollama = settings.customModel.trim();
  }

  return {
    default_provider: settings.provider,
    custom_providers,
    provider_models,
  };
}

export function mapCustomProvidersFromApi(
  raw: Array<{ id?: string; name?: string; base_url?: string; model?: string }> | undefined
): CustomProviderEntry[] {
  if (!raw?.length) return [];
  return raw
    .map((e) => ({
      id: String(e.id ?? '').trim(),
      name: String(e.name ?? e.id ?? '').trim(),
      baseUrl: String(e.base_url ?? '').trim(),
      model: String(e.model ?? '').trim(),
    }))
    .filter((e) => e.id && e.baseUrl && e.model);
}
