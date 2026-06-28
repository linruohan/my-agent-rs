const DEFAULT_MAX_STRING = 400;
const DEFAULT_MAX_JSON = 4000;

function truncateValue(value: unknown, maxString = DEFAULT_MAX_STRING): unknown {
  if (typeof value === 'string') {
    if (value.length <= maxString) return value;
    return `${value.slice(0, maxString)}…（${value.length} 字符）`;
  }
  if (Array.isArray(value)) {
    return value.map((item) => truncateValue(item, maxString));
  }
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [key, nested] of Object.entries(value as Record<string, unknown>)) {
      out[key] = truncateValue(nested, maxString);
    }
    return out;
  }
  return value;
}

export function formatArgsForDisplay(
  args: Record<string, unknown>,
  maxJson = DEFAULT_MAX_JSON
): string {
  const preview = truncateValue(args) as Record<string, unknown>;
  let json = JSON.stringify(preview, null, 2);
  if (json.length > maxJson) {
    json = `${json.slice(0, maxJson)}\n…（共 ${json.length} 字符）`;
  }
  return json;
}
