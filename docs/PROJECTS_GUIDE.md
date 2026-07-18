# Projects Guide

This workspace is a **hub-and-spoke** layout: one central skill library
(`aihub/`) shared across many projects (`projects/`).

## Layout

```
vasechka-workspace/
├── aihub/
│   ├── .claude/
│   │   ├── skills/            ← single source of truth
│   │   └── commands/
│   └── projects.yml           ← registry of your projects
├── projects/
│   ├── radar-app/.claude/skills → ../../../aihub/.claude/skills/
│   ├── radar-landing/.claude/skills → ../../../aihub/.claude/skills/
│   └── radar-api/.claude/skills → ../../../aihub/.claude/skills/
├── tasks/
│   ├── log/                   ← one folder per closed task, across all projects
│   └── routing.db             ← unified tracking DB
├── bin/                       ← workspace tooling
├── docs/
└── manifest.yml
```

## Why hub-and-spoke

**Traditional per-project skills:** each project bundles its own copy of
`plan-first.md`, `flow-first.md`, etc. Fix a bug in one — the others drift.

**Hub-and-spoke:** every project symlinks to `aihub/.claude/skills/`.
Fix once, applies everywhere. No drift, no duplicate maintenance.

## Adding a new project

**Automated (recommended):**

```bash
bash bin/new-project my-app-c
```

The script:
1. Creates `projects/my-app-c/`
2. Creates `.claude/skills` symlink to `aihub/.claude/skills/`
3. Adds entry to `aihub/projects.yml`

**Manual:**

```bash
mkdir -p projects/my-app-c/.claude
cd projects/my-app-c/.claude
ln -s ../../../aihub/.claude/skills skills
```

Then edit `aihub/projects.yml` and add:

```yaml
- id: my-app-c
  name: My App C
  path: projects/my-app-c
  status: active
```

## Registered projects

See `aihub/projects.yml` for the current list. Example entries:

- `radar-app` — main web application
- `radar-landing` — marketing site
- `radar-api` — backend API service

Replace with your own real project names.

## Unified task tracking

All tasks (across all projects) share `tasks/routing.db` and `tasks/log/`.
This means:

- One `bin/flow-ui/bin/serve` (Flow UI) shows tasks from every project
- Cross-project search "which tasks touched auth this month" works
- No per-project task-DB fragmentation

## Advanced: project-local skill overrides

By default every project inherits every skill from `aihub/.claude/skills/`
via symlink. Sometimes you want one project to use a *different* version
of a skill — a local patch, an experimental variant, or a
project-specific behaviour that shouldn't propagate.

### How overrides work

`.claude/skills/` is a directory (not a single symlink). Each individual
skill inside it is a symlink → `aihub/.claude/skills/<skill-name>/`.
Replace one symlink with a real folder and that project gets its own
copy — the other projects still see the upstream version.

### Example: override `plan-first` for one project

```bash
cd projects/my-app-a/.claude/skills

# Remove the symlink, replace with a real copy
rm plan-first
cp -r ../../../../aihub/.claude/skills/plan-first ./plan-first

# Now edit projects/my-app-a/.claude/skills/plan-first/SKILL.md freely
# — no other project is affected.
```

Verify: run any agent in `projects/my-app-a/` and confirm `plan-first`
still resolves (agents don't distinguish symlink from real folder).

### Symlink priority

If both a symlink and a real folder exist with the same name — the
filesystem entry that was created *last* wins. Best practice: always
`rm` the symlink first, then create the local folder.

### When NOT to override

Three anti-patterns to avoid:

1. **Bug fix that belongs upstream** — if the skill has a real bug,
   fix it in `aihub/.claude/skills/` so all projects benefit. Local
   override = drift + duplicate maintenance later.
2. **"Just this once" hack** — the moment you have a local override,
   it stops receiving upstream improvements. What was "just once"
   becomes permanent divergence.
3. **Team-shared behaviour** — if two teammates need the same override,
   it belongs upstream. Local overrides don't propagate through git
   (unless the project itself is under version control, in which case
   ⚠️ the override becomes tied to that repo, not the framework).

Use overrides only when the behaviour is genuinely project-unique and
you're OK with the drift.

## See also

- `../projects/README.md` — quick reference in the projects folder itself
- `./QUICKSTART.md` — 5-step first-task walkthrough
- `./CONCEPTS.md` — glossary of task/block/skill/chain/gate terms
- `./DEMO_DATA.md` — demo dataset guide (init-demo / archive-demo)
- `./TROUBLESHOOTING.md` — top failure modes and fixes
- `../aihub/projects.yml` — the actual project registry
