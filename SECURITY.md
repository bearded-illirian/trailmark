# Security Policy

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Report privately via one of:

1. **GitHub Security Advisory** (preferred) — open a
   [private security advisory](../../security/advisories/new) on this
   repository. GitHub keeps the report private until a fix is coordinated.
2. **Email** — the maintainer's contact address is in the repository's
   GitHub profile (please replace this line with a concrete email if you
   fork the framework and want reports to a specific address).

Please include as much of the following as you can:

- A brief description of the issue and its impact
- Steps to reproduce (proof-of-concept preferred)
- Affected version(s) — commit hash or release tag
- Any suggested mitigation

## What to expect

- **Acknowledgement** within 48 hours (business days).
- **Triage** within 7 days — severity classification and rough patch ETA.
- **Fix timeline** by severity:
  - Critical (RCE, credential exposure, path traversal): 7 days target
  - High (privilege escalation, DoS on core path): 14 days target
  - Medium / Low: next scheduled release
- **Coordinated disclosure** — we'll credit you in the security advisory
  unless you prefer to remain anonymous.

## Supported versions

| Version | Supported |
|---|---|
| v0.5.x (current) | ✅ |
| v0.4.x and older | ❌ (upgrade to v0.5+) |
| main (unreleased) | ✅ (best-effort) |

Older versions receive fixes only if the vulnerability affects the current
release too — the patch is applied to main; users on older versions need
to upgrade.

## Scope

This policy covers vulnerabilities in the framework code itself — skills,
tooling scripts under `bin/`, the Flow UI under `bin/flow-ui/`.

**Out of scope:**

- Vulnerabilities in Python packages listed in `requirements.txt` — report
  those to the respective upstream projects.
- Vulnerabilities in code that a framework user writes on top of the
  framework (their `projects/<name>/` code).
- Vulnerabilities in AI model providers (Anthropic, others) — report to
  the provider.
