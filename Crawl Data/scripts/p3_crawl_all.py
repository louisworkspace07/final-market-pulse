"""P3 — Bung crawl dữ liệu toàn thị trường (hoặc theo nhóm) với resume + rate-limit.

Crawl cả tài chính (financials) lẫn thông tin công ty (company) cho các mã.
Hỗ trợ Resume (bỏ qua mã đã crawl xong) và Crawl TỪ ĐẦU (--no-resume).

Ví dụ:
  python -m scripts.p3_crawl_all --group VN30                   # Resume crawl nhóm VN30
  python -m scripts.p3_crawl_all --group VN30 --no-resume        # Crawl lại từ đầu nhóm VN30
  python -m scripts.p3_crawl_all --group HOSE --limit 50         # 50 mã nhóm HOSE
  python -m scripts.p3_crawl_all --stage financials            # chỉ crawl báo cáo tài chính
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, httpguard, storage, board, progress
from src.crawler_financials import crawl_one as crawl_fin
from src.crawler_company import crawl_one as crawl_co
from src.runner import guard

STAGES = {"financials": crawl_fin, "company": crawl_co}


def run_stage(conn, stage: str, symbols: list[str], resume: bool, delay: float) -> None:
    fn = STAGES[stage]
    done_set = storage.get_done(conn, stage) if resume else set()
    todo = [s for s in symbols if s not in done_set]
    
    todo_count = len(todo)
    print(f"\n=== STAGE {stage} === cần làm {todo_count}")
    print(f"📋 STAGE {stage.upper()} | Tổng {len(symbols)} mã · Đã xong: {len(symbols)-todo_count} · Cần crawl: {todo_count}")

    if not todo:
        print(f"✅ Stage {stage} đã hoàn tất toàn bộ các mã!")
        return

    ok = err = 0
    for i, sym in enumerate(todo, 1):
        progress.start(sym)
        try:
            summary = guard(fn, conn, sym)
            failed = [k for k, v in summary.items() if v == -1]
            status = "partial" if failed else "ok"
            storage.set_state(conn, sym, stage, status, detail=str(summary))
            ok += 1
            progress.done(sym, status)
            tag = "✓" if status == "ok" else "~"
            print(f"[{i}/{todo_count}] {tag} {sym} {summary}")
        except (Exception, SystemExit) as exc:
            storage.set_state(conn, sym, stage, "error", detail=str(exc))
            err += 1
            progress.done(sym, "err")
            print(f"[{i}/{todo_count}] ✗ {sym}: {str(exc)[:80]}")
        conn.commit()
        time.sleep(delay)
    print(f"--- Stage {stage}: thành công {ok}, lỗi {err}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="ALL", help="VN30 | VN100 | HOSE | HNX | UPCOM | ALL | CUSTOM")
    ap.add_argument("--stage", choices=["financials", "company", "all"], default="all")
    ap.add_argument("--limit", type=int, default=0, help="0 = toàn bộ")
    ap.add_argument("--no-resume", action="store_true", help="Crawl lại TỪ ĐẦU (bỏ resume)")
    ap.add_argument("--delay", type=float, default=2.0, help="Giây nghỉ giữa các mã")
    args = ap.parse_args()

    config.ensure_dirs()
    httpguard.install(18)
    conn = storage.connect()

    syms = board.resolve_symbols(args.group)
    if args.limit > 0:
        syms = syms[:args.limit]

    stages = ["financials", "company"] if args.stage == "all" else [args.stage]
    mode_str = "TỪ ĐẦU (Re-crawl)" if args.no_resume else "RESUME (Tiếp tục mã chưa crawl)"
    print(f"🚀 BẮT ĐẦU CRAWL DỮ LIỆU | Nhóm: {args.group} ({len(syms)} mã) | Chế độ: {mode_str}")

    for st in stages:
        run_stage(conn, st, syms, resume=not args.no_resume, delay=args.delay)
        
    conn.close()
    print("\n✅ Hoàn tất Crawl Dữ Liệu.")


if __name__ == "__main__":
    main()
