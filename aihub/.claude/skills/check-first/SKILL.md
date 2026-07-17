---
name: check-first
description: |
  Coverage validation protocol before a final approval gate.
  Reads requirements from any structured requirements document, matches
  them against the proposed decomposition units (blocks, epics, tasks),
  outputs a coverage table. If gaps exist — stops, waits for user
  decision. If everything is covered — continues without pause.

  Use when: after proposing any decomposition of work (blocks / epics /
  tasks) before committing to execution — as a safety net that no
  requirement fell through the cracks.
---

# Check-First Protocol

Runs after a decomposition step in any workflow (e.g. after proposing
epics for a brief, or blocks for a specification). Verifies that every
requirement from the source document is covered by at least one
proposed unit.

---

## Step 1 — Extract requirements

From the already-read requirements document (brief, specification,
technical description, product doc) extract every requirement. Look in
sections like:

- Scope / What's included
- Acceptance criteria
- What must exist
- Functional requirements
- Non-functional requirements

Each requirement is one row. Don't duplicate near-identical items —
merge them if the essence is the same.

---

## Step 2 — Output a coverage table

```
Requirements coverage check:

┌─────┬────────────────────────────────────┬──────────────┬────────────┐
│  #  │ Requirement                        │ Unit         │ Status     │
├─────┼────────────────────────────────────┼──────────────┼────────────┤
│ 1   │ [requirement from source doc]      │ Unit N       │ ✅ Covered │
│ 2   │ [requirement from source doc]      │ Unit N       │ ✅ Covered │
│ 3   │ [requirement from source doc]      │ —            │ ⚠️ Gap     │
└─────┴────────────────────────────────────┴──────────────┴────────────┘
```

"Unit" = the smallest labelled thing in your decomposition: an epic, a
block, a task — whatever the current workflow produces.

---

## Step 3 — Decision

**If every row is ✅:**

```
✅ All requirements covered — continuing.
```

Proceed without pause.

**If there are ⚠️ gaps:**

```
⚠️ N gap(s) found. Options:
1. Add to an existing unit [Unit X]
2. Create a new unit
3. Move to backlog — not part of this cycle
```

Wait for user decision per gap. After decisions land — update the unit
list and continue.

---

## Rules

- Don't skip even when the decomposition looks obviously complete
- On gaps — don't proceed without a user decision
- Extract requirements from the source text, don't invent them
- The point of the protocol is a paper trail: even a "no gaps" result
  is a first-class artifact — future readers see what was checked
