export interface CronJob {
  name: string;
  cron: string;
  prompt: string;
  enabled: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  last_run_at?: string | null;
  last_run_status?: string | null;
}

export interface UpsertCronJobRequest {
  job: CronJob;
}
