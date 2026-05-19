import os
import sqlite3
from pathlib import Path


def get_db_path() -> Path:
    """Resolve the database file path."""
    if env_path := os.environ.get("KB_DATABASE"):
        return Path(env_path)
    if xdg := os.environ.get("XDG_DATA_HOME"):
        base = Path(xdg)
    else:
        base = Path.home() / ".local" / "share"
    path = base / "kb" / "kb.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _data_db_path() -> Path:
    """Fallback path inside the project data/ directory."""
    pkg_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = pkg_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "kb.db"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Return a connection with WAL mode and foreign keys enabled."""
    path = db_path or str(get_db_path())
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    content     TEXT    NOT NULL DEFAULT '',
    tags        TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_entries_created_at ON entries(created_at DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    title,
    content,
    tags,
    content='entries',
    content_rowid='id',
    tokenize='trigram'
);

CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, title, content, tags)
    VALUES (new.id, new.title, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, title, content, tags)
    VALUES ('delete', old.id, old.title, old.content, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, title, content, tags)
    VALUES ('delete', old.id, old.title, old.content, old.tags);
    INSERT INTO entries_fts(rowid, title, content, tags)
    VALUES (new.id, new.title, new.content, new.tags);
END;
"""


def init_db(db_path: str | None = None) -> None:
    """Idempotent schema initialization. Safe to call repeatedly."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
