import { getBackendBaseURL } from "@/core/config";

import type { CronJob } from "./types";

const BASE = () => `${getBackendBaseURL()}/api/cron-jobs`;

export async function listCronJobs(): Promise<CronJob[]> {
  const res = await fetch(BASE());
  if (!res.ok) throw new Error(`Failed to load cron jobs: ${res.statusText}`);
  const data = (await res.json()) as { jobs: CronJob[] };
  return data.jobs;
}

export async function upsertCronJob(job: CronJob): Promise<CronJob> {
  const res = await fetch(BASE(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job }),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `Failed to save cron job: ${res.statusText}`);
  }
  const data = (await res.json()) as { job: CronJob };
  return data.job;
}

export async function deleteCronJob(name: string): Promise<void> {
  const res = await fetch(`${BASE()}/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to delete cron job: ${res.statusText}`);
}

export async function toggleCronJob(name: string): Promise<CronJob> {
  const res = await fetch(`${BASE()}/${encodeURIComponent(name)}/toggle`, {
    method: "PATCH",
  });
  if (!res.ok) throw new Error(`Failed to toggle cron job: ${res.statusText}`);
  const data = (await res.json()) as { job: CronJob };
  return data.job;
}
