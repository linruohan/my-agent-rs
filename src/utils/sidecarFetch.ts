import { useSettingsStore } from '@/stores/settings';
import { isTauriEnv } from '@/utils/tauri';

export async function parseResponseError(resp: Response): Promise<string> {
  try {
    const data = await resp.json();
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join('; ');
    }
    if (data.message) return String(data.message);
    return JSON.stringify(data);
  } catch {
    return resp.statusText || `HTTP ${resp.status}`;
  }
}

export async function sidecarRequest(path: string, options: RequestInit = {}): Promise<Response> {
  const settings = useSettingsStore();
  if (settings.sidecarStatus !== 'running') {
    throw new Error('Sidecar 未就绪，请稍候再试');
  }
  const url = `http://127.0.0.1:${settings.sidecarPort}${path}`;
  try {
    return await fetch(url, options);
  } catch (e) {
    if (e instanceof TypeError) {
      throw new Error(
        `无法连接 Sidecar（端口 ${settings.sidecarPort}），请确认服务已启动`
      );
    }
    throw e;
  }
}

export async function sidecarJson<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json');
  }
  const resp = await sidecarRequest(path, { ...options, headers });
  if (!resp.ok) {
    throw new Error(await parseResponseError(resp));
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export async function resolveProviderApiKey(
  providerId: string,
  typedKey?: string
): Promise<string | null> {
  const trimmed = typedKey?.trim();
  if (trimmed) return trimmed;
  if (!isTauriEnv()) return null;
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    return await invoke<string>('get_api_key', { provider: providerId });
  } catch {
    return null;
  }
}
