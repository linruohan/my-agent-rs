const LEADER_KEY = 'pa-ws-leader';
const LEADER_STALE_MS = 5000;
const HEARTBEAT_MS = 2000;
export const BC_CHANNEL = 'personal-assistant-agent';

export const tabId = crypto.randomUUID();

export type WsLeaderRole = 'leader' | 'follower';

type LeaderRecord = { tabId: string; heartbeat: number };

type LeaderCallbacks = {
  onBecomeLeader: () => void;
  onBecomeFollower: () => void;
};

type ChannelHandler = (data: Record<string, unknown>) => void;

let role: WsLeaderRole = 'follower';
let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
let callbacks: LeaderCallbacks | null = null;
let bc: BroadcastChannel | null = null;
let channelHandler: ChannelHandler | null = null;
let initialized = false;

function readLeader(): LeaderRecord | null {
  try {
    const raw = localStorage.getItem(LEADER_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as LeaderRecord;
  } catch {
    return null;
  }
}

function writeLeader() {
  localStorage.setItem(
    LEADER_KEY,
    JSON.stringify({ tabId, heartbeat: Date.now() })
  );
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
}

function startHeartbeat() {
  if (heartbeatTimer) return;
  heartbeatTimer = setInterval(() => {
    if (role !== 'leader') return;
    writeLeader();
    postChannelMessage({ type: 'leader.ping', tabId });
  }, HEARTBEAT_MS);
}

function ensureChannel() {
  if (typeof BroadcastChannel === 'undefined') return;
  if (bc) return;
  bc = new BroadcastChannel(BC_CHANNEL);
  bc.onmessage = (e: MessageEvent) => {
    const data = e.data as Record<string, unknown>;
    if (data.type === 'leader.claimed' && data.tabId !== tabId) {
      setRole('follower');
    }
    if (data.type === 'leader.release') {
      tryClaimLeader();
    }
    if (data.type === 'leader.ping' && data.tabId !== tabId) {
      setRole('follower');
    }
    channelHandler?.(data);
  };
}

export function postChannelMessage(data: Record<string, unknown>) {
  ensureChannel();
  bc?.postMessage(data);
}

export function registerChannelHandler(handler: ChannelHandler | null) {
  channelHandler = handler;
}

function setRole(next: WsLeaderRole) {
  if (role === next) return;
  role = next;
  if (next === 'leader') {
    startHeartbeat();
    callbacks?.onBecomeLeader();
  } else {
    stopHeartbeat();
    callbacks?.onBecomeFollower();
  }
}

export function getWsLeaderRole(): WsLeaderRole {
  return role;
}

export function isWsLeader(): boolean {
  return role === 'leader';
}

export function tryClaimLeader(): boolean {
  const now = Date.now();
  const current = readLeader();
  if (current && current.tabId !== tabId && now - current.heartbeat < LEADER_STALE_MS) {
    setRole('follower');
    return false;
  }
  writeLeader();
  setRole('leader');
  postChannelMessage({ type: 'leader.claimed', tabId });
  return true;
}

export function releaseLeader() {
  if (role !== 'leader') return;
  const current = readLeader();
  if (current?.tabId === tabId) {
    localStorage.removeItem(LEADER_KEY);
  }
  stopHeartbeat();
  role = 'follower';
  postChannelMessage({ type: 'leader.release', tabId });
  callbacks?.onBecomeFollower();
}

function refreshRoleFromStorage() {
  const current = readLeader();
  const now = Date.now();
  if (!current || now - current.heartbeat >= LEADER_STALE_MS) {
    if (role === 'follower') tryClaimLeader();
    return;
  }
  if (current.tabId === tabId) {
    if (role !== 'leader') setRole('leader');
  } else if (role !== 'follower') {
    setRole('follower');
  }
}

export function registerLeaderCallbacks(cb: LeaderCallbacks) {
  callbacks = cb;
}

export function requestSyncFromLeader(
  threadId?: string | null,
  opts?: { historyOnly?: boolean }
) {
  postChannelMessage({
    type: 'sync.request',
    tabId,
    threadId: threadId ?? null,
    historyOnly: !!opts?.historyOnly,
  });
}

export function initWsLeaderElection() {
  if (initialized) return;
  initialized = true;
  ensureChannel();

  window.addEventListener('storage', (e) => {
    if (e.key === LEADER_KEY) refreshRoleFromStorage();
  });

  window.addEventListener('beforeunload', () => releaseLeader());

  tryClaimLeader();
}
