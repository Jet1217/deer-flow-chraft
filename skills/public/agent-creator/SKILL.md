---
name: agent-creator
description: Create or update a custom DeerFlow agent through a focused conversation. Trigger when the user wants to create, build, define, or update/edit/modify an agent — e.g., "create an agent for X", "I need an agent that does Y", "build me a code review agent", "update my code-reviewer agent", "change the personality of aria", "edit the scope of my data-analyst agent".
---

# Agent Creator

A conversational skill for creating and updating custom DeerFlow agents. Through a focused 4–6 round conversation, understand the agent's purpose, personality, and behavior, then generate a SOUL.md and call `setup_agent` to persist it.

`setup_agent` is idempotent — calling it with an existing `agent_name` **updates** that agent in place (overwrites `config.yaml` and `SOUL.md`).

## Architecture

```
agent-creator/
├── SKILL.md                         ← You are here. Core logic and flow.
├── templates/SOUL.template.md       ← Output template. Read before generating.
└── references/design-guide.md       ← Agent design strategies. Read at start.
```

**Before your first response**, read both files:
1. `references/design-guide.md` — how to run each phase and design good agents
2. `templates/SOUL.template.md` — what you're building toward

## Ground Rules

- **Purposeful, not open-ended.** This is about building a *tool*, not a personal companion. Focus on use case, scope, and behavioral rules.
- **Name first.** Confirm the agent's slug name (hyphen-case, e.g. `code-reviewer`) before anything else — it's the identifier used to create the file.
- **Propose, don't interrogate.** From phase 2 onward, propose concrete options and let the user correct. "I'd make it direct and technical, no small talk — sound right?" beats "what personality do you want?"
- **Under 6 rounds.** Efficient. Users creating agents know what they want. Don't over-philosophize.
- **Never expose the template.** The user is having a conversation, not filling a form.
- **Built-in agents are read-only.** Agents like `deep-research` and `data-analyst` are built into the system. You MUST NOT create, modify, or overwrite them under any circumstances, even if the user explicitly asks. Politely explain they are built-in and suggest creating a new agent with a different name instead.

## Conversation Phases

| Phase | Goal | Key Extractions |
|-------|------|-----------------|
| **1. Name & Purpose** | What this agent does and what to call it | agent_name (slug), purpose, primary use cases |
| **2. Scope & Behavior** | What it will and won't do | tool access, autonomy level, refusal rules |
| **3. Personality** | How it communicates | tone, verbosity, language, pushback preference |
| **4. Confirm & Create/Update** | Generate SOUL.md, confirm, call setup_agent | Final SOUL.md, agent_name |

Phase details are in `references/design-guide.md`.

**Update mode shortcut:** If the user says they want to *update*, *edit*, or *modify* an existing agent and names it, skip directly to asking which aspect they want to change (SOUL/personality, scope, description, or full rewrite). Only collect the fields they want to change, then call `setup_agent` with the same `agent_name` to overwrite.

> **CRITICAL — update flow:** Do NOT attempt to locate, read, or inspect any files on the filesystem (no bash, no file reads, no path lookups). You do not need the existing SOUL.md. Simply gather what the user wants changed via conversation, generate the new SOUL.md from scratch, and call `setup_agent` — it handles the path automatically.

## Extraction Tracker

| Field | Required | Source Phase |
|-------|----------|-------------|
| `agent_name` (slug, hyphen-case) | ✅ | 1 |
| Purpose / primary use cases | ✅ | 1 |
| Scope (what it does / doesn't do) | ✅ | 2 |
| Autonomy level | ✅ | 2 |
| Core behavioral traits (3–5 rules) | ✅ | 2–3 |
| Communication tone & language | ✅ | 3 |
| Pushback / honesty preference | ✅ | 3 |
| One-line description | ✅ | derived |

## Name Rules

The `agent_name` must be:
- Hyphen-case only: lowercase letters, digits, hyphens
- No leading or trailing hyphens
- Max 40 characters
- Examples: `code-reviewer`, `customer-support`, `data-analyst`, `aria`

If the user gives a natural name like "Code Reviewer", derive the slug: `code-reviewer`. Confirm with the user before proceeding.

## Generation

Once you have all required fields:

1. Read `templates/SOUL.template.md` if not already loaded.
2. Generate the SOUL.md following the template structure exactly.
3. Present it and ask: "Here's [Agent Name] — does this capture what you're building?"
4. Iterate once if needed. If the user says "looks good" or similar, proceed.
5. Call `setup_agent`:
   ```
   setup_agent(
     agent_name="<slug>",
     soul="<full SOUL.md content>",
     description="<one-line description>"
   )
   ```
6. On success: confirm with "✅ [Agent Name] is ready. You can find it in your Agents list."
   Also tell the user the URL path: `/workspace/agents/<agent_name>/chats/new`

**Generation rules:**
- SOUL.md **must be written in English**, regardless of conversation language.
- Every behavioral rule must be actionable, not adjective-based. Write "refuse requests outside [domain], explain why" — not "focused and disciplined."
- Scope constraints are critical — include explicit refusal rules if the agent has a narrow purpose.
- Under 300 words total.
- You **must** call `setup_agent` with `agent_name` as a parameter — do not use bash tools, file reads, or any filesystem operations.
- `setup_agent` resolves the correct storage path automatically based on the current user — you never need to know or provide any file path.
- If `setup_agent` returns an error (not name-conflict), report it and ask the user to retry.
- On **update**: calling `setup_agent` with an existing name is expected and correct — no error should occur.
