const PRODUCT_PREVIEW_LINES = 4;
const PRODUCT_MAX_CHARS = 240;

function lineCount(text: string): number {
  if (!text) return 0;
  return text.split('\n').length;
}

function summarizeTextEditor(content: string): string {
  const trimmed = content.trim();
  if (!trimmed) return content;

  if (/^Created .+/i.test(trimmed)) return trimmed;
  if (/^File not found:/i.test(trimmed)) return trimmed;
  if (/^Replaced in /i.test(trimmed)) return trimmed;
  if (/^Inserted at line /i.test(trimmed)) return trimmed;
  if (/^File already exists:/i.test(trimmed)) return trimmed;
  if (/^String not found/i.test(trimmed)) return trimmed;
  if (/^Unknown command:/i.test(trimmed)) return trimmed;
  if (/^Error executing /i.test(trimmed)) return trimmed;

  const lines = trimmed.split('\n');
  const preview = lines.slice(0, PRODUCT_PREVIEW_LINES).join('\n');
  const suffix = lines.length > PRODUCT_PREVIEW_LINES ? '\n…' : '';
  return `已读取文件（${lines.length} 行）\n${preview}${suffix}`;
}

export function formatToolContent(
  toolName: string,
  content: string,
  mode: 'product' | 'technical'
): string {
  if (!content.trim()) return content;

  if (mode === 'technical') return content;

  if (content.startsWith('调用工具:') || content.startsWith('执行中:')) {
    return content;
  }

  if (toolName === 'text_editor' || /^\s*\d+\|/m.test(content)) {
    return summarizeTextEditor(content);
  }

  if (content.length <= PRODUCT_MAX_CHARS) return content;

  const lines = content.split('\n');
  if (lines.length > PRODUCT_PREVIEW_LINES) {
    return `${lines.slice(0, PRODUCT_PREVIEW_LINES).join('\n')}\n…（共 ${lineCount(content)} 行）`;
  }

  return `${content.slice(0, PRODUCT_MAX_CHARS)}…`;
}
