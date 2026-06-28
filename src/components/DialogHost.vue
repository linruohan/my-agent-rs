<script setup lang="ts">
import { storeToRefs } from 'pinia';
import InputDialog from '@/components/InputDialog.vue';
import AlertDialog from '@/components/AlertDialog.vue';
import { useDialogStore } from '@/stores/dialog';

const dialog = useDialogStore();
const { promptOpen, promptOptions, alertOpen, alertOptions } = storeToRefs(dialog);
</script>

<template>
  <InputDialog
    :open="promptOpen"
    :title="promptOptions.title"
    :default-value="promptOptions.defaultValue"
    :placeholder="promptOptions.placeholder"
    :confirm-label="promptOptions.confirmLabel"
    :multiline="promptOptions.multiline"
    @confirm="dialog.confirmPrompt"
    @cancel="dialog.cancelPrompt"
  />
  <AlertDialog
    :open="alertOpen"
    :title="alertOptions.title"
    :message="alertOptions.message"
    :confirm-label="alertOptions.confirmLabel"
    @confirm="dialog.dismissAlert"
  />
</template>
