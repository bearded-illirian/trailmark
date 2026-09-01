# task-engine

Turnkey task-management widget: список задач + inline-edit статуса/дедлайна + комментарии. Dual-mode: **standalone** (собственная страница) или **embedded** (виджет внутри другого продукта).

- **Version:** 1.0.0
- **Contract:** [KITS_MANIFEST v1.0](../../docs/KITS_MANIFEST.md)
- **Stacks:** python-fastapi
- **Master:** vschk-lab/kits/task-engine/ (не редактируй sync'нутую копию — правь master и resync)

---

## Что делает

Показывает партнёру / клиенту / оператору список задач из одного или нескольких sources (personal + shared, personal + team, etc.). Партнёр отмечает статус, оставляет комментарии, может создать новую задачу (в writable-source). Read-only sources (общие материалы) видны с бейджем-меткой и не редактируются.

Contract-first: kit не владеет auth и не знает про схему консьюмера — auth-фабрика и source-mapping инжектируются consumer'ом.

---

## Quick-start — Standalone

Собственная страница на своём URL с magic-link auth. Аналог `talks-admin` в radar-self.

**1. Sync kit в проект:**

```
bash ~/Projects/vschk-lab/scripts/sync-kit.sh task-engine ~/Projects/{myproject} --stack=python-fastapi
```

**2. Инициализировать БД (per-portal / per-tenant / etc.):**

```
sqlite3 /path/to/tasks.sqlite < ~/Projects/{myproject}/data/kits/task-engine/schema.sql
```

**3. Подключить theme + kit CSS в HTML template:**

```
<link rel="stylesheet" href="/static/themes/saffron-graphite.css">
<link rel="stylesheet" href="/static/kits/task-engine/task-engine.css">
<script src="/static/kits/task-engine/task-engine.js"></script>
```

**4. Wire backend endpoint в main.py:**

```
from app.kits.task_engine import create_router

router = create_router(
    auth_fn=lambda token: validate_magic_link(token, scope="admin"),
    source_filter_fn=lambda identity: {
        "personal": {
            "path": f"/srv/data/{identity['code']}/tasks.sqlite",
            "label": "Задачи",
            "badgeColor": "var(--brand)",
            "writable": True,
        }
    },
)
app.include_router(router, prefix="/s/tasks-admin/{token}")
```

**5. Standalone HTML wrapper (в отдельном endpoint):**

```
<body>
  <header>...</header>
  <main id="task-engine-root"></main>
  <script>
    TaskEngine.mount(
      document.getElementById('task-engine-root'),
      {
        apiBase: '/s/tasks-admin/' + TOKEN,
        mode: 'standalone',
        title: 'Задачи',
        columns: [...],
        statuses: {...},
        actions: ['add']
      }
    );
  </script>
</body>
```

---

## Quick-start — Embedded

Виджет внутри существующего продукта (например таб «Задачи» в партнёрском портале flow-ui).

**1-3. Sync + init БД + подключить CSS:** те же шаги что в standalone.

**4. Wire backend в существующий product:**

```
from app.kits.task_engine import create_router

router = create_router(
    auth_fn=lambda token: partners.get_partner_by_token(token),
    source_filter_fn=lambda partner: {
        "personal": {
            "path": f"{partner['folder_path']}/tasks.sqlite",
            "label": "Личные",
            "badgeColor": "var(--brand)",
            "writable": True,
        },
        "shared": {
            "path": f"{portal_type_shared_folder}/tasks.sqlite",
            "label": "Общее",
            "badgeColor": "#3aa7e2",
            "writable": False,
        },
    },
)
app.include_router(router, prefix="/api/partner/{token}/tasks")
```

**5. Mount виджет в существующую страницу (при клике на таб):**

```
document.querySelector('[data-tab="tasks"]').addEventListener('click', () => {
  TaskEngine.mount(
    document.getElementById('right-panel'),
    {
      apiBase: '/api/partner/' + PARTNER_TOKEN + '/tasks',
      mode: 'embedded',
      columns: [...],
      statuses: {...}
    }
  );
});
```

Виджет вставляется в переданный container, использует var(--*) из подключённой темы, не диктует layout.

---

## Config reference

Передаётся в `TaskEngine.mount(container, config)`.

| Key | Type | Default | Description |
|---|---|---|---|
| `apiBase` | string | — (required) | Base URL для API-вызовов (без trailing slash) |
| `mode` | `'standalone'` \| `'embedded'` | `'embedded'` | Стиль mount'а (в standalone виджет добавляет hero-заголовок) |
| `title` | string | `'Задачи'` | Заголовок в standalone режиме |
| `columns` | array | (см. ниже) | Колонки таблицы, порядок = порядок отображения |
| `statuses` | object | (см. ниже) | Allow-list статусов + цвета бейджей |
| `sections` | object | `{groupBy: 'flat'}` | Группировка: `'flat'` \| `'project'` \| `'source'` |
| `actions` | array | `[]` | Кнопки над списком: subset of `['add', 'export']` |
| `hooks` | object | `{}` | JS-хуки для extensions (см. ниже) |

### `columns` default

```
[
  { key: 'text',     label: 'Задача',   type: 'text',  bold: true },
  { key: 'status',   label: 'Статус',   type: 'badge' },
  { key: 'deadline', label: 'Дедлайн',  type: 'date'  }
]
```

### `statuses` default

```
{
  "todo":  { "label": "Открыта",  "color": "var(--text-muted)" },
  "doing": { "label": "В работе", "color": "var(--link)" },
  "done":  { "label": "Готово",   "color": "var(--success)" }
}
```

---

## Hooks reference

| Hook | Signature | When called |
|---|---|---|
| `renderCell` | `(col, value, task) → HTMLString` | Custom render ячейки. Return string HTML. Если не задан — default renderer |
| `onSave` | `(task) → void` | После успешного PATCH — для аналитики / re-render соседних виджетов |
| `onCreate` | `(task) → void` | После успешного POST |
| `onDelete` | `(taskId) → void` | После успешного DELETE |
| `onCommentSubmit` | `(comment) → void` | После POST comment |

Пример:

```
hooks: {
  renderCell: (col, value, task) => {
    if (col === 'text' && task.priority === 'high') {
      return '<strong style="color: var(--danger)">' + value + '</strong>';
    }
    return null;  // fallback to default renderer
  },
  onSave: (task) => { console.log('saved', task.id); }
}
```

---

## Extension: custom columns

Consumer добавляет свою колонку в 3 шага:

**1. Расширить schema через delta.sql:**

```
-- {target}/data/kits/task-engine/delta.sql
ALTER TABLE tasks ADD COLUMN priority TEXT DEFAULT 'medium';
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
```

Применяется один раз после `schema.sql`.

**2. Расширить config:**

```
columns: [
  { key: 'text',     label: 'Задача',   type: 'text',  bold: true },
  { key: 'priority', label: 'Приоритет', type: 'badge' },  // ← новая
  { key: 'status',   label: 'Статус',   type: 'badge' },
  { key: 'deadline', label: 'Дедлайн',  type: 'date'  }
]
```

**3. Опционально — кастомный renderer через hooks.renderCell** (см. выше).

---

## Extension: custom source

Consumer может добавить любое количество sources через `source_filter_fn`. Widget сам создаст фильтр по source и покажет бейджи-метки.

Пример 3-х sources (personal + team + archive):

```
source_filter_fn=lambda user: {
    "personal": {"path": f".../{user['code']}/tasks.sqlite", "label": "Мои", ..., "writable": True},
    "team":     {"path": f".../teams/{user['team']}/tasks.sqlite", "label": "Команда", ..., "writable": True},
    "archive":  {"path": ".../archive/tasks.sqlite", "label": "Архив", ..., "writable": False}
}
```

Widget union'ит их по PK-namespace (source + local_id), показывает все.

---

## Compliance

Kit valid по KITS_MANIFEST v1.0 §7 checklist:
- ✅ kit.json содержит все обязательные поля
- ✅ README имеет 2 quick-start
- ✅ CHANGELOG актуален
- ✅ contracts/API.md присутствует (backend capability)
- ✅ frontend/task-engine.js экспортит TaskEngine.mount
- ✅ backend/python-fastapi/task_engine_router.py экспортит create_router
- ✅ CSS использует только var(--*) — theme-agnostic

Проверка через `/kit-check-compliance task-engine` (планируется).

---

## Consumers (registry)

Список обновляется автоматически sync-kit.sh в `kit.json.consumers[]`. На 2026-07-31 — пусто (первый sync в задаче 651 блок 510).

## References

- Контракт: [KITS_MANIFEST v1.0](../../docs/KITS_MANIFEST.md)
- Дизайн: [note-01-decision-summary.md в задаче 651](../../../vschk-platform/tasks/log/2026-07-31-vschk-lab--651-task-engine-kit-mvp/note-01-decision-summary.md)
- Reference pattern: `radar-self/app/interfaces/public/routes/modes/talks/admin.py` (call_improvements + inline-edit + comments)
