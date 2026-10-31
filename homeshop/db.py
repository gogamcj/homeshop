"""SQLite 저장소. 규모가 커지면 PostgreSQL로 옮길 수 있도록 표준 SQL만 쓴다."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from .channels import CHANNELS
from .models import Broadcast

DEFAULT_PATH = os.environ.get("HOMESHOP_DB", str(Path("data") / "homeshop.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    code      TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    kind      TEXT NOT NULL,
    homepage  TEXT
);

CREATE TABLE IF NOT EXISTS broadcasts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_code  TEXT NOT NULL REFERENCES channels(code),
    start_at      TEXT NOT NULL,
    end_at        TEXT,
    title         TEXT NOT NULL,
    product_name  TEXT NOT NULL DEFAULT '',
    brand         TEXT NOT NULL DEFAULT '',
    category      TEXT NOT NULL DEFAULT '',
    price         INTEGER,
    product_url   TEXT NOT NULL DEFAULT '',
    external_id   TEXT NOT NULL DEFAULT '',
    extra         TEXT NOT NULL DEFAULT '{}',
    collected_at  TEXT NOT NULL,
    UNIQUE (channel_code, start_at, external_id, product_name)
);

CREATE INDEX IF NOT EXISTS idx_bc_start ON broadcasts(start_at);
CREATE INDEX IF NOT EXISTS idx_bc_channel_start ON broadcasts(channel_code, start_at);
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    path = path or DEFAULT_PATH
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO channels(code, name, kind, homepage) VALUES (?,?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET name=excluded.name, kind=excluded.kind, homepage=excluded.homepage",
        [(c.code, c.name, c.kind, c.homepage) for c in CHANNELS],
    )
    conn.commit()


def upsert_broadcasts(conn: sqlite3.Connection, items: list[Broadcast]) -> int:
    """방송을 저장한다. 같은 방송이 다시 수집되면 최신 값으로 갱신한다. 저장 건수를 돌려준다."""
    now = datetime.now().isoformat(timespec="seconds")
    rows = [
        (
            b.channel_code,
            b.start_at.isoformat(timespec="minutes"),
            b.end_at.isoformat(timespec="minutes") if b.end_at else None,
            b.title,
            b.product_name,
            b.brand,
            b.category,
            b.price,
            b.product_url,
            b.external_id,
            json.dumps(b.extra, ensure_ascii=False),
            now,
        )
        for b in items
    ]
    conn.executemany(
        """
        INSERT INTO broadcasts(channel_code, start_at, end_at, title, product_name, brand,
                               category, price, product_url, external_id, extra, collected_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(channel_code, start_at, external_id, product_name) DO UPDATE SET
            end_at=excluded.end_at, title=excluded.title, brand=excluded.brand,
            category=excluded.category, price=excluded.price, product_url=excluded.product_url,
            extra=excluded.extra, collected_at=excluded.collected_at
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def search_broadcasts(
    conn: sqlite3.Connection,
    q: str = "",
    channel: str = "",
    category: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[dict]]:
    """조건에 맞는 방송을 (전체 건수, 목록)으로 돌려준다. 날짜는 YYYY-MM-DD, date_to 포함."""
    where, args = [], []
    if q:
        where.append("(b.title LIKE ? OR b.product_name LIKE ? OR b.brand LIKE ?)")
        like = f"%{q}%"
        args += [like, like, like]
    if channel:
        where.append("b.channel_code = ?")
        args.append(channel)
    if category:
        where.append("b.category = ?")
        args.append(category)
    if date_from:
        where.append("b.start_at >= ?")
        args.append(date_from)
    if date_to:
        where.append("b.start_at < date(?, '+1 day')")
        args.append(date_to)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    total = conn.execute(f"SELECT COUNT(*) FROM broadcasts b {clause}", args).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT b.*, c.name AS channel_name, c.kind AS channel_kind
        FROM broadcasts b JOIN channels c ON c.code = b.channel_code
        {clause}
        ORDER BY b.start_at DESC, b.channel_code
        LIMIT ? OFFSET ?
        """,
        args + [limit, offset],
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["extra"] = json.loads(d["extra"] or "{}")
        out.append(d)
    return total, out


def list_categories(conn: sqlite3.Connection) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT category FROM broadcasts WHERE category <> '' ORDER BY category"
        )
    ]


def channel_stats(conn: sqlite3.Connection, date_from: str = "", date_to: str = "") -> list[dict]:
    """채널별 방송 수와 평균 판매가."""
    where, args = [], []
    if date_from:
        where.append("b.start_at >= ?")
        args.append(date_from)
    if date_to:
        where.append("b.start_at < date(?, '+1 day')")
        args.append(date_to)
    clause = ("AND " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"""
        SELECT c.code, c.name, c.kind,
               COUNT(b.id) AS broadcasts,
               CAST(AVG(b.price) AS INTEGER) AS avg_price
        FROM channels c LEFT JOIN broadcasts b ON b.channel_code = c.code {clause}
        GROUP BY c.code ORDER BY broadcasts DESC, c.name
        """,
        args,
    ).fetchall()
    return [dict(r) for r in rows]
