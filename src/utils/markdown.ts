import { marked } from 'marked';

marked.setOptions({
  breaks: true,
  gfm: true,
});

export function renderMarkdown(text: string): string {
  if (!text.trim()) return '';
  return marked.parse(text, { async: false }) as string;
}
