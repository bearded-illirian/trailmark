---
title: Arch-Map
pitch: Automatic linking of an artifact to architecture elements
icon: 🗺
category: development
price: free
publish: true
order: 70
works_with:
  - id: arch-first
    why: After decomposition into blocks arch-map links the final artifact to architecture
  - id: plan-first
    why: After plan-first arch-map runs automatically — links the artifact to a layer
  - id: ship-first
    why: On task closure it propagates arch_ref up the chain brief → spec → epic
---

## What problem it solves

Every task touches one or more architecture layers — but at the end nobody knows which ones. A month later, when searching for "what was done in layer X", there are no labels, no link between tasks and architecture.

Without automatic linking every artifact "floats in the void": brief, spec, epic, task don't know which part of the architecture they belong to. You can't assemble a roadmap by layer, you can't trace a module's evolution.

## How it works

The skill reads `arch_items` from a project registry — the catalog of architecture elements (modules, services, APIs, DB tables). It works in two modes. **File-mode** — after `plan-first` matches paths of changed files against paths of architecture elements. **Feature-mode** — after `brief` or `spec` it searches the artifact text for slug / title / URL of elements.

Merge logic: doesn't overwrite an existing `arch_ref` — it appends (when an artifact touches multiple layers). On task closure through ship-first — propagates the final arch_ref up the `epic → spec → brief` chain.

Fully automatic. Doesn't ask the user, doesn't block the task. If `arch_items` is empty or nothing matches — simply `arch_ref = null`, no error.

## Result of the work

Every task / epic / spec / brief has explicit links to architecture layers. You can assemble the list "all tasks that touched module X" with a single SQL query. A roadmap per layer builds itself.

A month later you come back — you see that the `api/billing` layer got 4 tasks in the last 30 days: a list + links + context. The architecture becomes a live tool, not a diagram in a separate file.

## Skills it works with

| Skill | Why |
|---|---|
| arch-first | After decomposition into blocks arch-map links the final artifact to architecture |
| plan-first | After plan-first runs automatically — links the artifact to a layer |
| ship-first | On task closure propagates arch_ref up brief → spec → epic |
