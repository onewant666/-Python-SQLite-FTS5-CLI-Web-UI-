import re

from .database import get_connection

TITLE_WEIGHT = 10.0
CONTENT_WEIGHT = 3.0
TAGS_WEIGHT = 1.0

_CJK_RE = re.compile(r"[一-鿿]")


def _has_cjk(s: str) -> bool:
    return bool(_CJK_RE.search(s))


def build_fts_query(user_input: str) -> str:
    """Convert raw user input into a safe FTS5 query string."""
    if not user_input or not user_input.strip():
        return ""

    sanitized = re.sub(r'["\(\):\^+\-~\.]', "", user_input)
    tokens = sanitized.strip().split()

    escaped = []
    for token in tokens:
        if token.endswith("*"):
            escaped.append(f'"{token[:-1]}"*')
        else:
            escaped.append(f'"{token}"')

    return " ".join(escaped)


def _like_fallback(query: str, conn, page: int, per_page: int) -> tuple[list[dict], int]:
    """LIKE-based fallback for short CJK terms that trigram FTS5 may miss."""
    sanitized = re.sub(r'["\(\):\^+\-~\.]', "", query.strip())
    tokens = sanitized.split()

    if not tokens:
        return [], 0

    conditions = []
    params = []
    for token in tokens:
        like_pat = f"%{token}%"
        conditions.append("(title LIKE ? OR content LIKE ?)")
        params.extend([like_pat, like_pat])

    where = " AND ".join(conditions)

    count_sql = f"SELECT COUNT(*) FROM entries WHERE {where}"
    total = conn.execute(count_sql, params).fetchone()[0]

    search_sql = f"""
        SELECT id, title, content, tags, created_at, updated_at
        FROM entries
        WHERE {where}
        ORDER BY updated_at DESC
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(search_sql, params + [per_page, (page - 1) * per_page]).fetchall()

    results = []
    for row in rows:
        d = dict(row)
        d["tags"] = [t.strip() for t in d["tags"].split(",") if t.strip()]
        d["snippet"] = _generate_snippet(d["content"], tokens)
        d["rank"] = 999.0
        results.append(d)
    return results, total


def _generate_snippet(content: str, tokens: list[str], window: int = 60) -> str:
    """Generate a simple marked snippet for LIKE fallback results."""
    first_pos = len(content)
    first_token = tokens[0]
    idx = content.lower().find(first_token.lower())
    if idx == -1:
        for t in tokens[1:]:
            idx = content.lower().find(t.lower())
            if idx != -1:
                first_token = t
                break
    if idx == -1:
        idx = 0

    start = max(0, idx - window // 2)
    end = min(len(content), idx + len(first_token) + window // 2)
    snippet = content[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet += "..."

    for t in tokens:
        snippet = re.sub(
            f"({re.escape(t)})",
            r"<mark>\1</mark>",
            snippet,
            flags=re.IGNORECASE,
        )
    return snippet


def search_entries(
    query: str,
    db_path: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[dict], int]:
    fts_query = build_fts_query(query)
    if not fts_query:
        return [], 0

    conn = get_connection(db_path)
    try:
        count_sql = "SELECT COUNT(*) FROM entries_fts WHERE entries_fts MATCH ?"
        total = conn.execute(count_sql, (fts_query,)).fetchone()[0]

        search_sql = f"""
            SELECT
                e.id, e.title, e.content, e.tags, e.created_at, e.updated_at,
                snippet(entries_fts, 2, '<mark>', '</mark>', '...', 40) AS snippet,
                bm25(entries_fts, {TITLE_WEIGHT}, {CONTENT_WEIGHT}, {TAGS_WEIGHT}) AS rank
            FROM entries_fts
            JOIN entries e ON e.id = entries_fts.rowid
            WHERE entries_fts MATCH ?
            ORDER BY rank
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(
            search_sql,
            (fts_query, per_page, (page - 1) * per_page),
        ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            d["tags"] = [t.strip() for t in d["tags"].split(",") if t.strip()]
            results.append(d)

        # Fallback: if FTS5 returned nothing, try LIKE search for CJK queries
        if total == 0 and _has_cjk(query):
            results, total = _like_fallback(query, conn, page, per_page)

        return results, total
    except Exception:
        return [], 0
    finally:
        conn.close()


def search_suggestions(
    prefix: str, db_path: str | None = None, limit: int = 5
) -> list[str]:
    """Autocomplete titles by prefix."""
    if not prefix or not prefix.strip():
        return []

    safe = re.sub(r'["\(\):\^+\-~\.]', "", prefix.strip())
    fts_query = f'"{safe}"*'

    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT e.title FROM entries_fts "
            "JOIN entries e ON e.id = entries_fts.rowid "
            "WHERE entries_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (fts_query, limit),
        ).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []
    finally:
        conn.close()
