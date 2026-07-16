#!/bin/bash
# verify-contract.sh
# Lints every skill file listed in manifest.yml against SKILL_CONTRACT.md.
#
# Checks per skill (see docs/SKILL_CONTRACT.md#acceptance-criteria):
#   REQUIRED (fail → exit 1):
#     1. Frontmatter block (---...---) present at top of file.
#     2. `name:` field in frontmatter.
#     3. `description:` field with "Use when" substring.
#   BODY (non-blocking, migration path):
#     4. Body contains `## Input` heading (case-insensitive).
#     5. Body contains `## Output` heading (case-insensitive).
#     6. Body contains `## Hands off to` heading (case-insensitive).
#
# Exit 0 if all REQUIRED checks pass across all skills.
# Exit 1 if any REQUIRED check fails on any skill.
# BODY-check failures are logged but do NOT change exit code (Migration
# path per SKILL_CONTRACT.md).

set -e

# ── Paths ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$FRAMEWORK_ROOT/manifest.yml"

# ── Sanity checks ────────────────────────────────────────────────────────
[ -f "$MANIFEST" ] || { echo "❌ manifest.yml not found: $MANIFEST"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 required for YAML"; exit 1; }

# ── Verify ───────────────────────────────────────────────────────────────
MANIFEST="$MANIFEST" FRAMEWORK_ROOT="$FRAMEWORK_ROOT" python3 <<'PYEOF' && EXIT=0 || EXIT=$?
import os, re, sys, yaml

manifest_path = os.environ["MANIFEST"]
root          = os.environ["FRAMEWORK_ROOT"]

manifest = yaml.safe_load(open(manifest_path))

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
HEADING_RE     = lambda name: re.compile(rf"^##\s+{re.escape(name)}\s*$",
                                          re.MULTILINE | re.IGNORECASE)

def resolve_skill_file(destination_path):
    abs_path = os.path.join(root, destination_path.rstrip("/"))
    if os.path.isdir(abs_path):
        candidate = os.path.join(abs_path, "SKILL.md")
        return candidate if os.path.isfile(candidate) else None
    if os.path.isfile(abs_path):
        return abs_path
    return None

required_fails = 0
body_fails     = 0
skills_scanned = 0
missing        = 0

print("── Skill contract verification ──")
print()

for entry in manifest["entries"]:
    skill_id   = entry["id"]
    skill_path = resolve_skill_file(entry["destination_path"])
    if not skill_path:
        print(f"⚠️  [{skill_id}] source file not found — skipped")
        missing += 1
        continue

    skills_scanned += 1
    content = open(skill_path).read()
    rel_path = os.path.relpath(skill_path, root)

    # Check 1 — frontmatter present
    fm_match = FRONTMATTER_RE.match(content)
    if fm_match:
        print(f"✅ [{skill_id}] check-1 frontmatter: OK")
        fm = yaml.safe_load(fm_match.group(1)) or {}
        body = content[fm_match.end():]
    else:
        print(f"❌ [{skill_id}] check-1 frontmatter: MISSING (required) — {rel_path}")
        required_fails += 1
        fm, body = {}, content

    # Check 2 — name field
    if fm.get("name"):
        print(f"✅ [{skill_id}] check-2 name: OK")
    else:
        print(f"❌ [{skill_id}] check-2 name: MISSING (required)")
        required_fails += 1

    # Check 3 — description with "Use when"
    desc = fm.get("description", "")
    if desc and "Use when" in desc:
        print(f"✅ [{skill_id}] check-3 description+\"Use when\": OK")
    else:
        print(f"❌ [{skill_id}] check-3 description+\"Use when\": MISSING (required)")
        required_fails += 1

    # Checks 4-6 — body section headings
    for check_num, section in enumerate(("Input", "Output", "Hands off to"), start=4):
        if HEADING_RE(section).search(body):
            print(f"✅ [{skill_id}] check-{check_num} ## {section}: OK")
        else:
            print(f"⚠️  [{skill_id}] check-{check_num} ## {section}: NON-COMPLIANT (migration path)")
            body_fails += 1

    print()

print("── Summary ──")
print(f"Skills scanned:        {skills_scanned}")
print(f"Skills missing file:   {missing}")
print(f"REQUIRED failures:     {required_fails}")
print(f"BODY non-compliances:  {body_fails} (migration debt, non-blocking)")

if required_fails:
    print()
    print(f"❌ {required_fails} required check(s) failed — see log above")
    sys.exit(1)
else:
    print()
    print("✅ all required checks pass")
PYEOF

exit $EXIT
