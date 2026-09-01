-- task-engine kit — schema v1.1.0
--
-- Idempotent: safe to run on existing tasks.sqlite (CREATE TABLE IF NOT EXISTS).
-- Consumer applies this schema against a kit-owned SQLite file
-- (e.g. portals/school/anton-avgeft/tasks.sqlite).
--
-- v1.1 changes vs v1.0:
--   + meetings table (id, title, date, notes, created_at)
--   + tasks.meeting_id INTEGER NULL FK → meetings.id
--   + tasks.assigned_to TEXT NULL — кто ответственный
--
-- For existing v1.0 DBs, use migrations/v1.1-add-meetings.sql (ALTER TABLE flavor).

CREATE TABLE IF NOT EXISTS meetings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    date        TEXT,                                     -- ISO date, nullable
    notes       TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_meetings_date ON meetings(date);

CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key    TEXT    NOT NULL DEFAULT 'personal',
    project       TEXT,
    text          TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'todo',
    deadline      TEXT,
    contact_name  TEXT,                                    -- legacy, kept for BC
    assigned_to   TEXT,                                    -- v1.1: кто ответственный
    meeting_id    INTEGER REFERENCES meetings(id) ON DELETE SET NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_status      ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_source      ON tasks(source_key);
CREATE INDEX IF NOT EXISTS idx_tasks_project     ON tasks(project);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline    ON tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned    ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tasks_meeting     ON tasks(meeting_id);

CREATE TABLE IF NOT EXISTS task_comments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    author      TEXT    NOT NULL,
    text        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_task_comments_task_id ON task_comments(task_id);
