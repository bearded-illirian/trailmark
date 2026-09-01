#!/bin/bash
# build-codex-adapter.sh
# Builds the Codex adapter tree from the public skill tree.
#
#   aihub/.claude/skills/{name}/SKILL.md   (source, Claude-shaped)
#         ↓  copy + two transforms
#   adapters/codex/.agents/skills/{name}/SKILL.md   (Codex-shaped)
#
# Codex scans `.agents/skills` (repo, walking up to the repo root), then
# `$HOME/.agents/skills`. It invokes a skill explicitly as `$name`. Both
# differences are mechanical, so the adapter is generated rather than
# maintained by hand — see docs/AGENT_CONTRACT.md capabilities R1 and R2.
#
# Source is the PUBLIC tree inside this repository, not the aihub master.
# That way anyone who cloned the repo can rebuild the adapter; only the
# maintainer needs `bin/sync-from-aihub.sh` to refresh the source itself.
#
# Idempotent: re-running produces a byte-identical tree.
#
# Usage:
#   bash bin/build-codex-adapter.sh            # build (writes the tree)
#   bash bin/build-codex-adapter.sh --check    # verify only, non-zero if stale
#   bash bin/build-codex-adapter.sh --summary  # what a rebuild would change

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SRC="$ROOT/aihub/.claude/skills"
SRC_CMD="$ROOT/aihub/.claude/commands"
DST="$ROOT/adapters/codex/.agents/skills"

CHECK_MODE=0
SUMMARY_MODE=0
case "${1:-}" in
  --check)   CHECK_MODE=1 ;;
  --summary) SUMMARY_MODE=1 ;;
  "")        ;;
  *) echo "❌ Unknown option: $1"
     echo "usage: bash bin/build-codex-adapter.sh [--check | --summary]"
     exit 2 ;;
esac

[ -d "$SRC" ] || { echo "❌ source tree missing: $SRC"; exit 1; }

# ── Destination guard ────────────────────────────────────────────────────
# rsync --delete below wipes whatever sits at the destination. A typo in
# DST would therefore erase an unrelated directory. Refuse anything that
# is not the expected path inside this repository.
guard_destination() {
  local target="$1"
  case "$target" in
    "$ROOT"/adapters/codex/.agents/skills) ;;
    *) echo "❌ refusing to write outside the adapter tree: $target"; exit 1 ;;
  esac
}

# ── Skill name whitelist ─────────────────────────────────────────────────
# Only these names are rewritten in invocation calls. The literal string
# Skill('name') appears inside anti-pattern prose as a placeholder, not as
# a call (see AUDIT.md) — leaving it alone keeps that text readable.
SKILL_NAMES=()
for d in "$SRC"/*/; do
  [ -f "$d/SKILL.md" ] || continue
  SKILL_NAMES+=("$(basename "$d")")
done
[ ${#SKILL_NAMES[@]} -gt 0 ] || { echo "❌ no skills found under $SRC"; exit 1; }

# Entry points ship as commands upstream. Codex deprecated custom prompts in
# favour of skills, so they become ordinary skills here — and their names must
# join the whitelist before any rewriting, otherwise a Skill('go-fast') call
# inside another protocol would survive untranslated.
COMMAND_NAMES=()
if [ -d "$SRC_CMD" ]; then
  for entry in "$SRC_CMD"/*; do
    [ -e "$entry" ] || continue
    if [ -d "$entry" ] && [ -f "$entry/SKILL.md" ]; then
      COMMAND_NAMES+=("$(basename "$entry")")
    elif [ -f "$entry" ] && [[ "$entry" == *.md ]]; then
      COMMAND_NAMES+=("$(basename "${entry%.md}")")
    fi
  done
fi
SKILL_NAMES+=("${COMMAND_NAMES[@]}")

# ── Build into a staging directory ───────────────────────────────────────
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/codex-adapter.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT

rsync -a --exclude='*.public.md' --exclude='*.ru.md' --exclude='.DS_Store' \
  "$SRC/" "$STAGE/"

# Commands → skills. A folder-shaped command is already the right shape; a flat
# `{name}.md` becomes `{name}/SKILL.md`, because Codex discovers a skill by its
# folder and would silently ignore a loose markdown file at the tree root.
for entry in "$SRC_CMD"/*; do
  [ -e "$entry" ] || continue
  base="$(basename "$entry")"
  if [ -d "$entry" ] && [ -f "$entry/SKILL.md" ]; then
    rsync -a --exclude='*.public.md' --exclude='*.ru.md' --exclude='.DS_Store' \
      "$entry/" "$STAGE/$base/"
  elif [ -f "$entry" ] && [[ "$base" == *.md ]]; then
    name="${base%.md}"
    mkdir -p "$STAGE/$name"
    cp "$entry" "$STAGE/$name/SKILL.md"
  fi
done

CALLS_REWRITTEN=0
PATHS_REWRITTEN=0

# grep exits 1 when it finds nothing, which under `set -o pipefail` would
# abort the whole build on the first file that happens to contain no calls.
# Counting through a captured string keeps a legitimate zero a zero.
count_matches() {
  local pattern="$1" file="$2" hits
  hits=$(grep -o -- "$pattern" "$file" 2>/dev/null || true)
  [ -z "$hits" ] && { echo 0; return; }
  printf '%s\n' "$hits" | wc -l | tr -d ' '
}

# Every markdown file inside a skill folder, not just SKILL.md — companion
# manifests such as CADENCE_HEURISTICS.md are read by the skill at runtime
# and carry the same invocation syntax.
while IFS= read -r f; do
  [ -f "$f" ] || continue

  before_calls=$(count_matches "Skill('" "$f")
  for name in "${SKILL_NAMES[@]}"; do
    # Skill('flow-first') → $flow-first — exact names only.
    perl -pi -e "s/\\bSkill\\('\Q$name\E'\\)/\\\$$name/g" "$f"
    # Skill('cadence-first', task_id=…) → $cadence-first with (task_id=…)
    # Codex documents no argument syntax for `$name`, so arguments become
    # prose the running agent reads rather than a call signature it parses.
    perl -pi -e "s/\\bSkill\\('\Q$name\E',\\s*([^)]*)\\)/\\\$$name with (\$1)/g" "$f"
  done
  after_calls=$(count_matches "Skill('" "$f")
  CALLS_REWRITTEN=$((CALLS_REWRITTEN + before_calls - after_calls))

  before_paths=$(count_matches '\.claude/skills' "$f")
  perl -pi -e 's{\.claude/skills}{.agents/skills}g' "$f"
  PATHS_REWRITTEN=$((PATHS_REWRITTEN + before_paths))
done < <(find "$STAGE" -type f -name '*.md')

# ── Marker ───────────────────────────────────────────────────────────────
# Written into the tree rather than kept beside it: rsync --delete below
# would wipe a hand-placed file on the first rebuild, which is precisely the
# failure the marker warns about.
cat > "$STAGE/GENERATED.md" <<'MARKER'
# This tree is generated

Every file here is produced by `bin/build-codex-adapter.sh` from the skills in
`aihub/.claude/skills/` and `aihub/.claude/commands/`. Nothing in this folder is
edited by hand.

**An edit made here does not survive.** The next rebuild overwrites it, and
because a rebuild prints no warning about what it replaced, the change simply
disappears. The tree is committed so the port stays browsable and usable where
the bash generator cannot run — not because it is a source.

## Where to make the change instead

| You want to change | Edit |
|---|---|
| What a skill does | `aihub/.claude/skills/{name}/SKILL.md` |
| An entry point | `aihub/.claude/commands/{name}` |
| How the port is produced — invocation syntax, paths, invocation policy | `bin/build-codex-adapter.sh` |

Then rebuild:

```bash
bash bin/build-codex-adapter.sh
```

## This is enforced, not merely requested

`bash bin/build-codex-adapter.sh --check` compares this tree against what the
generator would produce right now. It runs in two places:

- **CI** — `.github/workflows/verify-contract.yml`, on every push and pull request to `main`
- **Publication** — `bin/sync-to-github.sh` refuses to publish a tree that has drifted

So a hand edit here fails a build rather than vanishing quietly. That is the
point: the failure mode this guards against is silent, and silent losses are
the ones nobody learns from.

See `../../README.md` for the adapter itself, and `docs/AGENT_CONTRACT.md` for
what a runtime has to provide.
MARKER

COMMANDS_BUILT=${#COMMAND_NAMES[@]}
SKILLS_BUILT=$(( ${#SKILL_NAMES[@]} - COMMANDS_BUILT ))
TOTAL_BUILT=${#SKILL_NAMES[@]}

# ── Invocation policy ────────────────────────────────────────────────────
# Codex may pick a skill on its own by matching the request against its
# description. That is fine for a skill that produces an artifact and stops
# for approval. It is not fine for one that acts outward — deploys, pushes,
# closes a task, or takes over the loop. Those must be asked for by name.
EXPLICIT_ONLY=(ship-first dev-auto-first go-guide)

POLICIES_WRITTEN=0
for name in "${EXPLICIT_ONLY[@]}"; do
  [ -d "$STAGE/$name" ] || continue
  mkdir -p "$STAGE/$name/agents"
  cat > "$STAGE/$name/agents/openai.yaml" <<YAML
# This skill deploys, pushes or takes over the execution loop. It runs only
# when asked for by name (\$$name) — never picked up implicitly from a
# description match. See docs/AGENT_CONTRACT.md capability O2.
policy:
  allow_implicit_invocation: false
YAML
  POLICIES_WRITTEN=$((POLICIES_WRITTEN + 1))
done

# ── Summary mode: say what a rebuild would change, write nothing ──────────
# Reads against the destination as it stands right now, so it has to run
# before the rsync below replaces it. Answers the question `git diff` answers
# badly here: a 300 KB generated tree diffs into noise, and the useful facts —
# which skills moved, what appeared, what vanished — drown in it.
if [ "$SUMMARY_MODE" -eq 1 ]; then
  if [ ! -d "$DST" ]; then
    echo "Adapter tree does not exist yet — a build would create $TOTAL_BUILT entries."
    exit 0
  fi

  CHANGED=(); ADDED=(); REMOVED=()

  while IFS= read -r f; do
    rel="${f#$STAGE/}"
    if [ ! -f "$DST/$rel" ]; then
      ADDED+=("$rel")
    elif ! cmp -s "$f" "$DST/$rel"; then
      CHANGED+=("$rel")
    fi
  done < <(find "$STAGE" -type f | sort)

  while IFS= read -r f; do
    rel="${f#$DST/}"
    [ -f "$STAGE/$rel" ] || REMOVED+=("$rel")
  done < <(find "$DST" -type f | sort)

  echo "════════════════════════════════════════════"
  echo "Codex adapter — what a rebuild would change"
  echo "════════════════════════════════════════════"

  if [ ${#CHANGED[@]} -eq 0 ] && [ ${#ADDED[@]} -eq 0 ] && [ ${#REMOVED[@]} -eq 0 ]; then
    echo "  nothing — the tree matches its source"
  else
    if [ ${#CHANGED[@]} -gt 0 ]; then
      echo "  changed (${#CHANGED[@]}):"
      printf '    %s\n' "${CHANGED[@]:0:10}"
      [ ${#CHANGED[@]} -gt 10 ] && echo "    … and $((${#CHANGED[@]} - 10)) more"
    fi
    # Appearances and disappearances are always few and always worth naming in
    # full: a vanished skill is the kind of thing a truncated list hides.
    [ ${#ADDED[@]} -gt 0 ]   && { echo "  appeared (${#ADDED[@]}):";   printf '    %s\n' "${ADDED[@]}"; }
    [ ${#REMOVED[@]} -gt 0 ] && { echo "  vanished (${#REMOVED[@]}):"; printf '    %s\n' "${REMOVED[@]}"; }
  fi

  echo ""
  echo "  skills:    $SKILLS_BUILT"
  echo "  commands:  $COMMANDS_BUILT"
  echo "  policies:  $POLICIES_WRITTEN (${EXPLICIT_ONLY[*]})"
  echo "════════════════════════════════════════════"
  echo "Nothing was written. Run without --summary to build."
  exit 0
fi

# ── Check mode: compare, never write ─────────────────────────────────────
if [ "$CHECK_MODE" -eq 1 ]; then
  if [ ! -d "$DST" ]; then
    echo "❌ adapter tree missing — run without --check to build it"
    exit 1
  fi
  if diff -r -q "$STAGE" "$DST" > /dev/null 2>&1; then
    echo "✅ adapter tree is up to date ($TOTAL_BUILT entries)"
    exit 0
  fi
  echo "❌ adapter tree is stale — differences:"
  diff -r -q "$STAGE" "$DST" || true
  echo ""
  echo "Run: bash bin/build-codex-adapter.sh"
  exit 1
fi

# ── Publish ──────────────────────────────────────────────────────────────
guard_destination "$DST"
mkdir -p "$DST"
rsync -a --delete "$STAGE/" "$DST/"

echo "════════════════════════════════════════════"
echo "Codex adapter built"
echo "  source:      aihub/.claude/skills"
echo "  destination: adapters/codex/.agents/skills"
echo "  skills:      $SKILLS_BUILT"
echo "  commands:    $COMMANDS_BUILT (shipped as skills — Codex deprecated prompts)"
echo "  calls rewritten Skill('x') → \$x:  $CALLS_REWRITTEN"
echo "  paths rewritten .claude → .agents: $PATHS_REWRITTEN"
echo "  explicit-only policies written:   $POLICIES_WRITTEN"
echo "════════════════════════════════════════════"
