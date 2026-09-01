---
title: Flow-First
pitch: Align understanding of the landscape before starting work
icon: 🗺
category: development
price: free
publish: true
order: 20
works_with:
  - id: idea-first
    why: Before flow-first idea-first identifies the task type (product / feature / fix)
  - id: library-first
    why: After flow-first library-first searches ready components based on the understood landscape
  - id: arch-map
    why: Links the result to architecture elements
---

## What problem it solves

The agent got a task and immediately started writing code. Ten files in, it turns out the agent started with the wrong layer — changes UI when the task is about the DB, or changes the email service when it's about SMTP settings. Context has ballooned, time is spent, result is wrong.

Without aligning understanding at the start, `library-first` runs on guesses: searches for ready code in the wrong layer, the LOC estimate is three times off, the found solution doesn't fit the context.

## How it works

The user gives 2-3 anchors — a file, a table, a route, a service. The skill reads **only those** (doesn't scan the whole project), and based on what it read fills a 4×3 table: Landscape / Problem / Solution / Result × UI / DB / Integrations.

Every cell is either filled with a concrete fact from the code or explicitly marked "not involved". Silence about a layer is forbidden. If a cell can't be filled — one targeted question to the user, not five.

The table is shown in one message and simultaneously written to `tasks/log/`. It waits for an explicit "ok" — without approval nothing continues.

## Result of the work

Library-first runs on understanding, not on guesses. The LOC estimate is accurate, ready solutions are found in the right layer. At the front of the work — the 4×3 table is a understanding checklist you can return to an hour later and still remember the context.

In long projects — 5-10 minutes on flow-first saves 1-3 hours on "wrong turn taken".

## Skills it works with

| Skill | Why |
|---|---|
| idea-first | Identifies the task type (product / feature / fix) — flow-first starts with that knowledge |
| library-first | After the table is approved — analysis of what's ready and what's new |
| arch-map | Links the artifact to the architecture layer |
