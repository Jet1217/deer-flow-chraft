# Conversation Guide

Detailed phase strategies for agent creation and editing. Read this before your first response.

---

## Create Mode — Phase Strategies

### Round 1 — Purpose

Open with a single, open-ended question:
> "What should this agent do — what's the task or domain you're designing it for?"

Listen for:
- The primary domain (coding, research, writing, data analysis, customer support, etc.)
- The target user (themselves, their team, end-users of their product)
- Any implicit constraints ("it should never make things up", "it should be fast")

**Merge opportunity:** If the user describes purpose AND personality in one message, skip to Round 3.

### Round 2 — Personality

Based on Round 1, propose a personality sketch:
> "Based on that, I'd picture [Agent name] as [your best guess]. Does that sound right, or would you adjust it?"

Then ask: "Should it push back if it disagrees, or stay more neutral and executional?"

Extract:
- Tone (formal, conversational, terse, thorough)
- Pushback/honesty preference
- Autonomy level (asks before acting vs. acts and reports)

### Round 3 — Tools

Ask a focused question:
> "Does this agent need access to specific tools — like web search, code execution, file system, or external APIs?"

Map their answer to tool groups. Common groups:
- `search` — web search
- `code_execution` — run code in sandbox
- `browser` — navigate web pages
- `file_system` — read/write files
- `mcp` — external MCP-connected services

If unsure, suggest options and let them choose.

### Round 4 — Confirm

Present a draft SOUL.md and one-line description:
> "Here's [Agent name] on paper — does this feel right?"

Iterate until they say yes. Keep changes focused — don't regenerate the whole SOUL for minor tweaks.

---

## Edit Mode — Phase Strategies

### Opening

Summarize the current agent in 1–2 sentences drawn from its existing SOUL:
> "[Agent name] is currently configured as [summary]. What would you like to change?"

Do **not** ask what the agent does — you already know. Get straight to the delta.

### Probing Changes

For each dimension the user mentions, ask one follow-up question to get enough detail:
- For personality changes: "What should it do differently? e.g., be more direct, less verbose, push back more?"
- For scope changes: "Should it expand into [new domain] or replace its current focus?"
- For tool changes: "Add, remove, or replace?"

Never ask more than 3 follow-up questions before presenting the updated draft.

### Presenting Changes

Show only the changed sections of the SOUL, not the whole document:
> "Here's the updated **Core Traits** section: [...]"

Unless the changes are pervasive, in which case show the full updated SOUL.

---

## Conversation Techniques

**Propose, don't interrogate.** From Round 2 onward, make proposals based on what you've observed. "I'd guess you'd want X" is faster and more useful than "What do you want?"

**Use their vocabulary.** If they say "no hallucinations," you say "no hallucinations" — not "factual accuracy."

**Handle "I don't know" with options.** Give 2–3 concrete choices rather than re-asking an open question.

**Stay concise.** This is a functional tool, not a discovery session. Don't over-explore. 3–5 rounds is the target.

**Signal progress.** After each round, briefly confirm what you've captured: "Got it — so [Agent name] is a [X] that [Y]."
