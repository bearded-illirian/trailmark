# Plan-First — Block 1.1

**Date:** 2026-01-15
**Block:** Audit email_service.py — find encryption branches and callers

## Plan

| # | Step | Brief summary |
|:-:|---|---|
| 1 | Ripgrep `MAIL_ENCRYPTION` across repo | Full callsite inventory. |
| 2 | Read email_service.py:_connect + _load_config | Map the three branches (ssl / tls / none). |
| 3 | Read tenant_notifier.py:47 + onboarding.py:112 | Understand caller-side error handling. |
| 4 | Note findings — flow-first + library-first artifacts | Fixed in earlier steps. |
| 5 | Report findings + hand off to block 2 | This block ships no code. |

## Risks

⚠️ Read-only audit — no risk of breaking anything.

## Out of scope

- Any code changes (block 2 scope)
- Configuration changes on prod (not needed for audit)
