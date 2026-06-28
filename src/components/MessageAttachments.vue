<script setup lang="ts">
import { computed } from 'vue';
import type { ChatAttachment } from '@/utils/attachments';
import { attachmentIcon, imageDataUrl } from '@/utils/attachments';
import { openExternalUrl, openLocalPath } from '@/utils/nativeOpen';

const props = defineProps<{
  attachments: ChatAttachment[];
}>();

const emit = defineEmits<{
  previewImage: [src: string, name: string];
}>();

const imageAttachments = computed(() =>
  props.attachments.filter((a) => a.type === 'image' && imageDataUrl(a))
);

const otherAttachments = computed(() =>
  props.attachments.filter((a) => a.type !== 'image')
);

async function onAttachmentClick(att: ChatAttachment) {
  if (att.type === 'url') {
    await openExternalUrl(att.content);
    return;
  }
  if (att.type === 'folder' && att.path) {
    await openLocalPath(att.path);
    return;
  }
  if (att.path) {
    await openLocalPath(att.path);
    return;
  }
  if (att.type === 'image') {
    const src = imageDataUrl(att);
    if (src) emit('previewImage', src, att.name);
  }
}

function onImageClick(att: ChatAttachment) {
  const src = imageDataUrl(att);
  if (src) emit('previewImage', src, att.name);
}
</script>

<template>
  <div v-if="attachments.length" class="message-attachments">
    <div v-if="imageAttachments.length" class="image-grid">
      <button
        v-for="(att, i) in imageAttachments"
        :key="`img-${i}`"
        type="button"
        class="image-thumb"
        :title="att.name"
        @click="onImageClick(att)"
      >
        <img :src="imageDataUrl(att)!" :alt="att.name" loading="lazy" />
      </button>
    </div>
    <div v-if="otherAttachments.length" class="attachment-list">
      <button
        v-for="(att, i) in otherAttachments"
        :key="`att-${i}`"
        type="button"
        class="attachment-chip"
        :class="{ clickable: att.type === 'url' || !!att.path }"
        @click="onAttachmentClick(att)"
      >
        <span class="att-icon">{{ attachmentIcon(att.type) }}</span>
        <span class="att-name">{{ att.name }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.message-attachments {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.image-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.image-thumb {
  padding: 0;
  border: 1px solid #2a2d35;
  border-radius: 8px;
  overflow: hidden;
  background: #0f1117;
  cursor: pointer;
  max-width: 240px;
  line-height: 0;
}

.image-thumb img {
  max-width: 240px;
  max-height: 180px;
  object-fit: cover;
  display: block;
}

.image-thumb:hover {
  border-color: #3b82f6;
}

.attachment-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.attachment-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #2a2d35;
  background: #16181d;
  color: #a1a1aa;
  font-size: 12px;
  cursor: default;
}

.attachment-chip.clickable {
  cursor: pointer;
}

.attachment-chip.clickable:hover {
  border-color: #3b82f6;
  color: #e4e4e7;
}

.att-name {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
