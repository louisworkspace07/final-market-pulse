"""P4 — Phân tích AI hàng loạt cho các mã cổ phiếu.

Hỗ trợ Resume (bỏ qua các mã đã phân tích xong) và Phân tích TỪ ĐẦU (--reanalyze), theo Nhóm (VN30, VN100, HOSE, HNX, UPCOM, ALL, CUSTOM).

Ví dụ:
  python -m scripts.p4_analyze --group VN30                   # Resume phân tích nhóm VN30
  python -m scripts.p4_analyze --group VN30 --reanalyze       # Phân tích lại từ đầu nhóm VN30
  python -m scripts.p4_analyze --all                         # Resume phân tích tất cả mã trong DB
  python -m scripts.p4_analyze --group CUSTOM                # Resume phân tích mã trong config/companies.txt
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, storage, board, progress
from src.analyzer import analyze_one, resolve_backend, close_gemini_threadlocal
from src.runner import guard

# Trần số luồng CDP song song (mỗi luồng = 1 tab Chrome riêng). Chỉnh bằng env.
MAX_WORKERS = int(os.environ.get("CDP_MAX_TABS", "3"))
# Backend local_api chỉ gọi HTTP nên chạy song song thoải mái hơn; trần riêng để
# không dội quá tải server local. Chỉnh bằng env LOCAL_API_MAX_WORKERS.
LOCAL_API_WORKERS = int(os.environ.get("LOCAL_API_MAX_WORKERS", "3"))


def _worker(sym: str, backend: str):
    """Chạy 1 mã trong thread riêng: SQLite conn riêng + Gemini/Claude riêng."""
    conn = storage.connect()
    try:
        r = guard(analyze_one, conn, sym, backend)
        return sym, r, None
    except (Exception, SystemExit) as exc:
        return sym, None, str(exc)[:100]
    finally:
        conn.close()
        # KHÔNG gọi close_gemini_threadlocal() ở đây vì ThreadPoolExecutor sẽ tái sử dụng thread.
        # Nếu stop() Playwright xong, lần gọi sau trên cùng thread sẽ bị lỗi asyncio loop.
        # Playwright CDP connection sẽ sống cùng thread và được tái sử dụng, rất tốt.


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="", help="VN30 | VN100 | HOSE | HNX | UPCOM | ALL | CUSTOM")
    ap.add_argument("--all", action="store_true", help="Phân tích tất cả mã đã crawl trong DB")
    ap.add_argument("--reanalyze", action="store_true", help="Phân tích LẠI từ đầu (bỏ resume)")
    ap.add_argument("--limit", type=int, default=0, help="Giới hạn số lượng mã")
    ap.add_argument("--workers", type=int, default=0,
                    help="0 = tự chọn theo backend (local_api/claude song song, gemini tuần tự)")
    ap.add_argument("--backend", default="", help="local_api (mặc định) | gemini | claude")
    args = ap.parse_args()

    backend = (args.backend or resolve_backend()).lower()
    conn = storage.connect()

    # Xắc định danh sách mã theo group/all/companies.txt
    if args.all or args.group.upper() == "ALL":
        syms = [r[0] for r in conn.execute("SELECT DISTINCT symbol FROM companies").fetchall()]
        if not syms:
            syms = board.resolve_symbols("ALL")
    elif args.group:
        syms = board.resolve_symbols(args.group)
    else:
        # Mặc định: lấy mã trong config/companies.txt, nếu rỗng thì lấy mã đã crawl trong DB
        syms = config.load_tickers()
        if not syms:
            syms = [r[0] for r in conn.execute("SELECT DISTINCT symbol FROM companies").fetchall()]

    # Resume vs Reanalyze
    if args.reanalyze:
        done_ai = set()
    else:
        done_ai = {r[0] for r in conn.execute("SELECT symbol FROM ai_analysis").fetchall()}

    todo = [s for s in syms if s not in done_ai]
    if args.limit > 0:
        todo = todo[:args.limit]

    conn.close()

    total_target = len(syms)
    todo_count = len(todo)
    already_done = len(syms) - todo_count

    mode_str = "TỪ ĐẦU (Re-analyze)" if args.reanalyze else "RESUME (Tiếp tục mã chưa phân tích)"
    print(f"=== STAGE analyze === cần làm {todo_count}")
    print(f"🤖 PHÂN TÍCH AI ({backend.upper()}) | Chế độ: {mode_str}")
    print(f"   Tổng: {total_target} mã · Đã phân tích: {already_done} · Cần làm: {todo_count}")

    if not todo:
        print("✅ Tất cả mã trong nhóm đã được phân tích đầy đủ. Không có mã nào cần làm tiếp!")
        return

    # Gemini CDP chạy tuần tự (tránh xung đột tab). local_api/claude chỉ là HTTP
    # nên chạy song song được; --workers 0 = tự chọn trần theo backend.
    if backend == "gemini":
        workers = 1
    elif args.workers > 0:
        workers = args.workers
    else:
        workers = LOCAL_API_WORKERS if backend == "local_api" else MAX_WORKERS

    print(f"▶ Bắt đầu xử lý {todo_count} mã (song song: {workers} luồng)...")
    
    ok_cnt, err_cnt = 0, 0
    if workers == 1:
        for i, sym in enumerate(todo, 1):
            progress.start(sym)
            sym_res, res, err = _worker(sym, backend)
            if err is None and res is not None:
                ok_cnt += 1
                progress.done(sym, "ok")
                risk = res.get("risk_level", "?") if isinstance(res, dict) else "?"
                print(f"[{i}/{todo_count}] ✓ {sym} (Rủi ro: {risk})")
            else:
                err_cnt += 1
                progress.done(sym, "err")
                print(f"[{i}/{todo_count}] ✗ {sym}: {err}")
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_worker, s, backend): s for s in todo}
            for i, fut in enumerate(as_completed(futs), 1):
                sym = futs[fut]
                progress.start(sym)
                sym_res, res, err = fut.result()
                if err is None and res is not None:
                    ok_cnt += 1
                    progress.done(sym, "ok")
                    risk = res.get("risk_level", "?") if isinstance(res, dict) else "?"
                    print(f"[{i}/{todo_count}] ✓ {sym} (Rủi ro: {risk})")
                else:
                    err_cnt += 1
                    progress.done(sym, "err")
                    print(f"[{i}/{todo_count}] ✗ {sym}: {err}")

    print(f"✅ Hoàn tất Phân Tích AI — Thành công: {ok_cnt}, Lỗi: {err_cnt}")


if __name__ == "__main__":
    main()
