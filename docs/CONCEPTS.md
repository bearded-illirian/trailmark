# Core Concepts

This is the framework's shared vocabulary. Every skill, script, and doc uses
these seven terms consistently — reading them once here saves rereading
scattered definitions across skill files. Terms are ordered bottom-up: from
the smallest concrete unit to the protocol that composes them.

## Artifact

Any file the framework tracks as a first-class output — a plan, a report, a
decision, a note. Every artifact is registered in a central database with
its type, block, round, and creation timestamp, so nothing produced by a
skill is orphaned.

> Example: `report-7.1.md` — the auto-generated summary of a plan-first
> execution, saved next to the task file it belongs to.

## Task

One unit of work with a stable slug and its own folder under `tasks/log/`.
A task holds every artifact produced while it's active: the original brief,
plans, reports, notes, decisions.

> Example: `2026-07-02-project--498-config-refactor/` — the folder where
> every artifact for a single multi-week task lives.

## Block

A named subdivision of a task, small enough to plan and ship in one skill
chain. Blocks are numbered, tracked in the database, and closed one at a
time with a commit hash.

> Example: "Block 7 — Design framework.yml schema" — one focused chunk of
> the parent task, with its own flow-first, library-first, plan-first, and
> report artifacts.

## Skill

A markdown protocol file with a defined trigger, steps, and output format.
Skills live under `core/`, `protocols/`, and `commands/` and are invoked
by name — the agent reads the file and follows its steps verbatim, without
shortcuts. The exact invocation syntax depends on the runtime; see
[`AGENT_CONTRACT.md`](./AGENT_CONTRACT.md).

> Example: `core/flow-first/SKILL.md` — a protocol that produces a 4×3
> landscape/problem/solution/result table before any code is written.

## Chain

The ordered sequence of skills that runs per block. The default chain is
`flow-first → library-first → plan-first → execute → report`, with each
skill consuming the previous one's artifact as its input.

> Example: A block starts with flow-first, whose approved table becomes
> library-first's input, whose LOC table becomes plan-first's input.

## Gate

A STOP point inside a chain where the framework pauses until an approval
arrives. Gates make review explicit rather than optional — the next skill
literally cannot start until the gate opens.

> Example: plan-first shows its plan table and stops, asking for
> autopilot/step-by-step/hybrid mode before any file is written.

## Approval

The mechanism that opens a gate. Can be an explicit human response
(`ok` / `go` / mode number) or an automated verdict from an orchestrator
skill that validated the artifact against a checklist.

> Example: A human types `1` at plan-first's mode prompt, or
> `dev-auto-first` reads the plan table, runs its validation rules, and
> auto-answers `1` on the user's behalf.

## How they compose

A **task** is decomposed into **blocks**; each block runs a **chain** of
**skills** that write **artifacts** and pause at **gates**; every gate
opens with an **approval**. Reading the framework's daily flow is exactly
this loop, repeated per block until the task closes.
