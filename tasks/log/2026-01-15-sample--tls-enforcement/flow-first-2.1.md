# Flow-First — Block 2.1

**Date:** 2026-01-15
**Block:** Add ValueError on invalid encryption config (load + send)

## Landscape

| UI | DB | Integrations |
|---|---|---|
| not involved (deferred) | not involved | `email_service._load_config()` — reads `os.environ["MAIL_ENCRYPTION"]`, stores in module-level `_ENCRYPTION`. `send_email()` calls `_connect()` which branches on `_ENCRYPTION` (per block 1 audit). |

## Problem

| UI | DB | Integrations |
|---|---|---|
| not involved | not involved | No validation at either config-load or send-time — invalid values pass through to plain SMTP branch. `onboarding.py:112` catches all `Exception` silently — will swallow the new `ValueError` if we don't narrow. |

## Solution

| UI | DB | Integrations |
|---|---|---|
| not involved | not involved | (a) In `_load_config()`: `if enc not in {"ssl", "tls"}: raise ValueError("MAIL_ENCRYPTION must be ssl or tls, got: " + repr(enc))`. (b) In `send_email()` before `_connect()`: same guard. (c) In `onboarding.py:112`: `except (smtplib.SMTPException, socket.error) as e` — narrow catch so `ValueError` bubbles up. |

## Result

| UI | DB | Integrations |
|---|---|---|
| not involved | not involved | Misconfigured `MAIL_ENCRYPTION` → app fails at startup with clear message. Silent plaintext delivery structurally impossible. `onboarding.py` still tolerates SMTP failures, but config errors bubble to the operator log. |
