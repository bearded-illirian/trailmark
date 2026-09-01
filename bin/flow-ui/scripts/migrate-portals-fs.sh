#!/usr/bin/env bash
# migrate-portals-fs.sh — refactor partner-content/ → portals/{type}/{code}/
# Task: vschk-lab--651 block 500
#
# Idempotent: guards на test -d, backup partners.db first.
# Rollback: restore partners.db from backup, mv dirs back manually.
#
# Apply on VDS: bash /path/to/migrate-portals-fs.sh /srv/vschk-flow-ui
# (accepts flow-ui root as arg, defaults to /srv/vschk-flow-ui)

set -euo pipefail

ROOT="${1:-/srv/vschk-flow-ui}"
TS="$(date +%Y%m%d-%H%M%S)"

echo "🔧 Portals refactor — root=$ROOT ts=$TS"

# ── 1. Backup partners.db first ────────────────────────────────
DB="$ROOT/partners.db"
if [ -f "$DB" ]; then
  cp "$DB" "$DB.bak-portals-$TS"
  echo "  ✓ Backup: $DB.bak-portals-$TS"
else
  echo "  ⚠️  partners.db not found at $DB — skipping backup"
fi

# ── 2. Apply schema migration (ALTER + UPDATE) ─────────────────
SCHEMA_SQL="$(dirname "$0")/../migrations/portals-schema-2026-07-31.sql"
if [ -f "$SCHEMA_SQL" ]; then
  # Check if column already exists to make ALTER idempotent
  HAS_COL=$(sqlite3 "$DB" "SELECT COUNT(*) FROM pragma_table_info('partners') WHERE name='portal_type'" 2>/dev/null || echo 0)
  if [ "$HAS_COL" = "0" ]; then
    sqlite3 "$DB" < "$SCHEMA_SQL"
    echo "  ✓ Schema migration applied (ALTER + UPDATE Anton)"
  else
    echo "  ↷ portal_type column already exists — running UPDATE only"
    sqlite3 "$DB" "UPDATE partners SET portal_type='school' WHERE code='anton-avgeft'"
  fi
else
  echo "  ⚠️  Schema SQL not found at $SCHEMA_SQL — skipping ALTER"
fi

# ── 3. Filesystem restructure ──────────────────────────────────
PC="$ROOT/partner-content"
PORTALS="$ROOT/portals"

# Guard: если portals/ уже существует и partner-content — симлинк, migration уже сделана
if [ -L "$PC" ] && [ -d "$PORTALS" ]; then
  echo "  ↷ Filesystem already migrated (partner-content symlink → portals/partner exists)"
  exit 0
fi

# Precondition: partner-content должен существовать как реальная директория (не симлинк)
if [ ! -d "$PC" ] || [ -L "$PC" ]; then
  echo "  ❌ Precondition failed: $PC must exist as a real directory"
  exit 2
fi

# Create portals/ structure
mkdir -p "$PORTALS/partner" "$PORTALS/school" "$PORTALS/school/_shared"
echo "  ✓ mkdir portals/{partner,school,school/_shared}"

# Move: partner bucket (singular — matches portal_type field values)
for item in _shared alexander-sansan1005; do
  if [ -d "$PC/$item" ]; then
    mv "$PC/$item" "$PORTALS/partner/$item"
    echo "  ✓ mv partner-content/$item → portals/partner/$item"
  fi
done

# Move: school bucket
if [ -d "$PC/anton-avgeft" ]; then
  mv "$PC/anton-avgeft" "$PORTALS/school/anton-avgeft"
  echo "  ✓ mv partner-content/anton-avgeft → portals/school/anton-avgeft"
fi

# Now partner-content должно быть пустое или содержать только неизвестные items
REMAINING=$(ls -A "$PC" 2>/dev/null | wc -l | tr -d ' ')
if [ "$REMAINING" != "0" ]; then
  echo "  ⚠️  $PC still contains $REMAINING unknown items — NOT removing, manual review needed"
  ls -la "$PC"
  echo "  ⚠️  Skipping symlink creation. Move remaining items manually, then re-run."
  exit 3
fi

# ── 4. Replace partner-content dir with symlink → portals/partner ─
rmdir "$PC"
ln -sfn portals/partner "$PC"
echo "  ✓ Created BC symlink: $PC → portals/partner"

# ── 5. Verify ──────────────────────────────────────────────────
echo ""
echo "🔍 Post-migration state:"
ls -la "$PORTALS/partner/" "$PORTALS/school/"
sqlite3 "$DB" "SELECT code, name, portal_type FROM partners ORDER BY portal_type, code"

echo ""
echo "✅ Portals refactor complete."
