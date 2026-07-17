# Report 2.1

**Date:** 2026-01-15
**Block:** Add ValueError on invalid encryption config (load + send)
**Status:** ✅

## What was done

✅ 1. Added whitelist guard to `email_service._load_config` — 4 LOC.
✅ 2. Added pre-connect guard to `send_email()` — 3 LOC.
✅ 3. Narrowed `handlers/onboarding.py:112` catch to `(smtplib.SMTPException, socket.error)` — 2 LOC diff.
✅ 4. Added `test_load_config_rejects_invalid` — monkeypatches env, asserts ValueError, message contains `ssl or tls`.
✅ 5. Added `test_send_email_rejects_invalid` — monkeypatches module-level _ENCRYPTION, asserts ValueError.
✅ 6. pytest — 47 passed, 0 failed (2 new + 45 existing green).
✅ 7. Commit `e7b4d92` + push.

## What was notable

- **Test discovery had one hiccup** — pytest didn't pick up new tests until I added `__init__.py` to the tests/ subdirectory. Added it, everything ran.
- **onboarding.py narrowed catch** exposed one previously-swallowed SMTP timeout on a test tenant — logged but no crash. Confirmed the narrowing was worth doing.
- **Message wording matters** — first draft said "Invalid encryption". Rewrote to "MAIL_ENCRYPTION must be ssl or tls, got: <value>" — now the operator immediately sees what to fix and what was there.

## Next

Ready to close task. Follow-ups (separate tasks): UI dropdown cleanup + tenant migration for existing `encryption=none` rows.
