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

## External Shares Engine (task 664)

Public magic-link URLs for sharing folders of documents + assets
externally, no auth required. Separate from partner portal.

**Difference from partners:** partners = trusted personal (Sansan, Kirill),
each with own portal + Flow Task engine kit. Shares = wide public audience
(courses, guides, docs) — one-click magic URL, no personality, download-first.

**Storage:**
- `data/external_shares.db` — SQLite with 3 tables: `external_shares`
  (id, code, title, token, folder_path, view_count, download_count),
  `external_share_visits` (audit log per visit), `external_share_downloads`
- `external-shares/{code}/` — folder with course/doc content (MD + assets)

**Public URL:** `/share/{token}/` — HTML shell with sidebar tree + main
pane rendering .md (marked.js) or inline image preview + «⬇ Скачать zip»
button. Path rewriter: `![alt](./screens/x.png)` in MD → served via
`/api/shares/{token}/asset?path=screens/x.png`.

**API:**
```
GET /share/{token}/                         → HTML shell (+ log_visit)
GET /api/shares/{token}/info                → metadata (title, counters)
GET /api/shares/{token}/tree?path=X         → JSON file tree
GET /api/shares/{token}/file?path=X         → text content (.md/.txt)
GET /api/shares/{token}/asset?path=X        → binary (PNG/JPG/PDF/etc)
GET /api/shares/{token}/zip                 → StreamingResponse zip (+ log_download)
```

**CLI:**
```bash
bin/create-share --code=my-course --title="My Course" \
                 [--description=...] [--folder=...] [--expires-days=30]
                 [--base-url=https://flow.vschk.online]

bin/share-stats --code=my-course
# → total counters + unique IPs + top-10 recent events + top referers
```

**Live:** https://flow.vschk.online/share/{token}/ — first record:
«Как собрать свой VPN за 1 час» (course VPN from task
vschk-platform--622-vpn-via-ai-coder-course).

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
