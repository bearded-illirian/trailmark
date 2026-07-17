---
title: Arch-First
pitch: Architecturally clean execution of complex multi-block tasks
icon: 🏛
category: development
price: free
publish: true
order: 60
works_with:
  - id: idea-first
    why: Idea determines that the task is a feature and requires architectural execution
  - id: habit-first
    why: For a new product arch-first runs after habit-first
  - id: flow-first
    why: Inside each block arch-first runs the cycle flow → library → plan → ship
  - id: arch-map
    why: Links the final artifact to the architecture layer
---

## What problem it solves

A large task (5+ blocks, a DB migration, rewriting skills) starts as a regular `/go-fast` — and two days later turns into mush: blocks overlap, decisions happen quietly, scope creeps, follow-up epics silently spawn right inside the task.

Without an explicit protocol for architectural cleanliness, every complex block is "solved on the fly" without recording why it was done this way and not another. A month later nobody remembers what was decided in which block.

## How it works

Decompose the task into numbered blocks with an explicit goal for each. Inside each block runs the full cycle `flow-first → library-first → plan-first → execute → ship-first`. Between blocks — recording of architectural decisions and scope vs out-of-scope.

If the task has an unfamiliar component — a separate **research phase before planning** produces a comparative table "as-is vs to-be" with a criticality rating per item.

After each block — a report with an explicit record: what decisions were made, what's out of scope, what goes into a follow-up. Epics are extracted explicitly, not born quietly.

## Result of the work

A complex task doesn't fall apart. A month later, inside each block, it's clear: what was decided, why, what stayed out of scope, what was extracted into a follow-up epic. Architectural decisions are recorded explicitly, not in "code comments".

If a task turns out to be too large mid-flight — it splits structurally into new tasks / an epic, rather than becoming a hidden epic inside a single `task.md`.

## Skills it works with

| Skill | Why |
|---|---|
| idea-first | Determines that the task is a feature and needs arch-first |
| habit-first | For a new product arch-first runs after habit-first |
| flow-first | Inside each block arch-first runs the full flow → library → plan → ship cycle |
| arch-map | Links the final artifact to the architecture layer |
