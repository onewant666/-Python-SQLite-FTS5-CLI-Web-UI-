from __future__ import annotations

from .database import get_connection


def create_entry(
    title: str,
    content: str = "",
    tags: list[str] | None = None,
    db_path: str | None = None,
) -> int:
    tags_str = ",".join(t.strip() for t in (tags or []) if t.strip())
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO entries (title, content, tags) VALUES (?, ?, ?)",
            (title.strip(), content, tags_str),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_entry(entry_id: int, db_path: str | None = None) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)
    finally:
        conn.close()


def get_all_entries(
    db_path: str | None = None, page: int = 1, per_page: int = 20
) -> tuple[list[dict], int]:
    conn = get_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM entries ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (per_page, (page - 1) * per_page),
        ).fetchall()
        return [_row_to_dict(r) for r in rows], total
    finally:
        conn.close()


def update_entry(
    entry_id: int,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
    db_path: str | None = None,
) -> bool:
    conn = get_connection(db_path)
    try:
        existing = conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if existing is None:
            return False

        new_title = title.strip() if title is not None else existing["title"]
        new_content = content if content is not None else existing["content"]
        if tags is not None:
            new_tags = ",".join(t.strip() for t in tags if t.strip())
        else:
            new_tags = existing["tags"]

        conn.execute(
            "UPDATE entries SET title=?, content=?, tags=?, updated_at=datetime('now','localtime') WHERE id=?",
            (new_title, new_content, new_tags, entry_id),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def delete_entry(entry_id: int, db_path: str | None = None) -> bool:
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_all_tags(db_path: str | None = None) -> list[tuple[str, int]]:
    """Return (tag_name, entry_count) sorted by count descending."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT tags FROM entries WHERE tags != ''").fetchall()
        counts: dict[str, int] = {}
        for row in rows:
            for tag in row["tags"].split(","):
                tag = tag.strip()
                if tag:
                    counts[tag] = counts.get(tag, 0) + 1
        return sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    finally:
        conn.close()


def get_entries_by_tag(
    tag: str, db_path: str | None = None, page: int = 1, per_page: int = 20
) -> tuple[list[dict], int]:
    conn = get_connection(db_path)
    try:
        pattern = f"%,{tag},%"
        total = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE ',' || tags || ',' LIKE ?",
            (pattern,),
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM entries WHERE ',' || tags || ',' LIKE ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (pattern, per_page, (page - 1) * per_page),
        ).fetchall()
        return [_row_to_dict(r) for r in rows], total
    finally:
        conn.close()


def get_recent_entries(
    db_path: str | None = None, limit: int = 10
) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM entries ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_entry_count(db_path: str | None = None) -> int:
    conn = get_connection(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    finally:
        conn.close()


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["tags"] = [t.strip() for t in d["tags"].split(",") if t.strip()]
    return d
