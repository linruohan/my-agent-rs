import { isTauriEnv } from '@/utils/tauri';
import { parseResponseError, sidecarBaseUrl } from '@/utils/sidecarFetch';
import { useSettingsStore } from '@/stores/settings';

/**
 * 通过 Tauri 原生网络请求拉取 OpenAI 兼容 /models 列表，不依赖 Sidecar。
 */
export async function fetchOpenAiCompatibleModels(
  baseUrl: string,
  apiKey: string
): Promise<string[]> {
  const trimmedUrl = baseUrl.trim();
  const trimmedKey = apiKey.trim();
  if (!trimmedUrl) throw new Error('请先填写 Base URL');
  if (!trimmedKey) throw new Error('请填写 API Key');

  if (isTauriEnv()) {
    const { invoke } = await import('@tauri-apps/api/core');
    const result = await invoke<{ models: string[] }>('fetch_openai_compatible_models', {
      baseUrl: trimmedUrl,
      apiKey: trimmedKey,
    });
    return result.models;
  }

  // Web 开发模式回退：仍走 Sidecar 预览接口
  const settings = useSettingsStore();
  const resp = await fetch(`${sidecarBaseUrl(settings.sidecarPort)}/providers/preview/models`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ base_url: trimmedUrl, api_key: trimmedKey }),
  });
  if (!resp.ok) {
    throw new Error(await parseResponseError(resp));
  }
  const data = (await resp.json()) as { models?: string[] };
  const models = data.models || [];
  if (!models.length) {
    throw new Error('未获取到模型，请检查 Base URL 与 API Key');
  }
  return models;
}
