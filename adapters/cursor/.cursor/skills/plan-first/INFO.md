---
title: Plan-First
pitch: A plan table and work mode before any code or document
icon: 📋
category: development
price: free
publish: true
order: 40
works_with:
  - id: library-first
    why: The LOC table is the basis for the plan's steps
  - id: ship-first
    why: After executing the plan — task finalization via ship-first
  - id: arch-map
    why: After plan-first — link the artifact to architecture
---

## What problem it solves

The agent rushed into code without a plan — and dropped half the details. Tests forgotten, DB migration skipped, commit message vague. An hour later the user sees code in the wrong place, not what was expected.

Without a work mode — the user doesn't know: will the agent do everything at once and bring a result, or wait for "go" after every step? Incompatible expectations → frustration on both sides.

## How it works

Before any action (document, code, refactor, migration, tests, git operation) — a 7-15 row table: what specifically we do at each step. Implementation steps only, no "study X" (that belongs in flow-first).

After the table — a mode choice: autopilot (all at once, running report) / step-by-step ("go" after each step) / hybrid (autopilot up to step N, then stop). The user chooses explicitly — no guessing.

After execution — a mandatory `report.md` with a "What was notable" block (deviations, non-obvious findings) and a "Next" block (a concrete next step).

## Result of the work

The plan is a single source of truth about what's happening. If the agent deviated — it shows in the report. If scope expanded — it's recorded. If a step was skipped — the user sees it immediately.

The work mode is agreed — the user doesn't wait while the agent is already sprinting, and the agent doesn't stall when the user is ready to let go.

## Skills it works with

| Skill | Why |
|---|---|
| library-first | The LOC table is the basis for the plan's steps. Atoms from library-first → steps in plan-first |
| ship-first | After executing all plan steps — finalization via ship-first (report, deploy, closure) |
| arch-map | After plan-first for a fast-track — link the artifact to the architecture layer |
