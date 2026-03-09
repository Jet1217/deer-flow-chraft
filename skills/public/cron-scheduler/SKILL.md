---
name: cron-scheduler
description: Create, modify, or delete scheduled tasks using cron expressions. Trigger when the user wants to schedule a task, set up a recurring job, automate something at a specific time, or manage existing scheduled tasks.
---

# Cron Scheduler

A conversational skill for creating and managing scheduled tasks. Through dialogue, collect the task details and cron expression, then persist the schedule to both the config file and the system crontab.

## Architecture

Scheduled tasks are stored in two places that must always stay in sync:

1. **`~/.deer-flow/cron-jobs.json`** — metadata store (name, cron, prompt, enabled, timestamps). Read by the Settings UI via the Gateway API.
2. **System crontab** (`crontab -e`) — the actual scheduler. Each enabled job has one entry that calls the DeerFlow cron runner.

The system crontab entry format for each job:
```
<cron-expr> cd <backend-dir> && uv run python -m src.cron.runner <job-name> >> <log-file> 2>&1
```

**You are responsible for keeping both in sync** on every create/update/delete/toggle operation.

## Setup — detect paths once per session

Before creating the first job, detect the required paths:

```bash
# Backend directory (where pyproject.toml lives)
BACKEND_DIR=$(python3 -c "
import subprocess, json
result = subprocess.run(['find', '/Users', '-name', 'pyproject.toml', '-path', '*/deer-flow*'], capture_output=True, text=True)
print(result.stdout.strip().split()[0].replace('/pyproject.toml','')) if result.stdout.strip() else print('')
" 2>/dev/null)

# Fallback: check common locations
[ -z "$BACKEND_DIR" ] && [ -f "$HOME/Documents/workspace/AILab/deer-flow-chraft/backend/pyproject.toml" ] && BACKEND_DIR="$HOME/Documents/workspace/AILab/deer-flow-chraft/backend"

# Config file
JOBS_FILE="$HOME/.deer-flow/cron-jobs.json"
mkdir -p "$HOME/.deer-flow"

# Log directory
LOG_DIR="$HOME/.deer-flow/cron-logs"
mkdir -p "$LOG_DIR"

echo "BACKEND_DIR=$BACKEND_DIR"
echo "JOBS_FILE=$JOBS_FILE"
```

If `BACKEND_DIR` cannot be detected, ask the user for the path to the `backend/` directory.

## Conversation Flow

### Creating a new task

Run 2–3 focused rounds:

| Round | Goal | Key Extractions |
|-------|------|-----------------|
| **1. What** | What should happen? | Task description / prompt to run |
| **2. When** | How often / at what time? | Cron expression or natural language schedule |
| **3. Confirm** | Present the job summary | User approves or adjusts |

**Natural language → cron conversion examples:**

| User says | Cron expression |
|-----------|-----------------|
| every day at 9am | `0 9 * * *` |
| every Monday at 8am | `0 8 * * 1` |
| every hour | `0 * * * *` |
| every 30 minutes | `*/30 * * * *` |
| first day of every month at midnight | `0 0 1 * *` |
| weekdays at 6pm | `0 18 * * 1-5` |

Always convert natural language to a valid 5-field cron expression (`minute hour day month weekday`). Cron runs in UTC — if the user specifies a local time, convert it and mention the UTC equivalent.

### Modifying an existing task

1. Ask which task to modify (or use context if provided).
2. Ask what to change: schedule, name, or the task prompt.
3. Present the updated summary for confirmation.
4. Run the update operations below.

### Deleting a task

1. Confirm the task name with the user.
2. Run the delete operations below.

---

## Operations

All operations must update **both** the config file and the system crontab.

### Helper: build crontab entry

```bash
_cron_entry() {
  local JOB_NAME="$1"
  local CRON_EXPR="$2"
  echo "$CRON_EXPR cd $BACKEND_DIR && uv run python -m src.cron.runner $JOB_NAME >> $LOG_DIR/$JOB_NAME.log 2>&1"
}
```

### Create / Update

```bash
# 1. Write to config file
python3 - <<'PYEOF'
import json, os
from datetime import datetime, timezone

jobs_file = os.path.expanduser("~/.deer-flow/cron-jobs.json")
jobs = json.loads(open(jobs_file).read()) if os.path.exists(jobs_file) else {}

job_name = "JOB_NAME_PLACEHOLDER"
cron_expr = "CRON_EXPR_PLACEHOLDER"
prompt = "PROMPT_PLACEHOLDER"
enabled = True

now = datetime.now(timezone.utc).isoformat()
existing = jobs.get(job_name, {})
jobs[job_name] = {
    "name": job_name,
    "cron": cron_expr,
    "prompt": prompt,
    "enabled": enabled,
    "created_at": existing.get("created_at", now),
    "updated_at": now,
    "last_run_at": existing.get("last_run_at"),
    "last_run_status": existing.get("last_run_status"),
}
open(jobs_file, "w").write(json.dumps(jobs, indent=2))
print(f"✅ Saved job '{job_name}' to config")
PYEOF

# 2. Update system crontab (remove old entry for this job, add new one)
CRON_MARKER="# deer-flow:JOB_NAME_PLACEHOLDER"
NEW_ENTRY="CRON_EXPR_PLACEHOLDER cd $BACKEND_DIR && uv run python -m src.cron.runner JOB_NAME_PLACEHOLDER >> $LOG_DIR/JOB_NAME_PLACEHOLDER.log 2>&1  $CRON_MARKER"

(crontab -l 2>/dev/null | grep -v "$CRON_MARKER"; echo "$NEW_ENTRY") | crontab -
echo "✅ Crontab updated"
crontab -l | grep "deer-flow:"
```

### Delete

```bash
# 1. Remove from config file
python3 - <<'PYEOF'
import json, os

jobs_file = os.path.expanduser("~/.deer-flow/cron-jobs.json")
if os.path.exists(jobs_file):
    jobs = json.loads(open(jobs_file).read())
    job_name = "JOB_NAME_PLACEHOLDER"
    if job_name in jobs:
        del jobs[job_name]
        open(jobs_file, "w").write(json.dumps(jobs, indent=2))
        print(f"✅ Removed job '{job_name}' from config")
    else:
        print(f"⚠️  Job '{job_name}' not found in config")
PYEOF

# 2. Remove from crontab
CRON_MARKER="# deer-flow:JOB_NAME_PLACEHOLDER"
crontab -l 2>/dev/null | grep -v "$CRON_MARKER" | crontab -
echo "✅ Removed from crontab"
```

### Toggle (enable / disable)

```bash
# 1. Toggle in config file
python3 - <<'PYEOF'
import json, os
from datetime import datetime, timezone

jobs_file = os.path.expanduser("~/.deer-flow/cron-jobs.json")
jobs = json.loads(open(jobs_file).read()) if os.path.exists(jobs_file) else {}
job_name = "JOB_NAME_PLACEHOLDER"

if job_name not in jobs:
    print(f"❌ Job '{job_name}' not found")
else:
    jobs[job_name]["enabled"] = not jobs[job_name].get("enabled", True)
    jobs[job_name]["updated_at"] = datetime.now(timezone.utc).isoformat()
    open(jobs_file, "w").write(json.dumps(jobs, indent=2))
    state = "enabled" if jobs[job_name]["enabled"] else "disabled"
    print(f"✅ Job '{job_name}' is now {state}")
    print(f"ENABLED={str(jobs[job_name]['enabled']).lower()}")
PYEOF

# 2. Update crontab: re-add active entry or comment it out
# Re-read enabled state from config, then rebuild crontab entry
python3 - <<'PYEOF'
import json, os, subprocess

jobs_file = os.path.expanduser("~/.deer-flow/cron-jobs.json")
jobs = json.loads(open(jobs_file).read())
job = jobs.get("JOB_NAME_PLACEHOLDER", {})
enabled = job.get("enabled", True)
cron_expr = job.get("cron", "")
job_name = "JOB_NAME_PLACEHOLDER"

backend_dir = "BACKEND_DIR_PLACEHOLDER"
log_dir = os.path.expanduser("~/.deer-flow/cron-logs")
marker = f"# deer-flow:{job_name}"
entry = f"{cron_expr} cd {backend_dir} && uv run python -m src.cron.runner {job_name} >> {log_dir}/{job_name}.log 2>&1  {marker}"
if not enabled:
    entry = f"# {entry}"

result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
lines = [l for l in result.stdout.splitlines() if marker not in l]
lines.append(entry)
new_crontab = "\n".join(lines) + "\n"
subprocess.run(["crontab", "-"], input=new_crontab, text=True)
print(f"✅ Crontab updated (enabled={enabled})")
PYEOF
```

### List

```bash
python3 - <<'PYEOF'
import json, os

jobs_file = os.path.expanduser("~/.deer-flow/cron-jobs.json")
if not os.path.exists(jobs_file):
    print("No scheduled tasks found.")
else:
    jobs = json.loads(open(jobs_file).read())
    if not jobs:
        print("No scheduled tasks found.")
    else:
        for name, job in jobs.items():
            status = "✅ enabled" if job.get("enabled", True) else "⏸ disabled"
            print(f"  {status}  {name}  [{job['cron']}]  — {job['prompt'][:60]}")
PYEOF
```

---

## Rules

- Job names must be lowercase with hyphens only (e.g. `daily-report`).
- Always show the cron expression AND its human-readable meaning (with UTC note) before confirming.
- After success, confirm: "✅ Scheduled: **[name]** — runs [human-readable schedule] (UTC)."
- If any step fails, report it clearly and do not claim success.
- Always verify crontab was updated: run `crontab -l | grep "deer-flow:"` after each change.
- Logs are written to `~/.deer-flow/cron-logs/<job-name>.log`.
