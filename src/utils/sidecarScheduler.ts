import {
  fetchSidecarAuthToken,
  sidecarAuthHeaders,
  sidecarBaseUrl,
} from '@/utils/sidecarFetch';

export type SchedulerJob = {
  id: string;
  job_type: string;
  payload: string;
  run_at: string;
  status: string;
};

export async function listSchedulerJobsRest(
  port: number,
  token?: string | null
): Promise<SchedulerJob[]> {
  const auth = token ?? (await fetchSidecarAuthToken(port));
  const resp = await fetch(`${sidecarBaseUrl(port)}/scheduler/jobs`, {
    headers: sidecarAuthHeaders(auth),
  });
  if (!resp.ok) {
    throw new Error(`scheduler list failed: ${resp.status}`);
  }
  const data = (await resp.json()) as { jobs?: SchedulerJob[] };
  return data.jobs ?? [];
}
