# Alternatives — how Trailmark compares to specific tools you may already use

This document covers **tool-level alternatives** — specific practices or single-
purpose tools people commonly use for the same pains Trailmark addresses.
Different from [COMPARISON.md](COMPARISON.md), which covers full agentic
frameworks (BMAD-Method, Superpowers, and similar).

The format here is intentionally compact — a short Q&A per alternative — rather
than the 10-axis canonical table used for frameworks. Tools are narrower than
frameworks, so the comparison is narrower too.

---

## Reader guide

| If you already use... | For which pain | Section |
|---|---|---|
| ADR files (`docs/adr/*.md`) | Tracking architectural decisions | [§1](#1--trailmark-vs-adr-files) |
| Obsidian / Notion / plain markdown notes | Tracking work history | TBD |
| `git log` + commit messages | Understanding what was done | TBD |
| Claude subagents | Task execution / delegation | TBD |
| Chat history + scrollback | Recalling recent context | TBD |

New alternatives are added incrementally as they come up. See the
[Contribution guide](#contribution-guide) if you want to propose one.

---

## §1 — Trailmark vs ADR files

**TL;DR** — ADR (Architecture Decision Records) solves a specific subset of
memory: recording *why* an architectural choice was made. Trailmark's registry
works at a broader layer — the full operational history of AI-assisted work,
not just decisions.

### What ADR solves well

- Persistent, versioned record of architectural choices ("we picked Postgres
  over Mongo because...")
- Simple, portable format — plain markdown in `docs/adr/` inside each repo
- Well-understood convention with mature tooling (adr-tools, log4brains, etc.)
- Human-readable — anyone with git access can follow the reasoning
- Zero infrastructure — no database, no service, no runtime

If tracking decisions is the only pain you have, ADR is a perfectly good fit
and Trailmark's registry is overkill.

### Where the pain diverges

Trailmark's registry is not a "better ADR" — it's a different scope entirely:

- **Artifact types.** ADR has one type: decision. Trailmark tracks 10+ types:
  `task.md`, `plan-first`, `library-first`, `flow-first`, `report`,
  `user-note`, `cadence-decisions`, `notes`, `decisions`, `audit`,
  `skill_invocations`.
- **Scope.** ADR lives per repo in `docs/adr/`. Trailmark's `routing.db` is
  one SQLite file shared across every project — cross-project queries work
  natively.
- **Query surface.** ADR is text — you `grep` or search in your IDE. Trailmark
  is SQL — `SELECT * FROM task_artifacts WHERE task_id LIKE '%endpoint-x%'`
  returns hits in milliseconds across all history.
- **What the agent can recall.** ADR answers "we chose X". Trailmark answers
  "what did we do three weeks ago on endpoint X, which block was last, which
  report is open, which skills were invoked, what's still pending".
- **Linkage.** ADR files are flat — cross-references are markdown links.
  Trailmark has foreign keys: `task_artifacts → task_blocks → artifacts`, plus
  `skill_invocations` as a separate audit table of every skill call.
- **UI.** ADR is read in your editor or GitHub. Trailmark ships a Flow UI at
  `localhost:8765` — a visual browser over the registry with filters by
  project, task, artifact type, and skill.

### Verdict

ADR and the Trailmark registry aren't competitors — they operate at different
scopes. ADR fits inside Trailmark as one artifact type among many. In fact,
Trailmark ships a `/decision-first` skill that produces `decision-NN.md` files
in exactly the ADR spirit — the difference is that those decisions are
registered in `routing.db` alongside the task and block context they came from,
so the agent recalls them together with the surrounding operational history.

Pick **ADR alone** if decision-tracking is the only pain you have. Pick
**Trailmark** if you also need to answer "what was I doing on this task last
month" without re-reading scattered markdown.

---

## Contribution guide

Want to add a new tool-level alternative to this document? Follow the compact
Q&A shape below.

### Rules

1. **Honest concession is mandatory.** The "What X solves well" section is not
   optional — if the alternative has no wins over Trailmark, it doesn't
   deserve a comparison entry.
2. **Verdict must name who wins in which scenario.** "Pick X if... Pick
   Trailmark if..." — never a flat "Trailmark is better".
3. **Keep it compact.** ALTERNATIVES entries are short by design — 4
   sub-sections, no 10-axis tables. If your entry needs a full framework
   comparison, it belongs in [COMPARISON.md](COMPARISON.md) instead.
4. **Update the Reader guide.** Replace the TBD placeholder or add a new row.

### Template block

Copy this skeleton, fill in the fields, replace `{ToolName}` throughout:

```markdown
## §N — Trailmark vs {ToolName}

**TL;DR** — one paragraph naming what {ToolName} is, what pain it addresses,
and the one-sentence pivot to how Trailmark's scope differs.

### What {ToolName} solves well

- Honest list of {ToolName}'s wins — 3-6 bullets
- Include the scenario where {ToolName} alone is sufficient

### Where the pain diverges

- Bullet 1 — a specific axis where Trailmark's registry differs
- Bullet 2 — another axis
- Bullet 3 — another axis
- Keep bullets specific — name the mechanism (SQL query / FK link / skill
  invocation / UI feature), not just "better"

### Verdict

Pick **{ToolName} alone** if ... . Pick **Trailmark** if ... .
```

### Submit

Open a PR against `docs/ALTERNATIVES.md` with:
- New `## §N` section following the template
- Updated Reader guide row (replace TBD or add new)

We'll merge if the comparison is honest and follows the compact shape.
