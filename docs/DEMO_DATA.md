# Demo Data

Complete guide to the demo dataset shipped with the framework:
what it is, how it's marked, and how to remove it safely.

---

## What `bin/init-demo` creates

Running `bash bin/init-demo` populates your workspace with a realistic
sample dataset so you can see the framework's hub-and-spoke shape
immediately (instead of staring at an empty Flow UI).

### Contents

| Entity | Count | Where it lives |
|---|---|---|
| Projects | 3 | `projects/demo-blog-cms/`, `projects/demo-analytics-api/`, `projects/demo-mobile-app/` |
| Tasks | 6 | 2 per project — `tasks/log/demo-*/` folders |
| Task blocks | 12 | 2 per task, some completed, some in-progress |
| Artifacts (files) | 6 | plan-first, flow-first, library-first, report, user-note samples |
| Artifact DB rows | 60 | full artifact metadata per task (rowids tracked) |
| Skill invocations | 36 | realistic distribution across ~7 skills |
| Deploys | 9 | 3 per project, dated over past 2 weeks |

**Total: 123 DB rows + 6 folders + 3 project directories.**

Every DB row is marked `is_demo=1`. Every project name is prefixed `demo-`.
Every rowid is tracked in `tasks/.demo-manifest.json`.

---

## 3-marker safety architecture

Removal (via `bin/archive-demo`) requires **all three markers** to match
before a row can be deleted:

| # | Marker | Where | Guards against |
|---|---|---|---|
| 1 | `is_demo=1` | DB column on each row | User's real data (`is_demo=0` or `NULL`) is invisible to the removal script |
| 2 | `project LIKE 'demo-%'` | Cross-check in DB query | Legacy rows without `is_demo` column can't accidentally match |
| 3 | `id IN manifest.rowids` | `tasks/.demo-manifest.json` | Only rows populated *by this init-demo run* are eligible — even other `is_demo=1` rows (say from a re-run) are ignored |

**Effect:** even if you name your own project `demo-my-real-work` and
populate real tasks in it, its rows (which have `is_demo=0` and are not
in `.demo-manifest.json`) will never be touched by `archive-demo`.

---

## What `bin/archive-demo` does

Five phases, each verifiable in the script output:

1. **Preflight** — reads `.demo-manifest.json`, cross-checks DB rows
   still match all 3 markers. Aborts if any drift detected.
2. **Backup** — writes `tasks/backups/routing.db.pre-archive-demo-<ISO>.bak`
   + tars up `tasks/log/demo-*` folders + manifest into
   `tasks/backups/demo-log-folders-<ISO>.tar.gz`.
3. **Confirm gate** — requires you to type the exact string
   `YES REMOVE DEMO`. Anything else aborts without touching data.
4. **Surgical DELETE** — runs 5 `DELETE ... WHERE id IN (...) AND is_demo=1`
   queries in this order: skill_invocations → task_artifacts → task_blocks
   → deploys → artifacts. All in one transaction.
5. **Post-verify** — counts remaining `is_demo=1` rows. Should be 0.
   If not — reports the leftover count without auto-restoring
   (user decides).

Removes `tasks/log/demo-*/` folders, `projects/demo-*/` directories,
`demo-*` entries in `aihub/projects.yml`, and finally `.demo-manifest.json`.

---

## Safety guarantees

Concrete scenarios and what happens:

| Scenario | Outcome |
|---|---|
| You have real tasks with `is_demo=0` in normal projects | ✅ Untouched — marker 1 fails |
| You created a project named `demo-my-notes` with real tasks | ✅ Untouched — markers 1 + 3 fail (rows not in manifest) |
| You re-ran `bin/init-demo` twice → manifest tracks the latest run only | ⚠️ Older demo rows from first run may leak past archive-demo — cleanup via manual SQL if this ever happens |
| Someone else's fork has `is_demo` column but no `.demo-manifest.json` | 🛑 archive-demo aborts at Preflight — refuses to guess which rows are yours |
| Confirm string mistyped | 🛑 Script exits with "Aborted — data untouched" |

---

## Backup and restore

**Backup location:** `tasks/backups/` (auto-created on first archive).
Retention is user-managed — nothing auto-deletes them.

Each archive creates two files:

- `routing.db.pre-archive-demo-<ISO>.bak` — full SQLite snapshot before delete
- `demo-log-folders-<ISO>.tar.gz` — task folders + manifest

**Restore command:**

```bash
bash bin/restore-demo-backup <timestamp>
```

Where `<timestamp>` is the ISO string in the backup filenames (e.g.
`2026-07-18T14:23:05`). The script restores the DB, extracts folders,
recreates project dirs + symlinks + `projects.yml` entries, and verifies
counts. Full round-trip: 123 rows + 6 folders + 3 project dirs.

Run with no args to see available backups:

```bash
bash bin/restore-demo-backup
```

---

## FAQ

**Q: Is `bin/init-demo` idempotent?**
A: Yes — checks `.demo-manifest.json` first and refuses to double-populate.
If you want to re-populate, run `bin/archive-demo` first.

**Q: Does it touch my `aihub/projects.yml`?**
A: Yes — appends 3 `demo-*` project entries. `archive-demo` removes them
cleanly (grep + regex delete on the `id: demo-*` lines).

**Q: Can I remove one demo project without removing all three?**
A: Not via `archive-demo` — it's all-or-nothing. For partial removal,
delete the project dir manually and issue SQL:
`DELETE FROM artifacts WHERE project='demo-blog-cms' AND is_demo=1;` etc.

**Q: What if `archive-demo` crashes mid-execution?**
A: The DB is inside a transaction — you'll either see all deletes or none.
Folders are removed after DB commit, so worst case you'd have folders
without DB rows (safe — Flow UI just shows them as empty). Restore from
backup if unsure.

**Q: Can I re-run `bin/init-demo` after archiving?**
A: Yes. Manifest was removed by archive, so init-demo starts fresh with
a new set of rowids.
