import {
  fetchSidecarAuthToken,
  sidecarAuthHeaders,
  sidecarBaseUrl,
} from '@/utils/sidecarFetch';

export async function getMemoryRest(
  port: number,
  namespace: string,
  key: string,
  token?: string | null
): Promise<Record<string, unknown>> {
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const resp = await fetch(
    `${sidecarBaseUrl(port)}/memory/${encodeURIComponent(namespace)}/${encodeURIComponent(key)}`,
    { headers: sidecarAuthHeaders(auth, { json: true }) }
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
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const resp = await fetch(
    `${sidecarBaseUrl(port)}/memory/${encodeURIComponent(namespace)}/${encodeURIComponent(key)}`,
    {
      method: 'PUT',
      headers: sidecarAuthHeaders(auth, { json: true }),
      body: JSON.stringify({ value }),
    }
  );
  if (!resp.ok) throw new Error(`memory set failed: ${resp.status}`);
}
