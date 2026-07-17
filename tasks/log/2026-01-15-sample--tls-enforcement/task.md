# sample--tls-enforcement

**Date:** 2026-01-15
**Project:** sample-app
**Type:** fast-track
**Number:** 1

## Task

Add TLS enforcement to `services/email_service.py` — the current code accepts
`encryption=none` and silently sends emails in plain text. Reject any encryption
value other than `ssl` or `tls`, both at config load and at send-time, with a
clear error message.

## Blocks

| # | Block title | Status | commit |
|:-:|---|:-:|---|
| 1 | Audit email_service.py — find encryption branches and callers | ✅ | a3f8c1d |
| 2 | Add ValueError on invalid encryption config (load + send) | ✅ | e7b4d92 |

## Task files

| File | Skill | Block | Round | Created |
|---|---|---|---|---|
| flow-first-1.1.md | flow-first | 1 | 1 | 2026-01-15 |
| library-first-1.1.md | library-first | 1 | 1 | 2026-01-15 |
| plan-first-1.1.md | plan-first | 1 | 1 | 2026-01-15 |
| report-1.1.md | plan-first | 1 | 1 | 2026-01-15 |
| user-note-1.1.md | plan-first | 1 | 1 | 2026-01-15 |
| flow-first-2.1.md | flow-first | 2 | 1 | 2026-01-15 |
| library-first-2.1.md | library-first | 2 | 1 | 2026-01-15 |
| plan-first-2.1.md | plan-first | 2 | 1 | 2026-01-15 |
| report-2.1.md | plan-first | 2 | 1 | 2026-01-15 |
| user-note-2.1.md | plan-first | 2 | 1 | 2026-01-15 |
