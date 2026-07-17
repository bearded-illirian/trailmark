# Report 1.1

**Date:** 2026-01-15
**Block:** Audit email_service.py — find encryption branches and callers
**Status:** ✅

## What was done

✅ 1. `rg "MAIL_ENCRYPTION" -l` → 3 files: `services/email_service.py`, `notifiers/tenant_notifier.py`, `handlers/onboarding.py`.
✅ 2. Read `email_service.py` — three branches in `_connect()`: `ssl` → SMTP_SSL, `tls` → SMTP + starttls(), fallthrough (`none` or anything unknown) → plain SMTP.
✅ 3. Read caller sites — `tenant_notifier.py:47` naked `send_email(...)`; `onboarding.py:112` wrapped in `try/except Exception: pass`.
✅ 4. Wrote flow-first-1.1 + library-first-1.1 with landscape + 2 watchpoints.
✅ 5. Handed off to block 2 with clear scope.

## What was notable

- **Fallthrough is the real bug** — even if we remove `none` from the UI, a typo like `tsl` in an env var silently downgrades to plain SMTP. Fix must whitelist, not blacklist.
- **onboarding.py silent-catch** — makes the ValueError from block 2 disappear unless we narrow the catch. Flagged in library-first Watchpoints for block 2 to address.
- **No prod incident yet** — but the ingredients are there. This is preventive, not reactive.

## Next

Block 2 — implement validation at config load + send-time, narrow onboarding.py catch to smtplib-only errors.
