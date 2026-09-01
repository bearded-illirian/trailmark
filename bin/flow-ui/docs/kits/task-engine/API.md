# task-engine — REST API contract v1.0.0

> Stack-agnostic. Реализуется adapter'ом в `backend/{stack}/`.
> На 2026-07-31 adapter'ов = 1: `python-fastapi`.

## Design

**Factory pattern.** Kit exposes `create_router(auth_fn, source_filter_fn) → APIRouter/Blueprint/Router`. Consumer injects two functions:

- `auth_fn(token) → identity_dict` — валидирует токен (magic-link, session, JWT — что угодно), возвращает identity или raises 401/404
- `source_filter_fn(identity) → filter_spec` — по identity возвращает какие sources[] доступны + writable-mask (например `{"personal": {"path": "...", "writable": true}, "shared": {...}}`)

Kit НЕ владеет auth и НЕ владеет привязкой identity → данные. Все endpoints работают через эти два fn.

**Base path** — определяется consumer'ом при `include_router(router, prefix="...")`. Примеры:
- Embedded: `/api/partner/{token}/`
- Standalone: `/s/tasks-admin/{token}/`

Ниже пути даны БЕЗ base prefix.

---

## Endpoints

### `GET /tasks`

List tasks доступные identity, объединённые из всех sources[].

**Query params:**

| Name | Type | Default | Notes |
|---|---|---|---|
| `source` | string (source_id) | all | Фильтр по конкретному source (personal / shared) |
| `status` | string (repeatable) | all | Фильтр по статусу (`?status=todo&status=doing`) |
| `project` | string | all | Фильтр по проекту |

**Response 200:**

```json
{
  "sources": [
    { "id": "personal", "label": "Личные", "badgeColor": "var(--brand)", "writable": true },
    { "id": "shared",   "label": "Общее школы", "badgeColor": "#3aa7e2", "writable": false }
  ],
  "tasks": [
    {
      "id": 42,
      "source_key": "personal",
      "project": null,
      "text": "Подключить Google Calendar",
      "status": "todo",
      "deadline": "2026-08-05",
      "contact_name": "Антон",
      "created_at": "2026-07-31T10:00:00",
      "updated_at": "2026-07-31T10:00:00",
      "writable": true,
      "comments_count": 0
    }
  ]
}
```

**Errors:** 401 (invalid token), 404 (token not found in auth_fn scope).

---

### `PATCH /task/{task_id}`

Обновить поля задачи. Разрешено только если source задачи writable=true.

**Body:**

```json
{
  "status": "doing",       // optional
  "deadline": "2026-08-10", // optional, null для очистки
  "text": "New wording"    // optional
}
```

**Response 200:** `{"ok": true, "task": {…}}` (обновлённая задача)

**Errors:**
- 400 (invalid status value — не из config.statuses)
- 403 (source read-only)
- 404 (task not found или не в scope identity)

---

### `POST /task`

Создать новую задачу в personal source. Shared sources не поддерживают create через API (только через прямой SQL от оператора).

**Body:**

```json
{
  "source_key": "personal",  // required, должен быть writable
  "project": null,            // optional
  "text": "New task",         // required
  "status": "todo",           // optional, default 'todo'
  "deadline": null,           // optional
  "contact_name": null        // optional
}
```

**Response 201:** `{"ok": true, "task": {…}}` (созданная задача с id)

**Errors:** 400 (missing text / invalid source), 403 (source read-only).

---

### `POST /task/{task_id}/comment`

Добавить комментарий к задаче. Разрешено на любую видимую задачу (даже shared read-only — комменты пишутся в consumer-owned БД).

**Body:**

```json
{
  "text": "Уточнил у клиента"   // required
}
```

**Response 201:**

```json
{
  "ok": true,
  "comment": {
    "id": 12,
    "task_id": 42,
    "author": "Антон",
    "text": "Уточнил у клиента",
    "created_at": "2026-07-31T15:00:00"
  }
}
```

`author` заполняется kit'ом из `identity.contact_name` (или fallback `identity.name`).

**Errors:** 400 (empty text), 404 (task not visible).

---

### `DELETE /task/{task_id}`

Удалить задачу. Разрешено только на personal (writable=true) sources.

**Response 200:** `{"ok": true}`

**Errors:** 403 (source read-only), 404 (task not found).

Delete каскадит `task_comments` через FK ON DELETE CASCADE.

---

## Auth injection contract

`auth_fn(token: str) → dict | raise HTTPException`

Ожидаемый identity dict:

```json
{
  "code": "anton-avgeft",        // stable identifier
  "name": "Антон Гефт",          // human name (для UI)
  "contact_name": "Антон",       // короткое имя для author в comments
  "portal_type": "school",       // consumer-specific
  "folder_path": "portals/school/anton-avgeft"  // абсолютный путь к папке портала
}
```

`source_filter_fn(identity: dict) → dict`:

Возвращает dict source_key → source spec:

```json
{
  "personal": {
    "path": "/srv/vschk-flow-ui/portals/school/anton-avgeft/tasks.sqlite",
    "label": "Личные",
    "badgeColor": "var(--brand)",
    "writable": true
  },
  "shared": {
    "path": "/srv/vschk-flow-ui/portals/school/_shared/tasks.sqlite",
    "label": "Общее школы",
    "badgeColor": "#3aa7e2",
    "writable": false
  }
}
```

Kit backend читает эти пути, открывает SQLite connections, объединяет list через UNION с source-tag'ами. PATCH/POST/DELETE проверяют `writable=true` перед выполнением.

---

## Error format

Все ошибки — стандартный FastAPI/Flask format:

```json
{
  "detail": "Source is read-only"
}
```

HTTP статус в заголовке (400 / 401 / 403 / 404 / 500).

---

## Не в scope v1.0

- WebSocket / SSE для live updates — polling пока
- Pagination — все задачи возвращаются одним batch'ем (assumption: <500 задач на portal)
- Bulk operations (PATCH multiple) — отдельные вызовы
- Attachments к комментам — plain text only
- History / audit log — только `updated_at`
- Search / full-text — client-side filter
