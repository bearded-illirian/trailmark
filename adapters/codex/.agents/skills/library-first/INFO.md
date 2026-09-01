---
title: Library-First
pitch: Task analysis via a table — what's ready, what's new
icon: 📚
category: development
price: free
publish: true
order: 30
works_with:
  - id: flow-first
    why: Before library-first — landscape alignment across 3 layers
  - id: plan-first
    why: After the LOC table is approved — a step-by-step plan
  - id: project-knowledge
    why: Source of knowledge "where to look" for ready solutions
---

## What problem it solves

The agent writes code from scratch where the project already has a ready component. The same thing — but in a different place, under a different name, with unnecessary differences. A month later there are 3 versions of one utility, nobody knows which to use.

Or the opposite — takes a "similar" ready component when the task actually requires something new. The LOC estimate is underestimated, two hours in it turns out it's not that at all.

## How it works

After flow-first the skill breaks the task into atomic actions. For each it decides: is there a ready component in the project (Library ✅) or from scratch (From scratch ⚠️). The concrete file / component name. LOC estimate. Type (ui / backend / integration / infra / ai-skill / manual).

The table is shown, written to the log, waits for an explicit "ok". If the total is >150 LOC or >3 "from scratch" rows — it offers escalation to a Brief (a large task requires a spec, not a fast-track).

Every risk in "Watchpoints" — with a concrete `file:line`, not an abstract "something might break".

## Result of the work

A plan with an honest task size and explicit reusable components. No surprises of "turned out twice as complex" mid-way. If the task really is large — it gets escalated early into the full cycle (brief → spec → epic), doesn't become a hidden epic.

Long-term — the project doesn't breed duplicates, ready components are found and used.

## Skills it works with

| Skill | Why |
|---|---|
| flow-first | Before library-first provides landscape understanding — the LOC table is built on facts, not guesses |
| plan-first | After the LOC approval — a step-by-step plan and work mode |
| project-knowledge | Router "where to look" when searching for a ready solution |
