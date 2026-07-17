---
title: Cadence-First
pitch: Meta-orchestrator — assigns Tier 1/2/3 cadence per block before plan-first
icon: 🎚
category: development
price: free
publish: true
order: 45
works_with:
  - id: plan-first
    why: Cadence-first decides which tier applies before plan-first Step 1.5 — right-sizes the skill chain per block scope
  - id: arch-first
    why: After decomposition into blocks arch-first invokes cadence-first batch — pre-baking cadence for all blocks at once
  - id: dev-auto-first
    why: Executor reads pre-baked recommended_cadence from task_blocks and applies the corresponding chain
---

## What problem it solves

Not all blocks in a task are equal in complexity. Full cycle (flow-first → library-first → plan-first → execute → ship-first) may be overkill for a one-line edit, but necessary for a fork with multiple decisions.

Without cadence classification the agent either applies the full chain to everything (overhead on trivial blocks) or skips protocol steps ad-hoc (drift, lost audit trail). Both are bad: the first burns time budget, the second breaks discipline.

## How it works

The skill reads title + type + atom_type of each block from task_blocks + task.md landscape. Applies Q1-Q6 rules (per the CADENCE_HEURISTICS.md manifest). Each Q is a boolean signal about the block's scope: Q1 does it change prod state? Q2 is landscape captured in another artifact? Q3 is a library-vs-scratch decision needed? Q4 is deliverable = doc / mechanical batch? Q5 HIGH-risk override? Q6 does it CREATE a lib primitive?

The Q1-Q6 matrix → tier: **Tier 1** full cycle (flow+lib+plan), **Tier 2** partial (lib+plan), **Tier 3** plan-only. Updates `task_blocks.recommended_cadence` per row + writes a `cadence-decisions-{R}.md` artifact with the Q-triggers audit trail per block.

Works in two modes — **standalone** (executor invokes on an ad-hoc block) and **batch** (arch-first Phase 2.5 pre-baking for a whole series). Batch mode is canonical for Mode Brief consumers.

## Result of the work

The right chain per block scope. Trivial edits run plan-only (skip flow+library), full integrations run the full cycle. Time budget is saved on simple blocks and discipline is preserved on complex ones. Each cadence decision is an audit trail with Q-triggers — a future reader sees why the tier was chosen.

Plus — a distribution warning if >70% Tier 1 (possible uniform-cycle bias) or >80% Tier 3 (possible under-classification) — signals of misclassification that need a review.

## Skills it works with

| Skill | Why |
|---|---|
| plan-first | Cadence decides which tier applies before plan-first Step 1.5 |
| arch-first | Batch mode is invoked by arch-first Phase 2.5 after decomposition |
| dev-auto-first | The executor reads pre-baked recommended_cadence from task_blocks |
