# Frequently Asked Questions

## Why another AI framework?

Most AI-driven coding leaves no trail. Decisions evaporate the moment a
session ends. Reviewers can't audit reasoning. Regressions can't be
attributed. Next session starts from zero.

This framework fixes that at the protocol level: every step of every skill
writes a first-class file and registers in `routing.db`. If a step didn't
produce an artifact, it didn't happen. See the [`README`](./README.md#why-artifact-first)
for the developed thesis.

## How is this different from LangChain / CrewAI?

LangChain and CrewAI ship a Python runtime plus an agent graph you code
against. Artifacts, if any, are ad-hoc — a callback, a log line, whatever
your setup captures. There's no first-class registry.

This framework ships skills (plain markdown), tooling (bash), and a
registry (SQLite). No runtime. No SDK. Every step is contractually required
to produce a tracked file. Different tool, different problem — see the
[comparison table](./README.md#how-this-compares) for detail.

## How does it compare to prescriptive documentation-first frameworks?

Prescriptive frameworks ship documentation — roles, rules, best practices,
checklists — that you apply by hand to your codebase. This framework ships
executable skills that already encode the discipline. Prescriptive
frameworks fit when you're formalising a team process; this framework fits
when you want the discipline without a process organisation to maintain it.

## Does it work on Windows?

Unix-first. The `bin/` scripts assume `bash 3.2+`, `sqlite3`, `python3`.
WSL should work but hasn't been tested end-to-end. Windows-native support
is out of scope for the MVP — patches welcome.

## Which AI models does it work with?

The shipped skills are written for Claude (they use the `Skill('name')`
invocation pattern of Claude Code and Claude Agent SDK). The artifact
contract itself is language-agnostic — any agent that can invoke skills
by name and read/write markdown can use it. Adapting for other providers
means renaming the invocation shape; the discipline transfers.

## Can I use it without Claude Code?

Yes — the artifact contract (write file + insert routing.db row) is what
matters, not the invocation harness. You can use the Claude Agent SDK,
raw API calls, or another agent framework, as long as your agent respects
the "one step = one file" rule and writes to the same `routing.db` schema.
Flow UI works over any populated `routing.db` regardless of who wrote it.

## How do I update the skills?

```bash
bash bin/sync-from-aihub.sh
```

This pulls from an upstream aihub source. Configure the upstream path in
`framework.yml` (default: bundled `./aihub`). Sync produces a per-run log
in `.sync-log/` for audit. Individual skill diffs land in
`aihub/.claude/skills/{name}/SKILL.md`.

## How do I write my own skill?

Follow [`docs/SKILL_CONTRACT.md`](./docs/SKILL_CONTRACT.md) — required
frontmatter fields, three body sections (Input / Output / Hands off to),
linter checks. Then register in `manifest.yml` and run
`bash bin/verify-contract.sh` to confirm compliance. See
[`CONTRIBUTING.md`](./CONTRIBUTING.md#adding-a-skill) for the full flow.

## What commit conventions do you follow?

Light convention: `<prefix>: <short summary>` where prefix is one of
`feat / fix / docs / refactor / chore / test`. Body optional, wrap at 72
columns. Reference issues with `Closes #NN`. See
[`CONTRIBUTING.md#commit-messages`](./CONTRIBUTING.md#commit-messages).

## What's on the roadmap?

Post-MVP priorities in rough order:

1. **CI polish** — GitHub Actions workflow, drift detection, PR gating.
2. **Skill authoring UX** — a scaffolding tool that generates a compliant
   `SKILL.md` skeleton from a short questionnaire.
3. **Flow UI improvements** — better artifact search, cross-project
   filtering, chart export.
4. **Multi-provider skill invocation** — a thin adapter so the same
   skills run under Claude Agent SDK / raw API / other harnesses.
5. **Non-Claude examples** — sample skills demonstrating how the artifact
   contract holds under a different model.

Community input welcome — open a [Discussion](../../discussions) in the
Ideas category if you want to shape it.
