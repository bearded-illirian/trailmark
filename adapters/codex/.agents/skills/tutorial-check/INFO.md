---
name: tutorial-check
tier: core
version: 1.0.0
audience: framework new users
tags: [tutorial, validator, onboarding, homework]
---

# tutorial-check

**Homework validator for the QUICKSTART walkthrough.** Read-only skill that
runs 5 SQL/file checks against the user's workspace and reports which
tutorial steps landed correctly.

## When to use

Run `/tutorial-check` after completing the 5-step homework in
`docs/QUICKSTART.md` § 5. First-time framework users invoke it once to
verify they understood the core loop; experienced users rarely re-invoke.

## What it does

Executes 5 independent checks (project created, task started, chain
approved, artifacts exist, task in Flow UI) plus an optional 6th
self-audit. Each check has a specific SQL query or file test. Failures
include a one-line remediation hint.

## Output

Compact box-drawing table with ✅/❌ per step + a summary status
(`Homework complete` / `Homework incomplete`) + suggested fixes per
failed step. Zero files written, zero DB rows modified.

## Related

`plan-first` (the artifact Check 3 depends on), `flow-first` +
`library-first` (siblings the tutorial exercises), `check-first`
(sibling coverage validator with similar report-and-exit pattern).
