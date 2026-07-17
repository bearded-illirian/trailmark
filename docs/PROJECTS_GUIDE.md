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

**Automated (recommended, once Block 24 lands):**

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

- One `bin/flow-ui/serve` (Flow UI) shows tasks from every project
- Cross-project search "which tasks touched auth this month" works
- No per-project task-DB fragmentation

## See also

- `../projects/README.md` — quick reference in the projects folder itself
- `./QUICKSTART.md` — 5-step first-task walkthrough
- `./CONCEPTS.md` — glossary of task/block/skill/chain/gate terms
- `../aihub/projects.yml` — the actual project registry
