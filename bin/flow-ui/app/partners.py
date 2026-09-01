"""
partners.py — Partner registry for magic-link access to Flow WSCK online.

Storage: separate SQLite (partners.db) — same pattern as access.py.
Not in routing.db (which is read-only source of truth for tasks/artifacts).

Schema:
  partners(id, code, name, tg_handle, magic_token, folder_path, created_at, is_active)

Access flow:
  URL /partner/{token}/ → validate_token(token) → resolve folder → serve files.
"""

from __future__ import annotations

import secrets
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional


_SCHEMA = """
CREATE TABLE IF NOT EXISTS partners (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  code               TEXT NOT NULL UNIQUE,
  name               TEXT NOT NULL,
  tg_handle          TEXT,
  magic_token        TEXT NOT NULL UNIQUE,
  folder_path        TEXT NOT NULL,
  created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
  is_active          INTEGER NOT NULL DEFAULT 1,
  tenant_code        TEXT,       -- task 660 block 9050: personal_flow shares routing
  owner_employee_id  INTEGER     -- task 660 block 9050: OAuth owner for Drive export
);
CREATE INDEX IF NOT EXISTS idx_partners_token   ON partners(magic_token) WHERE is_active=1;
CREATE INDEX IF NOT EXISTS idx_partners_code    ON partners(code);

-- portal_materials M:N (task 666 W20 block 20009)
-- Populated when radar-os items_create/update pushes materials[] via sync_upsert.
-- Viewer 20008 checks material_id ∈ portal via list_portal_materials().
CREATE TABLE IF NOT EXISTS portal_participants (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  partner_id  INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  role        TEXT NOT NULL DEFAULT 'client',
  is_active   INTEGER NOT NULL DEFAULT 1,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(partner_id, name)
);

CREATE TABLE IF NOT EXISTS portal_materials (
  partner_id    INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
  material_id   INTEGER NOT NULL,
  name          TEXT,
  size          INTEGER,
  mime          TEXT,
  sort_order    INTEGER DEFAULT 0,
  chapter       TEXT,
  is_extra      INTEGER DEFAULT 0,
  has_page      INTEGER DEFAULT 0,
  is_cover      INTEGER DEFAULT 0,
  PRIMARY KEY (partner_id, material_id)
);
CREATE INDEX IF NOT EXISTS idx_pm_partner ON portal_materials(partner_id, sort_order);
"""


# Имя ведущего со стороны студии. Константа, а не настройка: строка одна и та же
# для всех порталов, а поля в конфиге нет — заводить его значит править yml на
# проде ради одного значения. Когда порталы начнут вести разные люди, имя придёт
# из partners.owner_employee_id — он сейчас пуст у всех шестнадцати порталов
# (задача 706, блок 234).
PORTAL_OWNER_NAME = "Виктор"


@contextmanager
def _connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        # Task 660 block 9050: idempotent ALTER для existing partners.db
        # SQLite не supports ADD COLUMN IF NOT EXISTS — используем try/except.
        for alter in (
            "ALTER TABLE partners ADD COLUMN tenant_code TEXT",
            "ALTER TABLE partners ADD COLUMN owner_employee_id INTEGER",
            # Task 695 block 40: раздел материала — папка в клиентском портале
            "ALTER TABLE portal_materials ADD COLUMN chapter TEXT",
            # Task 695 block 80: персональный доп поверх пакета — дроп конкретному
            # человеку, а не часть заготовки
            "ALTER TABLE portal_materials ADD COLUMN is_extra INTEGER DEFAULT 0",
            # Task 701 block 7: у материала есть собранная страница — вторая
            # проекция того же документа. Признак, а не отдельная строка
            # (decision-02). Заполняется из payload синхронизации портала.
            "ALTER TABLE portal_materials ADD COLUMN has_page INTEGER DEFAULT 0",
            # Task 706 block 200: обложка портала — материал, который витрина
            # рисует на старте, когда читатель ещё ничего не выбрал. Признак,
            # а не отдельная сущность: тот же путь выдачи и та же проверка токена.
            "ALTER TABLE portal_materials ADD COLUMN is_cover INTEGER DEFAULT 0",
        ):
            try:
                conn.execute(alter)
            except sqlite3.OperationalError:
                # Column already exists — safe re-run
                pass
        yield conn
        conn.commit()
    finally:
        conn.close()


def generate_token(nbytes: int = 32) -> str:
    """Generate URL-safe crypto token. secrets.token_urlsafe(32) = ~43 chars."""
    return secrets.token_urlsafe(nbytes)


def create_partner(
    db_path: Path,
    code: str,
    name: str,
    tg_handle: Optional[str] = None,
    folder_path: Optional[str] = None,
    magic_token: Optional[str] = None,
    portal_type: str = "partner",
    tenant_code: Optional[str] = None,
) -> dict:
    """Create a new partner. Returns dict with all fields including generated token.

    tenant_code names the Radar OS tenant that owns this portal's catalogue. It is
    what lets the showcase ask Radar OS for material content later (task 695 block 32);
    without it the showcase holds material ids it cannot resolve. NULL for file-based
    portals, whose materials sit on our own disk and need nobody to resolve them.
    """
    token = magic_token or generate_token()
    folder = folder_path or code
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO partners "
            "(code, name, tg_handle, magic_token, folder_path, portal_type, tenant_code) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (code, name, tg_handle, token, folder, portal_type, tenant_code),
        )
        row = conn.execute(
            "SELECT * FROM partners WHERE code = ?", (code,)
        ).fetchone()
    return dict(row)


def upsert_partner(
    db_path: Path,
    code: str,
    name: str,
    tg_handle: Optional[str] = None,
    portal_type: str = "partner",
    folder_path: Optional[str] = None,
    tenant_code: Optional[str] = None,
) -> tuple[dict, bool]:
    """Upsert partner by code. Returns (row_dict, is_new).

    If code exists — UPDATE metadata (name, tg_handle, portal_type),
    PRESERVE magic_token + folder_path + created_at + is_active.
    If code new — INSERT via create_partner with generated token.

    Idempotency guarantee: existing magic-link URLs never break on re-upsert.
    Used by POST /api/portal/upsert (task 666 Block 7001).
    """
    with _connect(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM partners WHERE code = ?", (code,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE partners SET name = ?, tg_handle = ?, portal_type = ?, "
                "tenant_code = COALESCE(?, tenant_code) "
                "WHERE code = ?",
                (name, tg_handle, portal_type, tenant_code, code),
            )
            row = conn.execute(
                "SELECT * FROM partners WHERE code = ?", (code,)
            ).fetchone()
            return dict(row), False

    row = create_partner(
        db_path=db_path,
        code=code,
        name=name,
        tg_handle=tg_handle,
        folder_path=folder_path,
        portal_type=portal_type,
        tenant_code=tenant_code,
    )
    with _connect(db_path) as conn:
        _ensure_participants(conn, int(row["id"]), name)
    return row, True


def _ensure_participants(conn: sqlite3.Connection, partner_id: int, client_name: str) -> None:
    """Завести участников портала, если их ещё нет. Идемпотентно.

    Двое: клиент — по имени из карточки портала, и ведущий со стороны студии.
    Раньше список исполнителей был захардкожен в двух местах кода именами
    первого клиента, и Артём видел в своём кабинете «Антона» — человека,
    которого не знает (задача 706, блок 234).

    Зовётся и при создании портала, и при чтении по токену: шестнадцать
    порталов созданы до этой правки, и заполнение только при создании их бы
    не догнало.
    """
    # В карточке портала имя иногда записано вместе с ником: «Антон Гефт
    # (@AVGeft)». В выпадающем списке исполнителей нужен человек, а не строка
    # карточки — хвост в скобках отрезаем.
    human = re.sub(r"\s*\(@[^)]*\)\s*$", "", (client_name or "").strip()) or client_name
    conn.executemany(
        "INSERT OR IGNORE INTO portal_participants (partner_id, name, role) VALUES (?, ?, ?)",
        [(partner_id, human, "client"), (partner_id, PORTAL_OWNER_NAME, "owner")],
    )


def list_participants(db_path: Path, partner_id: int) -> list[dict]:
    """Участники портала для выпадающего списка исполнителей."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name, role FROM portal_participants "
            "WHERE partner_id = ? AND is_active = 1 ORDER BY role ASC, id",
            (partner_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_partner_by_token(db_path: Path, token: str) -> Optional[dict]:
    """Validate magic-link token. Returns partner dict or None if invalid/inactive."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM partners WHERE magic_token = ? AND is_active = 1",
            (token,),
        ).fetchone()
        if row:
            _ensure_participants(conn, int(row["id"]), row["name"])
    return dict(row) if row else None


def list_partners(db_path: Path, include_inactive: bool = False) -> list[dict]:
    """List all partners. Admin use only — never expose via partner API."""
    with _connect(db_path) as conn:
        if include_inactive:
            rows = conn.execute("SELECT * FROM partners ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM partners WHERE is_active = 1 ORDER BY created_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def deactivate_partner(db_path: Path, code: str) -> None:
    """Soft-delete partner. Token becomes invalid immediately."""
    with _connect(db_path) as conn:
        conn.execute("UPDATE partners SET is_active = 0 WHERE code = ?", (code,))


def regenerate_token(db_path: Path, code: str) -> str:
    """Regenerate magic token for existing partner. Old token becomes invalid.

    ⚠️ Silent no-op if code not found. For guarded rotate use rotate_partner_token.
    """
    new_token = generate_token()
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE partners SET magic_token = ? WHERE code = ?", (new_token, code)
        )
    return new_token


def rotate_partner_token(db_path: Path, code: str) -> Optional[str]:
    """Rotate magic_token with existence check. Returns new token or None if code not found.

    Guarded variant of regenerate_token — enables 404 semantics in API handlers.
    Used by POST /api/portal/rotate (task 666 Block 7002).
    """
    with _connect(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM partners WHERE code = ?", (code,)
        ).fetchone()
        if not existing:
            return None
        new_token = generate_token()
        conn.execute(
            "UPDATE partners SET magic_token = ? WHERE code = ?", (new_token, code)
        )
    return new_token


# ═══════════════════════════════════════════════════════════════
# portal_materials helpers (task 666 W20 block 20009)
# ═══════════════════════════════════════════════════════════════

def set_portal_structure(
    db_path: Path,
    partner_id: int,
    materials_list: list[dict],
    folders_list: Optional[list[dict]] = None,
) -> int:
    """Replace portal_folders + portal_materials rows for partner_id atomically.

    Args:
        materials_list: list of dicts each with keys
          {material_id, name, size, mime, sort_order?, chapter?, is_extra?,
           has_page?, folder_id?}. sort_order defaults to list index.
          folder_id — папка портала, в которой лежит материал; None = в корне
          (task 695 block 72000). chapter — наследие модели, где папка
          выводилась из поля материала: читается, но структуру больше не задаёт.
        folders_list: папки портала [{folder_id, title, sort_order}]. None —
          не трогать папки вовсе (старый вызов, который о них не знает).
          Пустой список — у портала папок нет, и это тоже состояние.

    Returns count of INSERT'ed rows.

    Used by POST /api/portal/upsert (W20 block 20009 refactor) after
    upsert_partner() succeeds. Legacy material_paths[] branch bypasses this.
    """
    with _connect(db_path) as conn:
        # Папки и материалы переписываются в ОДНОЙ транзакции (блок 72000).
        # Разнести на два вызова — завести состояние «папки приехали, материалы
        # нет», в котором портал выглядит работающим, а материалы молча лежат в
        # корне. Такого состояния сейчас не существует, и заводить его нельзя.
        if folders_list is not None:
            conn.execute("DELETE FROM portal_folders WHERE partner_id = ?", (partner_id,))
            folder_rows = []
            for idx, f in enumerate(folders_list):
                fid = f.get("folder_id")
                if not isinstance(fid, int) or fid <= 0:
                    continue
                folder_rows.append((
                    partner_id,
                    fid,
                    str(f.get("title") or ""),
                    int(f.get("sort_order", idx)),
                ))
            if folder_rows:
                conn.executemany(
                    "INSERT INTO portal_folders (partner_id, folder_id, title, sort_order) "
                    "VALUES (?, ?, ?, ?)",
                    folder_rows,
                )

        conn.execute("DELETE FROM portal_materials WHERE partner_id = ?", (partner_id,))
        rows = []
        for idx, m in enumerate(materials_list):
            mid = m.get("material_id")
            if not isinstance(mid, int) or mid <= 0:
                continue
            rows.append((
                partner_id,
                mid,
                str(m.get("name") or ""),
                int(m.get("size") or 0),
                str(m.get("mime") or ""),
                int(m.get("sort_order", idx)),
                str(m.get("chapter") or ""),
                1 if m.get("is_extra") else 0,
                # Старый монолит поля не пришлёт — тогда 0, и клиент увидит
                # текст. Отсюда порядок выкатки: монолит раньше витрины.
                1 if m.get("has_page") else 0,
                # Старый монолит поля не пришлёт — тогда 0, и портал ведёт себя
                # как раньше. Отсюда порядок выкатки: монолит раньше витрины.
                1 if m.get("is_cover") else 0,
                # В какой папке лежит материал. Пусто — в корне, и это законное
                # место, а не поломка (блок 72000).
                m.get("folder_id") if isinstance(m.get("folder_id"), int) else None,
            ))
        if rows:
            conn.executemany(
                "INSERT INTO portal_materials "
                "(partner_id, material_id, name, size, mime, sort_order, chapter, is_extra, has_page, is_cover, folder_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
    return len(rows)


def set_portal_materials(
    db_path: Path,
    partner_id: int,
    materials_list: list[dict],
) -> int:
    """Состав материалов без папок — прежний вызов, оставлен для совместимости.

    Папки при этом не трогаются вовсе (не переписываются и не удаляются): вызов
    ничего не знает о структуре и не должен её сносить.
    """
    return set_portal_structure(db_path, partner_id, materials_list, folders_list=None)


def list_portal_folders(db_path: Path, partner_id: int) -> list[dict]:
    """Папки портала в порядке, заданном оператором.

    Пустая папка — обычное состояние: «Тренажёр» заводится заранее, как место,
    куда будет складываться (decision-16).
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT folder_id, title, sort_order FROM portal_folders "
            "WHERE partner_id = ? ORDER BY sort_order, folder_id",
            (partner_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_portal_materials(db_path: Path, partner_id: int) -> list[dict]:
    """List portal_materials rows for partner_id ordered by sort_order.

    Used by viewer /portal/{token}/material/{id}/open (Block 20008 followup)
    для validation что material_id ∈ portal set.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT material_id, name, size, mime, sort_order "
            "FROM portal_materials WHERE partner_id = ? ORDER BY sort_order",
            (partner_id,),
        ).fetchall()
    return [dict(r) for r in rows]
