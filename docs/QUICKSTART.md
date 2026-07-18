# Quickstart

**5 minutes to your first tracked task.** By the end you'll have:

- A running Flow UI showing populated demo data
- Your own project registered with framework skills
- One real task with a complete artifact trail (plan → execute → report)

Assumes you've cloned the framework repo. If not: `git clone <repo>` first,
then `cd framework-public`.

---

## 1. Install (30 seconds)

```bash
bash bin/init
```

Answers three questions (framework name, path style, default AI). Writes
`framework.yml` — the workspace config every skill reads.

---

## 2. See it working — populate demo data

```bash
bash bin/init-demo
```

This populates the workspace with **3 demo projects × 2 tasks × 5 artifacts each**
(123 rows total in `tasks/routing.db`) — a realistic hub-and-spoke setup so
you can see how the framework looks when it's actually being used.

Everything created is marked `is_demo=1` in the DB and tracked in
`tasks/.demo-manifest.json`. Removal later is one command (see § 6).

---

## 3. Open Flow UI

```bash
bash bin/flow-ui/bin/serve
```

Opens on **http://127.0.0.1:8765**. You'll see:

- A **⚠️ yellow banner** at the top: "Demo mode — sample projects loaded"
- **3 projects** in the sidebar: `demo-blog-cms`, `demo-analytics-api`, `demo-mobile-app`
- **6 tasks** with populated artifacts, deploys, and skill invocations
- Click any task → see the full artifact tree (plan-first, library-first, report, etc.)

Take 2-3 minutes to click through. This is what your own workspace will
look like once you start real work.

Stop the server when done: `bash bin/flow-ui/bin/stop`.

---

## 4. Now try your own task

The demo shows you the shape. Now let's create something real. The
framework uses **hub-and-spoke**: skills live once in the framework root,
projects link to them. New projects inherit every skill by symlink.

### Create your first project

```bash
bash bin/new-project my-first-app
```

Creates `projects/my-first-app/` with `.claude/skills/` symlinked to the
framework's shared skill catalog. Also registers it in `aihub/projects.yml`
so Flow UI picks it up.

### Run your first task

```bash
cd projects/my-first-app
claude   # or your preferred Claude-compatible CLI
```

In the agent chat:

```
/go-start
/go-fast create a hello-world function in greetings.py
```

The framework auto-runs the chain: `flow-first` (4×3 understanding table)
→ `library-first` (LOC table + watchpoints) → `plan-first` (7-15 step plan).

Reply `ok` to approve each gate. On plan-first, choose **`1` (Autopilot)** —
the agent writes the file, produces `report-1.1.md` + `user-note-1.1.md`,
commits, and stops.

Refresh Flow UI at http://127.0.0.1:8765 — your task is now there,
alongside the demo ones.

---

## 5. Homework — verify you understood

Do these five steps **on your own project** (not on the demo). When done,
the `/tutorial-check` skill will validate your setup and report ✅ or ❌.

1. **Create a project** named `my-tutorial` via `bin/new-project my-tutorial`
2. **Start a task** in that project via `/go-start` then `/go-fast "add a README with project purpose"`
3. **Approve the chain** — reply `ok` at flow-first, `ok` at library-first, `1` at plan-first
4. **Verify artifacts** exist in `projects/my-tutorial/tasks/log/{slug}/`:
   `flow-first-*.md`, `library-first-*.md`, `plan-first-*.md`, `report-*.md`, `user-note-*.md`
5. **Open Flow UI** and confirm your task shows up with all 5 artifacts

Then run:

```
/tutorial-check
```

You'll get a pass/fail report telling you exactly which of the 5 steps
landed correctly and which need attention.

> *`/tutorial-check` is one of the shipped skills — it does 5-6 SQL/file
> checks against your workspace. Zero setup needed.*

---

## 6. Cleanup — remove demo data

When you're done exploring, remove the demo cleanly:

```bash
bash bin/archive-demo
```

**3-marker safety guaranteed.** The script only removes rows where
**all three** are true:

1. `is_demo=1` in the DB
2. `project LIKE 'demo-%'` prefix
3. `id IN .demo-manifest.json` (exact rowids tracked at populate-time)

Even if you named your own project `demo-my-real-work`, its rows
(is_demo=0) are untouched. The script asks for `YES REMOVE DEMO`
confirmation before deleting anything.

Auto-backup goes to `tasks/backups/` — reversible via
`bash bin/restore-demo-backup <timestamp>` if you change your mind.

---

## What just happened

You used the framework's five core concepts (all defined in
[`CONCEPTS.md`](./CONCEPTS.md)):

- **Task** — the `projects/my-first-app/tasks/log/{slug}/` folder that
  collected every artifact of this run
- **Block** — the single "add hello-world function" unit inside the task
- **Chain** — `flow-first → library-first → plan-first → execute → report`,
  the fixed skill sequence auto-run by `/go-fast`
- **Artifact** — each markdown file the skills wrote, tracked in `routing.db`
- **Gate + Approval** — the `ok` you typed at flow-first and library-first,
  and the `1` you typed at plan-first

---

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
shipped core/protocol/command skills work fully without them.

**How to install:** copy any of the three folders from the source repository
into your `.claude/skills/` directory. The framework auto-detects presence
per invocation and picks the fallback path if missing.

---

## Next steps

- Read [`CONCEPTS.md`](./CONCEPTS.md) for term-by-term depth
- Skim [`SKILLS_MAP.md`](./SKILLS_MAP.md) to see the other shipped skills
- Consult [`PROJECTS_GUIDE.md`](./PROJECTS_GUIDE.md) for advanced project layouts (project-local skill overrides, monorepo patterns)
- Consult [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) if any command above misbehaves
- Consult [`SKILL_CONTRACT.md`](./SKILL_CONTRACT.md) before writing a skill of your own
