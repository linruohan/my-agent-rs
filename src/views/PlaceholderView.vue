<script setup lang="ts">
defineProps<{
  title: string;
  description?: string;
  icon?: string;
}>();
</script>

<template>
  <div class="placeholder-view">
    <div class="icon">{{ icon || '🚧' }}</div>
    <h2>{{ title }}</h2>
    <p v-if="description">{{ description }}</p>
    <p class="sub">此功能即将推出</p>
  </div>
</template>

<style scoped>
.placeholder-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  text-align: center;
}

.icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.8;
}

h2 {
  font-size: 20px;
  color: var(--text-primary);
  margin-bottom: 8px;
}

p {
  color: var(--text-muted);
  font-size: 14px;
  max-width: 400px;
  line-height: 1.6;
}

.sub {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
