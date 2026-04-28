"""
create_empty_db.py
------------------
Generates a brand-new empty_pr_data.db with the full schema and zero rows.

Usage (run from the project root):
    python scripts/create_empty_db.py

The output file is placed in flask_app/data/empty_pr_data.db.
To use it: rename it to pr_data.db and drop it in flask_app/data/.
"""

import sqlite3
import os
import sys

# Allow importing from flask_app when run from project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEST = os.path.join(PROJECT_ROOT, "flask_app", "data", "empty_pr_data.db")

os.makedirs(os.path.dirname(DEST), exist_ok=True)

if os.path.exists(DEST):
    os.remove(DEST)

conn = sqlite3.connect(DEST)
c = conn.cursor()
c.execute("PRAGMA foreign_keys = ON;")

c.executescript("""
CREATE TABLE IF NOT EXISTS pr (
    id           TEXT PRIMARY KEY,
    number       TEXT NOT NULL,
    title        TEXT NOT NULL,
    category     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'en-cours',
    created_date TEXT NOT NULL,
    date_prev    TEXT NOT NULL DEFAULT '',
    date_reelle  TEXT NOT NULL DEFAULT '',
    note         TEXT NOT NULL DEFAULT '',
    custom_steps TEXT NOT NULL DEFAULT '',
    base_category TEXT NOT NULL DEFAULT ''
);

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

CREATE TABLE IF NOT EXISTS document (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'En attente',
    color        TEXT NOT NULL DEFAULT '#D4798A',
    done         INTEGER NOT NULL DEFAULT 0,
    created_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pr_document (
    id     TEXT PRIMARY KEY,
    pr_id  TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    name   TEXT NOT NULL,
    done   INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (pr_id) REFERENCES pr(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pr_doc_checklist (
    id         TEXT PRIMARY KEY,
    pr_id      TEXT NOT NULL,
    name       TEXT NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (pr_id) REFERENCES pr(id) ON DELETE CASCADE
);
""")

conn.commit()
conn.close()

print(f"Done!  Empty DB created at: {DEST}")
print("Rename it to pr_data.db and place it in flask_app/data/ — your colleague is ready to go.")
