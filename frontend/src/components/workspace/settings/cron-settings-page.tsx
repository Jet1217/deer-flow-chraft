"use client";

import {
  CalendarClockIcon,
  PencilIcon,
  PlusIcon,
  PowerIcon,
  Trash2Icon,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  useCronJobs,
  useDeleteCronJob,
  useToggleCronJob,
  useUpsertCronJob,
} from "@/core/cron";
import type { CronJob } from "@/core/cron";
import { useI18n } from "@/core/i18n/hooks";

import { SettingsSection } from "./settings-section";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

const EMPTY_JOB: CronJob = {
  name: "",
  cron: "",
  prompt: "",
  enabled: true,
};

// ---------------------------------------------------------------------------
// Job form dialog
// ---------------------------------------------------------------------------

function CronJobDialog({
  open,
  initial,
  onClose,
}: {
  open: boolean;
  initial?: CronJob;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const isEdit = !!initial;
  const [form, setForm] = useState<CronJob>(initial ?? EMPTY_JOB);
  const [errors, setErrors] = useState<Partial<Record<keyof CronJob, string>>>(
    {},
  );
  const upsert = useUpsertCronJob();

  const set = <K extends keyof CronJob>(key: K, value: CronJob[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({ ...e, [key]: undefined }));
  };

  const validate = (): boolean => {
    const errs: typeof errors = {};
    if (!form.name.trim()) errs.name = t.cron.errors.nameRequired;
    else if (!/^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$/.test(form.name))
      errs.name = t.cron.errors.nameInvalid;
    if (!form.cron.trim()) errs.cron = t.cron.errors.cronRequired;
    else if (form.cron.trim().split(/\s+/).length !== 5)
      errs.cron = t.cron.errors.cronInvalid;
    if (!form.prompt.trim()) errs.prompt = t.cron.errors.promptRequired;
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) return;
    try {
      await upsert.mutateAsync(form);
      toast.success(
        isEdit ? t.cron.toast.updated(form.name) : t.cron.toast.created(form.name),
      );
      onClose();
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? t.cron.editJob : t.cron.newJob}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Name */}
          <div className="space-y-1.5">
            <label htmlFor="cron-name" className="text-sm font-medium">{t.cron.fields.name}</label>
            <Input
              id="cron-name"
              placeholder="daily-report"
              value={form.name}
              disabled={isEdit}
              onChange={(e) => set("name", e.target.value.toLowerCase())}
            />
            {errors.name && (
              <p className="text-destructive text-xs">{errors.name}</p>
            )}
          </div>

          {/* Cron expression */}
          <div className="space-y-1.5">
            <label htmlFor="cron-expr" className="text-sm font-medium">{t.cron.fields.cron}</label>
            <Input
              id="cron-expr"
              placeholder="0 9 * * *"
              value={form.cron}
              onChange={(e) => set("cron", e.target.value)}
            />
            <p className="text-muted-foreground text-xs">
              {t.cron.fields.cronHint}
            </p>
            {errors.cron && (
              <p className="text-destructive text-xs">{errors.cron}</p>
            )}
          </div>

          {/* Prompt */}
          <div className="space-y-1.5">
            <label htmlFor="cron-prompt" className="text-sm font-medium">{t.cron.fields.prompt}</label>
            <Textarea
              id="cron-prompt"
              placeholder={t.cron.fields.promptPlaceholder}
              rows={3}
              value={form.prompt}
              onChange={(e) => set("prompt", e.target.value)}
            />
            {errors.prompt && (
              <p className="text-destructive text-xs">{errors.prompt}</p>
            )}
          </div>

          {/* Enabled */}
          <div className="flex items-center gap-3">
            <Switch
              id="cron-enabled"
              checked={form.enabled}
              onCheckedChange={(v) => set("enabled", v)}
            />
            <label htmlFor="cron-enabled" className="text-sm font-medium">{t.cron.fields.enabled}</label>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button onClick={handleSave} disabled={upsert.isPending}>
            {upsert.isPending ? t.common.saving : t.common.save}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Job row
// ---------------------------------------------------------------------------

function CronJobRow({ job }: { job: CronJob }) {
  const { t } = useI18n();
  const toggle = useToggleCronJob();
  const del = useDeleteCronJob();
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <>
      <div className="bg-card flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{job.name}</span>
            <Badge
              variant={job.enabled ? "default" : "secondary"}
              className="text-xs"
            >
              {job.enabled ? t.cron.status.active : t.cron.status.paused}
            </Badge>
          </div>
          <code className="text-muted-foreground bg-muted rounded px-1.5 py-0.5 text-xs">
            {job.cron}
          </code>
          <p className="text-muted-foreground line-clamp-2 text-sm">
            {job.prompt}
          </p>
          {job.last_run_at && (
            <p className="text-muted-foreground/70 text-xs">
              {t.cron.lastRun}: {formatRelativeTime(job.last_run_at)}
              {job.last_run_status && (
                <span
                  className={
                    job.last_run_status === "success"
                      ? "text-green-500"
                      : "text-destructive"
                  }
                >
                  {" "}
                  · {job.last_run_status}
                </span>
              )}
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            title={job.enabled ? t.cron.actions.pause : t.cron.actions.resume}
            disabled={toggle.isPending}
            onClick={() => toggle.mutate(job.name)}
          >
            <PowerIcon className="size-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            title={t.cron.actions.edit}
            onClick={() => setEditing(true)}
          >
            <PencilIcon className="size-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            title={t.cron.actions.delete}
            className="text-destructive hover:text-destructive"
            onClick={() => setConfirmDelete(true)}
          >
            <Trash2Icon className="size-4" />
          </Button>
        </div>
      </div>

      {editing && (
        <CronJobDialog
          open
          initial={job}
          onClose={() => setEditing(false)}
        />
      )}

      {/* Delete confirmation */}
      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{t.cron.deleteConfirm.title}</DialogTitle>
          </DialogHeader>
          <p className="text-muted-foreground text-sm">
            {t.cron.deleteConfirm.message(job.name)}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="destructive"
              disabled={del.isPending}
              onClick={async () => {
                try {
                  await del.mutateAsync(job.name);
                  toast.success(t.cron.toast.deleted(job.name));
                  setConfirmDelete(false);
                } catch (err) {
                  toast.error((err as Error).message);
                }
              }}
            >
              {del.isPending ? t.common.deleting : t.common.delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ---------------------------------------------------------------------------
// Main settings page
// ---------------------------------------------------------------------------

export function CronSettingsPage() {
  const { t } = useI18n();
  const { jobs, isLoading } = useCronJobs();
  const [creating, setCreating] = useState(false);

  return (
    <SettingsSection title={t.cron.title} description={t.cron.description}>
      <div className="flex w-full flex-col gap-4">
        <header className="flex justify-end">
          <Button size="sm" onClick={() => setCreating(true)}>
            <PlusIcon className="size-4" />
            {t.cron.newJob}
          </Button>
        </header>

        {isLoading ? (
          <div className="text-muted-foreground text-sm">{t.common.loading}</div>
        ) : jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <div className="bg-muted flex h-14 w-14 items-center justify-center rounded-full">
              <CalendarClockIcon className="text-muted-foreground h-7 w-7" />
            </div>
            <div>
              <p className="font-medium">{t.cron.emptyTitle}</p>
              <p className="text-muted-foreground mt-1 text-sm">
                {t.cron.emptyDescription}
              </p>
            </div>
            <Button
              variant="outline"
              className="mt-2"
              onClick={() => setCreating(true)}
            >
              <PlusIcon className="mr-1.5 h-4 w-4" />
              {t.cron.newJob}
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {jobs.map((job) => (
              <CronJobRow key={job.name} job={job} />
            ))}
          </div>
        )}
      </div>

      {creating && (
        <CronJobDialog open onClose={() => setCreating(false)} />
      )}
    </SettingsSection>
  );
}
