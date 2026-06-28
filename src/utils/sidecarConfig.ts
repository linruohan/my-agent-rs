import { sidecarBaseUrl } from '@/utils/sidecarFetch';

export type BootstrapPayload = {
  health?: Record<string, unknown>;
  tools?: {
    count?: number;
    enabled_count?: number;
    tools?: Array<{ name: string; description?: string; enabled?: boolean }>;
  };
  mcp?: {
    any_enabled?: boolean;
    loaded_count?: number;
    configured?: Record<string, { enabled?: boolean; transport?: string }>;
  } | null;
};

export type ProviderInfoPayload = {
  id: string;
  label: string;
  type: string;
  model: string;
  base_url?: string;
  is_custom?: boolean;
};

async function sidecarFetchJson<T>(
  port: number,
  path: string,
  init?: RequestInit
): Promise<T | null> {
  try {
    const resp = await fetch(`${sidecarBaseUrl(port)}${path}`, init);
    if (!resp.ok) return null;
    return (await resp.json()) as T;
  } catch {
    return null;
  }
}

export async function fetchSidecarHealth(port: number) {
  return sidecarFetchJson<Record<string, unknown>>(port, '/health');
}

export async function fetchSidecarBootstrap(port: number) {
  return sidecarFetchJson<BootstrapPayload>(port, '/bootstrap');
}

export async function fetchSidecarProviders(port: number) {
  return sidecarFetchJson<{ providers?: ProviderInfoPayload[] }>(port, '/providers');
}

export async function fetchProviderModelsRest(port: number, providerId: string, test = false) {
  const qs = test ? '?test=true' : '';
  return sidecarFetchJson<{
    models?: string[];
    tests?: Record<string, { ok: boolean; status_code: number }>;
    source?: string;
  }>(
    port,
    `/providers/${encodeURIComponent(providerId)}/models${qs}`
  );
}

export async function putSidecarJson(port: number, path: string, body: unknown): Promise<Response> {
  return fetch(`${sidecarBaseUrl(port)}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function postSidecar(port: number, path: string): Promise<Response> {
  return fetch(`${sidecarBaseUrl(port)}${path}`, { method: 'POST' });
}

export async function fetchMemorySummaryRest(port: number) {
  return sidecarFetchJson<{
    preferences?: Record<string, unknown>;
    history_stats?: { total_entries: number; total_hits: number };
  }>(port, '/memory/summary');
}

export async function waitSidecarHealthy(port: number, timeoutMs = 90000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const resp = await fetch(`${sidecarBaseUrl(port)}/health`);
      if (resp.ok) return;
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error('Sidecar 重启超时');
}
