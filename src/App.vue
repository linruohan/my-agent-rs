<script setup lang="ts">
import { onUnmounted } from 'vue';
import ChatView from '@/views/ChatView.vue';
import { useTauriNative } from '@/composables/useTauriNative';
import { useAgentWs } from '@/composables/useAgentWs';
import { useAppearance } from '@/composables/useAppearance';

useTauriNative();
useAppearance();
const { disconnect } = useAgentWs();

onUnmounted(() => {
  disconnect();
});
</script>

<template>
  <ChatView />
</template>
