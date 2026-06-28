const LEADER_KEY = 'pa-ws-leader';
const LEADER_STALE_MS = 5000;
const HEARTBEAT_MS = 2000;
const BC_CHANNEL = 'personal-assistant-agent';

export const tabId = crypto.randomUUID();

export type WsLeaderRole = 'leader' | 'follower';

type LeaderRecord = { tabId: string; heartbeat: number };

type LeaderCallbacks = {
  onBecomeLeader: () => void;
  onBecomeFollower: () => void;
};

let role: WsLeaderRole = 'follower';
let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
let callbacks: LeaderCallbacks | null = null;
let bc: BroadcastChannel | null = null;
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
    bc?.postMessage({ type: 'leader.ping', tabId });
  }, HEARTBEAT_MS);
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
  bc?.postMessage({ type: 'leader.claimed', tabId });
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
  bc?.postMessage({ type: 'leader.release', tabId });
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

export function initWsLeaderElection() {
  if (initialized) return;
  initialized = true;

  if (typeof BroadcastChannel !== 'undefined') {
    bc = new BroadcastChannel(BC_CHANNEL);
    bc.onmessage = (e: MessageEvent) => {
      const data = e.data as { type?: string; tabId?: string };
      if (data.type === 'leader.claimed' && data.tabId !== tabId) {
        setRole('follower');
      }
      if (data.type === 'leader.release') {
        tryClaimLeader();
      }
      if (data.type === 'leader.ping' && data.tabId !== tabId) {
        setRole('follower');
      }
    };
  }

  window.addEventListener('storage', (e) => {
    if (e.key === LEADER_KEY) refreshRoleFromStorage();
  });

  window.addEventListener('beforeunload', () => releaseLeader());

  tryClaimLeader();
}
