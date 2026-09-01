# Trailmark on Cursor — experimental

> **Written, not yet run.** This adapter was generated and reviewed, but has
> never been executed on a live Cursor install. Treat every claim below as a
> hypothesis until someone reports otherwise — including me. If you try it,
> [say how it went](https://github.com/bearded-illirian/trailmark/discussions/1);
> that is the single most useful thing anyone can do with it right now.

## Why this exists at all

Cursor reads `.claude/skills/` for compatibility, so cloning Trailmark into a
project probably gets Cursor to *see* the skills without any adapter at all.
Worth saying plainly, because it bounds what this folder is for.

Two things that clone would not get right:

- **Hand-offs.** The skills call each other 34 times, written as
  `Skill('library-first')` — Claude Code's syntax. In Cursor a skill is asked
  for as `/library-first`. A tree that says otherwise leaves the agent reading
  an instruction it cannot follow.
- **Invocation policy.** Three skills deploy, push, or take over the execution
  loop, and must never be picked up by a description match. Cursor reads that
  from a `disable-model-invocation` key in the skill's own frontmatter — a key
  the source tree does not carry.

So this adapter is not a rewrite. It is a directory move plus two mechanical
substitutions, with one key added to three files.

## What it contains

```
adapters/cursor/.cursor/skills/
  {skill}/SKILL.md              # 19 protocol and core skills
  {command}/SKILL.md            # go-fast, go-start — commands shipped as skills
```

21 entries, 41 files. The Codex tree holds 44 for the same 21 entries: three
`agents/openai.yaml` sidecars it needs for invocation policy. Cursor puts that
policy in the frontmatter, so there are no extra files here — the difference is
exactly those three.

Two transforms are applied to every markdown file under a skill folder:

| From | To | Why |
|---|---|---|
| `Skill('flow-first')` | `/flow-first` | Cursor asks for a skill by name with a slash |
| `.claude/skills` | `.cursor/skills` | Cursor's project-level skills directory |

Three skills carry `disable-model-invocation: true` in their frontmatter —
`ship-first`, `dev-auto-first` and `go-guide`. Being picked up by accident is a
different kind of mistake for a skill that pushes to a remote than for one that
writes a file and stops at an approval gate.

**This is also why there are two trees rather than one.** Codex accepts exactly
`name` and `description` in the frontmatter and takes its policy from a sidecar
file; Cursor takes it from a third key. No single tree satisfies both.

## Installing

Copy the tree to wherever Cursor looks. Repository-scoped, shared with everyone
who clones:

```bash
cp -r adapters/cursor/.cursor /path/to/your/project/
```

Or user-scoped, available in every project:

```bash
cp -r adapters/cursor/.cursor/skills/* ~/.cursor/skills/
```

Then open Cursor and check the skills are listed. Ask for one by name: type
`/go-start` in the agent chat. `Option+Enter` (Mac) or `Alt+Enter` (Windows)
pins a skill for the whole session instead of a single turn.

The rest of the framework — `bin/`, `tasks/routing.db`, the Flow UI — is
agent-agnostic and needs no adapter. Set it up exactly as
[`docs/QUICKSTART.md`](../../docs/QUICKSTART.md) describes.

## Known gaps

Honest list of where parity is incomplete or unverified. None of these are
guesses about Cursor's behaviour; they are places where the mapping is known to
be imperfect, or where the documentation does not say.

**Arguments to an explicit invocation.** Claude Code passes them —
`Skill('cadence-first', task_id='…')`. Cursor documents no equivalent for
`/name`. The adapter rewrites these as `/cadence-first with (task_id='…')`, so
the arguments survive as prose the agent reads rather than a signature it
parses. Whether that is enough is the first thing worth testing.

**Chaining.** Trailmark's whole design is skills invoking each other — 34
hand-offs. On Claude Code that is a tool call. Whether a Cursor skill can
trigger another one from inside its own body, rather than waiting for a human
to type `/next-skill`, is not documented. If it cannot, the framework still
works; the hand-offs just become manual.

**Body size.** Codex documents a 500-line ceiling; Cursor documents none. The
longest skill here is 410 lines. If Cursor has an undocumented limit below
that, this is where it would show.

**Two calls left untranslated on purpose.** `Skill('habit-first')` points at a
skill that is not part of the public release at all, and `Skill('*')` is a
wildcard inside a rule's prose. Both would be wrong to rewrite. The Codex tree
carries the same two.

**Hooks.** Cursor has none, and neither does Codex. Nothing here needs them —
see [`docs/AGENT_CONTRACT.md`](../../docs/AGENT_CONTRACT.md) D1 — but it is
worth naming, since the framework's own documentation used to imply otherwise.

## Checking it yourself

Fixtures assert the *shape* of what a run produces, never its wording:

```bash
bash bin/parity-run fixtures/plan-first/001-add-endpoint /path/to/log-dir
bash bin/parity-run --all /path/to/log-dir --verbose
```

Hand `fixtures/{skill}/{case}/input.md` to Cursor, let the chain run, then
point the runner at the log directory it produced. It reports per assertion and
exits non-zero on any failure. See [`fixtures/README.md`](../../fixtures/README.md),
or run the guided version with the `parity-check` skill.

The runner does not drive the agent — a shell script cannot make Cursor execute
a protocol. That part is yours.

## Rebuilding

The tree is generated, not hand-maintained. One generator serves every runtime;
Cursor is one profile in it, and the runtime name is the first argument:

```bash
bash bin/build-adapter.sh cursor            # rebuild
bash bin/build-adapter.sh cursor --check    # verify it is current, write nothing
bash bin/build-adapter.sh cursor --summary  # what a rebuild would change
bash bin/build-adapter.sh all --check       # every runtime at once — what CI runs
```

`--summary` names the skills that would move, appear or vanish. A generated tree
of this size diffs into noise, and a vanished skill is exactly the kind of fact
that noise hides.

Rebuilding is idempotent — the same source produces a byte-identical tree.

## Reference

- [`docs/AGENT_CONTRACT.md`](../../docs/AGENT_CONTRACT.md) — what a runtime must provide, the capability matrix, and how to add a third runtime as a profile
- [`docs/SKILL_CONTRACT.md`](../../docs/SKILL_CONTRACT.md) — how a skill file is written
- [`adapters/codex/README.md`](../codex/README.md) — the same framework for Codex
- [Discussion #1](https://github.com/bearded-illirian/trailmark/discussions/1) — where the port was requested and where results should land
