import { watch, onMounted } from 'vue';
import { useSettingsStore } from '@/stores/settings';
import { DEFAULT_APPEARANCE, resolveColorMode, resolveThemeId } from '@/utils/themes';

let systemModeListener: ((e: MediaQueryListEvent) => void) | null = null;

export function applyAppearanceToDocument() {
  const settings = useSettingsStore();
  const appearance = { ...DEFAULT_APPEARANCE, ...settings.appearance };
  const root = document.documentElement;
  const resolved = resolveColorMode(appearance.colorMode);

  root.setAttribute('data-theme', resolveThemeId(appearance.themeId));
  root.setAttribute('data-color-mode', resolved);
  root.style.setProperty(
    '--window-transparency',
    String((appearance.windowTransparency ?? 0) / 100)
  );
  root.lang = appearance.uiLanguage === 'en' ? 'en' : 'zh-CN';
}

export function useAppearance() {
  const settings = useSettingsStore();

  function setupSystemListener() {
    if (systemModeListener) return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    systemModeListener = () => {
      if (settings.appearance.colorMode === 'system') {
        applyAppearanceToDocument();
      }
    };
    mq.addEventListener('change', systemModeListener);
  }

  onMounted(() => {
    applyAppearanceToDocument();
    setupSystemListener();
  });

  watch(
    () => settings.appearance,
    () => applyAppearanceToDocument(),
    { deep: true }
  );
}
