import { ref } from 'vue';
import { defineStore } from 'pinia';

export interface RagSource {
  name: string;
}

export const useKnowledgeStore = defineStore('knowledge', () => {
  const sources = ref<string[]>([]);
  const lastIngestResult = ref('');
  const lastSearchResults = ref<Array<{ source: string; content: string; score: number }>>([]);
  const isLoading = ref(false);

  function setSources(list: string[]) {
    sources.value = list;
  }

  function setIngestResult(msg: string) {
    lastIngestResult.value = msg;
  }

  function setSearchResults(results: Array<{ source: string; content: string; score: number }>) {
    lastSearchResults.value = results;
  }

  return {
    sources,
    lastIngestResult,
    lastSearchResults,
    isLoading,
    setSources,
    setIngestResult,
    setSearchResults,
  };
});
