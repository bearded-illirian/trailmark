# Plan-First — Block 2.1

**Date:** 2026-01-15
**Block:** Add ValueError on invalid encryption config (load + send)

## Plan

| # | Step | Brief summary |
|:-:|---|---|
| 1 | Edit `email_service._load_config` — add whitelist guard | 4 LOC — raise ValueError if enc not in {ssl, tls}. |
| 2 | Edit `email_service.send_email` — pre-connect guard | 3 LOC — same check, defense-in-depth. |
| 3 | Edit `handlers/onboarding.py:112` — narrow catch | Change `except Exception` to `except (smtplib.SMTPException, socket.error)`. |
| 4 | Add test `tests/test_email_service.py::test_load_config_rejects_invalid` | pytest.raises(ValueError) with monkeypatched env. |
| 5 | Add test `tests/test_email_service.py::test_send_email_rejects_invalid` | pytest.raises(ValueError) with tampered _ENCRYPTION. |
| 6 | Run pytest — all green | Both new tests pass, existing tests still green. |
| 7 | Commit + push | «fix: reject invalid MAIL_ENCRYPTION at load and send». |

## Risks

⚠️ Config-load failure → app doesn't start. If prod env is misset, startup crashes. Mitigation: deployment checklist notes to verify MAIL_ENCRYPTION env is set to ssl or tls before restart.

⚠️ Narrowing onboarding.py catch might expose previously-silent SMTP errors. Verify those get logged and don't crash onboarding flow.

## Out of scope

- UI dropdown cleanup (block 3, separate task)
- Tenant migration for encryption=none (block 4, separate task)
