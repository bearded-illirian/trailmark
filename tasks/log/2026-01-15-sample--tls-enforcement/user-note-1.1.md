# User Note: sample--tls-enforcement — Block 1.1

**Date:** 2026-01-15

## What changed

Nothing user-facing yet — this was an audit block. Confirmed the encryption fallthrough bug and identified one silent-catch callsite in `onboarding.py:112` that will need attention in block 2.

## Where it affects

Audit only — no code changes in this block. Findings feed the fix in block 2.
