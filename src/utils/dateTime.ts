/** ISO 字符串 ↔ Date 转换，供统一日期控件使用 */

export function parseIso(iso: string): Date | null {
  if (!iso?.trim()) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function toIsoFromDate(d: Date | null | undefined, withTime = true): string {
  if (!d || Number.isNaN(d.getTime())) return '';
  if (withTime) return d.toISOString();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function toLocalDatetimeInput(iso: string): string {
  const d = parseIso(iso);
  if (!d) return '';
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const h = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${y}-${m}-${day}T${h}:${min}`;
}

export function localDatetimeToIso(local: string): string {
  if (!local.trim()) return '';
  const d = new Date(local);
  return Number.isNaN(d.getTime()) ? local : d.toISOString();
}
