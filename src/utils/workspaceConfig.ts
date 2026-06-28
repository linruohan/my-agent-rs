/** 将工作区路径同步到 Sidecar */
export async function syncWorkspaceToSidecar(path: string, port: number): Promise<void> {
  const trimmed = path.trim();
  if (!trimmed) return;

  try {
    const resp = await fetch(`http://127.0.0.1:${port}/config/workspace`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace: trimmed }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  } catch (e) {
    console.warn('同步工作区路径失败:', e);
  }
}

/** 从 Sidecar 加载工作区路径 */
export async function loadWorkspaceFromSidecar(port: number): Promise<string | null> {
  try {
    const resp = await fetch(`http://127.0.0.1:${port}/config/workspace`);
    if (!resp.ok) return null;
    const data = (await resp.json()) as { workspace?: string };
    return data.workspace?.trim() || null;
  } catch {
    return null;
  }
}
