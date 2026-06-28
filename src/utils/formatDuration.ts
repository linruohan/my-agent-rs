export function formatDuration(ms: number): string {
  const totalSec = Math.max(1, Math.round(ms / 1000));
  if (totalSec < 60) return `${totalSec}s`;

  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  if (min < 60) {
    return sec ? `${min}m ${sec}s` : `${min}m`;
  }

  const hr = Math.floor(min / 60);
  const remMin = min % 60;
  return remMin ? `${hr}h ${remMin}m` : `${hr}h`;
}
