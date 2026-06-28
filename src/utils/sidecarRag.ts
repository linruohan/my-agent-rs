function sidecarBase(port: number) {
  return `http://127.0.0.1:${port}`;
}

async function fetchAuthToken(port: number): Promise<string | null> {
  try {
    const resp = await fetch(`${sidecarBase(port)}/auth/token`);
    if (!resp.ok) return null;
    const data = (await resp.json()) as { token?: string };
    return data.token ?? null;
  } catch {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      return await invoke<string>('get_sidecar_token');
    } catch {
      return null;
    }
  }
}

function jsonHeaders(token: string | null): HeadersInit {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export async function listRagSourcesRest(port: number, token?: string | null): Promise<string[]> {
  const auth = token ?? (await fetchAuthToken(port));
  const resp = await fetch(`${sidecarBase(port)}/rag/sources`, {
    headers: jsonHeaders(auth),
  });
  if (!resp.ok) throw new Error(`rag list failed: ${resp.status}`);
  const data = (await resp.json()) as { sources?: string[] };
  return data.sources ?? [];
}

export async function ingestRagRest(
  port: number,
  source: string,
  content: string,
  token?: string | null
): Promise<string> {
  const auth = token ?? (await fetchAuthToken(port));
  const resp = await fetch(`${sidecarBase(port)}/rag/ingest`, {
    method: 'POST',
    headers: jsonHeaders(auth),
    body: JSON.stringify({ source, content }),
  });
  if (!resp.ok) {
    const err = (await resp.json().catch(() => ({}))) as { detail?: { message?: string } };
    throw new Error(err.detail?.message ?? `rag ingest failed: ${resp.status}`);
  }
  const data = (await resp.json()) as { result?: string };
  return data.result ?? '';
}

export async function searchRagRest(
  port: number,
  query: string,
  topK = 6,
  token?: string | null
): Promise<Array<{ source: string; content: string; score: number }>> {
  const auth = token ?? (await fetchAuthToken(port));
  const resp = await fetch(`${sidecarBase(port)}/rag/search`, {
    method: 'POST',
    headers: jsonHeaders(auth),
    body: JSON.stringify({ query, top_k: topK }),
  });
  if (!resp.ok) throw new Error(`rag search failed: ${resp.status}`);
  const data = (await resp.json()) as {
    results?: Array<{ source: string; content: string; score: number }>;
  };
  return data.results ?? [];
}

export async function deleteRagSourceRest(
  port: number,
  source: string,
  token?: string | null
): Promise<boolean> {
  const auth = token ?? (await fetchAuthToken(port));
  const resp = await fetch(`${sidecarBase(port)}/rag/delete`, {
    method: 'POST',
    headers: jsonHeaders(auth),
    body: JSON.stringify({ source }),
  });
  if (!resp.ok) throw new Error(`rag delete failed: ${resp.status}`);
  const data = (await resp.json()) as { ok?: boolean };
  return !!data.ok;
}

export async function getMemoryRest(
  port: number,
  namespace: string,
  key: string,
  token?: string | null
): Promise<Record<string, unknown>> {
  const auth = token ?? (await fetchAuthToken(port));
  const resp = await fetch(
    `${sidecarBase(port)}/memory/${encodeURIComponent(namespace)}/${encodeURIComponent(key)}`,
    { headers: jsonHeaders(auth) }
  );
  if (!resp.ok) throw new Error(`memory get failed: ${resp.status}`);
  const data = (await resp.json()) as { value?: Record<string, unknown> };
  return data.value ?? {};
}

export async function setMemoryRest(
  port: number,
  namespace: string,
  key: string,
  value: Record<string, unknown>,
  token?: string | null
): Promise<void> {
  const auth = token ?? (await fetchAuthToken(port));
  const resp = await fetch(
    `${sidecarBase(port)}/memory/${encodeURIComponent(namespace)}/${encodeURIComponent(key)}`,
    {
      method: 'PUT',
      headers: jsonHeaders(auth),
      body: JSON.stringify({ value }),
    }
  );
  if (!resp.ok) throw new Error(`memory set failed: ${resp.status}`);
}
