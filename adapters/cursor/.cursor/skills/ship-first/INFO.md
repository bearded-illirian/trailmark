---
title: Ship-First
pitch: "Task finalization: report, deploy, smoke test, closure"
icon: 🚀
category: session
price: free
publish: true
order: 50
works_with:
  - id: plan-first
    why: Plan-first invokes ship-first after executing a block
  - id: go-guide
    why: After the task ship-first may invoke go-guide to record a guide
  - id: arch-map
    why: Final linking of the artifact to architecture (propagate)
  - id: ui-ai-first
    why: If the task creates user-facing operations — ship-first invokes ui-ai-first
---

## What problem it solves

The agent wrote code and immediately moved on — no report, no commit, nothing deployed, nothing verified in prod, nothing closed in the registry. A week later nobody remembers what was done, the ship flow can't be reproduced.

Without a final protocol, a task "hangs" in a half-closed state: code exists, but nobody confirmed it works. STATUS.md is stale, sessions.md wasn't updated.

## How it works

The skill runs in two modes. **Per-block** — closes a single block after plan-first: writes `report-NN.md` + `user-note-NN.md`, commits + push + sync, runs a smoke test by atom type (backend → curl, infra → systemctl, ai-skill → re-read SKILL.md). Updates task_blocks status=done. Then either moves to the next block via flow-first or switches to task-level.

**Task-level** — closes the whole task: checks artifact completeness, optionally invokes ui-ai-first for a UX audit of new operations, assembles the final `user-note.md`, asks "close?", offers a guide via go-guide, linking via arch-map, updates the registry (status=done, atom counts), propagates arch_ref up the chain (epic → spec → brief), writes STATUS.md and sessions.md.

## Result of the work

The task is closed explicitly, not left hanging. Deploy done, smoke test passed. The registry contains the full picture (artifacts, blocks, metrics). STATUS.md shows the next step, sessions.md the history.

A week later any agent or human can restore the task's context in 2 minutes — reports, user notes, artifacts sit in one folder.

## Skills it works with

| Skill | Why |
|---|---|
| plan-first | Invokes ship-first after executing a block — atomic per-block finalization |
| go-guide | If the task yields knowledge — ship-first offers to record a guide |
| arch-map | Final architecture linking + propagate up the chain |
| ui-ai-first | For user-facing operations — ship-first invokes a UX audit |
