---
name: cron-scheduler
description: Create, modify, or delete scheduled tasks using cron expressions. Trigger when the user wants to schedule a task, set up a recurring job, automate something at a specific time, or manage existing scheduled tasks.
---

# Cron Scheduler

A conversational skill for creating and managing scheduled tasks. Through dialogue, collect the task details and cron expression, then call `manage_cron_job` to persist the schedule.

## What This Skill Does

- **Create** a new scheduled task with a cron expression, a name, and a prompt that FlowEngine will execute on schedule.
- **Modify** an existing task's schedule, name, or prompt.
- **Delete** a scheduled task.
- **List** all current scheduled tasks.

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

Always convert natural language to a valid 5-field cron expression (`minute hour day month weekday`).

### Modifying an existing task

1. Ask which task to modify (or use context if provided).
2. Ask what to change: schedule, name, or the task prompt.
3. Present the updated summary for confirmation.
4. Call `manage_cron_job` with `action: "update"`.

### Deleting a task

1. Confirm the task name with the user.
2. Call `manage_cron_job` with `action: "delete"`.

## Tool Call

Use the `bash` tool to call the Gateway API:

### Create / Update
```bash
curl -s -X POST http://localhost:8001/api/cron-jobs \
  -H "Content-Type: application/json" \
  -d '{
    "action": "upsert",
    "job": {
      "name": "<job-name>",
      "cron": "<cron-expression>",
      "prompt": "<what FlowEngine should do>",
      "enabled": true
    }
  }'
```

### Delete
```bash
curl -s -X DELETE http://localhost:8001/api/cron-jobs/<job-name>
```

### List
```bash
curl -s http://localhost:8001/api/cron-jobs
```

## Rules

- Job names must be lowercase with hyphens only (e.g. `daily-report`).
- Always show the cron expression AND its human-readable meaning before confirming.
- If the user's schedule is ambiguous, ask one clarifying question.
- After success, confirm: "✅ Scheduled: **[name]** — runs [human-readable schedule]."
- If the API returns an error, report it clearly and do not claim success.
