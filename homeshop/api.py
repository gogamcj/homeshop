"""검색 API와 웹 화면."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse

from . import db

STATIC = Path(__file__).parent / "static"


def create_app(db_path: str | None = None) -> FastAPI:
    conn = db.connect(db_path)
    db.init_db(conn)
    app = FastAPI(title="홈쇼핑 편성 검색", version="0.1.0")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/channels")
    def channels(date_from: str = "", date_to: str = ""):
        return db.channel_stats(conn, date_from, date_to)

    @app.get("/api/categories")
    def categories():
        return db.list_categories(conn)

    @app.get("/api/broadcasts")
    def broadcasts(
        q: str = "",
        channel: str = "",
        category: str = "",
        date_from: str = Query("", pattern=r"^(\d{4}-\d{2}-\d{2})?$"),
        date_to: str = Query("", pattern=r"^(\d{4}-\d{2}-\d{2})?$"),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        total, items = db.search_broadcasts(
            conn, q, channel, category, date_from, date_to, limit, offset
        )
        return {"total": total, "items": items}

    return app
