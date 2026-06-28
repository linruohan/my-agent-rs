import { hydrateLlmConfigFromSidecar } from '@/utils/llmUserConfig';
import { hydrateUserConfigFromSidecar } from '@/utils/userConfig';
import { loadWorkspaceFromSidecar } from '@/utils/workspaceConfig';

/** Pull Sidecar-backed settings (user_settings.yaml, llm_user.yaml, workspace) into Pinia. */
export async function hydrateSettingsFromSidecar(port: number): Promise<void> {
  if (!port) return;
  await Promise.all([
    hydrateUserConfigFromSidecar(port),
    hydrateLlmConfigFromSidecar(port),
    loadWorkspaceFromSidecar(port).then(async (path) => {
      if (!path) return;
      const { useSettingsStore } = await import('@/stores/settings');
      useSettingsStore().workspacePath = path;
    }),
  ]);
}
