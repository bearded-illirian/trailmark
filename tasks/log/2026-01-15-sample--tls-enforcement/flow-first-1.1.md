# Flow-First — Block 1.1

**Date:** 2026-01-15
**Block:** Audit email_service.py — find encryption branches and callers

## Landscape

| UI | DB | Integrations |
|---|---|---|
| Tenant settings form has `encryption` dropdown with values `ssl` / `tls` / `none`. | not involved | `services/email_service.py` — smtplib wrapper with `_connect()` branching on `MAIL_ENCRYPTION` env: `SMTP_SSL` for `ssl`, `starttls()` for `tls`, plain `SMTP` for `none`. Called from `notifiers/tenant_notifier.py:47` and `handlers/onboarding.py:112`. |

## Problem

| UI | DB | Integrations |
|---|---|---|
| UI accepts `none` and shows no warning — user sees successful save, later gets plaintext delivery without knowing. | not involved | `_connect()` silently accepts `none`, no validation at config load or send. If env is misspelled (`tsl`, `SSL`), falls through to plain SMTP branch — silent downgrade. |

## Solution

| UI | DB | Integrations |
|---|---|---|
| not involved (deferred to block 3) | not involved | Config-load validation: raise `ValueError("MAIL_ENCRYPTION must be ssl or tls")` in `email_service._load_config()` if value not in `{"ssl", "tls"}`. Send-time re-check: raise same error in `send_email()` before `_connect()`. |

## Result

| UI | DB | Integrations |
|---|---|---|
| not involved | not involved | Misconfigured tenant fails fast at startup with clear message. Silent plaintext delivery becomes structurally impossible. Both callsites (tenant_notifier, onboarding) get the exception; caller decides whether to alert admin or skip. |
