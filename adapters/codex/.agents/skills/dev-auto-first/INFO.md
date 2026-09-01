---
title: Dev-Auto-First
pitch: Autopilot for the per-block cycle — flow → library → plan → execute without approval on every step
icon: 🤖
category: development
price: free
publish: true
order: 85
works_with:
  - id: arch-first
    why: arch-first asks "how do we work?" — on choosing "autopilot" it hands off control here
  - id: audit-first
    why: audit-first also asks the mode and hands off to dev-auto-first when autopilot is selected
  - id: flow-first
    why: dev-auto-first invokes flow-first for each block and validates the artifact against rules
  - id: library-first
    why: dev-auto-first validates the LOC table and auto-approves through to plan-first
  - id: plan-first
    why: dev-auto-first answers "1 = Autopilot" in plan-first instead of the user
---

## What problem it solves

A complex task of 5+ blocks launched via `/arch-first` or `/audit-first` requires approval on every step of every block: "ok" after flow-first, "ok" after library-first, mode choice in plan-first, checking `report.md`. That's dozens of manual confirmations per task — even when every artifact is trivial and passes without edits.

Without an autopilot the engineer sits over the terminal and presses "go" × 25 times instead of doing something useful. On a complex 10-block task it's already × 50.

## How it works

dev-auto-first takes control after "autopilot" is chosen in arch-first / audit-first. For each block it:

1. Invokes `flow-first → library-first → plan-first` via `Skill()` calls
2. After each skill it reads the artifact (`flow-first-N.md`, `library-first-N.md`, `plan-first-N.md`) and validates against built-in rules (4 checks for flow-first, 6 for library-first, 5 for plan-first)
3. If all 🛑 checks pass — **immediately** invokes the next Skill without pause
4. In plan-first it answers "1 = Autopilot" instead of waiting for the user's choice
5. When validation fails (a 🛑 rule violated) — it escalates to a Telegram bot, waits 5 minutes for an operator's reply via polling

The operator's reply passes through an intent parser and is mapped to an action: `approve_anyway` / `stop` / `skip` / `retry` / `select`. The skill continues along the right branch.

## Result of the work

A complex multi-block task passes in one run without the engineer's participation. A Telegram ping arrives only when automatic validation truly can't make the decision — that's once per several blocks, not per every step.

At the end — a standard report with a list of blocks, statuses, and escalation counts. All escalations are recorded in a `dev_bot_sessions` audit trail.

## Skills it works with

| Skill | Why |
|---|---|
| arch-first | Hands off control to dev-auto-first when autopilot is chosen |
| audit-first | Same — hands off on autopilot |
| flow-first | dev-auto-first invokes and validates the artifact against 4 rules |
| library-first | dev-auto-first validates the LOC table against 6 rules |
| plan-first | dev-auto-first answers "1" instead of the user, validates the plan against 5 rules |
