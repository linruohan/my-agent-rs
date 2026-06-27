<script setup lang="ts">
import { onUnmounted } from 'vue';
import ChatView from '@/views/ChatView.vue';
import { useTauriNative } from '@/composables/useTauriNative';
import { useAgentWs } from '@/composables/useAgentWs';

useTauriNative();
const { disconnect } = useAgentWs();

onUnmounted(() => {
  disconnect();
});
</script>

<template>
  <ChatView />
</template>
