# -*- coding: utf-8 -*-
"""Market Pulse — pipeline tổng: chạy 3 module phân tích và xuất JSON
cho dashboard (gateway/static/data/*.json).

Cách chạy:  python run_pipeline.py [--refresh]
    --refresh : tải lại dữ liệu vĩ mô mới nhất từ World Bank API
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.normpath(os.path.join(BASE, "..", "data-crawler", "database", "market.db"))
OUT_DIR = os.path.join(BASE, "gateway", "static", "data")
os.makedirs(OUT_DIR, exist_ok=True)


def save(name: str, obj) -> None:
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    print(f"  -> {name} ({os.path.getsize(path)//1024} KB)")


def main() -> None:
    refresh = "--refresh" in sys.argv
    t0 = time.time()

    print("[1/4] Du bao vi mo (GDP, CPI) — World Bank + SARIMAX ...")
    from modules.macro_forecast.data_loader import load_macro
    from modules.macro_forecast.models import (forecast_annual, build_market_index,
                                                load_vnindex, return_distribution)
    macro = load_macro(refresh=refresh)
    macro_out = {
        "gdp_growth": forecast_annual(macro["gdp_growth"].dropna(), horizon=3),
        "cpi": forecast_annual(macro["cpi"].dropna(), horizon=3),
        "updated_at": time.strftime("%Y-%m-%d %H:%M"),
    }
    save("macro_forecast.json", macro_out)

    print("[1b/4] Mo rong vi mo (World Bank + FX + probe vang/dau + seed) ...")
    from modules.macro_ai.macro_data import build_macro_plus
    macro_plus = build_macro_plus()
    _n_ind = sum(1 for v in macro_plus["indicators"].values() if v.get("available"))
    print(f"  indicators OK: {_n_ind}/{len(macro_plus['indicators'])}"
          f" | fx={'OK' if macro_plus['fx'].get('available') else 'x'}"
          f" | gold={'OK' if macro_plus['gold'].get('available') else 'x'}"
          f" | oil={'OK' if macro_plus['oil'].get('available') else 'x'}")
    save("macro_plus.json", macro_plus)

    print("[2/4] Dai thong ke loi suat 30 phien tren VNINDEX that ...")
    vnidx = load_vnindex(DB_PATH)
    if len(vnidx):
        rng = return_distribution(vnidx, horizon=30)
    else:
        # fallback: proxy vốn hoá nếu chưa crawl market_index (P7)
        rng = return_distribution(build_market_index(DB_PATH), horizon=30)
        rng["source"] = "proxy vốn hoá (chưa có VNINDEX thật — chạy P7)"
    rng["updated_at"] = time.strftime("%Y-%m-%d %H:%M")
    rng.setdefault("source", "VNINDEX thật (market_index, VNDirect)")
    save("market_range.json", rng)

    print("[3/4] Cham diem suc khoe doanh nghiep (Z''-score, F-score) ...")
    from modules.business_health.scoring import score_all
    scores = score_all(DB_PATH)
    save("health_scores.json", {
        "companies": scores,
        "updated_at": time.strftime("%Y-%m-%d %H:%M"),
    })

    print("[4/4] Toi uu danh muc QUBO (quantum / quantum-inspired) ...")
    from modules.quantum_finance.portfolio_qubo import optimize_portfolio
    save("quantum_portfolio.json", {
        **optimize_portfolio(DB_PATH, k=5, top_n=12),
        "updated_at": time.strftime("%Y-%m-%d %H:%M"),
    })

    print(f"Xong trong {time.time()-t0:.1f}s. Mo dashboard: python gateway/app.py")


if __name__ == "__main__":
    main()
