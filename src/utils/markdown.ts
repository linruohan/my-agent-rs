import { marked } from 'marked';
import { linkifyLocalPaths } from '@/utils/attachments';
import { highlightCode } from '@/utils/codeHighlight';
import { highlightTermsInHtml } from '@/utils/highlightTerms';

marked.setOptions({
  breaks: true,
  gfm: true,
});

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function escapeAttr(text: string): string {
  return escapeHtml(text).replace(/'/g, '&#39;');
}

marked.use({
  renderer: {
    code({ text, lang }) {
      const language = escapeHtml(lang || 'code');
      const highlighted = highlightCode(text, lang || undefined);
      const langClass = lang ? ` class="language-${escapeHtml(lang)}"` : '';
      return `<div class="md-code-block">
  <div class="md-code-header">
    <span class="md-code-lang">${language}</span>
    <button type="button" class="md-copy-btn" data-copy-btn aria-label="复制代码">复制</button>
  </div>
  <pre><code${langClass}>${highlighted}</code></pre>
</div>`;
    },

    link({ href, title, text }) {
      const url = href ?? '';
      const label = escapeHtml(text);
      const titleAttr = title ? ` title="${escapeAttr(title)}"` : '';
      const safeHref = escapeAttr(url);
      return `<a href="${safeHref}" class="md-link" data-md-href="${safeHref}"${titleAttr}>${label}</a>`;
    },

    image({ href, title, text }) {
      const src = href ?? '';
      const alt = escapeHtml(text || title || '图片');
      const titleAttr = title ? ` title="${escapeAttr(title)}"` : '';
      const safeSrc = escapeAttr(src);
      return `<img src="${safeSrc}" alt="${alt}" class="md-image" data-md-image loading="lazy"${titleAttr} />`;
    },
  },
});

export interface RenderMarkdownOptions {
  highlightTerms?: string[];
}

export function renderMarkdown(text: string, options?: RenderMarkdownOptions): string {
  if (!text.trim()) return '';
  let html = marked.parse(text, { async: false }) as string;
  html = linkifyLocalPaths(html);
  if (options?.highlightTerms?.length) {
    html = highlightTermsInHtml(html, options.highlightTerms);
  }
  return html;
}

export function hasFencedCodeBlock(text: string): boolean {
  return /```[\s\S]+?```/.test(text);
}
