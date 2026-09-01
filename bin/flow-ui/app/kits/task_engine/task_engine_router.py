"""
task_engine_router.py — python-fastapi adapter for task-engine kit.
v1.0.0 · vschk-lab

Factory pattern with dependency injection:

    from vschk_lab_kits.task_engine import create_router

    router = create_router(
        auth_fn=lambda token: my_validate(token),
        source_filter_fn=lambda identity: {"personal": {...}, "shared": {...}},
    )
    app.include_router(router, prefix="/api/tasks")

Contract: kits/task-engine/contracts/API.md
Schema:   kits/task-engine/schema.sql

Kit НЕ владеет auth — consumer inject'ит auth_fn.
Kit НЕ владеет привязкой identity → data — consumer inject'ит source_filter_fn.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel


# ── Pydantic models ─────────────────────────────────────────────────

class TaskOut(BaseModel):
    id: int
    source_key: str
    project: Optional[str] = None
    text: str
    status: str
    deadline: Optional[str] = None
    contact_name: Optional[str] = None
    assigned_to: Optional[str] = None       # v1.1
    meeting_id: Optional[int] = None        # v1.1
    description: Optional[str] = None       # свёрстанное описание, задача 706 блок 2331
    panel_key: Optional[str] = None         # ключ панели документа, задача 721 блок 102
    created_at: str
    updated_at: str
    writable: bool = False
    comments_count: int = 0


class MeetingOut(BaseModel):
    id: int
    title: str
    date: Optional[str] = None
    notes: Optional[str] = None
    created_at: str


class SourceOut(BaseModel):
    id: str
    label: str
    badgeColor: str
    writable: bool


class TasksListOut(BaseModel):
    sources: list[SourceOut]
    tasks: list[TaskOut]
    meetings: list[MeetingOut] = []          # v1.1: for group-by-meeting UI
    # Кому можно назначить задачу. Приходит от витрины: кит про портал не знает
    # и знать не должен — он работает и на отдельной странице (задача 706,
    # блок 234). Раньше список был захардкожен именами первого клиента.
    participants: list[str] = []


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    deadline: Optional[str] = None
    text: Optional[str] = None
    assigned_to: Optional[str] = None        # v1.2
    meeting_id: Optional[int] = None         # v1.2
    description: Optional[str] = None
    panel_key: Optional[str] = None           # задача 721, блок 102


class TaskCreate(BaseModel):
    source_key: str
    project: Optional[str] = None
    text: str
    status: str = "todo"
    deadline: Optional[str] = None
    contact_name: Optional[str] = None
    assigned_to: Optional[str] = None       # v1.1
    meeting_id: Optional[int] = None        # v1.1
    description: Optional[str] = None
    panel_key: Optional[str] = None         # задача 721, блок 102


class CommentCreate(BaseModel):
    text: str
    # 'agent' присылает тот, кто пишет от имени цифрового сотрудника. Подделать
    # метку клиент может, но вред косметический и в его же кабинете — отдельный
    # ключ для агентов заводить рано, агентов ещё нет.
    author_kind: Optional[str] = None


class MeetingCreate(BaseModel):
    title: str
    date: Optional[str] = None
    notes: Optional[str] = None


class CommentOut(BaseModel):
    id: int
    task_id: int
    author: str
    text: str
    created_at: str
    author_kind: str = "human"


# ── Helpers ──────────────────────────────────────────────────────────

def _open_source(path: str) -> sqlite3.Connection:
    """Open a per-source SQLite connection with sensible defaults."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Схема — копия живой базы, работающей с 2025 года. Расхождение схем между
# порталами опаснее их отсутствия: чтение проверяет наличие колонок и молча
# деградирует, поэтому портал с самодельной схемой работал бы «почти
# правильно» и врал бы в мелочах.
_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS tasks (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        source_key    TEXT    NOT NULL DEFAULT 'personal',
        project       TEXT,
        text          TEXT    NOT NULL,
        status        TEXT    NOT NULL DEFAULT 'todo',
        deadline      TEXT,
        contact_name  TEXT,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at    TEXT    NOT NULL DEFAULT (datetime('now')),
        assigned_to   TEXT,
        meeting_id    INTEGER REFERENCES meetings(id) ON DELETE SET NULL
    )""",
    """CREATE TABLE IF NOT EXISTS task_comments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id     INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        author      TEXT    NOT NULL,
        text        TEXT    NOT NULL,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS meetings (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        date        TEXT,
        notes       TEXT,
        created_at  TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
)


def ensure_task_schema(conn: sqlite3.Connection) -> None:
    """Завести схему задач, если её ещё нет. Идемпотентно.

    ЗАЧЕМ. Схема не создавалась кодом нигде: CREATE TABLE был только для
    meetings, дописанный когда добавляли встречи. На 22.08.2026 база
    существовала у одного портала из шестнадцати — у самого старого, заведённого
    до появления каталожной ветки. У остальных вкладка «Задачи» открывалась,
    выглядела рабочей и пустой, а первая созданная задача падала на
    no such table: tasks. Задача 706, блок 2331, решение decision-16.

    ПОРЯДОК ОБЯЗАТЕЛЕН: сначала таблицы, потом добавление колонки. ALTER TABLE
    по несуществующей таблице падает, и портал без базы получил бы ошибку
    вместо базы.
    """
    for stmt in _SCHEMA:
        conn.execute(stmt)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    if "description" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN description TEXT")
    # Стабильный ключ панели документа. Ссылка в странице кабинета раньше
    # несла номер задачи — а номер свой в каждом кабинете, и один документ
    # нельзя было выдать двум клиентам. Ключ пишется сборщиком и живёт
    # дольше номера (задача 721, блок 102).
    if "panel_key" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN panel_key TEXT")
    # Кто оставил реплику — человек или агент. Различить по имени автора нельзя:
    # автора вычисляет сервер из имени партнёра портала, и агент, пишущий тем же
    # токеном, подписался бы именем клиента (задача 706, блок 2332).
    ccols = {r[1] for r in conn.execute("PRAGMA table_info(task_comments)").fetchall()}
    if "author_kind" not in ccols:
        conn.execute("ALTER TABLE task_comments ADD COLUMN author_kind TEXT DEFAULT 'human'")
    conn.commit()


def _ensure_source_ready(path: str) -> None:
    """Создать папку и схему для источника задач. Вызывается перед записью."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        ensure_task_schema(conn)
    finally:
        conn.close()


def _comments_sql(conn: sqlite3.Connection) -> str:
    """SELECT комментариев, переживающий отсутствие author_kind.

    Колонка появилась позже самих баз (задача 706, блок 2332). Схема
    обновляется при записи, поэтому портал, где ещё не создавали задач,
    читается старой формой — и это не ошибка, а нормальное состояние.
    """
    cols = {r[1] for r in conn.execute("PRAGMA table_info(task_comments)").fetchall()}
    kind = "COALESCE(author_kind, 'human')" if "author_kind" in cols else "'human'"
    return f"SELECT id, task_id, author, text, created_at, {kind} AS author_kind FROM task_comments"


def _query_tasks(
    sources: dict,
    status_filter: Optional[list[str]] = None,
    project_filter: Optional[str] = None,
    source_filter: Optional[str] = None,
) -> list[dict]:
    """UNION tasks from all sources, tag by source_key, sort desc by (source_key, id)."""
    out: list[dict] = []
    for src_id, src in sources.items():
        if source_filter and src_id != source_filter:
            continue
        try:
            conn = _open_source(src["path"])
        except sqlite3.Error:
            continue  # missing file → source silently empty (may not be initialized yet)
        try:
            # v1.1: assigned_to + meeting_id могут отсутствовать в старых consumer БД
            # graceful degrade — ставим NULL если column не найден
            cols_row = conn.execute("PRAGMA table_info(tasks)").fetchall()
            col_names = {row[1] for row in cols_row}
            has_assigned = "assigned_to" in col_names
            has_meeting = "meeting_id" in col_names
            has_descr = "description" in col_names
            has_panel_key = "panel_key" in col_names
            sel_extra = ""
            if has_assigned:
                sel_extra += ", assigned_to"
            if has_meeting:
                sel_extra += ", meeting_id"
            if has_descr:
                sel_extra += ", description"
            if has_panel_key:
                sel_extra += ", panel_key"
            sql = f"SELECT id, source_key, project, text, status, deadline, contact_name, created_at, updated_at{sel_extra} FROM tasks"
            where = []
            params: list = []
            if status_filter:
                placeholders = ",".join(["?"] * len(status_filter))
                where.append(f"status IN ({placeholders})")
                params.extend(status_filter)
            if project_filter:
                where.append("project = ?")
                params.append(project_filter)
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY id DESC"
            for row in conn.execute(sql, params).fetchall():
                d = dict(row)
                d["source_key"] = src_id
                d["writable"] = src.get("writable", False)
                d["comments_count"] = conn.execute(
                    "SELECT COUNT(*) FROM task_comments WHERE task_id = ?", (row["id"],)
                ).fetchone()[0]
                # v1.1 defaults для old schemas
                if not has_assigned:
                    d["assigned_to"] = None
                if not has_meeting:
                    d["meeting_id"] = None
                if not has_descr:
                    d["description"] = None
                out.append(d)
        finally:
            conn.close()
    return out


# ── Factory ──────────────────────────────────────────────────────────

def create_router(
    auth_fn: Callable[[str], dict],
    source_filter_fn: Callable[[dict], dict],
    participants_fn: Optional[Callable[[dict], list]] = None,
) -> APIRouter:
    """
    Build a task-engine APIRouter with injected auth + source resolution.

    auth_fn(token) → identity dict, raises HTTPException on invalid.
    source_filter_fn(identity) → {source_key: {path, label, badgeColor, writable}}.
    participants_fn(identity) → ["Имя", ...] — кому можно назначить задачу.
        Не задан — список пуст, и выпадающий список исполнителей пустой. Это
        лучше подстановки чужих имён: раньше кит по умолчанию предлагал
        «Антона» в кабинете любого клиента (задача 706, блок 234).
    """
    router = APIRouter(tags=["task-engine"])

    def _identity_or_401(token: str) -> dict:
        try:
            identity = auth_fn(token)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(401, "Invalid token")
        if not identity:
            raise HTTPException(401, "Invalid token")
        return identity

    def _sources_or_empty(identity: dict) -> dict:
        return source_filter_fn(identity) or {}

    @router.get("/{token}/tasks", response_model=TasksListOut)
    def list_tasks(
        token: str,
        source: Optional[str] = Query(None),
        status: Optional[list[str]] = Query(None),
        project: Optional[str] = Query(None),
    ) -> TasksListOut:
        identity = _identity_or_401(token)
        sources = _sources_or_empty(identity)
        tasks = _query_tasks(sources, status_filter=status, project_filter=project, source_filter=source)
        sources_out = [
            SourceOut(id=sid, label=s["label"], badgeColor=s["badgeColor"], writable=s.get("writable", False))
            for sid, s in sources.items()
        ]
        # v1.1: fetch meetings from writable sources (kit-owned)
        meetings_out: list[MeetingOut] = []
        seen_meeting_ids: set = set()
        for src_id, src in sources.items():
            if not src.get("writable"):
                continue
            try:
                conn = _open_source(src["path"])
            except sqlite3.Error:
                continue
            try:
                # Check if meetings table exists
                has_meetings = conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='meetings'"
                ).fetchone()[0]
                if not has_meetings:
                    continue
                for m in conn.execute(
                    "SELECT id, title, date, notes, created_at FROM meetings ORDER BY date DESC"
                ).fetchall():
                    if m["id"] in seen_meeting_ids:
                        continue
                    seen_meeting_ids.add(m["id"])
                    meetings_out.append(MeetingOut(**dict(m)))
            finally:
                conn.close()
        participants = []
        if participants_fn:
            try:
                participants = participants_fn(identity) or []
            except Exception:
                # Участники — удобство, а не условие работы списка задач.
                participants = []
        return TasksListOut(
            sources=sources_out,
            tasks=[TaskOut(**t) for t in tasks],
            meetings=meetings_out,
            participants=participants,
        )

    @router.post("/{token}/meetings", status_code=201)
    def create_meeting(token: str, body: MeetingCreate) -> dict:
        """v1.4: create new meeting in first writable source's meetings table."""
        identity = _identity_or_401(token)
        sources = _sources_or_empty(identity)
        title = (body.title or "").strip()
        if not title:
            raise HTTPException(400, "title is required")
        # Find first writable source
        writable_src = None
        for sid, src in sources.items():
            if src.get("writable"):
                writable_src = src
                break
        if not writable_src:
            raise HTTPException(403, "No writable source available")
        # Встреча может оказаться первой записью портала — папки ещё нет,
        # и sqlite3.connect в неё не попадёт.
        _ensure_source_ready(writable_src["path"])
        conn = _open_source(writable_src["path"])
        try:
            # Ensure meetings table exists (defensive — for old v1.0 DBs)
            # Раньше здесь стоял одиночный CREATE TABLE meetings. Он остался
            # бы вторым местом, задающим схему, — и разъехался бы с общим на
            # первой же правке.
            ensure_task_schema(conn)
            cur = conn.execute(
                "INSERT INTO meetings (title, date, notes) VALUES (?, ?, ?)",
                (title, body.date, body.notes),
            )
            conn.commit()
            new_id = cur.lastrowid
            row = dict(conn.execute(
                "SELECT id, title, date, notes, created_at FROM meetings WHERE id = ?",
                (new_id,)
            ).fetchone())
            return {"ok": True, "meeting": MeetingOut(**row).model_dump()}
        finally:
            conn.close()

    @router.get("/{token}/task/{task_id}/comments", response_model=list[dict])
    def list_comments(token: str, task_id: int) -> list[dict]:
        """v1.1: list existing comments for a task."""
        identity = _identity_or_401(token)
        sources = _sources_or_empty(identity)
        for src in sources.values():
            conn = _open_source(src["path"])
            try:
                row = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if not row:
                    continue
                comments = conn.execute(
                    _comments_sql(conn) + " WHERE task_id = ? ORDER BY created_at ASC",
                    (task_id,),
                ).fetchall()
                return [dict(c) for c in comments]
            finally:
                conn.close()
        raise HTTPException(404, "Task not found")

    @router.patch("/{token}/task/{task_id}")
    def update_task(token: str, task_id: int, body: TaskUpdate) -> dict:
        identity = _identity_or_401(token)
        sources = _sources_or_empty(identity)
        for src_id, src in sources.items():
            if not src.get("writable"):
                continue
            conn = _open_source(src["path"])
            try:
                row = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if not row:
                    continue
                updates, params = [], []
                if body.status is not None:
                    updates.append("status = ?")
                    params.append(body.status)
                if body.deadline is not None or body.deadline == "":
                    updates.append("deadline = ?")
                    params.append(body.deadline or None)
                if body.text is not None:
                    updates.append("text = ?")
                    params.append(body.text)
                # Проверка на None, а НЕ hasattr как у meeting_id строкой ниже:
                # там поле уходит в UPDATE всегда, и для описания это означало бы
                # затирание в ноль при каждой правке статуса.
                if body.description is not None:
                    updates.append("description = ?")
                    params.append(body.description)
                if body.panel_key is not None:
                    updates.append("panel_key = ?")
                    params.append(body.panel_key)
                # v1.2: also accept assigned_to + meeting_id in PATCH
                if hasattr(body, "assigned_to") and body.assigned_to is not None:
                    updates.append("assigned_to = ?")
                    params.append(body.assigned_to)
                # Проверка на None, а не hasattr: атрибут у pydantic-модели есть
                # всегда, поэтому прежнее условие было истинным при каждом PATCH и
                # затирало привязку к встрече в ноль. Клиенту достаточно было
                # отметить задачу сделанной, чтобы она перестала относиться ко
                # встрече. Так у восьми задач кабинета Лапина поле опустело —
                # не «забыли заполнить», а стёрло экспортом описаний (задача 715,
                # decision-01). Ловушка описана строкой выше для описания ещё в
                # блоке 2331 задачи 706; здесь её просто не закрыли.
                # Цена симметрии: отвязать задачу от встречи, передав null, теперь
                # нельзя — понадобится, потребуется явный признак.
                if body.meeting_id is not None:
                    updates.append("meeting_id = ?")
                    params.append(body.meeting_id)
                if not updates:
                    raise HTTPException(400, "No fields to update")
                updates.append("updated_at = ?")
                params.append(datetime.now().isoformat(sep=" ", timespec="seconds"))
                params.append(task_id)
                conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
                conn.commit()
                updated = dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())
                updated["source_key"] = src_id
                updated["writable"] = True
                updated["comments_count"] = conn.execute(
                    "SELECT COUNT(*) FROM task_comments WHERE task_id = ?", (task_id,)
                ).fetchone()[0]
                return {"ok": True, "task": TaskOut(**updated).model_dump()}
            finally:
                conn.close()
        raise HTTPException(404, "Task not found or source read-only")

    @router.post("/{token}/task", status_code=201)
    def create_task(token: str, body: TaskCreate) -> dict:
        identity = _identity_or_401(token)
        sources = _sources_or_empty(identity)
        src = sources.get(body.source_key)
        if not src:
            raise HTTPException(400, f"Unknown source: {body.source_key}")
        if not src.get("writable"):
            raise HTTPException(403, "Source is read-only")
        if not body.text or not body.text.strip():
            raise HTTPException(400, "text is required")
        # Портал мог никогда не заводить задач — базы и папки ещё нет.
        _ensure_source_ready(src["path"])
        conn = _open_source(src["path"])
        try:
            # v1.2: check if v1.1 columns exist для graceful degrade
            col_names = {r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()}
            has_v11 = "assigned_to" in col_names and "meeting_id" in col_names
            has_descr = "description" in col_names
            if has_v11 and has_descr:
                cur = conn.execute(
                    "INSERT INTO tasks (source_key, project, text, status, deadline, contact_name, assigned_to, meeting_id, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (body.source_key, body.project, body.text.strip(), body.status, body.deadline,
                     body.contact_name or identity.get("contact_name"),
                     body.assigned_to, body.meeting_id, body.description),
                )
            elif has_v11:
                cur = conn.execute(
                    "INSERT INTO tasks (source_key, project, text, status, deadline, contact_name, assigned_to, meeting_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (body.source_key, body.project, body.text.strip(), body.status, body.deadline,
                     body.contact_name or identity.get("contact_name"),
                     body.assigned_to, body.meeting_id),
                )
            else:
                cur = conn.execute(
                    "INSERT INTO tasks (source_key, project, text, status, deadline, contact_name) VALUES (?, ?, ?, ?, ?, ?)",
                    (body.source_key, body.project, body.text.strip(), body.status, body.deadline,
                     body.contact_name or identity.get("contact_name")),
                )
            # Ключ панели пишется отдельным UPDATE, а не в три ветки INSERT выше:
            # ветки различаются набором колонок ради старых баз, и правка каждой
            # умножила бы шанс ошибки в ручке, которая пишет в шестнадцать боевых
            # порталов (задача 721, блок 102).
            if body.panel_key:
                conn.execute("UPDATE tasks SET panel_key = ? WHERE id = ?",
                             (body.panel_key, cur.lastrowid))
            conn.commit()
            new_id = cur.lastrowid
            row = dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (new_id,)).fetchone())
            row["source_key"] = body.source_key
            row["writable"] = True
            row["comments_count"] = 0
            if not has_v11:
                row.setdefault("assigned_to", None)
                row.setdefault("meeting_id", None)
            if not has_descr:
                row.setdefault("description", None)
            return {"ok": True, "task": TaskOut(**row).model_dump()}
        finally:
            conn.close()

    @router.post("/{token}/task/{task_id}/comment", status_code=201)
    def add_comment(token: str, task_id: int, body: CommentCreate) -> dict:
        identity = _identity_or_401(token)
        sources = _sources_or_empty(identity)
        text = (body.text or "").strip()
        if not text:
            raise HTTPException(400, "text is required")
        author = identity.get("contact_name") or identity.get("name") or "anonymous"
        for src in sources.values():
            # Колонка author_kind могла появиться позже самой базы: схема
            # обновляется при записи, а не при чтении.
            if src.get("writable"):
                _ensure_source_ready(src["path"])
            conn = _open_source(src["path"])
            try:
                row = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if not row:
                    continue
                cur = conn.execute(
                    "INSERT INTO task_comments (task_id, author, text, author_kind) VALUES (?, ?, ?, ?)",
                    (task_id, author, text, "agent" if body.author_kind == "agent" else "human"),
                )
                conn.commit()
                comment = dict(conn.execute(
                    _comments_sql(conn) + " WHERE id = ?",
                    (cur.lastrowid,)
                ).fetchone())
                return {"ok": True, "comment": CommentOut(**comment).model_dump()}
            finally:
                conn.close()
        raise HTTPException(404, "Task not found")

    @router.delete("/{token}/task/{task_id}")
    def delete_task(token: str, task_id: int) -> dict:
        identity = _identity_or_401(token)
        sources = _sources_or_empty(identity)
        for src in sources.values():
            if not src.get("writable"):
                continue
            conn = _open_source(src["path"])
            try:
                cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                conn.commit()
                if cur.rowcount > 0:
                    return {"ok": True}
            finally:
                conn.close()
        raise HTTPException(404, "Task not found or source read-only")

    return router
