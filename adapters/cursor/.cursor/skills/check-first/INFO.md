---
title: Check-First
pitch: Verify requirement coverage by epics before final approval
icon: ✅
category: qa
price: free
publish: true
order: 90
works_with:
  - id: arch-first
    why: After coverage approval each epic goes into arch-first
  - id: plan-first
    why: A separate plan-first per epic after check-first
---

## What problem it solves

The agent proposes a decomposition of a large task into epics. On the surface it looks logical — but a week later it turns out: one requirement from the brief / spec is covered by no epic. It "was obvious" — so nobody isolated it.

Without an explicit coverage check, small requirements (especially edge cases and non-functional ones) get lost during decomposition. At final delivery: "Where's error handling?" — it isn't there.

## How it works

After the agent proposes the epics, `check-first` collects requirements from the brief / spec (Scope / Acceptance criteria / What must exist sections) into a flat list. For each requirement it checks: is it covered by at least one epic?

It outputs a table: requirement → epic → status (✅ covered / ⚠️ gap). If everything is ✅ — proceed without a pause. If there are gaps — stop, question: add an epic / extend an existing one / mark as out-of-scope.

Without approval of the coverage table, the decomposition workflow doesn't move past the epic proposal.

## Result of the work

Not a single brief / spec requirement is lost during decomposition. If something is marked out-of-scope — that's an explicit decision, not an omission. At final delivery everything promised to the client is implemented.

Long projects don't "discover missing requirements" two months in during a demo.

## Skills it works with

| Skill | Why |
|---|---|
| arch-first | After coverage approval each epic goes into arch-first |
| plan-first | A separate plan-first per epic after check-first |
