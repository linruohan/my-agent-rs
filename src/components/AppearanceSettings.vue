<script setup lang="ts">
import { computed, ref } from 'vue';
import { useSettingsStore } from '@/stores/settings';
import { THEME_LIST, UI_LANGUAGES } from '@/themes';

const settings = useSettingsStore();
const themeSearch = ref('');

const filteredThemes = computed(() => {
  const q = themeSearch.value.trim().toLowerCase();
  if (!q) return THEME_LIST;
  return THEME_LIST.filter(
    (t) =>
      t.name.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q) ||
      t.id.toLowerCase().includes(q)
  );
});

const colorModes = [
  { id: 'light', label: '明亮' },
  { id: 'dark', label: '暗色' },
  { id: 'system', label: '跟随系统' },
] as const;

const toolDisplayModes = [
  { id: 'product', label: '产品' },
  { id: 'technical', label: '技术' },
] as const;

const inlinePreviewModes = [
  { id: 'off', label: '关闭' },
  { id: 'ask', label: '询问' },
  { id: 'always', label: '总是' },
] as const;
</script>

<template>
  <div class="appearance-settings">
    <p class="section-intro">
      以下为桌面端界面偏好。「模式」控制明暗，「主题」控制配色与风格。
    </p>

    <section class="setting-block">
      <div class="block-head">
        <div>
          <h3>语言</h3>
          <p class="block-desc">选择桌面界面的显示语言</p>
        </div>
        <select v-model="settings.appearance.uiLanguage" class="control-select">
          <option v-for="lang in UI_LANGUAGES" :key="lang.id" :value="lang.id">
            {{ lang.label }}
          </option>
        </select>
      </div>
    </section>

    <section class="setting-block theme-block">
      <div class="block-head theme-head">
        <div>
          <h3>主题</h3>
          <p class="block-desc">桌面端调色板，所选模式叠加其上</p>
        </div>
        <div class="mode-tabs">
          <button
            v-for="m in colorModes"
            :key="m.id"
            type="button"
            class="mode-tab"
            :class="{ active: settings.appearance.colorMode === m.id }"
            @click="settings.appearance.colorMode = m.id"
          >
            {{ m.label }}
          </button>
        </div>
      </div>

      <input
        v-model="themeSearch"
        type="text"
        class="theme-search"
        placeholder="搜索主题…"
      />

      <div class="theme-grid">
        <button
          v-for="theme in filteredThemes"
          :key="theme.id"
          type="button"
          class="theme-card"
          :class="{ active: settings.appearance.themeId === theme.id }"
          @click="settings.appearance.themeId = theme.id"
        >
          <div class="theme-preview">
            <span
              class="preview-swatch"
              :style="{ background: theme.preview[0] }"
            />
            <span
              class="preview-swatch accent"
              :style="{ background: theme.preview[1] }"
            />
            <span
              class="preview-swatch"
              :style="{ background: theme.preview[2] }"
            />
          </div>
          <div class="theme-meta">
            <span class="theme-name">{{ theme.name }}</span>
            <span class="theme-desc">{{ theme.description }}</span>
          </div>
        </button>
      </div>
    </section>

    <section class="setting-block">
      <div class="block-head">
        <div>
          <h3>窗口透明</h3>
          <p class="block-desc">让整个窗口轻微透出桌面（macOS / Windows 桌面端）</p>
        </div>
        <div class="slider-wrap">
          <input
            v-model.number="settings.appearance.windowTransparency"
            type="range"
            min="0"
            max="100"
            step="5"
            class="slider"
          />
          <span class="slider-value">{{ settings.appearance.windowTransparency }}%</span>
        </div>
      </div>
    </section>

    <section class="setting-block">
      <div class="block-head">
        <div>
          <h3>工具调用显示</h3>
          <p class="block-desc">产品模式隐藏原始工具数据；技术模式显示完整输入/输出</p>
        </div>
        <div class="mode-tabs">
          <button
            v-for="m in toolDisplayModes"
            :key="m.id"
            type="button"
            class="mode-tab"
            :class="{ active: settings.appearance.toolCallDisplay === m.id }"
            @click="settings.appearance.toolCallDisplay = m.id"
          >
            {{ m.label }}
          </button>
        </div>
      </div>
    </section>

    <section class="setting-block">
      <div class="block-head">
        <div>
          <h3>内嵌预览</h3>
          <p class="block-desc">
            富媒体链接（YouTube、X 等）预览。「询问」先显示占位；「总是」自动加载；「关闭」保持纯链接
          </p>
        </div>
        <div class="mode-tabs">
          <button
            v-for="m in inlinePreviewModes"
            :key="m.id"
            type="button"
            class="mode-tab"
            :class="{ active: settings.appearance.inlinePreview === m.id }"
            @click="settings.appearance.inlinePreview = m.id"
          >
            {{ m.label }}
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.appearance-settings {
  width: 100%;
  max-width: none;
}

.section-intro {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.6;
  margin: 0 0 20px;
}

.setting-block {
  padding: 16px 0;
  border-bottom: 1px solid var(--border);
}

.setting-block:last-child {
  border-bottom: none;
}

.block-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.theme-head {
  align-items: center;
  margin-bottom: 12px;
}

h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px;
}

.block-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.5;
  max-width: 320px;
}

.control-select {
  min-width: 140px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  padding: 8px 12px;
  font-size: 13px;
  font-family: inherit;
}

.mode-tabs {
  display: flex;
  gap: 4px;
  background: var(--segment-track);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 3px;
  flex-shrink: 0;
}

.mode-tab {
  background: transparent;
  border: 1px solid transparent;
  color: var(--segment-item-text);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
  transition:
    background 0.15s,
    color 0.15s,
    border-color 0.15s,
    box-shadow 0.15s;
}

.mode-tab:hover:not(.active) {
  color: var(--text-primary);
  background: color-mix(in srgb, var(--text-primary) 6%, transparent);
}

.mode-tab.active {
  background: var(--segment-item-active-bg);
  color: var(--segment-item-active-text);
  border-color: var(--segment-item-active-border);
  font-weight: 600;
  box-shadow: 0 1px 3px var(--shadow-color);
}

.theme-search {
  width: 100%;
  box-sizing: border-box;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  padding: 10px 12px;
  font-size: 13px;
  margin-bottom: 12px;
  font-family: inherit;
}

.theme-search:focus {
  outline: none;
  border-color: var(--accent);
}

.theme-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
  max-height: 420px;
  overflow-y: auto;
  padding-right: 2px;
}

.theme-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-panel);
  border: 2px solid var(--border);
  border-radius: 10px;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition:
    border-color 0.15s,
    background 0.15s,
    box-shadow 0.15s;
}

.theme-card:hover:not(.active) {
  border-color: color-mix(in srgb, var(--accent) 45%, var(--border));
}

.theme-card.active {
  border-color: var(--choice-active-border);
  background: var(--choice-active-bg);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 35%, transparent);
}

.theme-preview {
  display: flex;
  gap: 3px;
  flex-shrink: 0;
}

.preview-swatch {
  width: 14px;
  height: 28px;
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.preview-swatch.accent {
  width: 18px;
}

.theme-meta {
  min-width: 0;
}

.theme-name {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.theme-card.active .theme-name {
  color: var(--accent);
}

.theme-card.active .theme-desc {
  color: var(--text-secondary);
}

.theme-desc {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
  line-height: 1.4;
}

.slider-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 200px;
}

.slider {
  flex: 1;
  accent-color: var(--accent);
}

.slider-value {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 36px;
  text-align: right;
}
</style>
