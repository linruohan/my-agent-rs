import { isTauriEnv } from '@/utils/tauri';

/** 用系统默认浏览器打开 URL */
export async function openExternalUrl(url: string): Promise<void> {
  const trimmed = url.trim();
  if (!trimmed) return;

  if (isTauriEnv()) {
    const { invoke } = await import('@tauri-apps/api/core');
    await invoke('open_external_url', { url: trimmed });
    return;
  }

  window.open(trimmed, '_blank', 'noopener,noreferrer');
}

/** 用系统默认程序打开本地文件或文件夹 */
export async function openLocalPath(path: string): Promise<void> {
  const trimmed = path.trim();
  if (!trimmed) return;

  if (isTauriEnv()) {
    const { invoke } = await import('@tauri-apps/api/core');
    await invoke('open_local_path', { path: trimmed });
    return;
  }

  console.warn('openLocalPath 仅在桌面端可用:', trimmed);
}

/** 在文件管理器中定位文件/文件夹 */
export async function revealInExplorer(path: string): Promise<void> {
  const trimmed = path.trim();
  if (!trimmed) return;

  if (isTauriEnv()) {
    const { invoke } = await import('@tauri-apps/api/core');
    await invoke('reveal_in_explorer', { path: trimmed });
    return;
  }

  console.warn('revealInExplorer 仅在桌面端可用:', trimmed);
}

/** 打开工作区文件夹 */
export async function openWorkspaceFolder(path: string): Promise<void> {
  const trimmed = path.trim();
  if (!trimmed) return;

  if (isTauriEnv()) {
    const { invoke } = await import('@tauri-apps/api/core');
    await invoke('open_workspace_folder', { path: trimmed });
    return;
  }

  console.warn('openWorkspaceFolder 仅在桌面端可用:', trimmed);
}

/** 判断 href 是否为 http(s) 外部链接 */
export function isHttpUrl(href: string): boolean {
  return /^https?:\/\//i.test(href.trim());
}

/** 判断 href 是否为 file:// 本地路径 */
export function isFileUrl(href: string): boolean {
  return /^file:\/\//i.test(href.trim());
}

/** 将 file:// URL 转为本地路径 */
export function fileUrlToPath(href: string): string {
  try {
    const url = new URL(href);
    let p = decodeURIComponent(url.pathname);
    // Windows: /C:/path -> C:/path
    if (/^\/[A-Za-z]:\//.test(p)) {
      p = p.slice(1);
    }
    return p;
  } catch {
    return href.replace(/^file:\/\//i, '');
  }
}

/** 判断字符串是否像本地绝对路径 */
export function looksLikeLocalPath(text: string): boolean {
  const t = text.trim();
  if (!t || isHttpUrl(t)) return false;
  if (isFileUrl(t)) return true;
  // Windows: C:\ or C:/
  if (/^[A-Za-z]:[\\/]/.test(t)) return true;
  // Unix absolute
  if (t.startsWith('/') && !t.startsWith('//')) return true;
  // UNC path
  if (t.startsWith('\\\\')) return true;
  return false;
}

/** 根据 href 自动选择打开方式 */
export async function openHref(href: string): Promise<void> {
  const trimmed = href.trim();
  if (!trimmed) return;

  if (isHttpUrl(trimmed)) {
    await openExternalUrl(trimmed);
    return;
  }

  if (isFileUrl(trimmed)) {
    await openLocalPath(fileUrlToPath(trimmed));
    return;
  }

  if (looksLikeLocalPath(trimmed)) {
    await openLocalPath(trimmed);
    return;
  }

  await openExternalUrl(trimmed);
}
