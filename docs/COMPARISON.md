# Framework Comparisons

This document compares Trailmark to its neighbours in the same niche — role-based
agentic frameworks, skill catalogs for Claude Code, editor-embedded rules, and
prescriptive documentation methods. Each block is honest about where the other
framework wins.

If you're evaluating alternatives, start with the **Reader guide** below to jump
straight to the framework you're considering.

---

## Reader guide

| Compare Trailmark with... | Category | Section |
|---|---|---|
| [BMAD-Method](https://github.com/bmadcode/BMAD-METHOD) | Role-based agile methodology | [§1](#1--trailmark-vs-bmad-method) |
| [Superpowers](https://github.com/obra/superpowers) | Skill catalog for Claude Code | [§2](#2--trailmark-vs-superpowers) |

More frameworks coming — see the [Contribution guide](#contribution-guide) if you
want to add one.

For a 10-second scan of all frameworks side by side → jump to the
[Super-matrix](#super-matrix--all-frameworks-at-a-glance) at the bottom.

---

## Category legend

Frameworks in the "AI-assisted engineering discipline" space fall into a few
distinct categories. Comparisons only make sense within or across categories
you actually care about.

| Category | What defines it | Example |
|---|---|---|
| **Role-based methodology** | Multiple AI personas with defined roles (Analyst, Dev, QA) and handoffs between them | BMAD-Method |
| **Skill catalog** | A pack of individual disciplined practices (TDD, brainstorming, planning) as reusable skills, composed by the user | Superpowers |
| **Editor-embedded rules** | System prompts / rule files loaded by an IDE (Cursor, Windsurf) | Cursor rules |
| **Executable orchestrator** | A Python/JS runtime with an agent graph you code against | LangChain, CrewAI |
| **Prescriptive documentation** | Text-only frameworks (roles, rules, checklists) you apply by hand | Various agile transplants |
| **Artifact-first process framework** | Skills + protocol chain + persistent registry — every step writes a tracked file | **Trailmark** |

Trailmark sits in its own category because it combines protocol enforcement,
per-block cadence orchestration, and a queryable artifact registry — none of
the other categories bundles all three.

---

## §1 — Trailmark vs BMAD-Method

**TL;DR** — BMAD is an agile methodology transplanted into AI: you manage a
team of AI personas (Analyst → PM → Architect → SM → Dev → QA) with formal
handoffs between them. Trailmark is a process methodology — no roles, but a
strict protocol chain and a persistent artifact registry.

**Category:** Role-based agile methodology
**Repo:** [bmadcode/BMAD-METHOD](https://github.com/bmadcode/BMAD-METHOD)

### Comparison table

| Axis | BMAD-Method | Trailmark |
|---|---|---|
| **What it is at core** | Agile methodology with AI personas (Analyst / PM / Architect / SM / Dev / QA) | Skill chain + artifact registry + tooling |
| **Methodology type** | Role-based — personas and handoffs between them | Process-based — how you reason, how you record, how you validate, how you close |
| **Working model** | Role personas, each loading its own context | Protocol chain (flow → library → plan → execute → report) with `cadence-first` assigning Tier 1/2/3 per block |
| **Ceremony level** | Heavy: PRD → Architecture Doc → Epic → Story → Dev → QA | Adaptive: `cadence-first` drops ceremony on trivial blocks (Tier 3 = plan-only) |
| **Step storage** | Markdown files (stories, PRDs, architecture docs) in the repo | **SQLite registry `routing.db`** + Flow UI over it — every artifact linked to task/block, queryable cross-session |
| **Approval gates** | Explicit handoffs between personas (SM → Dev → QA) | Enforced by protocol skills (`plan-first` waits for approval before code) |
| **Token / context handling** | High — each persona reloads full context on invocation | 5-10× less than agent-heavy — all skills run in the main Claude context, no subagents per step |
| **Runtime dependency** | Works with any agent (Claude Code / Cursor / Windsurf) | Requires Claude Code (uses `Skill()` invocation) |
| **Lock-in** | Markdown + templates only | Markdown + bash + sqlite, no SDK |
| **Philosophy** | *"You're not chatting with AI — you're managing an AI team"* | *"Every step is a file in the registry — audit trail beats chat"* |

### Key differences

- **Methodology axis:** BMAD's opinion is about *who does what* (agile roles).
  Trailmark's opinion is about *how you think and record what you did* (process
  protocol). Trailmark has no opinion on roles.
- **Storage axis:** BMAD produces documents. Trailmark produces documents *plus*
  a SQLite index over them — you can `SELECT` across sessions, projects, and
  weeks.
- **Ceremony axis:** BMAD ceremony is fixed per story. Trailmark ceremony is
  dynamic per block — `cadence-first` looks at block complexity and picks
  Tier 1 (full chain), Tier 2 (skip landscape), or Tier 3 (plan-only).
- **Runtime axis:** BMAD is agent-agnostic. Trailmark is Claude Code specific.

### Where BMAD wins

- Teams of 10+ where formal role handoffs and agile narrative match the
  existing process
- Organisations already fluent in agile / scrum vocabulary who want a direct
  AI transplant of that language
- Projects that need documented PRDs and story files as first-class deliverables
  for compliance / stakeholder review
- Cross-agent portability (works with Cursor, Windsurf, etc.)

### Where Trailmark wins

- Solo or small-team engineers who don't want to play multiple personas
- Cross-session continuity — pick up a task days later from the registry, not
  from re-reading markdown scattered across folders
- Adaptive ceremony — a one-line fix doesn't require a full PRD → Story chain
- Debuggable workflow — every step is a file, not a persona's internal state
- Token efficiency — no persona re-loading full context on every handoff

### Verdict

Pick **BMAD** if you're a team that already thinks in agile roles and wants
those roles as AI personas. Pick **Trailmark** if you're solo or small and want
process discipline plus a queryable audit trail without playing roles.

---

## §2 — Trailmark vs Superpowers

**TL;DR** — Superpowers is a curated pack of disciplined skills for Claude Code
(TDD, brainstorming, debugging, planning), composed by the user on demand.
Trailmark ships skills too, but wraps them in a protocol chain with meta-
orchestration and a persistent registry.

**Category:** Skill catalog for Claude Code
**Repo:** [obra/superpowers](https://github.com/obra/superpowers)

### Comparison table

| Axis | Superpowers | Trailmark |
|---|---|---|
| **What it is at core** | Skill pack of disciplined practices (TDD, brainstorming, debugging, planning) | Skill chain + artifact registry + tooling |
| **Methodology type** | None — a catalog of good skills without a common process | Process-based — protocol chain wraps skill invocation with approval gates and artifact writes |
| **Working model** | Individual skills, the user picks which one to invoke | Protocol chain (flow → library → plan → execute → report) with `cadence-first` deciding tier |
| **Ceremony level** | Light: one skill = one pattern, composition is on the user | Adaptive: `cadence-first` picks Tier 1/2/3, protocol chain enforced per tier |
| **Step storage** | Ephemeral — nothing centrally registered; skill output lives in whatever file it wrote | **SQLite registry `routing.db`** + Flow UI over it — every artifact linked to task/block, queryable cross-session |
| **Approval gates** | User's discretion — skills don't wait unless the user asks | Enforced by protocol skills (`plan-first` waits for approval before code) |
| **Token / context handling** | Low — single context, no orchestration overhead | Low — single context; plus `cadence-first` drops chain steps on trivial blocks for extra savings |
| **Runtime dependency** | Requires Claude Code (uses `Skill()` invocation) | Requires Claude Code (uses `Skill()` invocation) |
| **Lock-in** | Markdown + skills only | Markdown + bash + sqlite, no SDK |
| **Philosophy** | *"Good practices as reusable skills"* | *"Every step is a file in the registry — audit trail beats chat"* |

### Key differences

- **Methodology axis:** Superpowers is intentionally *skills only* — no
  cross-skill orchestration, no protocol wrapper. Trailmark's `*-first`
  protocol family (`flow-first`, `library-first`, `plan-first`, `ship-first`,
  etc.) is the methodology layer.
- **Registry axis:** Superpowers writes files where the skill happens to write.
  Trailmark writes every step to `routing.db` with task/block linkage plus a
  Flow UI to browse it.
- **Meta-orchestration axis:** Superpowers has no `cadence-first` equivalent —
  the user decides which skill to invoke when. Trailmark's `cadence-first`
  picks the chain automatically based on block complexity.
- **Contract axis:** Superpowers skills are independent. Trailmark skills
  reference each other explicitly (`plan-first` checks for `library-first`
  output, `library-first` follows `flow-first`, etc.) via a documented
  `SKILL_CONTRACT.md`.

### Where Superpowers wins

- Users who want a menu of high-quality skills without opinion on when to
  invoke them
- Existing Claude Code workflows that just need to slot in a few disciplined
  practices without adopting a whole framework
- Minimum footprint — no registry, no Flow UI, no protocol scaffolding

### Where Trailmark wins

- Cross-session memory — the registry survives context resets, sessions, weeks
- Enforced approval gates — protocol skills refuse to run without upstream
  artifacts, so discipline isn't optional
- Meta-orchestration — `cadence-first` picks the right amount of ceremony per
  block, so you don't manually decide "do I need library-first for this?"
- Auto-linkage — `arch-map` connects each artifact to an architecture element
  (rare in OSS AI frameworks)

### Verdict

Pick **Superpowers** if you want a small, sharp toolkit of skills without
adopting a process framework. Pick **Trailmark** if you want the toolkit *plus*
protocol enforcement, cross-session registry, and per-block cadence orchestration.

---

## Super-matrix — all frameworks at a glance

10-second scan of the entire library. Same axes as the individual sections,
compressed for cross-framework comparison.

| Axis | BMAD-Method | Superpowers | **Trailmark** |
|---|---|---|---|
| **What it is at core** | Agile methodology with AI personas | Skill pack of disciplined practices | Skill chain + artifact registry + tooling |
| **Methodology type** | Role-based (personas + handoffs) | None (skill catalog) | Process-based (protocol chain + artifacts) |
| **Working model** | Role personas, each with own context | Individual skills, user composes | Protocol chain with `cadence-first` tiering |
| **Ceremony level** | Heavy (PRD → Story → Dev → QA) | Light (one skill = one pattern) | Adaptive (Tier 1/2/3 per block) |
| **Step storage** | Markdown files in repo | Ephemeral | SQLite registry + Flow UI |
| **Approval gates** | Persona handoffs | User's discretion | Enforced by protocol skills |
| **Token / context** | High (persona reloads) | Low (single context) | Low (single context + tier skipping) |
| **Runtime dependency** | Any agent | Claude Code | Claude Code |
| **Lock-in** | Markdown + templates | Markdown + skills | Markdown + bash + sqlite |
| **Philosophy** | *"Manage an AI team"* | *"Good practices as skills"* | *"Audit trail beats chat"* |

---

## Contribution guide

Want to add a new framework to this comparison? Follow the canonical shape so
readers can scan any block predictably.

### Rules

1. **All 10 canonical axes are always filled.** No omissions — even "not
   applicable" is an answer worth writing.
2. **Include a `Where {Framework} wins` section.** Honest comparisons name
   real wins on the other side. A block that only says "Trailmark is better"
   won't get merged.
3. **Match section anchor with header.** README and Reader guide link into
   sections; GitHub auto-generates anchors from headers, so keep headers
   simple.
4. **Update the Super-matrix.** Every new framework adds one column.
5. **Update the Reader guide index.** New row pointing to the new section.

### Canonical 10 axes

Frozen — these are the same across every framework block:

1. What it is at core
2. Methodology type
3. Working model
4. Ceremony level
5. Step storage
6. Approval gates
7. Token / context handling
8. Runtime dependency
9. Lock-in
10. Philosophy

### Template block

Copy this skeleton, fill in the fields, replace `{FrameworkName}` throughout:

```markdown
## §N — Trailmark vs {FrameworkName}

**TL;DR** — one-paragraph elevator pitch of {FrameworkName} plus the
one-sentence pivot to how Trailmark differs.

**Category:** {role-based / skill-catalog / editor-embedded / prescriptive-docs / executable-orchestrator / other}
**Repo:** [{owner}/{repo}](https://github.com/{owner}/{repo})

### Comparison table

| Axis | {FrameworkName} | Trailmark |
|---|---|---|
| **What it is at core** | ... | ... |
| **Methodology type** | ... | ... |
| **Working model** | ... | ... |
| **Ceremony level** | ... | ... |
| **Step storage** | ... | ... |
| **Approval gates** | ... | ... |
| **Token / context handling** | ... | ... |
| **Runtime dependency** | ... | ... |
| **Lock-in** | ... | ... |
| **Philosophy** | *"..."* | *"..."* |

### Key differences

- **{Axis 1}:** ...
- **{Axis 2}:** ...

### Where {FrameworkName} wins

- ...
- ...

### Where Trailmark wins

- ...
- ...

### Verdict

Pick **{FrameworkName}** if ... . Pick **Trailmark** if ... .
```

### Submit

Open a PR against `docs/COMPARISON.md` with:
- New `## §N` section following the template
- New row in the Reader guide
- New column in the Super-matrix

We'll merge if the comparison is honest and follows the canonical shape.
