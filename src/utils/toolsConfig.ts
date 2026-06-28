import { sidecarBaseUrl } from '@/utils/sidecarFetch';

export type ConfigurableTool = {
  name: string;
  description?: string;
  enabled?: boolean;
  category?: string;
  risk?: string;
  has_user_override?: boolean;
};

export type ToolsConfigResponse = {
  tools?: ConfigurableTool[];
  count?: number;
  enabled_count?: number;
};

export async function loadToolsConfigFromSidecar(port: number): Promise<ToolsConfigResponse | null> {
  try {
    const resp = await fetch(`${sidecarBaseUrl(port)}/config/tools`);
    if (!resp.ok) return null;
    return (await resp.json()) as ToolsConfigResponse;
  } catch {
    return null;
  }
}

export function buildToolsConfigPayload(
  tools: ConfigurableTool[]
): { capability: Record<string, { enabled: boolean }>; business: Record<string, { enabled: boolean }> } {
  const capability: Record<string, { enabled: boolean }> = {};
  const business: Record<string, { enabled: boolean }> = {};
  for (const tool of tools) {
    const entry = { enabled: tool.enabled !== false };
    if (tool.category === 'business') {
      business[tool.name] = entry;
    } else {
      capability[tool.name] = entry;
    }
  }
  return { capability, business };
}

export async function saveToolsConfigToSidecar(
  port: number,
  tools: ConfigurableTool[]
): Promise<ToolsConfigResponse> {
  const payload = buildToolsConfigPayload(tools);
  const resp = await fetch(`${sidecarBaseUrl(port)}/config/tools`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    throw new Error('保存工具配置失败');
  }
  const data = (await resp.json()) as ToolsConfigResponse;
  await fetch(`${sidecarBaseUrl(port)}/tools/reload`, { method: 'POST' });
  return data;
}
