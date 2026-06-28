import { ref } from 'vue';
import { defineStore } from 'pinia';

export type PromptOptions = {
  title: string;
  defaultValue?: string;
  placeholder?: string;
  confirmLabel?: string;
  multiline?: boolean;
};

export type AlertOptions = {
  title: string;
  message: string;
  confirmLabel?: string;
};

export const useDialogStore = defineStore('dialog', () => {
  const promptOpen = ref(false);
  const promptOptions = ref<PromptOptions>({ title: '' });
  const alertOpen = ref(false);
  const alertOptions = ref<AlertOptions>({ title: '', message: '' });

  let promptResolve: ((value: string | null) => void) | null = null;
  let alertResolve: (() => void) | null = null;

  function prompt(options: PromptOptions): Promise<string | null> {
    return new Promise((resolve) => {
      promptResolve = resolve;
      promptOptions.value = options;
      promptOpen.value = true;
    });
  }

  function confirmPrompt(value: string) {
    promptOpen.value = false;
    promptResolve?.(value);
    promptResolve = null;
  }

  function cancelPrompt() {
    promptOpen.value = false;
    promptResolve?.(null);
    promptResolve = null;
  }

  function alert(options: AlertOptions): Promise<void> {
    return new Promise((resolve) => {
      alertResolve = resolve;
      alertOptions.value = options;
      alertOpen.value = true;
    });
  }

  function dismissAlert() {
    alertOpen.value = false;
    alertResolve?.();
    alertResolve = null;
  }

  return {
    promptOpen,
    promptOptions,
    alertOpen,
    alertOptions,
    prompt,
    confirmPrompt,
    cancelPrompt,
    alert,
    dismissAlert,
  };
});
