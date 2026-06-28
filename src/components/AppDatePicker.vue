<script setup lang="ts">
import { computed } from 'vue';
import { VueDatePicker } from '@vuepic/vue-datepicker';
import { zhCN } from 'date-fns/locale';
import { parseIso, toIsoFromDate } from '@/utils/dateTime';

const props = withDefaults(
  defineProps<{
    modelValue: string;
    mode?: 'date' | 'datetime';
    placeholder?: string;
    disabled?: boolean;
    clearable?: boolean;
  }>(),
  {
    mode: 'datetime',
    placeholder: '选择日期',
    disabled: false,
    clearable: true,
  }
);

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const inner = computed({
  get() {
    return parseIso(props.modelValue);
  },
  set(v: Date | null) {
    emit('update:modelValue', toIsoFromDate(v, props.mode === 'datetime'));
  },
});
</script>

<template>
  <VueDatePicker
    v-model="inner"
    class="app-date-picker"
    :locale="zhCN"
    :enable-time-picker="mode === 'datetime'"
    :placeholder="placeholder"
    :disabled="disabled"
    :clearable="clearable"
    auto-apply
    :teleport="true"
    format="yyyy/MM/dd"
    :time-config="{ enableTimePicker: mode === 'datetime' }"
  />
</template>

<style scoped>
.app-date-picker {
  width: 100%;
}

.app-date-picker :deep(.dp__input) {
  background: var(--bg-input, var(--bg-code));
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  padding: 8px 12px;
  min-height: 36px;
}

.app-date-picker :deep(.dp__input::placeholder) {
  color: var(--text-muted);
}

.app-date-picker :deep(.dp__input:focus) {
  outline: none;
  border-color: var(--accent);
}
</style>
