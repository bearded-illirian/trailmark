# flow-ui

Read-only web browser over a Claude Code framework `routing.db` +
`task_artifacts` + `projects.yml` + project filesystems. Local browser
for tasks, artifacts, files, deploys and skill-usage analytics.

- **Local:** `127.0.0.1:8765` after `bash bin/serve`
- **Deploy:** optional — see below

## Stack

FastAPI + uvicorn, SQLite (read-only over `routing.db`), Jinja + vanilla JS.
One write endpoint — `POST /api/access` (habit tracking, isolated `access.db`).

## Run locally

```bash
bash bin/serve    # start (idempotent, backgrounded)
bash bin/status   # check
bash bin/stop     # stop
```

Config: `cp config.example.yml config.yml` → edit paths. Env override via
`FLOW_UI_` prefix (e.g. `FLOW_UI_SERVER_PORT=8080`).

## Deploy (optional)

Local usage is the default. If you want git-push auto-deploy to a VDS
(bare repo + post-receive hook + snapshot backups), see
[`../../docs/AUTO_DEPLOY_RECIPE.md`](../../docs/AUTO_DEPLOY_RECIPE.md)
in the framework workspace. Nothing here binds you to a specific host.

## Endpoints

```
GET  /api/projects
GET  /api/projects/{id}
GET  /api/projects/{id}/tree?path=
GET  /api/projects/{id}/file?path=
GET  /api/projects/{id}/tasks
GET  /api/tasks/{task_id}
GET  /api/tasks/{task_id}/blocks
GET  /api/tasks/{task_id}/artifacts
GET  /api/artifacts/read?path=
GET  /api/skills
GET  /api/skills/{name}
GET  /api/skills/{name}/examples
GET  /api/stats
GET  /api/stats/skills
POST /api/access
```

## Auth

- Local — no auth.
- Behind SSO — reference implementation in `app/auth.py` gates traffic
  when `AUTH_MODE=platform` env is set. Contract in [AUTH.md](AUTH.md).
  Provide your own middleware if your SSO differs.

## Modes

| mode | Where project paths resolve | When |
|---|---|---|
| `local` | `project.path` (workspace-relative) | Local run |
| `vds` | `project.deploy_dir_vds` (server-absolute) | Prod behind SSO |
