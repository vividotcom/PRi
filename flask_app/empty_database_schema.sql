-- =============================================================================
--  PR Checklist App — Empty Database Schema
--  Use this file to initialize a fresh, empty database.
--
--  Instructions:
--    1. Copy this file to the flask_app/data/ folder on the new machine.
--    2. Run:  sqlite3 pr_data.db < empty_database_schema.sql
--    3. Start the Flask app normally — it will use this empty database.
-- =============================================================================

PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- PR table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pr (
    id            TEXT PRIMARY KEY,
    number        TEXT NOT NULL,
    title         TEXT NOT NULL,
    category      TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'en-cours',
    created_date  TEXT NOT NULL,
    custom_steps  TEXT DEFAULT '',
    base_category TEXT DEFAULT ''
);

-- -----------------------------------------------------------------------------
-- Task (checklist steps) table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS task (
    pr_id       TEXT NOT NULL,
    task_id     TEXT NOT NULL,
    title       TEXT,
    description TEXT,
    done        INTEGER NOT NULL DEFAULT 0,
    date_prev   TEXT DEFAULT '',
    date_reelle TEXT DEFAULT '',
    note        TEXT DEFAULT '',
    PRIMARY KEY (pr_id, task_id),
    FOREIGN KEY (pr_id) REFERENCES pr(id) ON DELETE CASCADE
);

-- -----------------------------------------------------------------------------
-- Global document tracker table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'En attente',
    color        TEXT NOT NULL DEFAULT '#D4798A',
    done         INTEGER NOT NULL DEFAULT 0,
    created_date TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- PR-specific document links (legacy, kept for compatibility)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pr_document (
    id    TEXT PRIMARY KEY,
    pr_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    name  TEXT NOT NULL,
    done  INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (pr_id) REFERENCES pr(id) ON DELETE CASCADE
);

-- -----------------------------------------------------------------------------
-- Per-PR document checklist (Documents de la PR)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pr_doc_checklist (
    id         TEXT PRIMARY KEY,
    pr_id      TEXT NOT NULL,
    name       TEXT NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (pr_id) REFERENCES pr(id) ON DELETE CASCADE
);
