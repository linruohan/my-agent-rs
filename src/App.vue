<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue';
import ChatView from '@/views/ChatView.vue';
import { useAgentWs } from '@/composables/useAgentWs';

const { connect, disconnect } = useAgentWs();

onMounted(() => {
  connect();
});

onUnmounted(() => {
  disconnect();
});
</script>

<template>
  <ChatView />
</template>
