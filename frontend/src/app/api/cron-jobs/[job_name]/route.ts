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

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ job_name: string }> },
) {
  const { job_name } = await params;
  const jobs = await loadJobs();
  if (!(job_name in jobs)) {
    return NextResponse.json({ detail: `Cron job '${job_name}' not found` }, { status: 404 });
  }
  delete jobs[job_name];
  await saveJobs(jobs);
  return NextResponse.json({ success: true, message: `Cron job '${job_name}' deleted` });
}

export async function PATCH(
  _request: Request,
  { params }: { params: Promise<{ job_name: string }> },
) {
  const { job_name } = await params;
  const jobs = await loadJobs();
  if (!(job_name in jobs)) {
    return NextResponse.json({ detail: `Cron job '${job_name}' not found` }, { status: 404 });
  }
  const job = jobs[job_name] as Record<string, unknown>;
  job.enabled = !job.enabled;
  job.updated_at = new Date().toISOString();
  await saveJobs(jobs);
  return NextResponse.json({ job });
}
