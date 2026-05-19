from __future__ import annotations

import os
import shutil
import webbrowser

import click

from .database import init_db, get_db_path, _data_db_path
from .models import (
    create_entry,
    get_entry,
    get_all_entries,
    update_entry,
    delete_entry,
    get_all_tags,
    get_entries_by_tag,
    get_recent_entries,
    get_entry_count,
)
from .search import search_entries


@click.group()
@click.version_option(package_name="kb")
def main():
    """KB — Local Knowledge Base with full-text search."""


def _ensure_db():
    """Resolve db path and ensure schema is initialized."""
    try:
        db_path = str(get_db_path())
    except Exception:
        db_path = str(_data_db_path())
    init_db(db_path)
    return db_path


# ── init ────────────────────────────────────────────────────────


@main.command()
@click.option("--db-path", default=None, help="Database file path")
def init(db_path):
    """Initialize the database (creates tables)."""
    if db_path:
        os.environ["KB_DATABASE"] = db_path
    path = _ensure_db()
    click.echo(f"Database initialized at {path}")


# ── add ─────────────────────────────────────────────────────────


@main.command()
@click.option("-t", "--title", required=True, help="Entry title")
@click.option("-c", "--content", default="", help="Entry content")
@click.option("--tags", default="", help="Comma-separated tags")
@click.option("-e", "--editor", is_flag=True, help="Open $EDITOR for content")
def add(title, content, tags, editor):
    """Add a new entry."""
    db_path = _ensure_db()

    if editor:
        edited = click.edit(content)
        if edited is None:
            click.echo("Aborted.")
            return
        content = edited

    if not content and not editor:
        content = click.prompt("Content", default="")

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    entry_id = create_entry(title=title, content=content, tags=tag_list, db_path=db_path)
    click.echo(f"Created entry #{entry_id}: {title}")


# ── search ──────────────────────────────────────────────────────


@main.command()
@click.argument("query")
@click.option("-n", "--limit", default=20, help="Results per page")
@click.option("-p", "--page", default=1, help="Page number")
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
def search(query, limit, page, json_out):
    """Full-text search."""
    db_path = _ensure_db()
    results, total = search_entries(query, db_path, page=page, per_page=limit)

    if json_out:
        import json

        click.echo(json.dumps(results, ensure_ascii=False, indent=2))
        return

    if not results:
        click.echo(f"No results for '{query}'.")
        return

    term_width = shutil.get_terminal_size().columns
    title_w = min(30, term_width // 3)

    click.echo(f"Found {total} result(s) for '{query}' (page {page}):\n")
    for entry in results:
        click.echo(
            click.style(f"#{entry['id']} ", fg="yellow")
            + click.style(f"{entry['title']:<{title_w}}", fg="cyan", bold=True)[:title_w]
        )
        snippet = entry.get("snippet", "")
        if snippet:
            click.echo(f"  {snippet}")
        if entry["tags"]:
            click.echo(f"  Tags: {', '.join(entry['tags'])}")
        click.echo(
            f"  {entry['updated_at']}"
        )
        click.echo()


# ── list ────────────────────────────────────────────────────────


@main.command("list")
@click.option("-n", "--limit", default=20, help="Entries per page")
@click.option("-p", "--page", default=1, help="Page number")
@click.option("--tag", default=None, help="Filter by tag")
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
def list_cmd(limit, page, tag, json_out):
    """List entries (newest first)."""
    db_path = _ensure_db()

    if tag:
        entries, total = get_entries_by_tag(tag, db_path, page=page, per_page=limit)
    else:
        entries, total = get_all_entries(db_path, page=page, per_page=limit)

    if json_out:
        import json

        click.echo(json.dumps(entries, ensure_ascii=False, indent=2))
        return

    if not entries:
        click.echo("No entries found." if not tag else f"No entries tagged '{tag}'.")
        return

    total_pages = max(1, (total + limit - 1) // limit)
    click.echo(f"Entries (page {page}/{total_pages}, {total} total):\n")

    for entry in entries:
        tags_str = f" [{', '.join(entry['tags'])}]" if entry["tags"] else ""
        click.echo(
            click.style(f"#{entry['id']:>4}", fg="yellow")
            + "  "
            + click.style(entry["title"], fg="cyan", bold=True)
            + click.style(tags_str, fg="magenta")
        )
        click.echo(f"       {entry['updated_at']}")
        click.echo()


# ── show ────────────────────────────────────────────────────────


@main.command()
@click.argument("entry_id", type=int)
def show(entry_id):
    """Display a single entry."""
    db_path = _ensure_db()
    entry = get_entry(entry_id, db_path)

    if entry is None:
        click.echo(f"Entry #{entry_id} not found.", err=True)
        raise SystemExit(1)

    click.echo(click.style(entry["title"], fg="cyan", bold=True))
    click.echo()
    if entry["tags"]:
        click.echo(click.style("Tags: ", fg="magenta") + ", ".join(entry["tags"]))
    click.echo(f"Created: {entry['created_at']}  |  Updated: {entry['updated_at']}")
    click.echo()
    click.echo(entry["content"])


# ── edit ────────────────────────────────────────────────────────


@main.command()
@click.argument("entry_id", type=int)
@click.option("-t", "--title", default=None, help="New title")
@click.option("-c", "--content", default=None, help="New content")
@click.option("--tags", default=None, help="New comma-separated tags")
@click.option("-e", "--editor", is_flag=True, help="Open $EDITOR to edit content")
def edit(entry_id, title, content, tags, editor):
    """Edit an entry."""
    db_path = _ensure_db()
    entry = get_entry(entry_id, db_path)

    if entry is None:
        click.echo(f"Entry #{entry_id} not found.", err=True)
        raise SystemExit(1)

    if editor:
        edited = click.edit(entry["content"])
        if edited is None:
            click.echo("Aborted.")
            return
        content = edited

    tag_list = (
        [t.strip() for t in tags.split(",") if t.strip()] if tags is not None else None
    )
    ok = update_entry(entry_id, title=title, content=content, tags=tag_list, db_path=db_path)
    if ok:
        click.echo(f"Updated entry #{entry_id}.")
    else:
        click.echo(f"Entry #{entry_id} not found.", err=True)


# ── delete ──────────────────────────────────────────────────────


@main.command()
@click.argument("entry_id", type=int)
@click.option("--force", is_flag=True, help="Skip confirmation")
def delete(entry_id, force):
    """Delete an entry."""
    db_path = _ensure_db()
    entry = get_entry(entry_id, db_path)

    if entry is None:
        click.echo(f"Entry #{entry_id} not found.", err=True)
        raise SystemExit(1)

    if not force:
        confirmed = click.confirm(
            f"Delete entry #{entry_id} '{entry['title']}'?"
        )
        if not confirmed:
            click.echo("Aborted.")
            return

    delete_entry(entry_id, db_path)
    click.echo(f"Deleted entry #{entry_id}.")


# ── tags ────────────────────────────────────────────────────────


@main.command()
def tags():
    """List all tags."""
    db_path = _ensure_db()
    tag_list = get_all_tags(db_path)

    if not tag_list:
        click.echo("No tags.")
        return

    for tag_name, count in tag_list:
        click.echo(
            click.style(f"{count:>4}", fg="yellow")
            + f"  {tag_name}"
        )


# ── web ─────────────────────────────────────────────────────────


@main.command()
@click.option("--host", default="127.0.0.1", help="Bind address")
@click.option("--port", default=5000, type=int, help="Port")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option("--no-open", is_flag=True, help="Don't open browser")
def web(host, port, debug, no_open):
    """Start the web interface."""
    from .app import create_app

    db_path = _ensure_db()
    app = create_app(db_path)

    if not no_open:
        webbrowser.open(f"http://{host}:{port}")

    click.echo(f"Starting KB web server at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


# ── info ────────────────────────────────────────────────────────


@main.command()
def info():
    """Show database info."""
    db_path = _ensure_db()
    count = get_entry_count(db_path)
    file_size = os.path.getsize(db_path)
    tag_list = get_all_tags(db_path)

    click.echo(f"Database path: {db_path}")
    click.echo(f"File size:     {file_size / 1024:.1f} KB")
    click.echo(f"Entries:       {count}")
    click.echo(f"Tags:          {len(tag_list)}")
