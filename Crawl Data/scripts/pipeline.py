"""Chạy 1 MẠCH từ đầu tới cuối cho một nhóm thị trường, tối ưu rate-limit.

Luồng: lấy mã nhóm → CRAWL (song song, token-bucket) → PHÂN TÍCH (tuần tự) → EXPORT.
- Crawl song song nhiều worker nhưng tổng request/phút bị ép sát trần (mặc định 55/60).
- Giá + định giá lấy từ VNDirect (host khác) nên không tốn quota vnstock.
- Phân tích chạy tuần tự (Gemini chỉ 1 tab; Claude thì song song được).
- Resume: bỏ qua mã đã xong (bảng crawl_state).

Ví dụ:
  python -m scripts.pipeline --group VN30
  python -m scripts.pipeline --group HOSE --workers 4 --backend claude
  python -m scripts.pipeline --group ALL --rate 55
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, httpguard, storage, board

def get_symbols(group: str) -> list[str]:
    return board.resolve_symbols(group)



def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="VN30",
                    help="VN30 | VN100 | HOSE | HNX | UPCOM | ALL")
    ap.add_argument("--workers", type=int, default=2)
    # Gói Guest vnstock = 20 req/phút. Để 18 (giới hạn tại tầng HTTP thật).
    ap.add_argument("--rate", type=float, default=18, help="HTTP request vnstock/phút tối đa (<20)")
    ap.add_argument("--backend", default="",
                    help="local_api (mặc định) | gemini (web/CDP) | claude")
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--reanalyze", action="store_true",
                    help="phân tích LẠI TỪ ĐẦU (bỏ resume ở stage analyze; làm lại cả mã đã có)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    config.ensure_dirs()
    # Giới hạn tại tầng HTTP thật: ≤ rate req/phút tới host vnstock (VNDirect được miễn).
    httpguard.install(args.rate)
    group = args.group.upper()
    t_start = time.time()

    print(f"🚀 PIPELINE nhóm {group} | {args.workers} worker | trần {args.rate} req/phút (HTTP) "
          f"| backend {args.backend}")
    syms = get_symbols(group)
    if args.limit:
        syms = syms[:args.limit]
    print(f"   {len(syms)} mã trong nhóm {group}")

    # Rate-limit thực thi ở httpguard.install(args.rate) phía trên: token-bucket
    # đếm từng HTTP request tới host vnstock (capacity mặc định trong httpguard.py),
    # nên nhiều worker vẫn bị ép tổng ≤ rate req/phút, tránh bị vnstock chặn.
    counter = {"done": 0, "err": 0}
    clock = threading.Lock()

    # ---- nạp danh mã vào DB (để có sector cho so sánh ngành) ----
    conn0 = storage.connect()
    for s in syms:
        storage.upsert_company(conn0, s)
    conn0.commit()
    resume = not args.no_resume
    fin_done = storage.get_done(conn0, "financials") if resume else set()
    co_done = storage.get_done(conn0, "company") if resume else set()
    conn0.close()

    todo = [s for s in syms if s not in fin_done or s not in co_done]
    backend = (args.backend or "").lower() or resolve_backend()
    # Gemini chỉ 1 tab → không thể phân tích song song. Claude phân tích
    # NGAY trong worker sau khi crawl xong từng mã ("dần luôn") → khỏi tốn pha riêng.
    inline = backend != "gemini"
    # PREFLIGHT local_api: server local chết/thiếu key → 4-5 lượt AI mỗi mã đều
    # fail, cả nghìn mã chỉ ra quant-only. Báo NGAY thay vì để phát hiện muộn.
    if backend == "local_api":
        from src import local_api
        st = local_api.status()
        if not st["has_key"]:
            print("\n⚠️  Thiếu LOCAL_API_KEY (Crawl Data/.env) — phân tích AI sẽ lỗi, "
                  "chỉ còn số liệu định lượng.")
        elif not st["up"]:
            print(f"\n⚠️  Không gọi được server AI local ở {st['url']} — hãy bật server "
                  "rồi chạy lại; nếu không, phân tích chỉ ra số liệu định lượng.")
        else:
            print(f"   ✓ Local API sẵn sàng: {st['url']} (model {st['model']})")
    print(f"\n=== STAGE crawl === tổng {len(syms)}, đã xong {len(syms) - len(todo)}, "
          f"cần làm {len(todo)}"
          + (f"  (phân tích {backend} ngay sau mỗi mã)" if inline else ""))

    def work(sym: str):
        conn = storage.connect()          # mỗi worker 1 kết nối (SQLite thread-safe)
        summary = {}
        try:
            if sym not in fin_done:
                s1 = guard(crawl_fin, conn, sym)
                storage.set_state(conn, sym, "financials",
                                  "partial" if any(v == -1 for v in s1.values()) else "ok", str(s1))
                summary.update(s1)
            if sym not in co_done:
                s2 = guard(crawl_co, conn, sym)
                storage.set_state(conn, sym, "company",
                                  "partial" if any(v == -1 for v in s2.values()) else "ok", str(s2))
                summary.update(s2)
            conn.commit()
            # PHÂN TÍCH NGAY (tận dụng lúc rảnh chờ rate-limit của worker khác)
            if inline:
                r = analyze_one(conn, sym, backend)
                summary["★"] = f"sk{r.get('metrics',{}).get('health_score','?')}/{r.get('risk_level','?')}"
            return sym, summary, None
        except (Exception, SystemExit) as exc:
            return sym, summary, str(exc)[:80]
        finally:
            conn.close()

    # ---- PHA 1: CRAWL (+ phân tích inline) song song ----
    # Chạy worker cho TẤT CẢ mã: mã đã crawl xong (resume) sẽ bỏ qua crawl
    # nhưng vẫn được phân tích inline → không sót mã nào.
    run_list = syms if inline else todo
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(work, s): s for s in run_list}
        for fut in as_completed(futs):
            sym, summary, err = fut.result()
            with clock:
                if err:
                    counter["err"] += 1; tag = "✗"
                else:
                    counter["done"] += 1; tag = "✓"
                k = counter["done"] + counter["err"]
            print(f"  [{k}/{len(run_list)}] {tag} {sym} "
                  f"{summary if not err else err}", flush=True)

    # ---- PHA 2: PHÂN TÍCH tuần tự (chỉ khi backend = Gemini) ----
    if not inline:
        # PREFLIGHT: Gemini cần Chrome CDP :9222 + đã đăng nhập. Kiểm tra TRƯỚC để
        # không treo cả 1400+ mã (mỗi mã fail connect ~3s) khi Chrome chưa mở.
        from src.gemini_cdp import cdp_available, GeminiCDP
        if not cdp_available():
            print("\n⚠️  BỎ QUA STAGE analyze: không kết nối được Chrome CDP ở "
                  "http://localhost:9222.")
            print("   → Chạy: python -m scripts.launch_chrome  rồi ĐĂNG NHẬP Gemini, "
                  "kiểm tra http://localhost:9222/json/version, sau đó chạy lại pipeline.")
        else:
            ready, msg = False, ""
            try:
                with GeminiCDP() as _g:
                    ready, msg = _g.preflight()
            except Exception as exc:
                ready, msg = False, str(exc)[:160]
            if not ready:
                print(f"\n⚠️  BỎ QUA STAGE analyze: Gemini chưa sẵn sàng — {msg}")
                print("   → Mở tab Gemini trong Chrome CDP và đăng nhập, rồi chạy lại.")
            else:
                conn = storage.connect()
                if args.reanalyze:
                    # START TỪ ĐẦU: làm lại tất cả (bỏ resume).
                    todo2 = list(syms)
                    print(f"\n=== STAGE analyze === 🔄 PHÂN TÍCH LẠI TỪ ĐẦU: {len(todo2)} mã")
                else:
                    # RESUME (mặc định): bỏ qua mã đã có phân tích → chạy tiếp, không làm lại từ đầu.
                    analyzed = {row[0] for row in conn.execute("SELECT symbol FROM ai_analysis")}
                    todo2 = [s for s in syms if s not in analyzed]
                    print(f"\n=== STAGE analyze === ▶ RESUME · tổng {len(syms)} | đã có "
                          f"{len(analyzed)} | cần phân tích {len(todo2)}")
                try:
                    for i, sym in enumerate(todo2, 1):
                        # Dòng "bắt đầu" để thấy tiến độ ngay (đa lượt Gemini mất vài phút/mã);
                        # analyzer in thêm từng lượt khía cạnh bên dưới.
                        print(f"  [{i}/{len(todo2)}] ▸ {sym} — đang phân tích...", flush=True)
                        try:
                            r = guard(analyze_one, conn, sym, backend)
                            print(f"  [{i}/{len(todo2)}] ✓ {sym} · sức khỏe "
                                  f"{r.get('metrics',{}).get('health_score','?')} · rủi ro "
                                  f"{r.get('risk_level','?')} [{r.get('mode')}]", flush=True)
                        except (Exception, SystemExit) as exc:
                            print(f"  [{i}/{len(todo2)}] ✗ {sym}: {str(exc)[:70]}", flush=True)
                finally:
                    conn.close()
                    close_gemini()

    # ---- PHA 3: EXPORT ----
    print("\n=== STAGE export ===")
    import scripts.p5_export as p5
    p5.main()

    mins = (time.time() - t_start) / 60
    print(f"\n✅ XONG nhóm {group}: crawl {counter['done']} ok / {counter['err']} lỗi · "
          f"{len(syms)} mã phân tích · {mins:.1f} phút")


if __name__ == "__main__":
    main()
