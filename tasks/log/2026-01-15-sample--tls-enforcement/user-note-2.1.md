# User Note: sample--tls-enforcement — Block 2.1

**Date:** 2026-01-15

## What changed

Email service now refuses to start (or send) if `MAIL_ENCRYPTION` is anything other than `ssl` or `tls`. Silent plaintext delivery is no longer possible — a misconfigured environment will fail loudly with a clear error message instead of quietly downgrading to unencrypted SMTP.

## Where it affects

- **All tenants** — startup will fail if MAIL_ENCRYPTION is misset. Ops must verify env before restart.
- **Onboarding flow** — will now see previously-hidden SMTP errors (were swallowed by `except Exception`); logged, doesn't crash.
- **Config docs** — remove `none` from the list of valid encryption values (follow-up task).
