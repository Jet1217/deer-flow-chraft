"""Cron job management API.

Read-only view of scheduled tasks. The actual scheduling is handled by the
system crontab — this API only reads/writes the cron-jobs.json config file.

The cron-scheduler skill is responsible for keeping crontab in sync with the
config file whenever jobs are created, updated, or deleted.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cron-jobs", tags=["cron"])


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _jobs_path() -> Path:
    from src.config.paths import get_paths

    path = get_paths().base_dir / "cron-jobs.json"
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
    r"(\*|\d{1,2}|\*/\d+|\d+-\d+|\d+(,\d+)*)\s+"  # hour
    r"(\*|\d{1,2}|\*/\d+|\d+-\d+|\d+(,\d+)*)\s+"  # day
    r"(\*|\d{1,2}|\*/\d+|\d+-\d+|\d+(,\d+)*)\s+"  # month
    r"(\*|\d|\*/\d+|\d+-\d+|\d+(,\d+)*)$"  # weekday
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
    """Persist job metadata to cron-jobs.json.

    Note: this endpoint only updates the config file. The caller (cron-scheduler
    skill) is responsible for also updating the system crontab.
    """
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

    logger.info("Cron job '%s' saved to config (cron=%s).", job.name, job.cron)
    return CronJobResponse(job=CronJob(**data))


@router.delete("/{job_name}", response_model=DeleteResponse, summary="Delete a cron job")
async def delete_cron_job(job_name: str) -> DeleteResponse:
    """Remove job from cron-jobs.json.

    Note: the caller (cron-scheduler skill) must also remove the entry from
    the system crontab.
    """
    jobs = _load_jobs()
    if job_name not in jobs:
        raise HTTPException(status_code=404, detail=f"Cron job '{job_name}' not found")
    del jobs[job_name]
    _save_jobs(jobs)
    logger.info("Cron job '%s' removed from config.", job_name)
    return DeleteResponse(success=True, message=f"Cron job '{job_name}' deleted")


@router.patch("/{job_name}/toggle", response_model=CronJobResponse, summary="Enable or disable a cron job")
async def toggle_cron_job(job_name: str) -> CronJobResponse:
    """Toggle enabled state in cron-jobs.json.

    Note: the caller must also update the system crontab (comment/uncomment
    the crontab entry) to reflect the new state.
    """
    jobs = _load_jobs()
    if job_name not in jobs:
        raise HTTPException(status_code=404, detail=f"Cron job '{job_name}' not found")
    jobs[job_name]["enabled"] = not jobs[job_name].get("enabled", True)
    jobs[job_name]["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_jobs(jobs)
    job = CronJob(**jobs[job_name])
    logger.info("Cron job '%s' toggled to enabled=%s.", job_name, job.enabled)
    return CronJobResponse(job=job)
