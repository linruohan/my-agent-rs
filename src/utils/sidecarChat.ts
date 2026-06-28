import type { ChatAttachment } from '@/utils/attachments';
import {
  fetchSidecarAuthToken,
  sidecarAuthHeaders,
  sidecarBaseUrl,
} from '@/utils/sidecarFetch';

function parseSseChunk(chunk: string, onEvent: (msg: Record<string, unknown>) => void) {
  for (const block of chunk.split('\n\n')) {
    if (!block.trim()) continue;
    for (const line of block.split('\n')) {
      if (line.startsWith('data: ')) {
        onEvent(JSON.parse(line.slice(6)) as Record<string, unknown>);
      }
    }
  }
}

async function readSseStream(
  resp: Response,
  onEvent: (msg: Record<string, unknown>) => void
): Promise<void> {
  if (!resp.body) {
    throw new Error('empty SSE body');
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';
    for (const part of parts) {
      parseSseChunk(`${part}\n\n`, onEvent);
    }
  }
  if (buffer.trim()) {
    parseSseChunk(`${buffer}\n\n`, onEvent);
  }
}

export async function streamChatRest(
  port: number,
  threadId: string,
  content: string,
  onEvent: (msg: Record<string, unknown>) => void,
  attachments?: ChatAttachment[],
  signal?: AbortSignal
): Promise<void> {
  const token = await fetchSidecarAuthToken(port);
  const resp = await fetch(`${sidecarBaseUrl(port)}/sessions/${encodeURIComponent(threadId)}/chat`, {
    method: 'POST',
    headers: sidecarAuthHeaders(token, { json: true, sse: true }),
    body: JSON.stringify({
      content,
      attachments: attachments?.length ? attachments : undefined,
    }),
    signal,
  });
  if (!resp.ok) {
    throw new Error(`chat stream failed: ${resp.status}`);
  }
  await readSseStream(resp, onEvent);
}

export async function streamChatResumeRest(
  port: number,
  threadId: string,
  decision: 'approve' | 'reject' | 'edit',
  onEvent: (msg: Record<string, unknown>) => void,
  editedArgs?: Record<string, unknown>,
  signal?: AbortSignal
): Promise<void> {
  const token = await fetchSidecarAuthToken(port);
  const resp = await fetch(
    `${sidecarBaseUrl(port)}/sessions/${encodeURIComponent(threadId)}/chat/resume`,
    {
      method: 'POST',
      headers: sidecarAuthHeaders(token, { json: true, sse: true }),
      body: JSON.stringify({ decision, edited_args: editedArgs }),
      signal,
    }
  );
  if (!resp.ok) {
    throw new Error(`chat resume failed: ${resp.status}`);
  }
  await readSseStream(resp, onEvent);
}

export async function stopChatRest(
  port: number,
  threadId: string,
  token?: string | null
): Promise<boolean> {
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const resp = await fetch(
    `${sidecarBaseUrl(port)}/sessions/${encodeURIComponent(threadId)}/chat/stop`,
    {
      method: 'POST',
      headers: sidecarAuthHeaders(auth, { sse: true }),
    }
  );
  if (!resp.ok) {
    throw new Error(`chat stop failed: ${resp.status}`);
  }
  const data = (await resp.json()) as { ok?: boolean };
  return !!data.ok;
}
