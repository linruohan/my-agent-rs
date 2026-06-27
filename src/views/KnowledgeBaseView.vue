<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useKnowledgeStore } from '@/stores/knowledge';
import { useAgentWs } from '@/composables/useAgentWs';

const knowledgeStore = useKnowledgeStore();
const { listRagSources, ingestRagContent, searchRag, deleteRagSource } = useAgentWs();

const searchQuery = ref('');
const dragOver = ref(false);
const SUPPORTED = ['.md', '.txt', '.markdown'];

onMounted(() => {
  listRagSources();
});

function isSupported(name: string) {
  const lower = name.toLowerCase();
  return SUPPORTED.some((ext) => lower.endsWith(ext));
}

async function processFiles(files: FileList | File[]) {
  for (const file of Array.from(files)) {
    if (!isSupported(file.name)) continue;
    const content = await file.text();
    ingestRagContent(file.name, content);
  }
}

function onDrop(e: DragEvent) {
  dragOver.value = false;
  if (e.dataTransfer?.files?.length) {
    processFiles(e.dataTransfer.files);
  }
}

function onFileInput(e: Event) {
  const input = e.target as HTMLInputElement;
  if (input.files?.length) {
    processFiles(input.files);
    input.value = '';
  }
}

function handleSearch() {
  const q = searchQuery.value.trim();
  if (q) searchRag(q);
}

function handleDelete(source: string) {
  if (confirm(`删除索引文档 "${source}"？`)) {
    deleteRagSource(source);
  }
}
</script>

<template>
  <div class="knowledge-view">
    <header>
      <h2>知识库</h2>
      <p class="hint">支持拖拽或选择 .md / .txt 文件导入（FAISS 混合检索）</p>
    </header>

    <div
      class="drop-zone"
      :class="{ over: dragOver }"
      @dragover.prevent="dragOver = true"
      @dragleave="dragOver = false"
      @drop.prevent="onDrop"
    >
      <p>将文档拖到此处</p>
      <label class="file-btn">
        选择文件
        <input type="file" accept=".md,.txt,.markdown" multiple hidden @change="onFileInput" />
      </label>
    </div>

    <p v-if="knowledgeStore.lastIngestResult" class="status">
      {{ knowledgeStore.lastIngestResult }}
    </p>

    <section class="sources">
      <h3>已索引文档 ({{ knowledgeStore.sources.length }})</h3>
      <ul v-if="knowledgeStore.sources.length">
        <li v-for="s in knowledgeStore.sources" :key="s">
          <span>{{ s }}</span>
          <button class="btn-delete" @click="handleDelete(s)">删除</button>
        </li>
      </ul>
      <p v-else class="empty">暂无文档，请导入</p>
    </section>

    <section class="search">
      <h3>检索测试</h3>
      <div class="search-row">
        <input v-model="searchQuery" placeholder="输入关键词…" @keydown.enter="handleSearch" />
        <button :disabled="knowledgeStore.isLoading" @click="handleSearch">搜索</button>
      </div>
      <div v-for="(r, i) in knowledgeStore.lastSearchResults" :key="i" class="result">
        <div class="meta">
          {{ r.source }} · score {{ r.score }}
          <span v-if="(r as any).methods"> · {{ (r as any).methods?.join('+') }}</span>
        </div>
        <p>{{ r.content.slice(0, 200) }}…</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.knowledge-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

header h2 {
  font-size: 18px;
  margin-bottom: 4px;
}

.hint {
  color: #71717a;
  font-size: 13px;
  margin-bottom: 20px;
}

.drop-zone {
  border: 2px dashed #2a2d35;
  border-radius: 12px;
  padding: 32px;
  text-align: center;
  color: #71717a;
  margin-bottom: 16px;
  transition: border-color 0.2s, background 0.2s;
}

.drop-zone.over {
  border-color: #3b82f6;
  background: #1e3a5f33;
}

.file-btn {
  display: inline-block;
  margin-top: 12px;
  background: #3b82f6;
  color: white;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.status {
  font-size: 13px;
  color: #10b981;
  margin-bottom: 16px;
}

.sources h3,
.search h3 {
  font-size: 14px;
  margin-bottom: 8px;
  color: #a1a1aa;
}

.sources ul {
  list-style: none;
  margin-bottom: 24px;
}

.sources li {
  padding: 6px 0;
  font-size: 13px;
  border-bottom: 1px solid #1f2128;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.btn-delete {
  background: none;
  border: none;
  color: #ef4444;
  cursor: pointer;
  font-size: 12px;
}

.empty {
  color: #71717a;
  font-size: 13px;
}

.search-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.search-row input {
  flex: 1;
  background: #16181d;
  border: 1px solid #2a2d35;
  border-radius: 6px;
  color: #e4e4e7;
  padding: 8px 12px;
}

.search-row button {
  background: #3b82f6;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
}

.result {
  background: #16181d;
  border: 1px solid #2a2d35;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
  font-size: 13px;
}

.meta {
  color: #71717a;
  font-size: 11px;
  margin-bottom: 6px;
}
</style>
