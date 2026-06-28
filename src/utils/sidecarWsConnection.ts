import { getActivePinia } from 'pinia';
import { useSettingsStore } from '@/stores/settings';

export const WS_RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000];
export const WS_TOKEN_FLUSH_MS = 50;

export const WS_WRITE_MSG_TYPES = new Set([
  'chat.send',
  'chat.stop',
  'chat.resume',
  'session.create',
  'session.delete',
  'session.archive',
  'session.unarchive',
  'rag.ingest',
  'rag.delete',
  'memory.set',
]);

let ws: WebSocket | null = null;
let reconnectAttempt = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

export function getSidecarWs(): WebSocket | null {
  return ws;
}

export function isSidecarWsOpen(): boolean {
  return ws?.readyState === WebSocket.OPEN;
}

export function sendSidecarWsRaw(data: Record<string, unknown>): boolean {
  const pinia = getActivePinia();
  if (pinia) {
    const settings = useSettingsStore(pinia);
    const msgType = data.type as string | undefined;
    if (settings.wsReadOnly && msgType && WS_WRITE_MSG_TYPES.has(msgType)) {
      return false;
    }
  }
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
    return true;
  }
  return false;
}

export function openSidecarWs(
  url: string,
  handlers: {
    onOpen: () => void;
    onMessage: (data: Record<string, unknown>) => void;
    onClose: () => void;
    onError: () => void;
  }
): void {
  const state = ws?.readyState;
  if (state === WebSocket.OPEN && ws!.url === url) return;
  if (state === WebSocket.CONNECTING && ws!.url === url) return;

  ws?.close();
  ws = new WebSocket(url);

  ws.onopen = handlers.onOpen;
  ws.onmessage = (e) => {
    try {
      handlers.onMessage(JSON.parse(e.data) as Record<string, unknown>);
    } catch {
      console.error('Failed to parse WS message');
    }
  };
  ws.onclose = handlers.onClose;
  ws.onerror = handlers.onError;
}

export function closeSidecarWs(): void {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = null;
  ws?.close();
  ws = null;
}

export function resetSidecarWsReconnectAttempt(): void {
  reconnectAttempt = 0;
}

export function scheduleSidecarWsReconnect(
  connect: () => void,
  canReconnect: () => boolean
): void {
  if (reconnectAttempt >= WS_RECONNECT_DELAYS.length) return;
  if (!canReconnect()) return;
  const delay = WS_RECONNECT_DELAYS[reconnectAttempt++];
  reconnectTimer = setTimeout(connect, delay);
}

export function canUseRestRead(sidecarStatus: string): boolean {
  return sidecarStatus === 'running';
}

export function canUseRestWrite(
  sidecarStatus: string,
  wsReadOnly: boolean
): boolean {
  return !wsReadOnly && sidecarStatus === 'running';
}
