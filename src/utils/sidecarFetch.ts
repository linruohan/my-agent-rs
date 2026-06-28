import { useSettingsStore } from '@/stores/settings';
import { isTauriEnv } from '@/utils/tauri';

const AUTH_STORAGE_KEY = 'pa-sidecar-auth-token';

export function sidecarBaseUrl(port: number) {
  return `http://127.0.0.1:${port}`;
}

export function sidecarWsUrl(port: number) {
  return `ws://127.0.0.1:${port}/ws`;
}

export async function fetchSidecarAuthToken(port: number): Promise<string | null> {
  if (isTauriEnv()) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      return await invoke<string>('get_sidecar_token');
    } catch {
      /* fall through */
    }
  }
  try {
    const cached = localStorage.getItem(AUTH_STORAGE_KEY);
    if (cached) return cached;
    const resp = await fetch(`${sidecarBaseUrl(port)}/auth/token`);
    if (!resp.ok) return null;
    const data = (await resp.json()) as { token?: string };
    if (data.token) {
      localStorage.setItem(AUTH_STORAGE_KEY, data.token);
      return data.token;
    }
  } catch {
    /* ignore */
  }
  return null;
}

export function sidecarAuthHeaders(
  token: string | null,
  opts?: { json?: boolean; sse?: boolean }
): HeadersInit {
  const headers: Record<string, string> = {
    Accept: opts?.sse ? 'text/event-stream' : 'application/json',
  };
  if (opts?.json) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

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
  const url = `${sidecarBaseUrl(settings.sidecarPort)}${path}`;
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
