import {
  fetchSidecarAuthToken,
  sidecarAuthHeaders,
  sidecarBaseUrl,
} from '@/utils/sidecarFetch';

export type SessionRow = {
  thread_id: string;
  title: string;
  created_at: string;
  archived?: boolean;
};

export type HistoryMessage = {
  role: string;
  content: string;
  tool_name?: string;
};

export async function fetchSessionsRest(
  port: number,
  token?: string | null,
  includeArchived = false
): Promise<SessionRow[]> {
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const qs = includeArchived ? '?include_archived=true' : '';
  const resp = await fetch(`${sidecarBaseUrl(port)}/sessions${qs}`, {
    headers: sidecarAuthHeaders(auth),
  });
  if (!resp.ok) {
    throw new Error(`sessions list failed: ${resp.status}`);
  }
  const data = (await resp.json()) as { sessions?: SessionRow[] };
  return data.sessions ?? [];
}

export async function fetchArchivedSessionsRest(
  port: number,
  token?: string | null
): Promise<SessionRow[]> {
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const resp = await fetch(`${sidecarBaseUrl(port)}/sessions/archived`, {
    headers: sidecarAuthHeaders(auth),
  });
  if (!resp.ok) {
    throw new Error(`archived sessions failed: ${resp.status}`);
  }
  const data = (await resp.json()) as { sessions?: SessionRow[] };
  return data.sessions ?? [];
}

export async function fetchSessionHistoryRest(
  port: number,
  threadId: string,
  token?: string | null
): Promise<HistoryMessage[]> {
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const resp = await fetch(`${sidecarBaseUrl(port)}/sessions/${encodeURIComponent(threadId)}/history`, {
    headers: sidecarAuthHeaders(auth),
  });
  if (!resp.ok) {
    throw new Error(`session history failed: ${resp.status}`);
  }
  const data = (await resp.json()) as { messages?: HistoryMessage[] };
  return data.messages ?? [];
}

export async function createSessionRest(
  port: number,
  title?: string,
  token?: string | null
): Promise<SessionRow> {
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const resp = await fetch(`${sidecarBaseUrl(port)}/sessions`, {
    method: 'POST',
    headers: sidecarAuthHeaders(auth, { json: true }),
    body: JSON.stringify({ title: title ?? null }),
  });
  if (!resp.ok) {
    throw new Error(`session create failed: ${resp.status}`);
  }
  const data = (await resp.json()) as SessionRow & { ok?: boolean };
  return {
    thread_id: data.thread_id,
    title: data.title,
    created_at: data.created_at,
    archived: data.archived ?? false,
  };
}

export async function deleteSessionRest(
  port: number,
  threadId: string,
  token?: string | null
): Promise<void> {
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const resp = await fetch(`${sidecarBaseUrl(port)}/sessions/${encodeURIComponent(threadId)}`, {
    method: 'DELETE',
    headers: sidecarAuthHeaders(auth),
  });
  if (!resp.ok) {
    throw new Error(`session delete failed: ${resp.status}`);
  }
}

export async function archiveSessionRest(
  port: number,
  threadId: string,
  token?: string | null
): Promise<void> {
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const resp = await fetch(
    `${sidecarBaseUrl(port)}/sessions/${encodeURIComponent(threadId)}/archive`,
    { method: 'POST', headers: sidecarAuthHeaders(auth) }
  );
  if (!resp.ok) {
    throw new Error(`session archive failed: ${resp.status}`);
  }
}

export async function unarchiveSessionRest(
  port: number,
  threadId: string,
  token?: string | null
): Promise<void> {
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const resp = await fetch(
    `${sidecarBaseUrl(port)}/sessions/${encodeURIComponent(threadId)}/unarchive`,
    { method: 'POST', headers: sidecarAuthHeaders(auth) }
  );
  if (!resp.ok) {
    throw new Error(`session unarchive failed: ${resp.status}`);
  }
}
