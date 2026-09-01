# Skills Map

An at-a-glance table of every shipped skill: what tier it lives in, what
it does, which other skills it invokes, and which other skills invoke it.
This file is populated by `bin/gen-skills-map.sh` — the schema below
describes what each column means and where its value comes from.

Reader path: [`CONCEPTS.md`](./CONCEPTS.md) defines what a "skill" is; this
map lists the concrete ones.

## Columns

### Skill

Short identifier used to invoke the skill (`Skill('flow-first')` on Claude Code,
`$flow-first` on Codex — see [`AGENT_CONTRACT.md`](./AGENT_CONTRACT.md)).
**Derived from:** `name:` field in `SKILL.md` frontmatter.

### Tier

Which layer of the framework the skill belongs to — `core` (universal
per-block cycle), `protocol` (opinionated methodology), or `command`
(user-facing entry point).
**Derived from:** `tier:` field of the skill's entry in `manifest.yml`.

### Role

One-sentence purpose, extracted so a reader can scan the table without
opening every SKILL.md.
**Derived from:** first paragraph of the `description:` field in the
skill's frontmatter, truncated at the first newline or ~100 characters.

### Invokes

List of skills this skill calls via `Skill('X')` during its own steps.
Chain-forming information.
**Derived from:** regex `Skill\('([a-z-]+)'\)` scan of the skill body,
unique names, comma-joined.

### Invoked by

Reverse of Invokes — which skills reference this one. Reveals who
"depends on" the skill and helps assess blast radius of changes.
**Derived from:** two-pass build over all skills' Invokes; each skill
lists the ones that named it.

### Delivers

The concrete artifact the skill produces per run (a table, a report file,
a decision doc). Answers "what will I get if I run this?".
**Derived from:** curated per-skill — no easy frontmatter extraction.
Populate manually or add an `output:` field to frontmatter in a future
schema bump.

## Table

| Skill | Tier | Role | Invokes | Invoked by | Delivers |
|---|---|---|---|---|---|
| go-start | command | Session startup skill. Reads platform docs, builds context, asks which project we're working on,… | go-fast | — (independent) | TODO |
| go-fast | command | Thin entry point into a self-organizing skill chain for a fast-track task. Creates a task (slug,… | idea-first | go-start | TODO |
| idea-first | protocol | Entry point of the self-organizing skill chain. Launched right after task creation. Asks 5-7… | ship-first, habit-first, arch-first, audit-first | go-fast | TODO |
| arch-first | protocol | Protocol for architecturally clean execution of complex multi-block tasks. Decomposition into… | flow-first, dev-auto-first | idea-first | TODO |
| audit-first | protocol | Audit-before-fix protocol — first find all gaps across 7 planes, prioritize, pin the gap table, and… | flow-first, dev-auto-first | idea-first | TODO |
| ui-ai-first | protocol | Final audit of a large task before closure — finds which operations are available only via code /… | — (leaf) | — (independent) | TODO |
| human-first | core | Takes the agent's last message and explains it in plain language — without technical jargon, with… | — (leaf) | — (independent) | TODO |
| flow-first | core | Understanding-alignment protocol before library-first. Asks the user for 2-3 anchors (file, table,… | — (leaf) | arch-first, audit-first, dev-auto-first, ship-first | TODO |
| library-first | core | Mandatory protocol before executing any fast-track task. Analyzes the task, builds a table: what we… | — (leaf) | dev-auto-first | TODO |
| plan-first | core | Mandatory protocol before any document creation, code writing, refactoring, DB migration, test… | — (leaf) | dev-auto-first | TODO |
| ship-first | core | Final task completion protocol: report → user-note → deploy → smoke test → close? → guide? →… | flow-first, arch-map | idea-first | TODO |
| decision-first | core | Makes an architectural / project / scope decision using a 5-part model INSTEAD of asking the user.… | — (leaf) | — (independent) | TODO |
| note-first | core | Saves the last assistant message as a note attached to the current task. Auto-numbered (note-01,… | — (leaf) | — (independent) | TODO |
| dev-auto-first | core | Autonomous orchestrator of the per-block go-fast cycle. Takes over after arch-first/audit-first… | library-first, plan-first, flow-first | arch-first, audit-first | TODO |
| cadence-first | core | Meta-orchestrator: assigns skill-chain cadence per block (Tier 1/2/3) via Q1-Q6 rules. Reads target… | — (leaf) | — (independent) | TODO |
| arch-map | core | Automatic linking of an artifact to project architecture elements. Two modes: file-mode (by file… | — (leaf) | ship-first | TODO |
| check-first | core | Coverage validation protocol before a final approval gate. Reads requirements from any structured… | — (leaf) | — (independent) | TODO |
| go-guide | core | Adds a new conceptual guide to a project's knowledge folder. Runs in three modes: interactive… | — (leaf) | — (independent) | TODO |


## Populating

Do not hand-edit rows below the schema. Run:

```bash
./bin/gen-skills-map.sh
```

The script walks every entry in `manifest.yml`, reads its `SKILL.md`,
builds the reverse-lookup graph across all skills, and overwrites the
`## Table` section in this file. Re-run whenever a skill is added,
removed, or has its frontmatter changed.
