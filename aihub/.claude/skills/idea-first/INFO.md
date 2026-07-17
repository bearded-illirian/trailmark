---
title: Idea-First
pitch: "Entry point: identifies the task type inside the fast-track workflow"
icon: 🎯
category: development
price: free
publish: true
order: 15
works_with:
  - id: habit-first
    why: For the "new product" branch — the next skill after idea-first
  - id: arch-first
    why: For the "new feature" branch (5+ blocks) — the next skill
  - id: audit-first
    why: For the "fix" branch — the next skill (audit gaps before a fix)
  - id: flow-first
    why: For small tasks after idea-first — straight to flow-first
---

## What problem it solves

The agent got a task — and dove straight into code via library-first. Half an hour later it turned out the task was about **designing a new habit**, not code. Or an **audit of gaps**, not a new feature. Or actually a huge task of 5 blocks was run through a mini-cycle.

Without an explicit type identification, every task goes through the same `flow → library → plan` pipeline. A small edit is overkill, a large one is under-invested. Product tasks run as code, behavioral ones get lost.

## How it works

A dialogue of 5-7 questions — no more. What do we want to do. What's the desired result. What we **don't** do. Size (1 commit / a week / a month). Which layer. Type: **product** (new service, needs habit design) / **feature** (extension of a product, in code) / **fix** (bug, unknown gaps).

The idea card is shown in one message and written to `tasks/log/`. It waits for an explicit "ok" — nothing continues without approval.

After approval — routing along the branch:
- **product** → habit-first (design the habit loop) → arch-first
- **feature** → arch-first (decompose into blocks)
- **fix** → audit-first (find all gaps before the fix)
- **small** — straight to flow-first without decomposition

Idea-first **does not read code** — it's a conversation about the task type, not technical analysis.

## Result of the work

Every task lands in the right pipeline from the first minute. Product tasks get habit design, features get architectural decomposition, fixes get a gap audit, small ones get a fast flow-first without overkill.

An hour into the work — no situation of "turned out it's actually a different task". The type is fixed explicitly, scope is agreed before start.

## Skills it works with

| Skill | Why |
|---|---|
| habit-first | For the "new product" branch — the next skill after idea-first |
| arch-first | For the "new feature" branch (5+ blocks) — the next skill |
| audit-first | For the "fix" branch — the next skill (audit gaps before a fix) |
| flow-first | For small tasks after idea-first — straight to flow-first |
