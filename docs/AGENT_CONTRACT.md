# Agent Contract

What a **runtime** must provide for Trailmark skills to work. The companion
to [`SKILL_CONTRACT.md`](./SKILL_CONTRACT.md): that file describes how a skill
*file* is written, this one describes what the agent running it has to be
able to do.

Reader path: [`CONCEPTS.md`](./CONCEPTS.md) defines what a "skill" is →
[`SKILL_CONTRACT.md`](./SKILL_CONTRACT.md) defines the shape of a skill file →
this file defines the runtime underneath both.

A runtime is any agent that loads skills and executes them: Claude Code,
Codex, or anything else. The framework's protocols are plain markdown and
carry no runtime assumptions of their own — every assumption they *do* make
is listed below, so a port is a matter of checking a list rather than reading
4000 lines of protocol.

## What a capability is

A **capability** is one thing a skill needs the runtime to do. Capabilities
are either **required** — a skill cannot function without them — or
**optional**, in which case the skill must still work, in a documented
degraded form, when the runtime lacks it.

The split matters because it bounds the port. A runtime missing a required
capability cannot host Trailmark at all. A runtime missing an optional one
hosts it with a named, predictable reduction — not with silent breakage.

## Required capabilities

### R1 — Skill discovery from a directory tree

The runtime loads skills from a directory, one folder per skill, each
containing a `SKILL.md` with YAML frontmatter. Folder name matches the
`name` field.

Trailmark does not care *which* directory, only that one exists and is
scanned. The adapter for each runtime places the tree where that runtime
looks for it.

### R2 — Explicit invocation by name

A human, or a running skill, can invoke a named skill deliberately. This is
what makes a chain a chain: `idea-first` hands off to `arch-first`, which
hands off to `flow-first`, and each hand-off is an explicit act rather than
a hope that the right thing gets picked up.

Syntax is runtime-specific and is declared in the matrix below. What must
hold is that invoking by name is *possible and unambiguous*.

### R3 — A stop-and-wait gate

A skill must be able to halt, present something to a human, and refuse to
continue until that human answers. `library-first` waits for approval of the
LOC table; `plan-first` waits for a mode choice; `arch-first` waits before
irreversible steps.

Without this the framework degenerates into an autocomplete that writes
files. The gate is the discipline.

### R4 — File read and write

Skills read source files and write artifacts — `plan-first-{N}.{R}.md`,
`report-{N}.{R}.md` and the rest — to a task log directory on disk. Every
step of every protocol ends in a file.

### R5 — Shell command execution

Artifacts are registered in `routing.db` via `sqlite3`, task folders are
created with `mkdir`, deploys run through `git`. A runtime that cannot run
shell commands cannot maintain the audit trail.

Note that R4 and R5 together are what keep `routing.db` and the Flow UI
runtime-agnostic: the database is written by ordinary commands, so nothing
in the data layer knows which agent produced a row.

## Optional capabilities

### O1 — Post-tool hook

The runtime can run something automatically after a tool call completes —
Claude Code's `PostToolUse`.

**No shipped skill depends on this.** It is worth stating plainly, because the
opposite is easy to assume: the two things a hook is useful for here — syncing
`tasks/` after a write, and checking that a block produced the artifacts its
cadence required — are already written as ordinary protocol steps (`ship-first`
Steps B4 and B5). A hook can automate them; nothing breaks without one.

**Degradation:** see D1.

### O2 — Implicit invocation by description

The runtime may select a skill on its own by matching the user's request
against the skill's `description`. Convenient, never load-bearing: no chain
in Trailmark depends on a skill being picked up implicitly.

Where the runtime supports it, implicit invocation is switched **off** for the
skills that act outward rather than produce an artifact and wait — the ones that
deploy, push, close a task, or take over the execution loop. Being picked up by
accident is harmless for a skill that stops at an approval gate and dangerous
for one that does not. On Codex this is `agents/openai.yaml` with
`policy.allow_implicit_invocation: false`; the adapter writes it for
`ship-first`, `dev-auto-first` and `go-guide`.

**Degradation:** none needed — explicit invocation (R2) covers every path.

### O3 — Slash commands separate from skills

Some runtimes distinguish a "command" from a "skill". Trailmark ships two
entry points, `go-fast` and `go-start`, which historically lived as commands.

**Degradation:** see D2.

## Capability matrix

| | Claude Code | Codex |
|---|---|---|
| R1 skill directory | `.claude/skills/` | `.agents/skills/` (repo, scanned from cwd up to repo root), `$HOME/.agents/skills`, `/etc/codex/skills` |
| R1 frontmatter | `name`, `description` | `name`, `description` — and **no other fields** |
| R1 body size | no hard limit | under 500 lines, target under 5k words |
| R1 name rules | kebab-case | lowercase, digits, hyphens; ≤64 chars; folder name equals `name` |
| R2 explicit invocation | `Skill('name')` | `$name` |
| R3 stop-and-wait gate | yes | yes |
| R4 file read/write | yes | yes |
| R5 shell execution | yes | yes |
| O1 post-tool hook | yes — `PostToolUse` | **no** |
| O2 implicit invocation | yes | yes — by `description` match; can be disabled per skill via `agents/openai.yaml` |
| O3 separate slash commands | yes — `.claude/commands/` | deprecated; custom prompts superseded by skills |

The Codex column is drawn from OpenAI's published documentation and from a
measurement of Trailmark's own skills against its stated rules — every one
of them complies without edits. It has **not** yet been confirmed by a live run;
see the adapter's README for current status.

## Degradation rules

A skill that relies on an optional capability must name the fallback in its
own body. The rule is not "skip the step" — it is "perform the step by other
means".

### D1 — No post-tool hook (O1 absent)

Replace the hook with an **explicit end-of-step verification**: the skill
states, as an ordinary protocol step, what must be true before it proceeds,
and checks it by running a command.

The shipped skills already work this way, so nothing has to be added for a
hook-less runtime. `ship-first` Step B4 runs the `tasks/` sync as its own step;
Step B5 queries `task_artifacts` for the current block and refuses to close it
when an artifact its cadence required is absent.

The failure mode this guards against is the quiet one. A missing hook throws
no error; it simply stops verifying, and the loss shows up weeks later as
artifacts nobody wrote. An explicit step fails loudly or not at all.

### D2 — No separate slash commands (O3 absent)

Ship the entry point as an ordinary skill. `go-fast` and `go-start` are
protocols like any other; nothing in them requires command status. On a
runtime with commands they may be installed either way.

### D3 — General rule

Never let a missing optional capability turn into a silently skipped step. If
the fallback cannot be expressed as an explicit step, the capability is not
optional for that skill, and the skill must say so.

## Acceptance criteria

A runtime is considered supported when, for the reference fixture set:

- [ ] R1 — the skill tree is discovered; all shipped skills are listed by the runtime
- [ ] R2 — a skill invoked by name runs, and a skill invoking another by name hands off
- [ ] R3 — an approval gate halts execution and resumes only after a human answers
- [ ] R4 — the expected artifact appears in the task log directory with the expected sections
- [ ] R5 — the corresponding row appears in `routing.db`
- [ ] D1 — where the runtime lacks O1, the end-of-step verification runs and reports

These are checked mechanically by the parity runner rather than by reading
output — see the fixture suite under `fixtures/`. Assertions are structural:
they check that an artifact exists, carries the required sections and
registers its row. They do not compare prose, which differs between runtimes
and between runs of the same runtime.

## Adding a runtime

1. Fill a new column in the capability matrix from that runtime's documentation.
2. For every optional capability it lacks, confirm a degradation rule covers it.
3. Build the skill tree into the directory that runtime scans — see `bin/` for the existing generators.
4. Run the parity fixtures and record which acceptance criteria pass.
5. Mark the adapter experimental until every criterion passes on a live run.
