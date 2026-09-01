-- Migration: add portal_type column to partners table
-- Task: vschk-lab--651 block 500
-- Date: 2026-07-31
--
-- Idempotent: uses defensive SELECT-before-ALTER pattern via bash caller.
-- Direct: adds portal_type NOT NULL DEFAULT 'partner' and sets Anton to 'school'.
--
-- Apply on VDS:
--   sqlite3 /srv/vschk-flow-ui/partners.db < portals-schema-2026-07-31.sql
--
-- Rollback:
--   Column drop не поддерживается в SQLite без table recreate.
--   Если нужен rollback — restore из backup partners.db.bak-{timestamp}.

-- Add column only if it doesn't exist (idempotent via CREATE-if-not-exists trigger fallback):
-- SQLite lacks IF NOT EXISTS for ADD COLUMN → bash caller runs conditional.
-- Below runs the ALTER unconditionally; caller wraps in try/echo.

ALTER TABLE partners ADD COLUMN portal_type TEXT NOT NULL DEFAULT 'partner';

-- Set Anton to school type (Alex remains 'partner' по default)
UPDATE partners SET portal_type = 'school' WHERE code = 'anton-avgeft';

-- Verify (не изменяет данных)
SELECT code, name, portal_type FROM partners ORDER BY portal_type, code;
