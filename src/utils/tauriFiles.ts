import { isTauriEnv } from '@/utils/tauri';
import type { ChatAttachment } from '@/utils/attachments';
import { folderNameFromPaths, fileToBase64, isBinaryExtension } from '@/utils/attachments';

const FILE_FILTERS = [
  {
    name: '文档与图片',
    extensions: ['md', 'txt', 'markdown', 'pdf', 'json', 'csv', 'png', 'jpg', 'jpeg', 'webp', 'gif'],
  },
];

const IMAGE_FILTERS = [
  { name: '图片', extensions: ['png', 'jpg', 'jpeg', 'webp', 'gif'] },
];

interface FileReadResult {
  name: string;
  content: string;
  is_binary: boolean;
  mime_type?: string | null;
}

function resultToAttachment(path: string, result: FileReadResult): ChatAttachment {
  if (result.is_binary && result.mime_type?.startsWith('image/')) {
    return {
      type: 'image',
      name: result.name,
      content: result.content,
      path,
      mimeType: result.mime_type ?? undefined,
    };
  }
  if (result.is_binary) {
    return {
      type: 'file',
      name: result.name,
      content: result.content,
      path,
      mimeType: result.mime_type ?? undefined,
    };
  }
  return {
    type: 'text',
    name: result.name,
    content: result.content,
    path,
  };
}

async function readPath(path: string): Promise<ChatAttachment> {
  const { invoke } = await import('@tauri-apps/api/core');
  const result = await invoke<FileReadResult>('read_local_file', { path });
  return resultToAttachment(path, result);
}

/** Tauri 原生文件选择器 */
export async function pickFilesViaDialog(multiple = true): Promise<ChatAttachment[]> {
  const { open } = await import('@tauri-apps/plugin-dialog');
  const selected = await open({
    title: '选择文件',
    multiple,
    filters: FILE_FILTERS,
  });
  if (!selected) return [];
  const paths = Array.isArray(selected) ? selected : [selected];
  const attachments: ChatAttachment[] = [];
  for (const path of paths) {
    try {
      attachments.push(await readPath(path));
    } catch (e) {
      console.warn('读取文件失败:', path, e);
    }
  }
  return attachments;
}

/** Tauri 原生图片选择器 */
export async function pickImagesViaDialog(): Promise<ChatAttachment[]> {
  const { open } = await import('@tauri-apps/plugin-dialog');
  const selected = await open({
    title: '选择图片',
    multiple: true,
    filters: IMAGE_FILTERS,
  });
  if (!selected) return [];
  const paths = Array.isArray(selected) ? selected : [selected];
  const attachments: ChatAttachment[] = [];
  for (const path of paths) {
    try {
      attachments.push(await readPath(path));
    } catch (e) {
      console.warn('读取图片失败:', path, e);
    }
  }
  return attachments;
}

/** Tauri 原生文件夹选择器 */
export async function pickFolderViaDialog(): Promise<ChatAttachment | null> {
  const { open } = await import('@tauri-apps/plugin-dialog');
  const selected = await open({
    title: '选择文件夹',
    directory: true,
    multiple: false,
    recursive: true,
  });
  if (!selected || Array.isArray(selected)) return null;

  const { invoke } = await import('@tauri-apps/api/core');
  const entries = await invoke<string[]>('list_directory', { path: selected });
  const name = selected.split(/[/\\]/).filter(Boolean).pop() || 'folder';

  return {
    type: 'folder',
    name,
    content: entries.join('\n'),
    path: selected,
  };
}

/** 根据环境选择文件（Tauri dialog 或 HTML input fallback） */
export async function pickFilesNative(): Promise<ChatAttachment[] | 'use-html'> {
  if (!isTauriEnv()) return 'use-html';
  return pickFilesViaDialog(true);
}

export async function pickImagesNative(): Promise<ChatAttachment[] | 'use-html'> {
  if (!isTauriEnv()) return 'use-html';
  return pickImagesViaDialog();
}

export async function pickFolderNative(): Promise<ChatAttachment | 'use-html' | null> {
  if (!isTauriEnv()) return 'use-html';
  return pickFolderViaDialog();
}

/** 从 HTML FileList 构建附件（Web fallback） */
export async function attachmentsFromFileList(files: FileList): Promise<ChatAttachment[]> {
  const attachments: ChatAttachment[] = [];

  for (const file of Array.from(files)) {
    if (file.type.startsWith('image/')) {
      const b64 = await fileToBase64(file);
      attachments.push({
        type: 'image',
        name: file.name,
        content: b64,
        mimeType: file.type,
      });
    } else if (isBinaryExtension(file.name)) {
      const b64 = await fileToBase64(file);
      attachments.push({
        type: 'file',
        name: file.name,
        content: b64,
        mimeType: file.type || undefined,
      });
    } else {
      const content = await file.text();
      attachments.push({ type: 'text', name: file.name, content });
    }
  }
  return attachments;
}

/** 从 webkitdirectory FileList 构建文件夹附件 */
export function attachmentFromFolderFiles(files: FileList): ChatAttachment {
  const names = Array.from(files).map((f) => {
    const rel = (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name;
    return rel.replace(/\\/g, '/');
  });
  return {
    type: 'folder',
    name: folderNameFromPaths(names),
    content: names.join('\n'),
  };
}
