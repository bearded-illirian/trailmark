---
title: UI/AI-First
pitch: "Final audit: what remained accessible only through code"
icon: 🎛
category: qa
price: free
publish: true
order: 100
works_with:
  - id: ship-first
    why: Ship-first invokes ui-ai-first automatically when user-facing operations exist
  - id: arch-first
    why: Applied to the end of an arch-first task before closure
  - id: go-guide
    why: Some type-A findings (skill / AI) get recorded via go-guide
---

## What problem it solves

A large task is closed: features implemented, tests pass, prod deployed. But 3 months later it turns out half the capabilities are **on paper**: the operator can't use them because access is only via curl with an admin token, direct SQL INSERT, or invoking a skill in the CLI.

This is **technical debt that looks like "all done"**. Reports say "feature is in prod", in reality — nobody except the task author uses it.

## How it works

Runs after implementation of a large task (`arch-first`), before formal closure. For each implemented block: reads `task.md` + reports + guides + code → lists the operations "only via code / curl / SQL" → forms a sub-table.

For each operation — an **A/B** classification:
- **A — a skill or AI agent** for rare or technical operations (cheap to build, doesn't burden the UI)
- **B — a UI task** for frequent operator operations (needs a form, button, dashboard)

At the end — a master table of all operations + a prioritized roadmap by stages.

`ui-ai-first` **does not implement** the found items — only classifies and records them as a roadmap. Implementation is separate work streams.

## Result of the work

Before closing a task it's clear: what's accessible to the operator through UI, what needs to be automated by a skill, what to extract into a UI task. The roadmap is explicit — no "suddenly remembered a month later".

Long-term — features don't hang "implemented in code but dead". Every capability either has an interface, or has a skill, or is explicitly marked out-of-scope for the operator.

## Skills it works with

| Skill | Why |
|---|---|
| ship-first | Invokes ui-ai-first automatically when user-facing operations exist |
| arch-first | Applied to the end of an arch-first task before closure |
| go-guide | Some type-A findings (skill / AI) get recorded via go-guide |
