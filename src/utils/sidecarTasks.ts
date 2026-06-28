import { sidecarBaseUrl } from '@/utils/sidecarFetch';

export type TaskReminderRow = {
  job_id: string;
  run_at: string;
  title: string;
  message: string;
  entity_type: string;
  entity_id?: number;
};

/** Entity-aware reminders (todo/project/task + scheduler jobs). Prefer over raw `/scheduler/jobs`. */
export async function fetchTaskRemindersRest(port: number): Promise<TaskReminderRow[]> {
  try {
    const resp = await fetch(`${sidecarBaseUrl(port)}/tasks/reminders`);
    if (!resp.ok) return [];
    const data = (await resp.json()) as { reminders?: TaskReminderRow[] };
    return data.reminders ?? [];
  } catch {
    return [];
  }
}
