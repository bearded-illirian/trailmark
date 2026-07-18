#!/bin/bash
# sync-to-github.sh
# Syncs framework-public/ → github.com/bearded-illirian/framework (public mirror).
# Idempotent: safe to re-run any time. Uses temp clone → rsync → commit → push.
#
# v0.1.0 (block 20 of task aihub--594): initial script.
# v0.2.0 (block 22): REPO_SLUG configurable via GH_REPO_SLUG env var
# (default: bearded-illirian/framework). git user.email derived from local
# hostname instead of hardcoded personal value.
#
# Consumes: framework-public/.gitignore (exclude rules — plus explicit --exclude below).
# Auth: GH_TOKEN loaded from ~/.gh-token (mode 600).
#
# Usage:
#   bash bin/sync-to-github.sh                                  # default commit message with timestamp
#   bash bin/sync-to-github.sh --message "custom message"       # custom commit message
#   GH_REPO_SLUG="user/repo" bash bin/sync-to-github.sh          # override target repo
#
# Recommended commit message style:
#   - Keep under 60 chars (renders cleanly in GitHub file tree)
#   - Conventional prefix (feat/fix/docs/chore) followed by short subject
#   - NO internal task numbers, NO mixed languages, NO parenthetical asides
#   - Good:  "feat: init-demo lifecycle"
#   - Bad:   "polish: 594 blocks 9430+9440 — Russian README v0.8.0 parity + FAQ/templates brand cleanup"

set -e

# ── Auth ─────────────────────────────────────────────────────────────────
[ -f "$HOME/.gh-token" ] || { echo "❌ ~/.gh-token missing (mode 600 expected)"; exit 1; }
export GH_TOKEN=$(cat "$HOME/.gh-token")

# ── Paths ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_SLUG="${GH_REPO_SLUG:-bearded-illirian/trailmark}"
REPO_URL="https://x-access-token:${GH_TOKEN}@github.com/${REPO_SLUG}.git"

TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TEMP_DIR="/tmp/framework-mirror-${TS//[:]/}"

# ── Commit message ───────────────────────────────────────────────────────
MSG="sync $TS"
if [ "$1" = "--message" ] && [ -n "$2" ]; then
  MSG="$2"
fi

echo "════════════════════════════════════════════"
echo "Sync-to-github started at $TS"
echo "Source: $SOURCE_DIR"
echo "Target: github.com/$REPO_SLUG (branch: main)"
echo "Message: $MSG"
echo "════════════════════════════════════════════"

# ── Clone target repo ────────────────────────────────────────────────────
echo "→ Cloning target..."
git clone --depth 1 "$REPO_URL" "$TEMP_DIR" 2>&1 | tail -3

# ── Rsync source → temp clone ────────────────────────────────────────────
# Belt+suspenders exclude: .gitignore alone via rsync has quirky pattern semantics.
echo "→ Rsync..."
rsync -a --delete \
  --exclude=".git" \
  --exclude=".git/" \
  --exclude=".gitignore" \
  --exclude="AUDIT.md" \
  --exclude="framework.yml" \
  --exclude=".DS_Store" \
  --exclude=".sync-log/" \
  --exclude="*.bak-*" \
  "$SOURCE_DIR/" "$TEMP_DIR/"

# ── Copy .gitignore separately (we want it in public but not to be a source pattern) ─
cp "$SOURCE_DIR/.gitignore" "$TEMP_DIR/.gitignore"

# ── Commit + push ────────────────────────────────────────────────────────
cd "$TEMP_DIR"

# Ensure git identity is set for the commit
# Uses GitHub noreply email format: <numeric-id>+<username>@users.noreply.github.com
# — links commits to the GitHub account (contribution graph fills), keeps email private.
# Override via GH_SYNC_EMAIL / GH_SYNC_NAME env vars if forking.
git config user.email "${GH_SYNC_EMAIL:-288121890+bearded-illirian@users.noreply.github.com}"
git config user.name "${GH_SYNC_NAME:-bearded-illirian}"

git add -A
if git diff --staged --quiet; then
  echo "✅ No changes to sync (public mirror already up to date)."
else
  git commit -m "$MSG" 2>&1 | tail -3
  echo "→ Pushing..."
  git push origin main 2>&1 | tail -3
  echo "✅ Push complete."
fi

# ── Cleanup ──────────────────────────────────────────────────────────────
cd /
rm -rf "$TEMP_DIR"

echo "════════════════════════════════════════════"
echo "Sync-to-github completed."
echo "Public: https://github.com/$REPO_SLUG"
echo "════════════════════════════════════════════"
