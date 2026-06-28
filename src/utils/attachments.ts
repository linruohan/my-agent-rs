import { looksLikeLocalPath } from '@/utils/nativeOpen';

/** 聊天附件 */
export interface ChatAttachment {
  type: 'text' | 'image' | 'url' | 'folder' | 'file';
  name: string;
  content: string;
  /** Tauri 模式下本地文件的完整路径 */
  path?: string;
  mimeType?: string;
}

export function attachmentIcon(type: ChatAttachment['type']): string {
  switch (type) {
    case 'image':
      return '🖼';
    case 'folder':
      return '📁';
    case 'url':
      return '🔗';
    case 'file':
    case 'text':
    default:
      return '📄';
  }
}

export function imageDataUrl(att: ChatAttachment): string | null {
  if (att.type !== 'image') return null;
  if (att.content.startsWith('data:')) return att.content;
  const mime = att.mimeType || 'image/png';
  return `data:${mime};base64,${att.content}`;
}

/** 将 File 读为 base64 字符串 */
export async function fileToBase64(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let binary = '';
  const chunk = 8192;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

const BINARY_EXT = new Set([
  'pdf',
  'png',
  'jpg',
  'jpeg',
  'gif',
  'webp',
  'zip',
  'doc',
  'docx',
  'xls',
  'xlsx',
]);

export function isBinaryExtension(name: string): boolean {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  return BINARY_EXT.has(ext);
}

/** 从 webkitRelativePath 提取文件夹名 */
export function folderNameFromPaths(paths: string[]): string {
  if (!paths.length) return 'folder';
  const first = paths[0];
  const slash = first.indexOf('/');
  return slash > 0 ? first.slice(0, slash) : first;
}

/** 检测 markdown 文本中的裸本地路径并 linkify（在 marked 之后 post-process） */
export function linkifyLocalPaths(html: string): string {
  // 跳过已有链接、代码块内的内容
  const parts = html.split(/(<a[\s\S]*?<\/a>|<code[\s\S]*?<\/code>|<pre[\s\S]*?<\/pre>)/gi);
  return parts
    .map((part, i) => {
      if (i % 2 === 1) return part;
      return part.replace(
        /(?:^|[\s(>])((?:file:\/\/\/|file:\/\/)?[A-Za-z]:[\\/][^\s<>"']+|(?:file:\/\/\/|file:\/\/)?\/[^\s<>"']+)/g,
        (match, path: string) => {
          const prefix = match.slice(0, match.indexOf(path));
          if (!looksLikeLocalPath(path)) return match;
          const escaped = path
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;');
          return `${prefix}<a href="#" class="md-local-path" data-local-path="${escaped}">${escaped}</a>`;
        }
      );
    })
    .join('');
}
