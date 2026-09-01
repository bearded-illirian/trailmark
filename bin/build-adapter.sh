#!/bin/bash
# build-adapter.sh
# Builds a runtime adapter tree from the public skill tree.
#
#   aihub/.claude/skills/{name}/SKILL.md      (source, Claude-shaped)
#        ↓
#   adapters/{runtime}/…/{name}/SKILL.md      (runtime-shaped)
#
# One engine, one profile per runtime. A profile is data — five facts that
# distinguish one runtime from another: where the tree goes, how a skill is
# invoked by name, what the skills path is called, how implicit invocation is
# forbidden, and what the generated-tree marker says. Everything below the
# profile block knows no runtime name.
#
# Adding a runtime is a profile, not a second script. Two scripts drift on the
# first change to the engine — and drift silently, because both still exit 0.
#
# Consumes: aihub/.claude/skills/, aihub/.claude/commands/
# Produces: adapters/{runtime}/ — committed, never hand-edited (see GENERATED.md)
#
# Usage:
#   bash bin/build-adapter.sh codex              # build the codex tree
#   bash bin/build-adapter.sh codex --check      # verify only, non-zero if stale
#   bash bin/build-adapter.sh codex --summary    # what a rebuild would change
#   bash bin/build-adapter.sh                    # list the runtimes and exit

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SRC="$ROOT/aihub/.claude/skills"
SRC_CMD="$ROOT/aihub/.claude/commands"

# ── Runtime profiles ─────────────────────────────────────────────────────
# Every value a runtime needs, and nothing a runtime does not. Read once into
# P_* variables; the engine never branches on the runtime name again.
#
#   P_LABEL      human name, used in output and in the tree marker
#   P_DST        where the tree is written
#   P_SKILLPATH  what the runtime calls its skills directory
#   P_CALL       prefix that turns a skill name into an explicit invocation
#   P_POLICY     how implicit invocation is forbidden: yaml-file | frontmatter
#   P_TMPNAME    staging directory prefix, so parallel builds stay tellable apart
RUNTIMES="codex cursor"

load_profile() {
  case "$1" in
    codex)
      P_LABEL="Codex"
      P_DST="$ROOT/adapters/codex/.agents/skills"
      P_SKILLPATH=".agents/skills"
      P_CALL='$'
      P_POLICY="yaml-file"
      P_TMPNAME="codex-adapter"
      ;;
    cursor)
      P_LABEL="Cursor"
      P_DST="$ROOT/adapters/cursor/.cursor/skills"
      P_SKILLPATH=".cursor/skills"
      P_CALL='/'
      P_POLICY="frontmatter"
      P_TMPNAME="cursor-adapter"
      ;;
    *) return 1 ;;
  esac
  return 0
}

usage() {
  echo "usage: bash bin/build-adapter.sh <runtime> [--check | --summary]"
  echo ""
  echo "runtimes: $RUNTIMES"
  echo "          all — check or summarise every runtime at once"
  echo ""
  echo "  --check     verify the committed tree matches its source, write nothing"
  echo "  --summary   name what a rebuild would change, write nothing"
  exit 2
}

RUNTIME="${1:-}"
[ -n "$RUNTIME" ] || usage
shift

# ── all: every runtime in one pass ───────────────────────────────────────
# Only for the read-only modes. The question "is everything generated still
# in step with its source" is asked about the whole repository, and asking it
# per runtime means one day asking it about all but one — silently, because a
# runtime nobody checked looks exactly like a runtime that passed.
if [ "$RUNTIME" = "all" ]; then
  for r in $RUNTIMES; do
    [ "$r" = "all" ] && { echo "❌ a runtime may not be named 'all' — it collides with the all-runtimes form"; exit 2; }
  done
  MODE="${1:-}"
  case "$MODE" in
    --check|--summary) ;;
    *) echo "❌ 'all' requires --check or --summary — it does not build"; usage ;;
  esac
  STALE=""
  FAILED=0
  for r in $RUNTIMES; do
    if [ "$MODE" = "--summary" ]; then
      bash "${BASH_SOURCE[0]}" "$r" --summary || FAILED=1
    else
      if bash "${BASH_SOURCE[0]}" "$r" --check > /dev/null 2>&1; then
        echo "✅ $r — up to date"
      else
        echo "❌ $r — stale or hand-edited"
        STALE="$STALE $r"
        FAILED=1
      fi
    fi
  done
  if [ "$MODE" = "--check" ] && [ -n "$STALE" ]; then
    echo ""
    echo "Rebuild the runtimes that drifted, review the diff, then continue:"
    for r in $STALE; do echo "  bash bin/build-adapter.sh $r"; done
  fi
  exit $FAILED
fi

load_profile "$RUNTIME" || { echo "❌ unknown runtime: $RUNTIME"; echo "   known: $RUNTIMES"; exit 2; }

CHECK_MODE=0
SUMMARY_MODE=0
case "${1:-}" in
  --check)   CHECK_MODE=1 ;;
  --summary) SUMMARY_MODE=1 ;;
  "")        ;;
  *) echo "❌ Unknown option: $1"; usage ;;
esac

DST="$P_DST"

[ -d "$SRC" ] || { echo "❌ source tree missing: $SRC"; exit 1; }

# ── Destination guard ────────────────────────────────────────────────────
# rsync --delete below wipes whatever sits at the destination. A typo in
# DST would therefore erase an unrelated directory. Refuse anything that
# is not the expected path inside this repository.
guard_destination() {
  local target="$1"
  # Compared against the profile's own destination rather than a hardcoded
  # path: a second runtime must be buildable, and a typo must still be refused.
  # The path is also required to sit inside adapters/ — a profile with a
  # mistaken destination is exactly as dangerous as a typo on the command line.
  case "$target" in
    "$ROOT"/adapters/*) [ "$target" = "$P_DST" ] || {
        echo "❌ destination does not match the $RUNTIME profile: $target"; exit 1; } ;;
    *) echo "❌ refusing to write outside adapters/: $target"; exit 1 ;;
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
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/$P_TMPNAME.XXXXXX")"
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
    # Skill('flow-first') → {prefix}flow-first — exact names only.
    # Name and prefix travel through the environment so the perl program can
    # stay in single quotes: the prefix is `$` on one runtime and `/` on
    # another, and both are hostile to a double-quoted shell string.
    NAME="$name" PFX="$P_CALL" perl -pi -e '
      BEGIN { $n = $ENV{NAME}; $p = $ENV{PFX}; }
      s{\bSkill\(\x27\Q$n\E\x27\)}{$p$n}g;
      # Skill(\x27cadence-first\x27, task_id=…) → {prefix}cadence-first with (task_id=…)
      # No runtime documents an argument syntax for an explicit call, so the
      # arguments become prose the agent reads rather than a signature it parses.
      s{\bSkill\(\x27\Q$n\E\x27,\s*([^)]*)\)}{$p$n with ($1)}g;
    ' "$f"
  done
  after_calls=$(count_matches "Skill('" "$f")
  CALLS_REWRITTEN=$((CALLS_REWRITTEN + before_calls - after_calls))

  before_paths=$(count_matches '\.claude/skills' "$f")
  SKILLPATH="$P_SKILLPATH" perl -pi -e '
    BEGIN { $s = $ENV{SKILLPATH}; } s{\.claude/skills}{$s}g;' "$f"
  PATHS_REWRITTEN=$((PATHS_REWRITTEN + before_paths))
done < <(find "$STAGE" -type f -name '*.md')

# ── Marker ───────────────────────────────────────────────────────────────
# Written into the tree rather than kept beside it: rsync --delete below
# would wipe a hand-placed file on the first rebuild, which is precisely the
# failure the marker warns about.
cat > "$STAGE/GENERATED.md" <<'MARKER'
# This tree is generated

Every file here is produced by `bin/build-adapter.sh @RUNTIME@` from the skills
in `aihub/.claude/skills/` and `aihub/.claude/commands/`. Nothing in this folder
is edited by hand.

**An edit made here does not survive.** The next rebuild overwrites it, and
because a rebuild prints no warning about what it replaced, the change simply
disappears. The tree is committed so the port stays browsable and usable where
the bash generator cannot run — not because it is a source.

## Where to make the change instead

| You want to change | Edit |
|---|---|
| What a skill does | `aihub/.claude/skills/{name}/SKILL.md` |
| An entry point | `aihub/.claude/commands/{name}` |
| How @LABEL@ differs from other runtimes — invocation syntax, paths, invocation policy | the `@RUNTIME@` profile in `bin/build-adapter.sh` |

Then rebuild:

```bash
bash bin/build-adapter.sh @RUNTIME@
```

## This is enforced, not merely requested

`bash bin/build-adapter.sh @RUNTIME@ --check` compares this tree against what
the generator would produce right now. It runs in two places:

- **CI** — `.github/workflows/verify-contract.yml`, on every push and pull request to `main`
- **Publication** — `bin/sync-to-github.sh` refuses to publish a tree that has drifted

So a hand edit here fails a build rather than vanishing quietly. That is the
point: the failure mode this guards against is silent, and silent losses are
the ones nobody learns from.

See `../../README.md` for the adapter itself, and `docs/AGENT_CONTRACT.md` for
what a runtime has to provide.
MARKER

# The marker is written with placeholders and filled afterwards: the text
# carries backticks, and an expanding heredoc would run them as commands.
RUNTIME="$RUNTIME" LABEL="$P_LABEL" perl -pi -e '
  s{\@RUNTIME\@}{$ENV{RUNTIME}}g; s{\@LABEL\@}{$ENV{LABEL}}g;' "$STAGE/GENERATED.md"

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
  case "$P_POLICY" in
    yaml-file)
      # A sidecar file. Used where the runtime's frontmatter is closed to
      # extra keys — Codex accepts `name` and `description` and nothing else.
      mkdir -p "$STAGE/$name/agents"
      cat > "$STAGE/$name/agents/openai.yaml" <<YAML
# This skill deploys, pushes or takes over the execution loop. It runs only
# when asked for by name ($P_CALL$name) — never picked up implicitly from a
# description match. See docs/AGENT_CONTRACT.md capability O2.
policy:
  allow_implicit_invocation: false
YAML
      [ -s "$STAGE/$name/agents/openai.yaml" ] || {
        echo "❌ policy file not written for $name"; exit 1; }
      ;;
    frontmatter)
      # A key in the skill's own frontmatter. Used where the runtime reads the
      # policy from there rather than from a sidecar.
      #
      # The lazy `(?:.*?\n)*?` stops at the FIRST closing `---`. That matters:
      # these skill bodies use `---` as a markdown rule, and a greedy match
      # would bury the key somewhere in the prose, where the runtime never
      # looks and no reader notices.
      [ -f "$STAGE/$name/SKILL.md" ] || continue
      perl -0pi -e '
        s{\A(---\n(?:.*?\n)*?)(---\n)}
         {$1 . "disable-model-invocation: true\n" . $2}e
        unless /^disable-model-invocation:/m;
      ' "$STAGE/$name/SKILL.md"
      # Verified, not assumed, and verified inside the frontmatter rather than
      # within the first N lines: a longer description would push the key past
      # any fixed window. A regex that matches nothing writes nothing and says
      # nothing — without this the counter below reports a policy that is not
      # there, which is the exact failure the policy exists to prevent.
      awk '/^---$/{n++; if (n==2) exit} n==1' "$STAGE/$name/SKILL.md" \
        | grep -q '^disable-model-invocation: true$' || {
        echo "❌ frontmatter policy not applied to $name — refusing to build a tree that claims it"
        exit 1; }
      ;;
    *) echo "❌ unknown invocation policy in profile $RUNTIME: $P_POLICY"; exit 1 ;;
  esac
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
  echo "$P_LABEL adapter — what a rebuild would change"
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
  echo "Run: bash bin/build-adapter.sh $RUNTIME"
  exit 1
fi

# ── Publish ──────────────────────────────────────────────────────────────
guard_destination "$DST"
mkdir -p "$DST"
rsync -a --delete "$STAGE/" "$DST/"

echo "════════════════════════════════════════════"
echo "$P_LABEL adapter built"
echo "  source:      aihub/.claude/skills"
echo "  destination: ${DST#$ROOT/}"
echo "  skills:      $SKILLS_BUILT"
echo "  commands:    $COMMANDS_BUILT (shipped as skills)"
echo "  calls rewritten Skill('x') → $P_CALL""x:  $CALLS_REWRITTEN"
echo "  paths rewritten .claude/skills → $P_SKILLPATH: $PATHS_REWRITTEN"
echo "  explicit-only policies written ($P_POLICY): $POLICIES_WRITTEN"
echo "════════════════════════════════════════════"
