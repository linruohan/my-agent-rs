<script setup lang="ts">
import { computed } from 'vue';
import { VueDatePicker } from '@vuepic/vue-datepicker';
import { zhCN } from 'date-fns/locale';
import { parseIso, toIsoFromDate } from '@/utils/dateTime';
import { useSettingsStore } from '@/stores/settings';
import { resolveColorMode } from '@/utils/themes';

const settings = useSettingsStore();

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

const isDark = computed(() => resolveColorMode(settings.appearance.colorMode) === 'dark');
</script>

<template>
  <VueDatePicker
    v-model="inner"
    class="app-date-picker"
    :dark="isDark"
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
</style>
