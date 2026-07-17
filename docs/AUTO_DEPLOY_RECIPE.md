# Auto-Deploy Recipe (git push → VDS)

An **optional** recipe for pushing code from your Mac to a VDS in one command.
Not required by the framework — a `git push origin main` triggers a
post-receive hook that checks out files into the deploy folder and (optionally)
restarts a service.

The framework itself works fully without this. Use this only if you want
"one push = live in prod" ergonomics for the projects you build with it.

## What you get

```
Mac                              VDS
├─ your project                 ├─ /srv/git/my-app.git   (bare repo)
│  └─ git push origin main ──▶  │     └─ post-receive hook
│                                │        ├─ checkout → /srv/my-app
│                                │        ├─ snapshot → /srv/git/backups.git
│                                │        └─ (optional) systemctl restart
```

## Prerequisites

- Any Linux VDS with SSH access (root or sudo user)
- `git` installed on the VDS
- SSH key auth from your Mac to the VDS (recommended over password)

Placeholders used below (replace with your values):

- `<vds-host>` — e.g. `myserver.example` or `192.0.2.10` (RFC 5737 docs IP)
- `<user>@<vds-host>` — e.g. `root@myserver.example`
- `<app-name>` — folder name of your project (`my-app` in examples)

## Step 1 — Create the bare repo on VDS

SSH in and create the bare repo:

```bash
ssh <user>@<vds-host>
mkdir -p /srv/git
cd /srv/git
git init --bare my-app.git
```

Also create the deploy destination folder:

```bash
mkdir -p /srv/my-app
```

## Step 2 — Write the post-receive hook

On the VDS, create the hook script:

```bash
cat > /srv/git/my-app.git/hooks/post-receive <<'HOOK'
#!/bin/bash
# post-receive — checkout latest push into deploy dir + snapshot backup
set -e

DEPLOY_DIR="/srv/my-app"
BACKUPS_REPO="/srv/git/backups.git"

# 1. Checkout files into deploy dir
git --git-dir=/srv/git/my-app.git --work-tree="$DEPLOY_DIR" checkout -f main

# 2. Snapshot backup (optional but recommended)
if [ -d "$BACKUPS_REPO" ]; then
    SNAPSHOT_REF="refs/backups/my-app/$(date -u +%Y-%m-%dT%H-%M-%SZ)"
    NEW_SHA=$(git --git-dir=/srv/git/my-app.git rev-parse main)
    git --git-dir="$BACKUPS_REPO" update-ref "$SNAPSHOT_REF" "$NEW_SHA" 2>/dev/null || true
fi

# 3. Restart service if you run one (uncomment + adjust)
# systemctl restart my-app.service

echo "✅ Deployed my-app @ $(date -u +%Y-%m-%dT%H:%M:%SZ)"
HOOK
chmod +x /srv/git/my-app.git/hooks/post-receive
```

**Snapshot backups** live in a shared `/srv/git/backups.git` bare repo. Create
it once if you want backup functionality:

```bash
git init --bare /srv/git/backups.git
```

## Step 3 — Point your local repo at the VDS

Back on your Mac, in your project folder:

```bash
cd projects/my-app
git remote add prod <user>@<vds-host>:/srv/git/my-app.git
```

## Step 4 — Push

```bash
git push prod main
```

Every push triggers checkout + snapshot on the VDS. The response lines from
the hook stream back to your terminal.

## Rollback

To roll back to a previous snapshot:

```bash
# List snapshots
ssh <user>@<vds-host> "git --git-dir=/srv/git/backups.git for-each-ref \
  refs/backups/my-app/ --sort=-creatordate \
  --format='%(refname:lstrip=3)  %(objectname:short)'" | head -5

# Reset deploy dir to a snapshot SHA
ssh <user>@<vds-host> "cd /srv/my-app && git --git-dir=/srv/git/my-app.git \
  --work-tree=/srv/my-app checkout -f <snapshot-sha>"
```

## Safety notes

- **Never commit secrets.** `.env`, private keys, `credentials.json` — all
  should be in `.gitignore`. Once pushed to a bare repo, git history keeps
  them forever.
- **Test on a dev branch first.** Create a separate deploy dir for `dev`
  branch to avoid overwriting prod on every commit.
- **Backup before enabling.** Ensure `/srv/git/backups.git` exists BEFORE
  first push, otherwise the initial snapshot is silently skipped.
- **Service restart is optional.** Only add `systemctl restart` if you run
  a systemd service. For static sites, no restart needed.

## When NOT to use this recipe

- **You already use a CI/CD platform** (GitHub Actions deploying to your VDS
  is functionally equivalent). Pick one, not both.
- **Multiple developers push to prod directly.** Add branch protection or a
  PR-merge gate first — post-receive hook doesn't enforce review.
- **You need blue-green or canary deploys.** This recipe is single-slot
  overwrite; use a proper deploy tool for zero-downtime rollouts.

## Framework integration

The framework's skills can reference `env.server_primary` from your
`framework.yml`. If you set it to `<user>@<vds-host>`, some skills (like
`ship-first`) can output ready-to-copy `ssh` / `curl` commands scoped to
your deploy target.

This is an opt-in convenience — the skills don't require this recipe to be
active; they just adapt their output if the value is present.
