# Your Projects

Put each of your projects in a subfolder here. Every project shares the same
skill library from `../aihub/.claude/skills/` via a symlink.

## Layout

```
projects/
├── my-app-a/
│   └── .claude/
│       └── skills → ../../../aihub/.claude/skills/
├── my-app-b/
│   └── .claude/
│       └── skills → ../../../aihub/.claude/skills/
└── ...
```

## How to add a new project

**Automated (recommended):**

```bash
bash bin/new-project my-app-c
```

The script creates `projects/my-app-c/`, sets up the symlink, and registers
the project in `aihub/projects.yml`.

**Manual:**

```bash
mkdir -p projects/my-app-c/.claude
cd projects/my-app-c/.claude
ln -s ../../../aihub/.claude/skills skills
```

Then add an entry to `aihub/projects.yml`:

```yaml
- id: my-app-c
  name: My App C
  path: projects/my-app-c
  status: active
```

## Why symlinks

One central skill library. Fix a bug in `plan-first` once — every project
benefits immediately. No duplicate copies, no drift between projects.

## See also

- `../docs/PROJECTS_GUIDE.md` — full guide to project layout
- `../docs/QUICKSTART.md` — first-run walkthrough
