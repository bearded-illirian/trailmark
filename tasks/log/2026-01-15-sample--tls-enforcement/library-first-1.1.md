# Library-First — Block 1.1

**Date:** 2026-01-15

## Table

| # | What we do | Source | What we use | LOC | Type |
|:-:|---|---|---|:-:|---|
| 1 | Grep `MAIL_ENCRYPTION` and `_connect(` across services/ + notifiers/ + handlers/ | Library ✅ | ripgrep | 0 | backend |
| 2 | Read email_service.py:_connect + _load_config to map current branches | Library ✅ | existing code | 0 | backend |
| 3 | Read caller sites (tenant_notifier.py:47, onboarding.py:112) — check for existing exception handling | Library ✅ | existing code | 0 | backend |
| 4 | Document findings in flow-first (already done) | Library ✅ | flow-first-1.1.md | 0 | backend |

## Summary

Rows "From scratch ⚠️": 0
Rows "Library ✅": 4
Total new LOC: 0
Types: backend

Audit-only block — no code changes here. Findings feed block 2 (validation implementation).

## Watchpoints

⚠️ `handlers/onboarding.py:112` — silent-catch of `Exception` around `send_email()`. If block 2 raises `ValueError`, it will be swallowed here. Audit noted; block 2 plan needs to decide: (a) let it swallow (onboarding proceeds even if email fails), (b) narrow the catch to `smtplib.*` only, (c) log + re-raise. Preference: option (b).

⚠️ `tenant_notifier.py:47` — no exception handling around `send_email()`. Any raised `ValueError` bubbles up to the cron caller; check if cron logger captures stderr for debugging.

## Out of scope

- Adding the actual validation (block 2)
- Refactoring `_connect()` to use a config class (out — YAGNI)
- Removing `encryption=none` from the UI dropdown (block 3 in a future task)
- Rewriting caller-site exception handling (only narrowing where directly relevant)
