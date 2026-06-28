<script setup lang="ts">
import { computed, ref } from 'vue';
import { renderMarkdown } from '@/utils/markdown';
import { openHref, openLocalPath } from '@/utils/nativeOpen';

const props = defineProps<{
  content: string;
  variant?: 'assistant' | 'user';
}>();

const html = computed(() => renderMarkdown(props.content));

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
    const code = block?.querySelector('code');
    const text = code?.textContent ?? '';
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
.markdown-body :deep(p) {
  margin: 0.4em 0;
}

.markdown-body :deep(p:first-child) {
  margin-top: 0;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.4em 0;
  padding-left: 1.4em;
}

.markdown-body :deep(li) {
  margin: 0.25em 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 0.6em 0 0.3em;
  font-size: 1em;
  font-weight: 600;
}

.markdown-body :deep(h1:first-child),
.markdown-body :deep(h2:first-child),
.markdown-body :deep(h3:first-child) {
  margin-top: 0;
}

.markdown-body :deep(a),
.markdown-body :deep(.md-local-path) {
  color: #60a5fa;
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
  border: 1px solid #2a2d35;
}

.markdown-body :deep(:not(pre) > code) {
  background: rgba(0, 0, 0, 0.25);
  border-radius: 4px;
  padding: 0.1em 0.35em;
  font-size: 0.9em;
  font-family: ui-monospace, 'Cascadia Code', monospace;
}

.markdown-assistant :deep(:not(pre) > code) {
  background: #0f1117;
}

.markdown-body :deep(.md-code-block) {
  margin: 0.5em 0;
  border: 1px solid #2a2d35;
  border-radius: 8px;
  overflow: hidden;
  background: #0f1117;
}

.markdown-body :deep(.md-code-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: #16181d;
  border-bottom: 1px solid #2a2d35;
}

.markdown-body :deep(.md-code-lang) {
  font-size: 11px;
  color: #71717a;
  text-transform: lowercase;
  font-family: ui-monospace, monospace;
}

.markdown-body :deep(.md-copy-btn) {
  background: none;
  border: 1px solid #374151;
  border-radius: 4px;
  color: #a1a1aa;
  font-size: 11px;
  padding: 2px 8px;
  cursor: pointer;
  font-family: inherit;
  line-height: 1.4;
}

.markdown-body :deep(.md-copy-btn:hover) {
  background: #252830;
  color: #e4e4e7;
}

.markdown-body :deep(.md-copy-btn.copied) {
  color: #10b981;
  border-color: rgba(16, 185, 129, 0.35);
}

.markdown-body :deep(.md-code-block pre) {
  margin: 0;
  padding: 10px 12px;
  overflow-x: auto;
  background: transparent;
}

.markdown-body :deep(.md-code-block pre code) {
  background: none;
  padding: 0;
  font-size: 0.85em;
  font-family: ui-monospace, 'Cascadia Code', monospace;
  color: #e4e4e7;
  white-space: pre;
}

.markdown-body :deep(blockquote) {
  margin: 0.5em 0;
  padding-left: 12px;
  border-left: 3px solid #3b82f6;
  color: #a1a1aa;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #2a2d35;
  margin: 0.8em 0;
}

.image-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.85);
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
  color: #fff;
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
  color: #a1a1aa;
  font-size: 13px;
  text-align: center;
}
</style>
