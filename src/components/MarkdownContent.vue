<script setup lang="ts">
import { computed, ref } from 'vue';
import { renderMarkdown } from '@/utils/markdown';
import { openHref, openLocalPath } from '@/utils/nativeOpen';

const props = defineProps<{
  content: string;
  variant?: 'assistant' | 'user';
  highlightTerms?: string[];
}>();

const html = computed(() =>
  renderMarkdown(props.content, { highlightTerms: props.highlightTerms })
);

const previewSrc = ref<string | null>(null);
const previewAlt = ref('');

function closePreview() {
  previewSrc.value = null;
  previewAlt.value = '';
}

async function onClick(e: MouseEvent) {
  const target = e.target as HTMLElement;

  const btn = target.closest('[data-copy-btn]') as HTMLButtonElement | null;
  if (btn) {
    e.preventDefault();
    e.stopPropagation();
    const block = btn.closest('.md-code-block');
    const lineCells = block?.querySelectorAll('.md-code-lc');
    const code = block?.querySelector('code');
    const text =
      lineCells && lineCells.length
        ? [...lineCells].map((el) => el.textContent ?? '').join('\n')
        : (code?.textContent ?? '');
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      const prev = btn.textContent;
      btn.textContent = '已复制';
      btn.classList.add('copied');
      setTimeout(() => {
        btn.textContent = prev;
        btn.classList.remove('copied');
      }, 2000);
    } catch {
      btn.textContent = '失败';
      setTimeout(() => {
        btn.textContent = '复制';
      }, 2000);
    }
    return;
  }

  const localLink = target.closest('[data-local-path]') as HTMLAnchorElement | null;
  if (localLink) {
    e.preventDefault();
    e.stopPropagation();
    const path = localLink.dataset.localPath;
    if (path) await openLocalPath(path);
    return;
  }

  const mdLink = target.closest('[data-md-href]') as HTMLAnchorElement | null;
  if (mdLink) {
    e.preventDefault();
    e.stopPropagation();
    const href = mdLink.dataset.mdHref ?? mdLink.getAttribute('href') ?? '';
    if (href) await openHref(href);
    return;
  }

  const img = target.closest('[data-md-image]') as HTMLImageElement | null;
  if (img) {
    e.preventDefault();
    e.stopPropagation();
    previewSrc.value = img.src;
    previewAlt.value = img.alt || '图片';
  }
}
</script>

<template>
  <div
    class="markdown-body"
    :class="variant === 'user' ? 'markdown-user' : 'markdown-assistant'"
    v-html="html"
    @click="onClick"
  />

  <Teleport to="body">
    <div v-if="previewSrc" class="image-preview-overlay" @click="closePreview">
      <div class="image-preview-wrap" @click.stop>
        <button type="button" class="preview-close" aria-label="关闭" @click="closePreview">×</button>
        <img :src="previewSrc" :alt="previewAlt" class="preview-image" />
        <p v-if="previewAlt" class="preview-caption">{{ previewAlt }}</p>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.markdown-body {
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
  line-height: 1;
}

.markdown-body :deep(p) {
  margin: 0.2em 0;
}

.markdown-body :deep(p:first-child) {
  margin-top: 0;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.25em 0;
  padding-left: 1.4em;
}

.markdown-body :deep(li) {
  margin: 0.1em 0;
}

.markdown-body :deep(li > p) {
  margin: 0;
}

.markdown-body :deep(li > p + p) {
  margin-top: 0.2em;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 0.5em 0 0.25em;
  font-weight: 650;
  line-height: 1.35;
}

.markdown-body :deep(h1) {
  font-size: 1.35em;
  color: var(--syntax-title, var(--accent));
}

.markdown-body :deep(h2) {
  font-size: 1.2em;
  color: var(--syntax-title, var(--accent));
}

.markdown-body :deep(h3) {
  font-size: 1.08em;
  color: color-mix(in srgb, var(--syntax-type, var(--accent)) 85%, var(--text-primary));
}

.markdown-body :deep(h4) {
  font-size: 1em;
  color: var(--text-primary);
}

.markdown-body :deep(h1:first-child),
.markdown-body :deep(h2:first-child),
.markdown-body :deep(h3:first-child),
.markdown-body :deep(h4:first-child) {
  margin-top: 0;
}

.markdown-body :deep(a),
.markdown-body :deep(.md-local-path) {
  color: var(--accent);
  text-decoration: none;
  cursor: pointer;
}

.markdown-body :deep(a:hover),
.markdown-body :deep(.md-local-path:hover) {
  text-decoration: underline;
}

.markdown-body :deep(.md-image) {
  max-width: 100%;
  max-height: 320px;
  border-radius: 8px;
  margin: 0.5em 0;
  cursor: zoom-in;
  border: 1px solid var(--border);
}

.markdown-body :deep(:not(pre) > code) {
  background: var(--bg-code, var(--bg-input));
  border: 1px solid color-mix(in srgb, var(--border) 80%, transparent);
  border-radius: 4px;
  padding: 0.1em 0.35em;
  font-size: 0.9em;
  font-family: ui-monospace, 'Cascadia Code', monospace;
  color: var(--syntax-string, var(--success));
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-all;
}

.markdown-user :deep(:not(pre) > code) {
  background: color-mix(in srgb, var(--text-on-accent) 12%, transparent);
  border-color: color-mix(in srgb, var(--text-on-accent) 20%, transparent);
  color: var(--text-on-accent);
}

.markdown-assistant :deep(:not(pre) > code) {
  background: var(--bg-code, var(--bg-input));
}

.markdown-body :deep(.md-code-block) {
  margin: 0.35em 0;
  max-width: 100%;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-input);
}

.markdown-body :deep(.md-code-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border);
}

.markdown-body :deep(.md-code-lang) {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: lowercase;
  font-family: ui-monospace, monospace;
}

.markdown-body :deep(.md-copy-btn) {
  background: none;
  border: 1px solid var(--btn-secondary-bg);
  border-radius: 4px;
  color: var(--text-secondary);
  font-size: 11px;
  padding: 2px 8px;
  cursor: pointer;
  font-family: inherit;
  line-height: 1.4;
}

.markdown-body :deep(.md-copy-btn:hover) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.markdown-body :deep(.md-copy-btn.copied) {
  color: var(--success);
  border-color: rgba(16, 185, 129, 0.35);
}

.markdown-body :deep(.md-code-block pre) {
  margin: 0;
  padding: 0;
  max-width: 100%;
  overflow-x: auto;
  background: transparent;
}

.markdown-body :deep(.md-code-block pre code) {
  display: block;
  background: none;
  padding: 0;
  font-size: 0.85em;
  font-family: ui-monospace, 'Cascadia Code', monospace;
  color: var(--text-primary);
  white-space: normal;
  border: none;
  line-height: 1.2;
}

.markdown-body :deep(.md-code-line) {
  display: flex;
  min-width: max-content;
  line-height: 1.2;
}

.markdown-body :deep(.md-code-ln) {
  flex: 0 0 calc(var(--md-ln-digits, 1) * 1em + 16px);
  min-width: calc(var(--md-ln-digits, 1) * 1em + 16px);
  padding: 0 8px;
  text-align: right;
  color: var(--text-muted);
  user-select: none;
  border-right: 1px solid var(--border);
  background: color-mix(in srgb, var(--bg-panel) 70%, transparent);
  font-family: ui-monospace, 'Cascadia Code', monospace;
  font-variant-numeric: tabular-nums;
  white-space: pre;
  box-sizing: border-box;
}

.markdown-body :deep(.md-code-lc) {
  flex: 1;
  padding: 0 12px;
  min-width: 0;
}

.markdown-body :deep(.tok-keyword) {
  color: var(--syntax-keyword, var(--danger));
  font-weight: 600;
}

.markdown-body :deep(.tok-string) {
  color: var(--syntax-string, var(--success));
}

.markdown-body :deep(.tok-comment) {
  color: var(--syntax-comment, var(--text-muted));
  font-style: italic;
}

.markdown-body :deep(.tok-number) {
  color: var(--syntax-number, var(--warning));
}

.markdown-body :deep(.tok-function) {
  color: var(--syntax-function, var(--accent));
}

.markdown-body :deep(.tok-type) {
  color: var(--syntax-type, var(--accent));
}

.markdown-body :deep(.tok-boolean) {
  color: var(--syntax-boolean, var(--warning));
}

.markdown-body :deep(strong) {
  color: var(--syntax-keyword, var(--text-primary));
  font-weight: 650;
}

.markdown-body :deep(em) {
  color: var(--text-secondary);
}

.markdown-body :deep(del) {
  color: var(--text-muted);
  text-decoration: line-through;
}

.markdown-body :deep(.md-search-hit) {
  background: var(--warning-muted);
  color: var(--text-highlight);
  padding: 0.05em 0.2em;
  border-radius: 3px;
  font-weight: 550;
}

.markdown-body :deep(.md-table-wrap) {
  overflow-x: auto;
  max-width: 100%;
  margin: 0.6em 0;
  -webkit-overflow-scrolling: touch;
}

.markdown-body :deep(.md-table-wrap table) {
  width: 100%;
  min-width: 520px;
  border-collapse: collapse;
  font-size: 0.92em;
  table-layout: auto;
}

.markdown-body :deep(table) {
  width: 100%;
  max-width: 100%;
  border-collapse: collapse;
  margin: 0.6em 0;
  font-size: 0.92em;
  table-layout: auto;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
  vertical-align: top;
  white-space: nowrap;
}

.markdown-body :deep(td:nth-child(2)) {
  white-space: normal;
  min-width: 6em;
  max-width: 14em;
}

.markdown-body :deep(th) {
  background: var(--bg-panel);
  color: var(--syntax-title, var(--accent));
  font-weight: 600;
}

.markdown-assistant :deep(h1),
.markdown-assistant :deep(h2),
.markdown-assistant :deep(h3) {
  color: color-mix(in srgb, var(--accent) 35%, var(--text-primary));
}

.markdown-assistant :deep(strong) {
  color: var(--text-primary);
}

.markdown-assistant :deep(th) {
  background: var(--bg-elevated);
  color: var(--text-primary);
  font-weight: 650;
  border-color: color-mix(in srgb, var(--border) 70%, var(--text-muted));
}

.markdown-assistant :deep(td) {
  color: var(--text-primary);
  border-color: color-mix(in srgb, var(--border) 70%, var(--text-muted));
}

.markdown-assistant :deep(tr:nth-child(even) td) {
  background: color-mix(in srgb, var(--bg-elevated) 45%, var(--bg-panel));
}

:global(html[data-color-mode='dark']) .markdown-assistant :deep(h1),
:global(html[data-color-mode='dark']) .markdown-assistant :deep(h2),
:global(html[data-color-mode='dark']) .markdown-assistant :deep(h3) {
  color: color-mix(in srgb, var(--accent) 25%, var(--text-primary));
}

:global(html[data-color-mode='dark']) .markdown-assistant :deep(strong) {
  color: color-mix(in srgb, var(--accent) 20%, var(--text-primary));
  font-weight: 650;
}

:global(html[data-color-mode='dark']) .markdown-assistant :deep(th) {
  background: color-mix(in srgb, var(--bg-elevated) 85%, var(--text-primary) 5%);
  color: var(--text-primary);
}

:global(html[data-color-mode='dark']) .markdown-assistant :deep(tr:nth-child(even) td) {
  background: color-mix(in srgb, var(--bg-elevated) 35%, transparent);
}

.markdown-user :deep(tr:nth-child(even) td) {
  background: color-mix(in srgb, var(--bg-input) 55%, transparent);
}

.markdown-body :deep(blockquote) {
  margin: 0.5em 0;
  padding: 0.35em 0 0.35em 12px;
  border-left: 3px solid var(--accent);
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--accent) 6%, transparent);
  border-radius: 0 6px 6px 0;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 0.8em 0;
}

.image-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: var(--overlay-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.image-preview-wrap {
  position: relative;
  max-width: min(90vw, 1200px);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.preview-close {
  position: absolute;
  top: -36px;
  right: 0;
  background: none;
  border: none;
  color: var(--text-on-accent);
  font-size: 28px;
  cursor: pointer;
  line-height: 1;
}

.preview-image {
  max-width: 100%;
  max-height: calc(90vh - 40px);
  object-fit: contain;
  border-radius: 8px;
}

.preview-caption {
  margin-top: 12px;
  color: var(--text-secondary);
  font-size: 13px;
  text-align: center;
}
</style>
