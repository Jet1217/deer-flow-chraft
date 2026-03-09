"""Cron job management API.

Provides CRUD endpoints for scheduled tasks. Jobs are persisted to
`backend/.deer-flow/cron-jobs.json` and executed by the cron runner
(APScheduler) that starts with the Gateway.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.config.paths import resolve_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cron-jobs", tags=["cron"])

# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

_CRON_JOBS_FILE = ".deer-flow/cron-jobs.json"


def _jobs_path() -> Path:
    path = resolve_path(_CRON_JOBS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_jobs() -> dict[str, dict]:
    path = _jobs_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        logger.warning("Failed to parse cron-jobs.json, resetting.", exc_info=True)
        return {}


def _save_jobs(jobs: dict[str, dict]) -> None:
    _jobs_path().write_text(json.dumps(jobs, indent=2, default=str))


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_CRON_RE = re.compile(
    r"^(\*|[0-5]?\d|\*/\d+|\d+-\d+|\d+(,\d+)*)\s+"  # minute
    r"(\*|\d{1,2}|\*/\d+|\d+-\d+|\d+(,\d+)*)\s+"    # hour
    r"(\*|\d{1,2}|\*/\d+|\d+-\d+|\d+(,\d+)*)\s+"    # day
    r"(\*|\d{1,2}|\*/\d+|\d+-\d+|\d+(,\d+)*)\s+"    # month
    r"(\*|\d|\*/\d+|\d+-\d+|\d+(,\d+)*)$"            # weekday
)

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$|^[a-z0-9]$")


def _validate_cron(expr: str) -> bool:
    return bool(_CRON_RE.match(expr.strip()))


def _validate_name(name: str) -> bool:
    return bool(_NAME_RE.match(name))


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CronJob(BaseModel):
    name: str = Field(..., description="Unique job identifier (lowercase, hyphens)")
    cron: str = Field(..., description="5-field cron expression (min hour day month weekday)")
    prompt: str = Field(..., description="Prompt FlowEngine will execute on schedule")
    enabled: bool = Field(default=True, description="Whether the job is active")
    created_at: str | None = Field(default=None, description="ISO creation timestamp")
    updated_at: str | None = Field(default=None, description="ISO last-update timestamp")
    last_run_at: str | None = Field(default=None, description="ISO last execution timestamp")
    last_run_status: str | None = Field(default=None, description="Status of last run")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _validate_name(v):
            raise ValueError("Job name must be lowercase letters, digits, and hyphens (no leading/trailing hyphens)")
        return v

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        if not _validate_cron(v):
            raise ValueError(f"Invalid cron expression: '{v}'. Must be 5 fields: minute hour day month weekday")
        return v.strip()


class UpsertCronJobRequest(BaseModel):
    job: CronJob


class CronJobsListResponse(BaseModel):
    jobs: list[CronJob]


class CronJobResponse(BaseModel):
    job: CronJob


class DeleteResponse(BaseModel):
    success: bool
    message: str


# ---------------------------------------------------------------------------
# Scheduler integration (optional — graceful if APScheduler not installed)
# ---------------------------------------------------------------------------

_scheduler = None


def _get_scheduler():
    global _scheduler
    return _scheduler


def init_scheduler(scheduler) -> None:
    """Called from Gateway lifespan to register the APScheduler instance."""
    global _scheduler
    _scheduler = scheduler


def _sync_to_scheduler(job: CronJob) -> None:
    """Add or replace a job in APScheduler if available."""
    sched = _get_scheduler()
    if sched is None:
        return
    try:
        from apscheduler.triggers.cron import CronTrigger

        fields = job.cron.split()
        trigger = CronTrigger(
            minute=fields[0],
            hour=fields[1],
            day=fields[2],
            month=fields[3],
            day_of_week=fields[4],
        )

        async def _run_job(job_name: str, prompt: str) -> None:
            try:
                from src.client import DeerFlowClient

                client = DeerFlowClient()
                thread_id = f"cron-{job_name}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
                await client.stream(prompt, thread_id=thread_id)
                logger.info("Cron job '%s' completed.", job_name)
                _mark_run(job_name, "success")
            except Exception:
                logger.exception("Cron job '%s' failed.", job_name)
                _mark_run(job_name, "failed")

        import asyncio

        def _sync_wrapper(job_name: str, prompt: str) -> None:
            asyncio.create_task(_run_job(job_name, prompt))

        sched.add_job(
            _sync_wrapper,
            trigger=trigger,
            id=job.name,
            args=[job.name, job.prompt],
            replace_existing=True,
        )
        if not job.enabled:
            sched.pause_job(job.name)
    except Exception:
        logger.warning("Failed to sync job '%s' to scheduler.", job.name, exc_info=True)


def _remove_from_scheduler(job_name: str) -> None:
    sched = _get_scheduler()
    if sched is None:
        return
    try:
        sched.remove_job(job_name)
    except Exception:
        pass


def _mark_run(job_name: str, status: str) -> None:
    jobs = _load_jobs()
    if job_name in jobs:
        jobs[job_name]["last_run_at"] = datetime.now(timezone.utc).isoformat()
        jobs[job_name]["last_run_status"] = status
        _save_jobs(jobs)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=CronJobsListResponse, summary="List all cron jobs")
async def list_cron_jobs() -> CronJobsListResponse:
    jobs = _load_jobs()
    return CronJobsListResponse(jobs=[CronJob(**v) for v in jobs.values()])


@router.get("/{job_name}", response_model=CronJobResponse, summary="Get a cron job")
async def get_cron_job(job_name: str) -> CronJobResponse:
    jobs = _load_jobs()
    if job_name not in jobs:
        raise HTTPException(status_code=404, detail=f"Cron job '{job_name}' not found")
    return CronJobResponse(job=CronJob(**jobs[job_name]))


@router.post("", response_model=CronJobResponse, summary="Create or update a cron job")
async def upsert_cron_job(request: UpsertCronJobRequest) -> CronJobResponse:
    jobs = _load_jobs()
    now = datetime.now(timezone.utc).isoformat()
    job = request.job

    if job.name in jobs:
        existing = jobs[job.name]
        data = job.model_dump()
        data["created_at"] = existing.get("created_at", now)
        data["updated_at"] = now
        data["last_run_at"] = existing.get("last_run_at")
        data["last_run_status"] = existing.get("last_run_status")
    else:
        data = job.model_dump()
        data["created_at"] = now
        data["updated_at"] = now

    jobs[job.name] = data
    _save_jobs(jobs)
    _sync_to_scheduler(CronJob(**data))

    logger.info("Cron job '%s' upserted (cron=%s).", job.name, job.cron)
    return CronJobResponse(job=CronJob(**data))


@router.delete("/{job_name}", response_model=DeleteResponse, summary="Delete a cron job")
async def delete_cron_job(job_name: str) -> DeleteResponse:
    jobs = _load_jobs()
    if job_name not in jobs:
        raise HTTPException(status_code=404, detail=f"Cron job '{job_name}' not found")
    del jobs[job_name]
    _save_jobs(jobs)
    _remove_from_scheduler(job_name)
    logger.info("Cron job '%s' deleted.", job_name)
    return DeleteResponse(success=True, message=f"Cron job '{job_name}' deleted")


@router.patch("/{job_name}/toggle", response_model=CronJobResponse, summary="Enable or disable a cron job")
async def toggle_cron_job(job_name: str) -> CronJobResponse:
    jobs = _load_jobs()
    if job_name not in jobs:
        raise HTTPException(status_code=404, detail=f"Cron job '{job_name}' not found")
    jobs[job_name]["enabled"] = not jobs[job_name].get("enabled", True)
    jobs[job_name]["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_jobs(jobs)
    job = CronJob(**jobs[job_name])
    _sync_to_scheduler(job)
    return CronJobResponse(job=job)
