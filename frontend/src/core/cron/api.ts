import { getBackendBaseURL } from "@/core/config";

import type { CronJob } from "./types";

// Gateway API (requires Gateway process to be running)
const GATEWAY_BASE = () => `${getBackendBaseURL()}/api/cron-jobs`;
// Local Next.js API (always available — reads ~/.deer-flow/cron-jobs.json directly)
const LOCAL_BASE = "/api/cron-jobs";

async function fetchWithFallback(
  gatewayUrl: string,
  localUrl: string,
  init?: RequestInit,
): Promise<Response> {
  try {
    const res = await fetch(gatewayUrl, { ...init, signal: AbortSignal.timeout(3000) });
    if (res.ok || res.status < 500) return res;
    throw new Error(`Gateway returned ${res.status}`);
  } catch {
    return fetch(localUrl, init);
  }
}

export async function listCronJobs(): Promise<CronJob[]> {
  const res = await fetchWithFallback(GATEWAY_BASE(), LOCAL_BASE);
  if (!res.ok) throw new Error(`Failed to load cron jobs: ${res.statusText}`);
  const data = (await res.json()) as { jobs: CronJob[] };
  return data.jobs;
}

export async function upsertCronJob(job: CronJob): Promise<CronJob> {
  const res = await fetchWithFallback(GATEWAY_BASE(), LOCAL_BASE, {
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
  const res = await fetchWithFallback(
    `${GATEWAY_BASE()}/${encodeURIComponent(name)}`,
    `${LOCAL_BASE}/${encodeURIComponent(name)}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(`Failed to delete cron job: ${res.statusText}`);
}

export async function toggleCronJob(name: string): Promise<CronJob> {
  const res = await fetchWithFallback(
    `${GATEWAY_BASE()}/${encodeURIComponent(name)}/toggle`,
    `${LOCAL_BASE}/${encodeURIComponent(name)}`,
    { method: "PATCH" },
  );
  if (!res.ok) throw new Error(`Failed to toggle cron job: ${res.statusText}`);
  const data = (await res.json()) as { job: CronJob };
  return data.job;
}
