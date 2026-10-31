"""명령줄 도구.

  python -m homeshop init-db
  python -m homeshop import-csv 편성표.csv
  python -m homeshop collect --date 2026-10-31 [--channel gs --channel cj]
  python -m homeshop serve --port 8000
"""
from __future__ import annotations

import argparse
import logging
from datetime import date

from . import adapters, collector, db, importer


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="homeshop")
    p.add_argument("--db", default=None, help="SQLite 파일 경로 (기본: data/homeshop.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db")

    imp = sub.add_parser("import-csv")
    imp.add_argument("path")

    col = sub.add_parser("collect")
    col.add_argument("--date", default=date.today().isoformat())
    col.add_argument("--channel", action="append", help="채널 코드 (여러 번 지정 가능)")

    srv = sub.add_parser("serve")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.cmd == "serve":
        import uvicorn

        from .api import create_app

        uvicorn.run(create_app(args.db), host=args.host, port=args.port)
        return 0

    conn = db.connect(args.db)
    db.init_db(conn)

    if args.cmd == "init-db":
        print("DB 준비 완료")
    elif args.cmd == "import-csv":
        n = db.upsert_broadcasts(conn, importer.read_csv(args.path))
        print(f"{n}건 저장")
    elif args.cmd == "collect":
        if not adapters.registered_codes():
            print("등록된 채널 어댑터가 없습니다. homeshop/adapters/ 에 어댑터를 추가하세요.")
            return 1
        res = collector.collect(conn, date.fromisoformat(args.date), args.channel)
        for code, n in res.saved.items():
            print(f"[저장] {code}: {n}건")
        for code, why in res.skipped.items():
            print(f"[건너뜀] {code}: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
