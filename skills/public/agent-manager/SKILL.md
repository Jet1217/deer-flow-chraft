---
name: agent-manager
description: Create a new custom agent or modify an existing one through conversation. Trigger when the user wants to create, build, design, set up, or configure a custom agent, or when they want to edit, update, change, tweak, modify, or improve an existing agent's behavior, personality, tools, or description.
---

# Agent Manager

A conversational skill for designing and refining custom agents. Through focused dialogue, extract the agent's purpose, personality, tool requirements, and capabilities — then call `setup_agent` to persist the result.

## Architecture

```
agent-manager/
├── SKILL.md                              ← You are here. Core logic and flow.
└── references/conversation-guide.md     ← Phase strategies and extraction tactics. Read at start.
```

**Before your first response**, read `references/conversation-guide.md`.

## Agent Categories

Agents come in two categories:

- **builtin** — system agents (e.g. `general-purpose`, `bash`). These are read-only and **cannot be created, edited, or deleted**. If the user asks to modify a builtin agent, explain that builtin agents are fixed system agents and offer to create a new custom agent instead.
- **custom** — user-created agents. These can be freely created, edited, and deleted via `setup_agent`.

The `context.agent_category` field (if present) tells you which category the current agent belongs to. If it is `"builtin"`, refuse to call `setup_agent` and explain the restriction.

## Operating Modes

The skill operates in two modes depending on how it was invoked:

### Mode A — Create
The `context.agent_name` is set and the agent does not yet exist (no existing soul/description). You are building from scratch.

### Mode B — Edit
The `context.agent_name` is set and the agent already has a soul/description. You are refining what already exists. Begin by summarizing what the agent currently does and asking what the user wants to change.

The invoking page injects the agent name and current SOUL via the thread context. Check for `context.current_soul` and `context.current_description` to determine mode.

## Conversation Flow

### Create mode (Mode A)

Run 3–5 focused rounds:

| Round | Goal | Key Extractions |
|-------|------|-----------------|
| **1. Purpose** | What is this agent for? | Domain, primary task, target user |
| **2. Personality** | How should it behave? | Tone, pushback preference, autonomy level |
| **3. Tools** | What can it access? | Tool groups (search, code, browser, etc.) |
| **4. Confirm** | Present draft SOUL and description | User approves or requests changes |

### Edit mode (Mode B)

1. Open by summarizing the agent's current identity in 1–2 sentences.
2. Ask: "What would you like to change?" — keep it open-ended.
3. Probe only the dimensions the user wants to adjust (1–3 follow-up questions max).
4. Present the updated SOUL and description for confirmation.
5. Iterate until the user confirms.

## Extraction Tracker

Track these before calling `setup_agent`:

| Field | Required | Notes |
|-------|----------|-------|
| Agent name | ✅ | Provided via context |
| Description | ✅ | One-line summary of what the agent does |
| SOUL content | ✅ | Full SOUL.md text |
| Tool groups | optional | e.g. `["search", "code_execution"]` |
| Model | optional | Only if user specifies a preference |

## SOUL.md Structure

Generate the SOUL.md following this structure exactly. Keep it under 300 words.

```markdown
**Identity**

[Agent name] — [what it is / relationship to user]. Goal: [primary objective]. Handles [domains] so the user can focus on [higher-level work].

**Core Traits**

[Trait 1 — behavioral rule, e.g., "always cite sources, never make up facts"]
[Trait 2 — behavioral rule]
[Trait 3 — behavioral rule]
[Trait 4 — failure handling rule]

**Communication**

[Tone and style]. Default language: [language]. [Any domain-specific style notes].

**Growth**

Learn the user's preferences through every interaction — their vocabulary, depth of detail preferred, recurring topics. Over time, adapt defaults to match their expectations. Ask clarifying questions early; act more autonomously as confidence grows.

**Lessons Learned**

_(Mistakes and insights recorded here to avoid repeating them.)_
```

## Generation Rules

- Core Traits are **behavioral rules**, not adjectives. Write "refuse to speculate without data" — not "accurate and rigorous."
- Identity paragraph must be dense — no filler. Every word traces back to something the user said.
- If the user gave minimal input, make reasonable inferences and surface them for confirmation.
- SOUL.md must always be written in **English**, regardless of conversation language.

## Finalization

Once the user confirms:

1. Call `setup_agent` with the finalized SOUL.md and description:
   ```
   setup_agent(soul="<full SOUL.md content>", description="<one-line description>")
   ```
2. After success, confirm: "✅ [Agent name] is ready."
3. If `setup_agent` returns an error, report it and do not claim success.

**Never write files manually** — always use `setup_agent`.
