/**
 * Next.js API route for cron jobs — reads directly from ~/.deer-flow/cron-jobs.json.
 * This is a server-side fallback that works even when the Gateway is not running.
 * The Gateway API (/api/cron-jobs) takes precedence when available.
 */
import { readFile, writeFile, mkdir } from "fs/promises";
import { homedir } from "os";
import { join } from "path";
import { NextResponse } from "next/server";

function jobsFilePath(): string {
  return join(homedir(), ".deer-flow", "cron-jobs.json");
}

async function loadJobs(): Promise<Record<string, unknown>> {
  try {
    const content = await readFile(jobsFilePath(), "utf-8");
    return JSON.parse(content) as Record<string, unknown>;
  } catch {
    return {};
  }
}

async function saveJobs(jobs: Record<string, unknown>): Promise<void> {
  const dir = join(homedir(), ".deer-flow");
  await mkdir(dir, { recursive: true });
  await writeFile(jobsFilePath(), JSON.stringify(jobs, null, 2), "utf-8");
}

export async function GET() {
  const jobs = await loadJobs();
  return NextResponse.json({ jobs: Object.values(jobs) });
}

export async function POST(request: Request) {
  const body = (await request.json()) as { job?: Record<string, unknown> };
  const job = body.job;
  if (!job || typeof job.name !== "string") {
    return NextResponse.json({ detail: "Invalid job" }, { status: 422 });
  }

  const jobs = await loadJobs();
  const now = new Date().toISOString();
  const existing = (jobs[job.name] ?? {}) as Record<string, unknown>;

  jobs[job.name] = {
    ...job,
    created_at: existing.created_at ?? now,
    updated_at: now,
    last_run_at: existing.last_run_at ?? null,
    last_run_status: existing.last_run_status ?? null,
  };

  await saveJobs(jobs);
  return NextResponse.json({ job: jobs[job.name] }, { status: 201 });
}
