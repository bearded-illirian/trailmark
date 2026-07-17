# Library-First — Block 2.1

**Date:** 2026-01-15

## Table

| # | What we do | Source | What we use | LOC | Type |
|:-:|---|---|---|:-:|---|
| 1 | Add whitelist validation to email_service._load_config | Library ✅ | Python built-in ValueError | ~4 | backend |
| 2 | Add same guard to send_email() before _connect() | Library ✅ | Python built-in ValueError | ~3 | backend |
| 3 | Narrow onboarding.py:112 catch to (smtplib.SMTPException, socket.error) | Library ✅ | stdlib smtplib + socket | ~2 | backend |
| 4 | Add pytest test — MAIL_ENCRYPTION=xyz raises ValueError at load | Library ✅ | pytest.raises | ~8 | backend |
| 5 | Add pytest test — send_email raises ValueError with tampered _ENCRYPTION | Library ✅ | pytest.raises + monkeypatch | ~10 | backend |

## Summary

Rows "From scratch ⚠️": 0
Rows "Library ✅": 5
Total new LOC: ~27
Types: backend

Small block, all reusing stdlib + pytest. No new dependencies.

## Watchpoints

⚠️ `_load_config()` is called at module import — a `ValueError` here means the app fails to start. Deployment safety: if env is misset in prod, the startup log is the only signal. Verify the operator's log-forwarding picks up stderr.

⚠️ `send_email()` guard is technically redundant if `_load_config()` runs first, but keeps `_ENCRYPTION` tamper-safe if anything mutates it at runtime (rare — noted defense-in-depth).

## Out of scope

- UI change to remove `none` from encryption dropdown (block 3 in a future task)
- Migration of existing tenants with `encryption=none` (block 4 in a future task — will need coordination)
- Rewriting `_connect()` — the branch structure is fine, only validation needed
