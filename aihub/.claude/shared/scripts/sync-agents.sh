#!/bin/bash
# sync-agents.sh
# Syncs skills/commands/agents/hooks/shared from workspace/aihub/.claude/
# to every registered project's .claude/ folder.
#
# Reads project destinations from ../../projects.yml (workspace/aihub/projects.yml).
# Skips personal data files that live only in each project's .claude/.
#
# Usage (from workspace root):
#   bash aihub/.claude/shared/scripts/sync-agents.sh
#
# Also invoked automatically by plan-first Step 3.5b after each block completes.

set -e

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# CORE = workspace/aihub/.claude (script's grandparent)
CORE="$(cd "$SCRIPT_DIR/../.." && pwd)"
# WORKSPACE = workspace root (aihub's parent)
WORKSPACE="$(cd "$CORE/../.." && pwd)"
PROJECTS_YML="$CORE/../projects.yml"

# ── Sanity ───────────────────────────────────────────────────────────────────
[ -d "$CORE" ] || { echo "❌ CORE not found: $CORE"; exit 1; }
[ -f "$PROJECTS_YML" ] || { echo "⚠️  projects.yml not found at $PROJECTS_YML — nothing to sync to."; exit 0; }

# ── Read TARGETS from projects.yml ──────────────────────────────────────────
# Each active project → $WORKSPACE/projects/{id}/.claude
TARGETS=()
while IFS= read -r project_path; do
  [ -z "$project_path" ] && continue
  TARGETS+=("$WORKSPACE/$project_path/.claude")
done < <(python3 -c "
import yaml, sys
try:
    d = yaml.safe_load(open('$PROJECTS_YML'))
    for p in d.get('projects', []):
        if p.get('status') == 'active':
            print(p.get('path', ''))
except Exception as e:
    print(f'WARNING: {e}', file=sys.stderr)
")

if [ ${#TARGETS[@]} -eq 0 ]; then
  echo "⚠️  No active projects in $PROJECTS_YML — nothing to sync."
  exit 0
fi

# ── Global excludes (personal per-project data — never overwrite) ───────────
EXCLUDES=(
  --exclude=projects/
  --exclude=sessions/
  --exclude=session-env/
  --exclude=history.jsonl
  --exclude=settings.json
  --exclude=settings.local.json
  --exclude=.session-project
  --exclude=paste-cache/
  --exclude=file-history/
  --exclude=backups/
  --exclude=telemetry/
  --exclude=cache/
  --exclude=mcp-needs-auth-cache.json
)

# ── Sync loop ───────────────────────────────────────────────────────────────
echo "🔄 Sync source: $CORE"
echo "   Projects:   ${#TARGETS[@]}"
echo ""

for TARGET in "${TARGETS[@]}"; do
  if [ ! -d "$(dirname "$TARGET")" ]; then
    echo "⚠️  Skipping (project folder missing): $TARGET"
    continue
  fi

  mkdir -p "$TARGET"

  # Sync full .claude tree — skills, commands, hooks, shared, agents.
  # --delete drops anything in TARGET that's not in CORE (except excluded personal files).
  rsync -a --delete "${EXCLUDES[@]}" "$CORE/" "$TARGET/"

  echo "✅ $TARGET"
done

echo ""
echo "Done."
