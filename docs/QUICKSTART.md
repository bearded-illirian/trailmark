# Quickstart

Five steps to your first tracked task. Assumes you already ran `./bin/init`
per the [main README](../README.md). If not, do that first — this
walkthrough won't work without a filled-in `framework.yml`.

## 1. Create a sample project

Point a project at the framework skills. From anywhere on disk:

```bash
mkdir hello-framework
cd hello-framework
mkdir -p .claude/skills
ln -s ../../../framework/core/*       .claude/skills/
ln -s ../../../framework/protocols/*  .claude/skills/
ln -s ../../../framework/commands/*   .claude/skills/
```

(Substitute the actual path to your cloned framework folder for
`../../../framework/`. On systems without symlinks, `cp -r` works too —
you just lose auto-updates when the framework changes.)

Any Claude-compatible agent launched in `hello-framework/` will now see
every shipped skill by name.

## 2. Invoke go-fast with a first task

In the agent chat:

```
/go-fast add a hello function to greetings.py
```

The framework starts the chain automatically. You'll see a folder appear
under `tasks/log/` — the task's home. That folder is the **task**
(from CONCEPTS.md).

## 3. Answer flow-first anchors

The chain's first skill (`flow-first`) will pause and ask:

```
Give me 2-3 anchors — file, table, route, or entry point.
```

Reply with a real path or "no analog yet". For our example:

```
greetings.py (doesn't exist yet)
```

flow-first now writes `flow-first-1.1.md` in the task folder — that's an
**artifact**. You'll see a 4×3 Landscape/Problem/Solution/Result table.
Reply `ok` to approve.

## 4. Approve the library-first table

`library-first` runs next. It shows a LOC table:

```
| # | What we do              | Source           | LOC | Type    |
| 1 | Create greetings.py     | From scratch ⚠️ | ~5  | backend |
```

Plus a Watchpoints block and an Out-of-scope block. Reply `ok` if the
table matches your intent — that's your **approval** opening the
library-first **gate**.

## 5. Choose plan-first autopilot mode

`plan-first` presents a step-by-step plan (7-15 rows) and asks:

```
What mode do we work in?
1. 🚀 Autopilot
2. 🔁 Step-by-step
3. 🎯 Hybrid
```

Reply `1`. The agent now writes the file, produces `report-1.1.md` +
`user-note-1.1.md`, and commits — no more prompts until the block closes.

You just ran one full **block** of one **chain**, produced 5 artifacts
(flow-first, library-first, plan-first, report, user-note), and passed
2 approval gates.

## What just happened

You used the framework's five core concepts (all defined in
[`CONCEPTS.md`](./CONCEPTS.md)):

- **Task** — the `hello-framework/tasks/log/{slug}/` folder that
  collected every artifact of this run.
- **Block** — the single Add-hello-function unit inside the task.
- **Chain** — `flow-first → library-first → plan-first → execute →
  report`, the fixed skill sequence.
- **Artifact** — each markdown file the skills wrote, tracked in
  `routing.db`.
- **Gate + Approval** — the `ok` you typed at flow-first and
  library-first, and the `1` you typed at plan-first.

## Optional skills — install for full functionality

The framework references three skills as advanced features. If you don't
install them, the framework degrades gracefully via documented fallbacks —
no crashes, just less automation.

| Skill | Referenced by | Fallback if not installed |
|---|---|---|
| `dev-auto-first` | `arch-first`, `audit-first` | Manual mode — user drives each block by typing `go` at each gate |
| `arch-map` | `ship-first` | `arch_ref = null` — architecture mapping step is skipped |
| `habit-first` | `idea-first` | New-product tasks are routed to `arch-first` (treated as features) |

**Rationale:** these are optional dependencies — not core requirements. The
13 core/protocol/command skills shipped in this framework work fully without
them. Enhanced automation with them.

**How to install:** copy any of the three folders from the source repository
into your `.claude/skills/` directory. The framework auto-detects presence
per invocation and picks the fallback path if missing.

## Next steps

- Read [`CONCEPTS.md`](./CONCEPTS.md) for term-by-term depth.
- Skim [`SKILLS_MAP.md`](./SKILLS_MAP.md) to see the other shipped
  skills — decision-first, ship-first, note-first, and more.
- Consult [`SKILL_CONTRACT.md`](./SKILL_CONTRACT.md) before writing a
  new skill of your own.
- Try a real task in one of your own projects — the same 5-step flow
  scales.
