import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import './styles/main.css';
import './themes/index.css';
import '@vuepic/vue-datepicker/dist/main.css';
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
    root.innerHTML = `<div class="boot-error">
      <h2>界面加载失败</h2>
      <pre>${String(err)}</pre>
    </div>`;
  }
};

app.mount('#app');
document.documentElement.classList.add('app-ready');
logStartupMilestone('Vue app mounted');
