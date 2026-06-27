<script setup lang="ts">
import SessionSidebar from '@/components/SessionSidebar.vue';
import ChatPanel from '@/components/ChatPanel.vue';
import ConfirmModal from '@/components/ConfirmModal.vue';
import StatusBar from '@/components/StatusBar.vue';
</script>

<template>
  <div class="chat-view">
    <SessionSidebar />
    <div class="main-area">
      <ChatPanel />
      <StatusBar />
    </div>
    <ConfirmModal />
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  height: 100vh;
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
</style>
