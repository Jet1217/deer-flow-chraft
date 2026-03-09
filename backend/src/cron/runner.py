"""Cron job runner — executed by system crontab.

Usage:
    python -m src.cron.runner <job_name>

The runner loads the job config from ~/.deer-flow/cron-jobs.json,
finds the matching job, and runs its prompt through DeerFlowClient.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [cron/%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("runner")


def _jobs_path() -> Path:
    from src.config.paths import get_paths

    return get_paths().base_dir / "cron-jobs.json"


def _load_jobs() -> dict[str, dict]:
    path = _jobs_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        logger.warning("Failed to parse cron-jobs.json", exc_info=True)
        return {}


def _save_jobs(jobs: dict[str, dict]) -> None:
    path = _jobs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jobs, indent=2, default=str))


def _mark_run(job_name: str, status: str) -> None:
    jobs = _load_jobs()
    if job_name in jobs:
        jobs[job_name]["last_run_at"] = datetime.now(timezone.utc).isoformat()
        jobs[job_name]["last_run_status"] = status
        _save_jobs(jobs)


async def _run(job_name: str) -> None:
    jobs = _load_jobs()
    job = jobs.get(job_name)
    if not job:
        logger.error("Job '%s' not found in cron-jobs.json", job_name)
        sys.exit(1)

    if not job.get("enabled", True):
        logger.info("Job '%s' is disabled, skipping.", job_name)
        return

    prompt = job.get("prompt", "")
    if not prompt:
        logger.error("Job '%s' has no prompt, skipping.", job_name)
        return

    thread_id = f"cron-{job_name}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    logger.info("Starting job '%s' (thread_id=%s)", job_name, thread_id)

    try:
        from src.client import DeerFlowClient

        client = DeerFlowClient()
        await client.stream(prompt, thread_id=thread_id)
        logger.info("Job '%s' completed successfully.", job_name)
        _mark_run(job_name, "success")
    except Exception:
        logger.exception("Job '%s' failed.", job_name)
        _mark_run(job_name, "failed")
        sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m src.cron.runner <job_name>", file=sys.stderr)
        sys.exit(1)

    job_name = sys.argv[1]
    asyncio.run(_run(job_name))


if __name__ == "__main__":
    main()
