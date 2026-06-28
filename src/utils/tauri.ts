/** 是否在 Tauri 桌面 WebView 中运行 */
export function isTauriEnv(): boolean {
  if (typeof window === 'undefined') return false;
  return '__TAURI_INTERNALS__' in window || '__TAURI__' in window;
}
