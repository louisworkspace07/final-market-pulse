# -*- coding: utf-8 -*-
"""Portfolio Analyzer — Trụ cột 4 của Decision Copilot.

Người dùng nhập danh mục [{symbol, qty}] → trả về:
- Tỷ trọng từng mã + tỷ trọng theo ngành + chỉ số tập trung HHI
- Ma trận tương quan giữa các mã (từ giá lịch sử trong market.db)
- Độ biến động danh mục (năm hoá) + đóng góp rủi ro biên từng mã
- Gợi ý tái cân bằng: chạy QUBO trên universe = (mã đang nắm ∪ mã khoẻ nhất
  theo health_scores) — tái dùng engine modules/quantum_finance.

Mọi số liệu trả về kèm nhãn nguồn (audit trail) đúng Trụ cột 1 — Minh bạch.
"""
import json
import os
import sqlite3

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(BASE, "..", ".."))
DATA_DIR = os.path.join(ROOT, "gateway", "static", "data")

HHI_WARN = 0.30   # HHI ngành > 0.30 → cảnh báo tập trung
CORR_WARN = 0.70  # tương quan cặp > 0.7 → "tưởng đa dạng mà cùng nhịp"


def _load_prices(db_path: str, symbols: list[str]) -> pd.DataFrame:
    con = sqlite3.connect(db_path)
    q = "select symbol, time, close from price where symbol in ({})".format(
        ",".join("?" * len(symbols)))
    px = pd.read_sql(q, con, params=symbols)
    con.close()
    if px.empty:
        return pd.DataFrame()
    px["date"] = pd.to_datetime(px["time"].str[:10])
    wide = px.pivot_table(index="date", columns="symbol", values="close")
    start = max((wide[c].first_valid_index() for c in wide.columns
                 if wide[c].first_valid_index() is not None), default=None)
    if start is None:
        return pd.DataFrame()
    return wide.loc[start:].ffill().dropna()


def _company_meta(db_path: str, symbols: list[str]) -> dict:
    con = sqlite3.connect(db_path)
    q = ("select symbol, organ_name, sector, current_price from companies "
         "where symbol in ({})").format(",".join("?" * len(symbols)))
    rows = con.execute(q, symbols).fetchall()
    con.close()
    return {r[0]: {"name": r[1], "sector": r[2] or "Chưa phân ngành",
                   "current_price": r[3]} for r in rows}


def _health_lookup() -> dict:
    path = os.path.join(DATA_DIR, "health_scores.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {c["symbol"]: c for c in data.get("companies", [])}


def analyze_portfolio(db_path: str, holdings: list[dict]) -> dict:
    """holdings: [{"symbol": "FPT", "qty": 100}, ...]"""
    holdings = [h for h in holdings
                if h.get("symbol") and float(h.get("qty", 0) or 0) > 0]
    if not holdings:
        return {"error": "Danh mục trống — nhập ít nhất 1 mã với khối lượng > 0."}

    symbols = [h["symbol"].strip().upper() for h in holdings]
    qty = {h["symbol"].strip().upper(): float(h["qty"]) for h in holdings}

    meta = _company_meta(db_path, symbols)
    unknown = [s for s in symbols if s not in meta]

    wide = _load_prices(db_path, [s for s in symbols if s in meta])
    have_px = list(wide.columns) if not wide.empty else []
    no_px = [s for s in symbols if s in meta and s not in have_px]

    # ---- giá trị & tỷ trọng: ưu tiên giá đóng cửa mới nhất, fallback current_price
    values, positions = {}, []
    for s in symbols:
        if s not in meta:
            continue
        price = float(wide[s].iloc[-1]) if s in have_px else (meta[s]["current_price"] or 0)
        if not price:
            no_px.append(s)
            continue
        values[s] = price * qty[s]
    total = sum(values.values())
    if total <= 0:
        return {"error": "Không có dữ liệu giá cho bất kỳ mã nào trong danh mục. "
                         f"Mã không nhận diện được: {unknown}"}

    health = _health_lookup()
    weights = {s: v / total for s, v in values.items()}
    for s, w in sorted(weights.items(), key=lambda x: -x[1]):
        h = health.get(s, {})
        positions.append({
            "symbol": s, "name": meta[s]["name"], "sector": meta[s]["sector"],
            "qty": qty[s],
            "price": round(values[s] / qty[s], 2),
            "value": round(values[s], 0),
            "weight_pct": round(w * 100, 2),
            "health_score": h.get("health_score"),
            "z_zone": h.get("z_zone"),
        })

    # ---- tập trung ngành (HHI)
    sector_w = {}
    for s, w in weights.items():
        sector_w[meta[s]["sector"]] = sector_w.get(meta[s]["sector"], 0) + w
    hhi = sum(w * w for w in sector_w.values())
    top_sector = max(sector_w, key=sector_w.get)

    # ---- tương quan + rủi ro (chỉ mã có chuỗi giá)
    corr_matrix, corr_pairs_warn, risk = None, [], None
    if len(have_px) >= 2:
        rets = wide[have_px].pct_change().dropna()
        corr = rets.corr()
        corr_matrix = {
            "symbols": have_px,
            "matrix": [[round(float(corr.iloc[i, j]), 2)
                        for j in range(len(have_px))] for i in range(len(have_px))],
        }
        for i in range(len(have_px)):
            for j in range(i + 1, len(have_px)):
                c = float(corr.iloc[i, j])
                if c >= CORR_WARN:
                    corr_pairs_warn.append(
                        {"pair": [have_px[i], have_px[j]], "corr": round(c, 2)})

        w_vec = np.array([weights[s] for s in have_px])
        w_vec = w_vec / w_vec.sum()
        cov = rets.cov().values * 252
        port_var = float(w_vec @ cov @ w_vec)
        port_vol = float(np.sqrt(port_var))
        mcr = cov @ w_vec / np.sqrt(port_var)          # marginal contribution
        pct_contrib = w_vec * mcr / np.sqrt(port_var)  # % đóng góp rủi ro
        risk = {
            "portfolio_vol_pct": round(port_vol * 100, 2),
            "risk_contribution": [
                {"symbol": s, "weight_pct": round(float(w_vec[k]) * 100, 1),
                 "risk_pct": round(float(pct_contrib[k]) * 100, 1)}
                for k, s in enumerate(have_px)],
            "n_days": int(len(rets)),
        }

    # ---- gợi ý tái cân bằng bằng QUBO (universe = mã đang nắm + mã khoẻ có giá)
    rebalance = None
    try:
        from modules.quantum_finance.portfolio_qubo import (
            load_returns, build_qubo, simulated_annealing, brute_force, qubo_energy)
        rets_all = load_returns(db_path, top_n=14)
        universe = [s for s in rets_all.columns]
        # đảm bảo mã đang nắm (có giá) nằm trong universe
        extra = [s for s in have_px if s not in universe]
        if extra:
            universe = (extra + universe)[:14]
            rets_all = _load_prices(db_path, universe).pct_change().dropna()
        k = min(max(len(have_px), 3), 6)
        Q = build_qubo(rets_all[universe], k=k)
        x, e = simulated_annealing(Q)
        bx, be = brute_force(Q) if len(universe) <= 20 else (x, e)
        chosen = [s for s, b in zip(universe, bx) if b]
        mu = rets_all[universe].mean() * 252
        keep = [s for s in chosen if s in have_px]
        add = [s for s in chosen if s not in have_px]
        drop = [s for s in have_px if s not in chosen]
        rebalance = {
            "method": "QUBO (Markowitz) — nghiệm chính xác brute-force, "
                      "đối chiếu simulated annealing",
            "suggested": chosen, "keep": keep, "add": add, "drop": drop,
            "exp_return_pct": round(float(mu[chosen].mean()) * 100, 2) if chosen else 0,
            "k": k, "universe": universe,
        }
    except Exception as ex:  # không chặn kết quả chính nếu QUBO lỗi
        rebalance = {"error": f"Không chạy được gợi ý tái cân bằng: {ex}"}

    return {
        "total_value": round(total, 0),
        "positions": positions,
        "sectors": [{"sector": s, "weight_pct": round(w * 100, 1)}
                    for s, w in sorted(sector_w.items(), key=lambda x: -x[1])],
        "hhi": round(hhi, 3),
        "concentration_warning": (
            f"Danh mục tập trung cao (HHI={hhi:.2f}): riêng ngành {top_sector} "
            f"chiếm {sector_w[top_sector]*100:.0f}%." if hhi > HHI_WARN else None),
        "correlation": corr_matrix,
        "high_corr_pairs": corr_pairs_warn,
        "risk": risk,
        "rebalance": rebalance,
        "not_found": unknown,
        "no_price_data": sorted(set(no_px)),
        "sources": [
            {"label": "Giá đóng cửa & tương quan",
             "source": "market.db · bảng price (crawl vnstock)",
             "updated_at": str(wide.index[-1].date()) if not wide.empty else None,
             "confidence": "Cao"},
            {"label": "Phân ngành & giá tham chiếu",
             "source": "market.db · bảng companies", "confidence": "Cao"},
            {"label": "Điểm sức khỏe", "source": "health_scores.json "
             "(Altman Z'' + Piotroski F từ BCTC)", "confidence": "Trung bình"},
            {"label": "Gợi ý tái cân bằng", "source": "QUBO/Markowitz trên lợi suất "
             "252 ngày — kết quả mô hình, KHÔNG phải khuyến nghị đầu tư",
             "confidence": "Trung bình"},
        ],
    }


if __name__ == "__main__":
    db = os.path.join(ROOT, "..", "Crawl Data", "database", "market.db")
    demo = [{"symbol": "FPT", "qty": 100}, {"symbol": "VCB", "qty": 200},
            {"symbol": "ACB", "qty": 300}, {"symbol": "HPG", "qty": 500}]
    print(json.dumps(analyze_portfolio(db, demo), ensure_ascii=False, indent=1)[:3000])
