"""명령줄 도구.

  python -m homeshop init-db
  python -m homeshop import-csv 편성표.csv
  python -m homeshop import-page 저장한편성표.html [--site hmall]
  python -m homeshop collect --date 2026-10-31 [--channel gs --channel cj]
  python -m homeshop serve --port 8000
"""
from __future__ import annotations

import argparse
import logging
from datetime import date

from . import adapters, collector, db, importer, pages


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="homeshop")
    p.add_argument("--db", default=None, help="SQLite 파일 경로 (기본: data/homeshop.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db")

    imp = sub.add_parser("import-csv")
    imp.add_argument("path")

    pg = sub.add_parser("import-page", help="브라우저로 저장한 편성표 페이지 가져오기")
    pg.add_argument("paths", nargs="+")
    pg.add_argument("--site", choices=pages.supported(), help="자동 인식이 안 될 때 지정")

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
    elif args.cmd == "import-page":
        for path in args.paths:
            try:
                items = pages.read_page(path, args.site)
            except (pages.PageImportError, OSError) as e:
                print(f"[실패] {path}: {e}")
                continue
            n = db.merge_page_broadcasts(conn, items)
            detailed = sum(1 for b in items if b.product_name)
            print(f"[저장] {path}: 방송 {len({(b.channel_code, b.start_at) for b in items})}건, "
                  f"상품 상세 {detailed}건 (갱신 {n}행)")
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
