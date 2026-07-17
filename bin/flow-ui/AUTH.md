# AUTH

Flow UI does not require authentication for local use — `bash bin/serve`
binds to loopback and skips any middleware.

## Enabling SSO

If you run behind SSO, wire a middleware into `app/main.py` that:

- Reads a session cookie
- Validates it (against your session store — DB, Redis, JWT, whatever)
- Rejects unauthenticated requests with `302 → your login URL`
- Exempts `/health` and `/openapi.json`

A reference implementation sitting on top of a SQLite session table lives in
[`app/auth.py`](app/auth.py). It's activated by env `AUTH_MODE=platform` and
expects a `platform_db` path in `config.yml`. Treat it as an example — copy,
adapt, or replace with your own.

## Notes

- Do not commit any session-store URLs or cookie secrets to this repo.
- Do not commit `config.yml` (see `.gitignore`).
- If you write your own middleware, register it in `app/main.py` behind the
  same `AUTH_MODE` env guard so local dev continues to work without config.
