#!/bin/bash
# gen-skills-map.sh
# Regenerates the `## Table` section of docs/SKILLS_MAP.md from the current
# manifest.yml and the shipped SKILL.md files.
#
# Reads:
#   manifest.yml            — tier per entry, source_path resolution
#   {destination_path}/SKILL.md OR {destination_path}   — frontmatter + body
#   docs/SKILLS_MAP.md      — preserves everything OUTSIDE `## Table`
#
# Writes:
#   docs/SKILLS_MAP.md      — regenerated `## Table` section only
#
# Column derivation (per SKILL_CONTRACT.md + SKILLS_MAP.md schema):
#   Skill      — frontmatter.name
#   Tier       — manifest.yml entry tier
#   Role       — first paragraph of frontmatter.description (truncated ~100 chars)
#   Invokes    — grep `Skill\('([a-z-]+)'\)` in body, unique, comma-joined
#   Invoked by — reverse-lookup graph across all skills
#   Delivers   — TODO placeholder (manual curation per schema)

set -e

# ── Paths ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$FRAMEWORK_ROOT/manifest.yml"
TARGET="$FRAMEWORK_ROOT/docs/SKILLS_MAP.md"

# ── Sanity checks ────────────────────────────────────────────────────────
[ -f "$MANIFEST" ] || { echo "❌ manifest.yml not found: $MANIFEST"; exit 1; }
[ -f "$TARGET" ]   || { echo "❌ SKILLS_MAP.md not found: $TARGET"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 required for YAML"; exit 1; }

# ── Regenerate via python3 ───────────────────────────────────────────────
MANIFEST="$MANIFEST" FRAMEWORK_ROOT="$FRAMEWORK_ROOT" TARGET="$TARGET" python3 <<'PYEOF'
import os, re, yaml

manifest_path = os.environ["MANIFEST"]
root          = os.environ["FRAMEWORK_ROOT"]
target        = os.environ["TARGET"]

manifest = yaml.safe_load(open(manifest_path))

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
SKILL_REF_RE   = re.compile(r"Skill\('([a-z][a-z0-9-]*)'\)")

def resolve_skill_file(destination_path):
    """Return path to the SKILL.md (or single .md for commands)."""
    abs_path = os.path.join(root, destination_path.rstrip("/"))
    if os.path.isdir(abs_path):
        candidate = os.path.join(abs_path, "SKILL.md")
        return candidate if os.path.isfile(candidate) else None
    if os.path.isfile(abs_path):
        return abs_path
    return None

def role_from_description(desc):
    """Take first paragraph of description, truncate at word boundary ~100 chars."""
    if not desc:
        return ""
    first = desc.strip().split("\n\n", 1)[0].replace("\n", " ").strip()
    if len(first) <= 100:
        return first
    cut = first[:100].rsplit(" ", 1)[0]
    return cut + "…"

# ── Pass 1 — collect per-skill data ──────────────────────────────────────
skills = []            # ordered list of dicts
name_to_index = {}

for entry in manifest["entries"]:
    skill_path = resolve_skill_file(entry["destination_path"])
    if not skill_path:
        continue
    content = open(skill_path).read()
    m = FRONTMATTER_RE.match(content)
    if not m:
        continue
    fm = yaml.safe_load(m.group(1))
    body = content[m.end():]
    invokes_raw = SKILL_REF_RE.findall(body)
    # Dedupe preserving order, exclude self-references
    seen = set()
    invokes = []
    self_name = fm.get("name", entry["id"])
    for ref in invokes_raw:
        if ref == self_name or ref in seen:
            continue
        seen.add(ref)
        invokes.append(ref)
    skills.append({
        "name":        fm.get("name", entry["id"]),
        "tier":        entry.get("tier", "?"),
        "role":        role_from_description(fm.get("description", "")),
        "invokes":     invokes,
        "invoked_by":  [],
    })
    name_to_index[fm.get("name", entry["id"])] = len(skills) - 1

# ── Pass 2 — reverse-lookup graph ───────────────────────────────────────
for i, s in enumerate(skills):
    for ref in s["invokes"]:
        if ref in name_to_index:
            skills[name_to_index[ref]]["invoked_by"].append(s["name"])

# ── Generate table ──────────────────────────────────────────────────────
lines = ["| Skill | Tier | Role | Invokes | Invoked by | Delivers |",
         "|---|---|---|---|---|---|"]
for s in skills:
    invokes    = ", ".join(s["invokes"]) or "— (leaf)"
    invoked_by = ", ".join(sorted(set(s["invoked_by"]))) or "— (independent)"
    role       = s["role"].replace("|", "\\|") or "—"
    lines.append(f"| {s['name']} | {s['tier']} | {role} | {invokes} | {invoked_by} | TODO |")

new_table = "\n".join(lines) + "\n"

# ── In-place replace ## Table section ───────────────────────────────────
original = open(target).read()
pattern  = re.compile(r"(## Table\n\n).*?(?=\n## |\Z)", re.DOTALL)
m        = pattern.search(original)
if not m:
    raise SystemExit(f"❌ Could not locate ## Table section in {target}")

updated = original[:m.start()] + m.group(1) + new_table + "\n" + original[m.end():]
open(target, "w").write(updated)

print(f"Regenerated {len(skills)} skills → {target}")
PYEOF
