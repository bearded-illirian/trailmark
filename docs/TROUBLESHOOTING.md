# Troubleshooting

Top failure modes and their fixes. Check here first when something
misbehaves — most issues have a one-line diagnosis and a one-line fix.

---

## 1. Flow UI won't start

**Symptom:** `bash bin/flow-ui/bin/serve` exits immediately, or
`http://127.0.0.1:8765/` doesn't load.

**Diagnose:**

```bash
bash bin/flow-ui/bin/status    # shows current state
lsof -i :8765                  # check if port is already taken
```

**Fixes:**

| Cause | Fix |
|---|---|
| Port 8765 already in use | Stop the other process: `lsof -ti :8765 \| xargs kill`. Or change port in `bin/flow-ui/app/main.py`. |
| Python deps missing | `pip install -r bin/flow-ui/requirements.txt` |
| Python version too old | Flow UI needs Python 3.9+. Check: `python3 --version`. |
| Serve script says "already running" but page 500s | `bash bin/flow-ui/bin/stop && bash bin/flow-ui/bin/serve` — full restart |

---

## 2. `bin/init` didn't create `framework.yml`

**Symptom:** After running `bash bin/init`, no `framework.yml` in workspace
root — or it exists but is empty.

**Fixes:**

| Cause | Fix |
|---|---|
| You answered `Ctrl+C` mid-wizard | Rerun `bash bin/init` — it's idempotent, defaults are safe |
| Workspace root has no write permission | `chmod u+w .` in workspace root and rerun |
| Wrong directory | `bin/init` writes to CWD. Ensure you `cd` to the framework root first, not `bin/` |
| `python3` not on PATH | Install Python 3.9+ — `bin/init` uses it for YAML parsing |

Verify success:

```bash
cat framework.yml    # should show 3 keys: aihub, deploy, telegram
```

---

## 3. `bin/init-demo` says "already populated"

**Symptom:** Running `bash bin/init-demo` refuses with "manifest exists".

**Cause:** `tasks/.demo-manifest.json` already tracks a previous
init-demo run. The script is idempotent — it won't double-populate.

**Fix (recommended):**

```bash
bash bin/archive-demo         # remove current demo cleanly (3-marker safety)
bash bin/init-demo            # re-populate fresh
```

**Fix (manual):** if archive-demo also refuses (drift detected),
delete manifest by hand:

```bash
rm tasks/.demo-manifest.json
# Then manually clean up whatever demo rows/folders remain
sqlite3 tasks/routing.db "DELETE FROM artifacts WHERE is_demo=1"
rm -rf tasks/log/demo-* projects/demo-*
```

Then rerun `bin/init-demo`.

---

## 4. New project doesn't show in Flow UI

**Symptom:** After `bin/new-project my-app`, Flow UI sidebar doesn't
show `my-app`.

**Fixes:**

| Cause | Fix |
|---|---|
| Flow UI cached | Refresh page (Cmd+R). Flow UI reads projects.yml per request but the sidebar can stale. |
| `projects.yml` wasn't updated | `cat aihub/projects.yml` — look for `- id: my-app`. Missing? Add manually. |
| Symlink broken | `ls -la projects/my-app/.claude/skills` — should point to aihub. If not, recreate. |
| No tasks in project yet | Flow UI only lists projects that have registered tasks OR appear in projects.yml. Ensure yml entry. |

---

## 5. `/go-fast` doesn't find skills

**Symptom:** Agent responds "no skill named X" or the `/go-fast` command
itself is missing.

**Fixes:**

| Cause | Fix |
|---|---|
| Agent launched outside project dir | `cd projects/<your-project>` first, then launch the agent |
| `.claude/skills/` symlink broken | `ls -la projects/<name>/.claude/skills` — should resolve to `aihub/.claude/skills/`. Fix: `bin/new-project` (safe, idempotent) or recreate symlink manually |
| Agent can't invoke a skill by name | The framework needs a runtime that loads a skill tree and invokes skills by name — Claude Code via `Skill('name')`, Codex via `$name`. Standard chat agents don't work. Full requirements: [`AGENT_CONTRACT.md`](./AGENT_CONTRACT.md). |
| Skills folder empty | `ls aihub/.claude/skills/` — should show 18+ folders. If empty, run `bash bin/sync-from-aihub.sh` (or clone repo again). |

---

## 6. `archive-demo` aborts at preflight

**Symptom:** `bash bin/archive-demo` refuses with "manifest/DB drift detected".

**Cause:** Something changed the demo rows outside of init-demo — direct
SQL edits, a partial delete, or a re-populate without archive first.

**Fix:** the safest recovery is restore from the last backup:

```bash
ls tasks/backups/       # find the latest pre-archive-demo-<ts>.bak
bash bin/restore-demo-backup <timestamp>
```

If no backup exists yet (first run drift), archive by hand:

```bash
# Manual cleanup — bypasses 3-marker safety, use with care
sqlite3 tasks/routing.db "DELETE FROM artifacts WHERE is_demo=1"
sqlite3 tasks/routing.db "DELETE FROM task_blocks WHERE task_id LIKE 'demo-%'"
rm -rf tasks/log/demo-* projects/demo-*
rm tasks/.demo-manifest.json
```

**Prevent recurrence:** don't edit `is_demo` rows or `.demo-manifest.json`
by hand. If you need to alter demo data, archive → edit `bin/init-demo` →
re-populate.

---

## 7. `tutorial-check` reports fail on a step

**Symptom:** `/tutorial-check` reports ❌ on one of the 5 homework steps.

Common per-step fixes:

| Step | Fail reason | Fix |
|---|---|---|
| 1. Project created | Project dir missing / not in projects.yml | Rerun `bash bin/new-project my-tutorial` |
| 2. Task started | No `tasks/log/{slug}/` folder for the project | `cd projects/my-tutorial && claude`, then `/go-start` then `/go-fast "..."` |
| 3. Chain approved | Task exists but missing plan-first artifact | Approve the plan-first gate — reply `1` for autopilot |
| 4. Artifacts exist | Fewer than 5 artifact files in task folder | Chain didn't complete — check plan-first-*.md for errors; rerun task with the same slug |
| 5. Task in Flow UI | Task folder exists but Flow UI doesn't show it | Check `sqlite3 tasks/routing.db "SELECT * FROM artifacts WHERE id='{slug}'"`. Empty = task never registered — rerun /go-start. |

---

## Getting more help

If none of the above fixes work:

- **Search Discussions** — someone may have hit the same issue:
  `https://github.com/bearded-illirian/trailmark/discussions`
- **File an Issue** — include: OS, Python version, exact command you ran,
  and the full error output:
  `https://github.com/bearded-illirian/trailmark/issues/new`
- **Read** [`docs/CONCEPTS.md`](./CONCEPTS.md) — many "it's not working"
  reports turn out to be a concept mismatch (task vs block vs chain)

When reporting bugs, please include:

```bash
cat framework.yml
ls -la aihub/.claude/skills/ | head -25
sqlite3 tasks/routing.db "SELECT count(*) FROM artifacts"
bash bin/flow-ui/bin/status
```

That's enough context to diagnose 90% of reports.
