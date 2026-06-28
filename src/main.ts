import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import './styles/main.css';
import './styles/themes.css';
import { applyAppearanceToDocument } from '@/composables/useAppearance';
import { logStartupMilestone } from '@/utils/startupTiming';

const pinia = createPinia();
const app = createApp(App);
app.use(pinia);

try {
  applyAppearanceToDocument();
} catch (err) {
  console.error('Failed to apply appearance:', err);
}

app.config.errorHandler = (err, _instance, info) => {
  console.error('[Vue error]', err, info);
  const root = document.getElementById('app');
  if (root && !root.querySelector('.boot-error')) {
    root.innerHTML = `<div class="boot-error" style="padding:24px;color:#fca5a5;background:#0f1117;height:100vh;font-family:sans-serif">
      <h2 style="color:#e4e4e7;margin-bottom:12px">界面加载失败</h2>
      <pre style="font-size:12px;white-space:pre-wrap;color:#a1a1aa">${String(err)}</pre>
    </div>`;
  }
};

app.mount('#app');
document.documentElement.classList.add('app-ready');
logStartupMilestone('Vue app mounted');
