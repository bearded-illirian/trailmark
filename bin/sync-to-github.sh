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
#   bash bin/sync-to-github.sh --no-wait                         # publish, do not wait for CI
#   GH_REPO_SLUG="user/repo" bash bin/sync-to-github.sh          # override target repo
#
# After a push the script waits for the workflow run on that exact commit and
# reports its outcome. The wait never changes the exit code — see wait_for_ci.
# Ceiling via CI_WAIT_TIMEOUT (seconds, default 420).
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

# ── Pre-flight: generated trees must match their source ──────────────────
# Runs before the clone, so a refusal leaves no temp directory behind.
#
# The generator is REQUIRED, not optional. It used to be wrapped in
# `if [ -x … ]`, meaning a rename or a move silently switched the check off
# and publication carried on reporting success. That is the failure this gate
# exists to prevent, so its own absence must be loud too.
#
# `all` covers every runtime in one call: asking per runtime is how one
# runtime eventually goes unchecked, and an unchecked tree looks exactly like
# a tree that passed.
# ── Publish allowlist ────────────────────────────────────────────────────
# manifest.yml says what may be published, by top-level path. This function
# compares that list against the tree about to be published and refuses in
# both directions.
#
# One direction is the leak: a directory appears in the working tree — because
# a synced tool brought its own content along — and rides the next publish out.
# That happened on 2026-09-01. The other direction is the quiet loss: a
# framework path drops out of the list, rsync --delete removes it from the
# mirror, and nobody notices until someone looks for a file that used to exist.
check_publish_allowlist() {
  local listed present missing_from_tree unlisted
  listed=$(MANIFEST="$SOURCE_DIR/manifest.yml" python3 -c '
import os, sys, yaml
try:
    d = yaml.safe_load(open(os.environ["MANIFEST"], encoding="utf-8")) or {}
except Exception as e:
    print("PARSE_ERROR", e, file=sys.stderr); sys.exit(1)
for p in d.get("publish_allowlist") or []:
    print(p)
') || { echo "❌ cannot read publish_allowlist from manifest.yml"; exit 1; }

  if [ -z "$listed" ]; then
    echo "❌ manifest.yml has no publish_allowlist — refusing to publish."
    echo ""
    echo "Without it this script publishes whatever happens to sit in the working"
    echo "tree, which is how client documents reached the public mirror."
    echo "Add the section and list the paths that belong here."
    exit 1
  fi

  # What the rsync below would carry: top-level entries minus what it excludes
  # anyway. Kept in step with the --exclude flags by hand — a mismatch here
  # surfaces as a false refusal, never as a silent publish.
  present=$(cd "$SOURCE_DIR" && ls -A \
    | grep -v -x -e ".git" -e ".sync-log" -e ".DS_Store" -e "framework.yml" -e "AUDIT.md" \
    | sort)

  unlisted=$(comm -23 <(printf "%s\n" "$present") <(printf "%s\n" "$listed" | sort))
  missing_from_tree=$(comm -13 <(printf "%s\n" "$present") <(printf "%s\n" "$listed" | sort))

  if [ -n "$unlisted" ]; then
    echo "❌ paths in the tree that publish_allowlist does not cover — refusing to publish:"
    printf "     %s\n" $unlisted
    echo ""
    echo "Either it belongs in the public mirror — add it to publish_allowlist in"
    echo "manifest.yml — or it does not, and it should not sit in framework-public."
    echo "If a synced tool brought it along, exclude it in sync_rules as well, and"
    echo "delete it by hand: rsync --delete does not remove what an exclude protects."
    exit 1
  fi

  if [ -n "$missing_from_tree" ]; then
    echo "❌ publish_allowlist lists paths that are not in the tree — refusing to publish:"
    printf "     %s\n" $missing_from_tree
    echo ""
    echo "The list has drifted from reality. Publishing now would strip them from"
    echo "the mirror — rsync --delete removes on the far side what is missing here."
    echo "Restore the paths, or drop them from publish_allowlist deliberately."
    exit 1
  fi
}

BUILDER="$SCRIPT_DIR/build-adapter.sh"
if [ ! -x "$BUILDER" ]; then
  echo "❌ generator not found or not executable: $BUILDER"
  echo ""
  echo "This script publishes generated adapter trees. Without the generator"
  echo "there is no way to tell whether those trees still match their source,"
  echo "and publishing them unchecked is exactly what this gate prevents."
  echo "Restore bin/build-adapter.sh, or publish from a checkout that has it."
  exit 1
fi
check_publish_allowlist

if ! bash "$BUILDER" all --check > /dev/null 2>&1; then
  echo "❌ a generated adapter tree is stale or edited by hand — refusing to publish."
  echo ""
  bash "$BUILDER" all --check || true
  exit 1
fi

TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TEMP_DIR="/tmp/framework-mirror-${TS//[:]/}"

# ── Commit message ───────────────────────────────────────────────────────
MSG="sync $TS"
WAIT_CI=1
while [ $# -gt 0 ]; do
  case "$1" in
    --message) [ -n "${2:-}" ] && { MSG="$2"; shift; } ;;
    --no-wait) WAIT_CI=0 ;;
    *)         echo "⚠️  unknown argument: $1 (ignored)" ;;
  esac
  shift
done

# ── CI outcome ───────────────────────────────────────────────────────────────────────
# The push is irreversible; this wait is not. Nothing below may change the
# script's exit code — a reader who sees a non-zero status concludes the
# publish failed and goes fixing something that is already fine. Every branch
# ends in `return 0`, including the ones that report a red build.
CI_WAIT_TIMEOUT="${CI_WAIT_TIMEOUT:-420}"

wait_for_ci() {
  local sha="$1"
  local waited=0 run_id="" status="" conclusion=""
  local actions_url="https://github.com/$REPO_SLUG/actions"

  if ! command -v gh > /dev/null 2>&1; then
    echo "ⓘ gh is not installed — skipping the CI wait."
    echo "  Watch it here: $actions_url"
    return 0
  fi
  if ! gh auth status > /dev/null 2>&1; then
    echo "ⓘ gh is not authenticated — skipping the CI wait."
    echo "  Watch it here: $actions_url"
    return 0
  fi

  echo "→ Waiting for CI on $sha ..."

  # Matched by commit sha, never by "the most recent run": somebody else's
  # push can land between ours and this query, and reporting their result as
  # ours is worse than reporting nothing at all.
  while [ "$waited" -lt 90 ]; do
    run_id=$(gh run list -R "$REPO_SLUG" --commit "$sha" --limit 1 \
               --json databaseId --jq '.[0].databaseId' 2>/dev/null || true)
    [ "$run_id" = "null" ] && run_id=""
    [ -n "$run_id" ] && break
    sleep 5
    waited=$((waited + 5))
  done

  if [ -z "$run_id" ]; then
    echo "ⓘ No workflow run registered for $sha after ${waited}s."
    echo "  Either this repository runs no workflows, or GitHub is slow to queue."
    echo "  Watch it here: $actions_url"
    return 0
  fi

  waited=0
  while [ "$waited" -lt "$CI_WAIT_TIMEOUT" ]; do
    status=$(gh run view "$run_id" -R "$REPO_SLUG" --json status \
               --jq .status 2>/dev/null || true)
    [ "$status" = "completed" ] && break
    sleep 10
    waited=$((waited + 10))
  done

  if [ "$status" != "completed" ]; then
    echo "ⓘ CI still running after ${CI_WAIT_TIMEOUT}s — not waiting further."
    echo "  $actions_url/runs/$run_id"
    return 0
  fi

  conclusion=$(gh run view "$run_id" -R "$REPO_SLUG" --json conclusion \
                 --jq .conclusion 2>/dev/null || true)
  if [ "$conclusion" = "success" ]; then
    echo "✅ CI passed — $actions_url/runs/$run_id"
    return 0
  fi

  echo "❌ CI finished with: ${conclusion:-unknown}"
  echo "   $actions_url/runs/$run_id"
  echo ""
  # Which step broke, not merely that something did — otherwise the reader
  # opens the browser anyway and the wait bought nothing.
  gh run view "$run_id" -R "$REPO_SLUG" --json jobs \
    --jq '.jobs[] | .name as $j | .steps[]
          | select(.conclusion != "success" and .conclusion != "skipped")
          | "   \($j) → \(.name): \(.conclusion)"' 2>/dev/null || true
  echo ""
  echo "The push already happened. This is a red build on published code,"
  echo "not a failed publish — fix forward."
  return 0
}

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
PUSHED_SHA=""
if git diff --staged --quiet; then
  echo "✅ No changes to sync (public mirror already up to date)."
else
  git commit -m "$MSG" 2>&1 | tail -3
  echo "→ Pushing..."
  git push origin main 2>&1 | tail -3
  echo "✅ Push complete."
  PUSHED_SHA=$(git rev-parse HEAD)
fi

# ── Cleanup ──────────────────────────────────────────────────────────────
cd /
rm -rf "$TEMP_DIR"

# ── Report the CI outcome ────────────────────────────────────────────────────────
# gh addresses the repository with -R, so it needs no working directory — the
# call sits after the cleanup on purpose.
if [ -n "$PUSHED_SHA" ] && [ "$WAIT_CI" = "1" ]; then
  wait_for_ci "$PUSHED_SHA"
elif [ -n "$PUSHED_SHA" ]; then
  echo "ⓘ --no-wait: not waiting for CI. https://github.com/$REPO_SLUG/actions"
fi

echo "════════════════════════════════════════════"
echo "Sync-to-github completed."
echo "Public: https://github.com/$REPO_SLUG"
echo "════════════════════════════════════════════"
