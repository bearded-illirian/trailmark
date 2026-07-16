#!/bin/bash
# sync-from-aihub.sh
# Syncs whitelisted skills and commands from aihub → framework-public per manifest.yml.
# Idempotent: safe to re-run any time. Fails fast (`set -e`) — one rsync error aborts.
#
# v0.2.0 (block 42): consumes SKILL.public.md as source (validated by
# skill-public-check v2.0 for zero D1-D6 leaks). Post-rsync rename step
# transforms SKILL.public.md → SKILL.md in destination — external users see
# canonical name. Internal SKILL.md (may be RU or contain project refs) is
# now in exclude_patterns.
#
# v0.3.0 (block 25): go-fast now uses commands/go-fast.public.md source.
# Single-file entries are renamed natively via manifest destination_path
# (rsync copies source_file → destination_path, so destination filename is
# whatever destination_path specifies). No extra rename step needed for
# single-file .public.md — only directory-scoped SKILL.public.md entries
# require the post-rsync rename loop below.
#
# Consumed manifest: framework-public/manifest.yml (v0.2.0+)
# Writes:
#   - core/{skill}/SKILL.md, protocols/{skill}/SKILL.md, commands/{cmd} — synced + renamed
#   - .sync-log/sync-{ISO}.log                          — per-run audit trail
#   - .sync-log/last-synced.yml                         — companion state (per-entry HEAD sha)
#
# Related tasks:
#   - aihub--498-vschk-framework Block 3 (initial script)
#   - aihub--498-vschk-framework Block 42 (F2 v0.2.0 upgrade — consume SKILL.public.md + rename)
#   - aihub--548-skills-public-export-en (upstream SKILL.public.md producer)
#   - aihub--549-extend-public-exports-framework-mvp (human-first + ui-ai-first coverage)

set -e

# ── Paths ────────────────────────────────────────────────────────────────
AIHUB_ROOT="/Users/viktor/Projects/aihub"
FRAMEWORK_PUBLIC="/Users/viktor/Projects/vschk-platform/framework-public"
MANIFEST="$FRAMEWORK_PUBLIC/manifest.yml"
LOG_DIR="$FRAMEWORK_PUBLIC/.sync-log"

# ── Sanity checks ────────────────────────────────────────────────────────
[ -f "$MANIFEST" ] || { echo "❌ Manifest not found: $MANIFEST"; exit 1; }
[ -d "$AIHUB_ROOT/.claude" ] || { echo "❌ Aihub .claude not found: $AIHUB_ROOT/.claude"; exit 1; }
mkdir -p "$LOG_DIR"

# ── Aihub HEAD sha (fallback: unknown if git missing/failing) ────────────
AIHUB_SHA=$(git -C "$AIHUB_ROOT" rev-parse HEAD 2>/dev/null || echo "unknown")

# ── Timestamps ───────────────────────────────────────────────────────────
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_FILE="$LOG_DIR/sync-$TS.log"

echo "════════════════════════════════════════════" | tee "$LOG_FILE"
echo "Sync-from-aihub started at $TS"                 | tee -a "$LOG_FILE"
echo "Aihub HEAD: $AIHUB_SHA"                          | tee -a "$LOG_FILE"
echo "Manifest:   $MANIFEST"                           | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo ""

# ── Parse manifest (python3 helper) ──────────────────────────────────────
# Emits tab-separated per entry:
#   id \t tier \t source_path \t destination_path \t exclude_flags
# where exclude_flags = space-separated "--exclude=PATTERN" tokens ready for rsync.
# The python3 script receives MANIFEST via env var — no in-heredoc substitution needed.
PARSED=$(MANIFEST="$MANIFEST" python3 <<'PYEOF'
import yaml, os
d = yaml.safe_load(open(os.environ["MANIFEST"]))
excl = d.get("sync_rules", {}).get("exclude_patterns", [])
flags = " ".join([f'--exclude={p}' for p in excl])
for e in d["entries"]:
    print("\t".join([e["id"], e["tier"], e["source_path"], e["destination_path"], flags]))
PYEOF
)

# ── Main rsync loop ──────────────────────────────────────────────────────
# Trailing-slash rule (documented in manifest.yml):
#   src/ → rsync copies CONTENTS of src/ into dst
#   src  → rsync copies src FOLDER itself into dst
# Manifest uses trailing slash for directory entries by convention.
ENTRIES_COUNT=0
WARNINGS_COUNT=0

while IFS=$'\t' read -r ID TIER SRC DST EXCL_FLAGS; do
  [ -z "$ID" ] && continue
  ENTRIES_COUNT=$((ENTRIES_COUNT + 1))

  SRC_FULL="$AIHUB_ROOT/.claude/$SRC"
  DST_FULL="$FRAMEWORK_PUBLIC/$DST"

  if [ ! -e "$SRC_FULL" ]; then
    echo "⚠️  [$ID] source missing: $SRC_FULL" | tee -a "$LOG_FILE"
    WARNINGS_COUNT=$((WARNINGS_COUNT + 1))
    continue
  fi

  mkdir -p "$(dirname "$DST_FULL")"

  if [ -d "$SRC_FULL" ]; then
    # Directory: --delete + exclude patterns (drops staging/RU/domains/public variants)
    rsync -a --delete $EXCL_FLAGS "$SRC_FULL" "$DST_FULL" >> "$LOG_FILE" 2>&1
  else
    # Single file (e.g. commands/go-fast.md): no --delete, no exclude
    rsync -a "$SRC_FULL" "$DST_FULL" >> "$LOG_FILE" 2>&1
  fi

  echo "✅ [$ID] $TIER — $SRC → $DST" | tee -a "$LOG_FILE"
done <<< "$PARSED"

echo "" | tee -a "$LOG_FILE"

# ── Post-rsync rename: SKILL.public.md → SKILL.md (v0.2.0) ───────────────
# External users see canonical `SKILL.md` name. Internal SKILL.public.md was
# consumed as source; rename happens on destination only. Idempotent — if
# SKILL.md already exists in destination (from previous manual add), skip.
echo "── Post-rsync rename (SKILL.public.md → SKILL.md) ──" | tee -a "$LOG_FILE"
RENAMED_COUNT=0

for scope in "$FRAMEWORK_PUBLIC/core" "$FRAMEWORK_PUBLIC/protocols" "$FRAMEWORK_PUBLIC/commands"; do
  [ -d "$scope" ] || continue
  find "$scope" -name "SKILL.public.md" -type f | while read -r pub_file; do
    dst_file="$(dirname "$pub_file")/SKILL.md"
    if [ -f "$dst_file" ]; then
      rm -f "$dst_file"  # overwrite — sync is authoritative
    fi
    mv "$pub_file" "$dst_file"
    echo "  ✓ renamed: $pub_file → SKILL.md" | tee -a "$LOG_FILE"
    RENAMED_COUNT=$((RENAMED_COUNT + 1))
  done
done

echo "Renamed: $RENAMED_COUNT files" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# ── Config resolver (sync-time inject per D05) ───────────────────────────
# Substitutes aihub-source literals with `{{ config.paths.X }}` tokens so
# framework-public/ files ship public-safe. Longest-paths-first order
# prevents partial-match overshadow. IPs deferred to Blocks 12-16 (schema
# mismatch: env.server_primary = root@<host>, not bare IP).
echo "── Config resolver (sync-time inject) ──" | tee -a "$LOG_FILE"

SUBST_SUMMARY=$(FRAMEWORK_PUBLIC="$FRAMEWORK_PUBLIC" python3 <<'PYEOF'
import os, re

LITERAL_TO_TOKEN = {
    "~/Projects/vschk-platform/tasks/routing.db":   "{{ config.paths.routing_db }}",
    "~/Projects/vschk-platform/framework-public":   "{{ config.paths.framework_public_root }}",
    "~/Projects/vschk-platform/tasks/log":          "{{ config.paths.log_dir_base }}",
    "~/Projects/vschk-platform/tasks":              "{{ config.paths.tasks_root }}",
    "/Users/viktor/Projects/aihub":                 "{{ config.paths.aihub_root }}",
    "~/Projects/aihub":                             "{{ config.paths.aihub_root }}",
}
ordered = sorted(LITERAL_TO_TOKEN.items(), key=lambda kv: -len(kv[0]))

root = os.environ["FRAMEWORK_PUBLIC"]
scope_dirs = [os.path.join(root, d) for d in ("core", "protocols", "commands")]
counts = {lit: 0 for lit, _ in ordered}
files_touched = 0

for scope in scope_dirs:
    if not os.path.isdir(scope):
        continue
    for dirpath, _, filenames in os.walk(scope):
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            fp = os.path.join(dirpath, fn)
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read()
            original = content
            for literal, token in ordered:
                new_content, n = re.subn(re.escape(literal), token, content)
                if n:
                    counts[literal] += n
                    content = new_content
            if content != original:
                files_touched += 1
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(content)

for literal, token in ordered:
    if counts[literal]:
        print(f"  {counts[literal]:>4} × {literal} → {token}")
print(f"Files touched: {files_touched}, total substitutions: {sum(counts.values())}")
PYEOF
)

echo "$SUBST_SUMMARY" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# ── Hardcode audit — surface private references that leaked past exclude ─
# Non-blocking: warnings only, script continues.
HARDCODE_PATTERNS=(
  "31\.130\.148\.26"                 # MSK VDS
  "89\.19\.214\.51"                  # NL VDS (Telegram)
  "\.vschk\.online"                  # vschk-specific domains (may match legitimate examples)
  "/Users/viktor/Desktop/"           # legacy Desktop paths (pre-task-507)
  "~/Desktop/"                       # tilde-based Desktop paths
  # AUDIT §3 — vschk-platform workspace paths (post-task-507 migration)
  "/Users/viktor/Projects/"          # absolute Projects paths
  "~/Projects/vschk-platform/"       # tilde-based vschk-platform paths
)

echo "── Hardcode audit ──" | tee -a "$LOG_FILE"
HARDCODE_HITS=0

for pattern in "${HARDCODE_PATTERNS[@]}"; do
  HITS=$(grep -rInE "$pattern" \
    "$FRAMEWORK_PUBLIC/core" \
    "$FRAMEWORK_PUBLIC/protocols" \
    "$FRAMEWORK_PUBLIC/commands" \
    2>/dev/null || true)
  if [ -n "$HITS" ]; then
    COUNT=$(echo "$HITS" | wc -l | tr -d ' ')
    HARDCODE_HITS=$((HARDCODE_HITS + COUNT))
    echo "⚠️  Pattern '$pattern' — $COUNT hits (first 5):" | tee -a "$LOG_FILE"
    echo "$HITS" | head -5 | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
  fi
done

if [ "$HARDCODE_HITS" -eq 0 ]; then
  echo "✅ Hardcode audit clean" | tee -a "$LOG_FILE"
else
  echo "⚠️  Total hardcode hits: $HARDCODE_HITS (non-blocking, review before public release)" | tee -a "$LOG_FILE"
  WARNINGS_COUNT=$((WARNINGS_COUNT + 1))
fi

echo "" | tee -a "$LOG_FILE"

# ── Update companion state file .sync-log/last-synced.yml ────────────────
# Design deviation from strict D02 (which suggested inline last_synced_commit in manifest):
# storing in a separate machine-written state file preserves manifest.yml comments/formatting.
# Semantic equivalent — per-entry sha tracking still recorded.
STATE_FILE="$LOG_DIR/last-synced.yml"

MANIFEST_PATH="$MANIFEST" \
AIHUB_SHA_ENV="$AIHUB_SHA" \
STATE_PATH="$STATE_FILE" \
TS_ENV="$TS" \
python3 <<'PYEOF'
import yaml, os
d = yaml.safe_load(open(os.environ["MANIFEST_PATH"]))
state = {
    "meta": {
        "manifest_version": d["meta"]["version"],
        "last_sync_at": os.environ["TS_ENV"],
        "aihub_head_sha": os.environ["AIHUB_SHA_ENV"],
    },
    "entries": {e["id"]: os.environ["AIHUB_SHA_ENV"] for e in d["entries"]},
}
with open(os.environ["STATE_PATH"], "w") as f:
    yaml.safe_dump(state, f, sort_keys=False, default_flow_style=False)
PYEOF

echo "✅ State updated: $STATE_FILE" | tee -a "$LOG_FILE"

# ── Summary ──────────────────────────────────────────────────────────────
echo "" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "Sync completed at $TS"                          | tee -a "$LOG_FILE"
echo "Entries synced: $ENTRIES_COUNT / 13"            | tee -a "$LOG_FILE"
echo "Warnings:       $WARNINGS_COUNT"                | tee -a "$LOG_FILE"
echo "Hardcode hits:  $HARDCODE_HITS"                 | tee -a "$LOG_FILE"
echo "Audit log:      $LOG_FILE"                      | tee -a "$LOG_FILE"
echo "State file:     $STATE_FILE"                    | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════" | tee -a "$LOG_FILE"
