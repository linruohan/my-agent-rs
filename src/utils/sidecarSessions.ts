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

function sidecarBase(port: number) {
  return `http://127.0.0.1:${port}`;
}

function authHeaders(token: string | null, json = false): HeadersInit {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (json) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
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

export async function fetchSessionsRest(
  port: number,
  token?: string | null,
  includeArchived = false
): Promise<SessionRow[]> {
  const auth = token ?? (await fetchAuthToken(port));
  const qs = includeArchived ? '?include_archived=true' : '';
  const resp = await fetch(`${sidecarBase(port)}/sessions${qs}`, {
    headers: authHeaders(auth),
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
  const auth = token ?? (await fetchAuthToken(port));
  const resp = await fetch(`${sidecarBase(port)}/sessions/archived`, {
    headers: authHeaders(auth),
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
  const auth = token ?? (await fetchAuthToken(port));
  const resp = await fetch(`${sidecarBase(port)}/sessions/${encodeURIComponent(threadId)}/history`, {
    headers: authHeaders(auth),
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
  const auth = token ?? (await fetchAuthToken(port));
  const resp = await fetch(`${sidecarBase(port)}/sessions`, {
    method: 'POST',
    headers: authHeaders(auth, true),
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
  const auth = token ?? (await fetchAuthToken(port));
  const resp = await fetch(`${sidecarBase(port)}/sessions/${encodeURIComponent(threadId)}`, {
    method: 'DELETE',
    headers: authHeaders(auth),
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
  const auth = token ?? (await fetchAuthToken(port));
  const resp = await fetch(
    `${sidecarBase(port)}/sessions/${encodeURIComponent(threadId)}/archive`,
    { method: 'POST', headers: authHeaders(auth) }
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
  const auth = token ?? (await fetchAuthToken(port));
  const resp = await fetch(
    `${sidecarBase(port)}/sessions/${encodeURIComponent(threadId)}/unarchive`,
    { method: 'POST', headers: authHeaders(auth) }
  );
  if (!resp.ok) {
    throw new Error(`session unarchive failed: ${resp.status}`);
  }
}
