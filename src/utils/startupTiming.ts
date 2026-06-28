const APP_BOOT_T0 = performance.now();

export function logStartupMilestone(label: string, extra?: Record<string, unknown>) {
  const elapsedMs = Math.round(performance.now() - APP_BOOT_T0);
  const suffix = extra ? ` ${JSON.stringify(extra)}` : '';
  console.info(`[startup] +${elapsedMs}ms ${label}${suffix}`);
}

export function getBootElapsedMs() {
  return Math.round(performance.now() - APP_BOOT_T0);
}
