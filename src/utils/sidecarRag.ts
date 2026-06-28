import {
  fetchSidecarAuthToken,
  sidecarAuthHeaders,
  sidecarBaseUrl,
} from '@/utils/sidecarFetch';

export async function listRagSourcesRest(port: number, token?: string | null): Promise<string[]> {
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const resp = await fetch(`${sidecarBaseUrl(port)}/rag/sources`, {
    headers: sidecarAuthHeaders(auth, { json: true }),
  });
  if (!resp.ok) throw new Error(`rag list failed: ${resp.status}`);
  const data = (await resp.json()) as { sources?: string[] };
  return data.sources ?? [];
}

export async function ingestRagRest(
  port: number,
  source: string,
  content: string,
  token?: string | null,
  path?: string
): Promise<string> {
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const resp = await fetch(`${sidecarBaseUrl(port)}/rag/ingest`, {
    method: 'POST',
    headers: sidecarAuthHeaders(auth, { json: true }),
    body: JSON.stringify({ source, content, path: path ?? '' }),
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
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const resp = await fetch(`${sidecarBaseUrl(port)}/rag/search`, {
    method: 'POST',
    headers: sidecarAuthHeaders(auth, { json: true }),
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
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const resp = await fetch(`${sidecarBaseUrl(port)}/rag/delete`, {
    method: 'POST',
    headers: sidecarAuthHeaders(auth, { json: true }),
    body: JSON.stringify({ source }),
  });
  if (!resp.ok) throw new Error(`rag delete failed: ${resp.status}`);
  const data = (await resp.json()) as { ok?: boolean };
  return !!data.ok;
}
