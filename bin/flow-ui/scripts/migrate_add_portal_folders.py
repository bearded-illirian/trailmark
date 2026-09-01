"""
migrate_add_portal_folders.py — папки портала в partners.db (задача 695 блок 72000).

Идемпотентна: CREATE TABLE IF NOT EXISTS + PRAGMA table_info перед ALTER.
Безопасна к повторному запуску.

Зачем (decision-16): до этого блока папок как сущности не было — витрина
выводила их из строкового поля chapter у материалов. Пустая папка при такой
модели невозможна в принципе: папка приезжала только прицепом к материалу.
А пустая папка — требование, а не крайний случай: место, куда будет
складываться, клиент должен видеть заранее.

Что делает:
  1. portal_folders — папки портала (номер из Radar OS, имя, порядок)
  2. portal_materials.folder_id — в какой папке лежит материал; NULL = в корне

folder_id хранится тем же числом, что и в Radar OS: витрина номеров не
выдумывает, она показывает то, что прислали.

Запуск:
    python3 scripts/migrate_add_portal_folders.py [db_path]
    PARTNERS_DB_PATH=/srv/vschk-flow-ui/data/partners.db python3 scripts/migrate_add_portal_folders.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = "/srv/vschk-flow-ui/data/partners.db"


def migrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portal_folders (
              partner_id  INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
              folder_id   INTEGER NOT NULL,
              title       TEXT    NOT NULL,
              sort_order  INTEGER DEFAULT 0,
              PRIMARY KEY (partner_id, folder_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pf_partner ON portal_folders(partner_id, sort_order)"
        )

        cols = [r[1] for r in conn.execute("PRAGMA table_info(portal_materials)")]
        if "folder_id" not in cols:
            conn.execute("ALTER TABLE portal_materials ADD COLUMN folder_id INTEGER")
            print("  portal_materials.folder_id — добавлена")
        else:
            print("  portal_materials.folder_id — уже есть")

        conn.commit()
        print(f"✅ Миграция применена: {db_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.getenv("PARTNERS_DB_PATH", DEFAULT_DB)
    if not Path(path).exists():
        sys.exit(f"База не найдена: {path}")
    migrate(path)
