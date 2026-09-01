# Trailmark on Codex — experimental

> **Written, not yet run.** This adapter was generated and reviewed, but has
> never been executed on a live Codex install. Treat every claim below as a
> hypothesis until someone reports otherwise — including me. If you try it,
> [say what happened](https://github.com/bearded-illirian/trailmark/discussions/1);
> that is the single most useful thing anyone can do with it right now.

## Why this exists at all

Discussion #1 asked for a Codex port. When it was opened in July the assumption
was that the formats diverge and every protocol would need rewriting.

They converged instead. Codex now discovers skills the same way Claude Code
does — a folder per skill, a `SKILL.md`, YAML frontmatter with `name` and
`description` — and it deprecated custom prompts in favour of skills. All 17
Trailmark skills already satisfy Codex's stated rules without a single edit to
their bodies: frontmatter carries exactly the two permitted fields, the longest
skill is 410 lines against a 500-line ceiling, every name is valid.

So this adapter is not a rewrite. It is a directory move plus two mechanical
substitutions.

## What it contains

```
adapters/codex/.agents/skills/
  {skill}/SKILL.md              # 17 protocol skills
  {command}/SKILL.md            # go-fast, go-start — commands shipped as skills
  {some}/agents/openai.yaml     # explicit-only invocation, 3 skills
```

Two transforms are applied to every markdown file under a skill folder:

| From | To | Why |
|---|---|---|
| `Skill('flow-first')` | `$flow-first` | Codex invokes a skill explicitly as `$name` |
| `.claude/skills` | `.agents/skills` | Codex scans `.agents/skills` |

Three skills ship with `agents/openai.yaml` setting
`policy.allow_implicit_invocation: false` — `ship-first`, `dev-auto-first` and
`go-guide`. They deploy, push, or take over the execution loop, and being picked
up by accident is a different kind of mistake than being picked up by accident
for a skill that stops at an approval gate.

## Installing

Copy the tree to wherever Codex looks. Repository-scoped, shared with everyone
who clones:

```bash
cp -r adapters/codex/.agents /path/to/your/project/
```

Or user-scoped, available in every project:

```bash
cp -r adapters/codex/.agents/skills/* ~/.agents/skills/
```

Then start Codex and check the skills are listed. Invoke one by name:
`$go-start`.

The rest of the framework — `bin/`, `tasks/routing.db`, the Flow UI — is
agent-agnostic and needs no adapter. Set it up exactly as
[`docs/QUICKSTART.md`](../../docs/QUICKSTART.md) describes.

## Known gaps

Honest list of where parity is incomplete or unverified. None of these are
guesses about Codex's behaviour; they are places where the mapping is known to
be imperfect.

**Arguments to an explicit invocation.** Claude Code passes them —
`Skill('cadence-first', task_id='…')`. Codex documents no equivalent syntax for
`$name`. The adapter rewrites these as `$cadence-first with (task_id='…')`, so
the arguments survive as prose the agent reads rather than a signature it
parses. Whether that is enough is the first thing worth testing.

**Chaining.** Trailmark's whole design is skills invoking each other — 29 such
hand-offs across 11 skills. On Claude Code that is a tool call. Whether a Codex
skill can trigger another one from inside its own body, rather than waiting for
a human to type `$next-skill`, is unknown. If it cannot, the framework still
works; the hand-offs just become manual.

**Two calls left untranslated on purpose.** `Skill('habit-first')` points at a
skill that is not part of the public release at all, and `Skill('*')` is a
wildcard inside a rule's prose. Both would be wrong to rewrite.

**Hooks.** Codex has none. Nothing here needs them — see
[`docs/AGENT_CONTRACT.md`](../../docs/AGENT_CONTRACT.md) D1 — but it is worth
naming, since the framework's own documentation used to imply otherwise.

## Checking it yourself

Fixtures assert the *shape* of what a run produces, never its wording:

```bash
bash bin/parity-run fixtures/plan-first/001-add-endpoint /path/to/log-dir
```

Hand `fixtures/{skill}/{case}/input.md` to Codex, let the chain run, then point
the runner at the log directory it produced. It reports per assertion and exits
non-zero on any failure. See [`fixtures/README.md`](../../fixtures/README.md).

The runner does not drive the agent — a shell script cannot make Codex execute a
protocol. That part is yours.

## Rebuilding

The tree is generated, not hand-maintained. After any change to the skills:

```bash
bash bin/build-codex-adapter.sh          # rebuild
bash bin/build-codex-adapter.sh --check  # verify it is current, write nothing
```

Rebuilding is idempotent — the same source produces a byte-identical tree.

## Reference

- [`docs/AGENT_CONTRACT.md`](../../docs/AGENT_CONTRACT.md) — what a runtime must provide, and the Claude Code / Codex capability matrix
- [`docs/SKILL_CONTRACT.md`](../../docs/SKILL_CONTRACT.md) — how a skill file is written
- [Discussion #1](https://github.com/bearded-illirian/trailmark/discussions/1) — where the port was requested and where results should land
