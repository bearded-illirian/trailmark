---
title: Audit-First
pitch: Audit gaps before a fix across 6 planes
icon: 🔍
category: qa
price: free
publish: true
order: 80
works_with:
  - id: idea-first
    why: For a "fix" type idea-first hands off to audit-first
  - id: flow-first
    why: For each found gap a separate flow-first runs
  - id: library-first
    why: After per-gap flow-first — library-first for ready components
  - id: plan-first
    why: The fix plan for a specific gap after library-first
---

## What problem it solves

The task sounds like "fix a bug in X" — the agent walks to the visible symptom and fixes it. A week later it turns out the symptom was the tip of an iceberg: the real problem was in auth, or timeouts, or a race condition. Wrong thing got fixed.

Without a full picture of problems before the fix, every edit rides on a guess about what's actually broken. An hour is spent on the symptom, the real gap remains and surfaces a month later in a different place.

## How it works

Before any fix — a mandatory audit phase across **6 planes**: Security (auth / authz / secrets), Performance (queries / timeouts), Integrity (transactions / races), Observability (logs / metrics), Configuration (env / deploy), UX (operation availability).

For each plane — concrete grep / code analysis. Found gaps are collected into a table with priority (HIGH / MED / LOW) and an explicit "how it was found".

It waits for an explicit approval of the gaps table. Without approval — no code. Only after approval — `flow-first` on each priority gap separately, then `library-first → plan-first → fix`.

## Result of the work

The **real** problem gets fixed, not the symptom. A month later there's no "it turned out the gap was deeper". All found gaps are recorded — even LOW ones may become the reference for the next audit.

Long-term — modules with an audit history are more stable than those where fixes happened "on user request".

## Skills it works with

| Skill | Why |
|---|---|
| idea-first | For a "fix" type idea-first hands off to audit-first |
| flow-first | For each found gap — a separate flow-first |
| library-first | After per-gap flow-first — search for ready components |
| plan-first | Fix plan for a specific gap |
