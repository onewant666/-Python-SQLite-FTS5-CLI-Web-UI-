from flask import Flask, render_template, request, redirect, url_for, jsonify
from .database import init_db
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
from .search import search_entries, search_suggestions


def create_app(db_path: str) -> Flask:
    app = Flask(__name__)
    app.config["KB_DATABASE"] = db_path
    app.config["KB_PER_PAGE"] = 20

    init_db(db_path)

    @app.route("/")
    def index():
        recent = get_recent_entries(db_path, limit=10)
        tags = get_all_tags(db_path)[:20]
        max_count = max((c for _, c in tags), default=1)

        def font_size(count: int) -> str:
            if max_count <= 1:
                return "1rem"
            ratio = count / max_count
            return f"{0.8 + ratio * 1.2:.2f}rem"

        tag_data = [{"name": n, "count": c, "size": font_size(c)} for n, c in tags]
        return render_template("index.html", entries=recent, tags=tag_data)

    @app.route("/search")
    def search():
        q = request.args.get("q", "").strip()
        page = request.args.get("page", 1, type=int)
        per_page = app.config["KB_PER_PAGE"]

        if not q:
            return redirect(url_for("index"))

        results, total = search_entries(q, db_path, page=page, per_page=per_page)
        total_pages = max(1, (total + per_page - 1) // per_page)

        return render_template(
            "search.html",
            query=q,
            results=results,
            total=total,
            page=page,
            total_pages=total_pages,
        )

    @app.route("/entry/<int:entry_id>")
    def entry(entry_id):
        entry_data = get_entry(entry_id, db_path)
        if entry_data is None:
            return "Not Found", 404
        return render_template("entry.html", entry=entry_data)

    @app.route("/new", methods=["GET", "POST"])
    def new():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            if not title:
                return render_template("edit.html", error="Title is required.")
            content = request.form.get("content", "")
            tags_str = request.form.get("tags", "")
            tag_list = [t.strip() for t in tags_str.split(",") if t.strip()]
            entry_id = create_entry(title, content, tag_list, db_path)
            return redirect(url_for("entry", entry_id=entry_id))
        return render_template("edit.html")

    @app.route("/edit/<int:entry_id>", methods=["GET", "POST"])
    def edit(entry_id):
        entry_data = get_entry(entry_id, db_path)
        if entry_data is None:
            return "Not Found", 404

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            if not title:
                return render_template(
                    "edit.html", entry=entry_data, error="Title is required."
                )
            content = request.form.get("content", "")
            tags_str = request.form.get("tags", "")
            tag_list = [t.strip() for t in tags_str.split(",") if t.strip()]
            update_entry(entry_id, title, content, tag_list, db_path)
            return redirect(url_for("entry", entry_id=entry_id))

        return render_template("edit.html", entry=entry_data)

    @app.route("/delete/<int:entry_id>", methods=["POST"])
    def delete(entry_id):
        delete_entry(entry_id, db_path)
        return redirect(url_for("index"))

    @app.route("/tags")
    def tags_page():
        tag_list = get_all_tags(db_path)
        max_count = max((c for _, c in tag_list), default=1)

        def font_size(count: int) -> str:
            if max_count <= 1:
                return "1rem"
            ratio = count / max_count
            return f"{0.8 + ratio * 1.2:.2f}rem"

        tags_data = [
            {"name": n, "count": c, "size": font_size(c)} for n, c in tag_list
        ]
        return render_template("tags.html", tags=tags_data)

    @app.route("/tag/<tag>")
    def tag_view(tag):
        page = request.args.get("page", 1, type=int)
        per_page = app.config["KB_PER_PAGE"]
        entries, total = get_entries_by_tag(tag, db_path, page=page, per_page=per_page)
        total_pages = max(1, (total + per_page - 1) // per_page)
        return render_template(
            "search.html",
            query=f"tag:{tag}",
            results=entries,
            total=total,
            page=page,
            total_pages=total_pages,
            tag=tag,
        )

    @app.route("/api/search")
    def api_search():
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify([])
        suggestions = search_suggestions(q, db_path, limit=5)
        return jsonify(suggestions)

    return app
