# -*- coding: utf-8 -*-
"""Quantum Lab (PILLAR-Q) — wizard tối ưu danh mục QUBO 3 bước.

Bọc modules/quantum_finance/portfolio_qubo.py thành trải nghiệm sản phẩm:
- universe(): danh sách mã có đủ dữ liệu giá (kèm tên, ngành) cho bước 1.
- start_lab(): chạy tối ưu ở THREAD NỀN (QAOA chậm) → job_id; UI poll status.
- Quiz khẩu vị (bước 2, client-side) map ra risk_aversion λ:
    bảo thủ λ=4 · cân bằng λ=2 · tăng trưởng λ=1  (PDF triage mục 44).

Legal: kết quả là MÔ PHỎNG HỌC THUẬT trên dữ liệu lịch sử — mọi payload đều
gắn disclaimer; không có từ ngữ khuyến nghị (giữ nguyên tinh thần legal.py).
"""
import sqlite3
import threading
import time
import uuid

import numpy as np
import pandas as pd

from modules.quantum_finance.portfolio_qubo import (
    HAS_PENNYLANE, brute_force, build_qubo, qaoa_solve, qubo_energy,
    simulated_annealing)

DISCLAIMER = ("Kết quả là mô phỏng học thuật trên dữ liệu lịch sử — "
              "KHÔNG phải khuyến nghị phân bổ hay lời khuyên đầu tư. "
              "Quyết định và trách nhiệm thuộc về nhà đầu tư.")

_jobs: dict = {}          # job_id -> {status, steps[], result, error}
_MAX_QAOA_N = 14          # >14 qubit simulator quá chậm


def _ro(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)


def universe(db_path: str) -> dict:
    """Mã có ≥60 phiên giá (đủ tính lợi suất) + tên + ngành cho bước chọn."""
    conn = _ro(db_path)
    try:
        rows = conn.execute(
            """SELECT p.symbol, count(*) AS n, c.organ_name, c.sector
               FROM price p LEFT JOIN companies c ON c.symbol = p.symbol
               GROUP BY p.symbol HAVING n >= 60 ORDER BY p.symbol""").fetchall()
    finally:
        conn.close()
    return {"symbols": [{"symbol": r[0], "n_days": r[1],
                         "name": r[2] or "", "sector": r[3] or ""} for r in rows],
            "disclaimer": DISCLAIMER}


def _returns_for(db_path: str, symbols: list[str]) -> pd.DataFrame:
    conn = _ro(db_path)
    try:
        marks = ",".join("?" * len(symbols))
        px = pd.read_sql(
            f"select symbol, time, close from price where symbol in ({marks})",
            conn, params=symbols)
    finally:
        conn.close()
    px["date"] = pd.to_datetime(px["time"].str[:10])
    wide = px.pivot_table(index="date", columns="symbol", values="close")
    from modules.macro_forecast.models import _align_panel
    wide = _align_panel(wide)
    return wide.pct_change().dropna()


def _run(job: dict, db_path: str, symbols: list[str], k: int, lam: float):
    def step(name, status, detail=""):
        for s in job["steps"]:
            if s["name"] == name:
                s.update(status=status, detail=detail)
                return
        job["steps"].append({"name": name, "status": status, "detail": detail})

    try:
        step("Nạp lợi suất lịch sử", "running")
        rets = _returns_for(db_path, symbols)
        symbols = list(rets.columns)          # mã nào thiếu dữ liệu bị loại
        n = len(symbols)
        if n < max(4, k):
            raise ValueError(f"chỉ {n} mã đủ dữ liệu — cần ≥ {max(4, k)}")
        step("Nạp lợi suất lịch sử", "done", f"{n} mã · {len(rets)} phiên")

        step("Dựng ma trận QUBO", "running")
        Q = build_qubo(rets, k, lam)
        step("Dựng ma trận QUBO", "done", f"{n}×{n}, λ={lam}, K={k}")

        mu = rets.mean() * 252
        cov = rets.cov() * 252

        def describe(x):
            picked = [s for s, b in zip(symbols, x) if b]
            if not picked:
                return {"symbols": [], "exp_return": 0, "volatility": 0, "sharpe": None}
            w = np.full(len(picked), 1 / len(picked))
            r = float(w @ mu[picked].values)
            v = float(np.sqrt(w @ cov.loc[picked, picked].values @ w))
            return {"symbols": picked,
                    "exp_return": round(r * 100, 2),
                    "volatility": round(v * 100, 2),
                    "sharpe": round(r / v, 2) if v > 1e-9 else None}

        methods = {}

        step("Brute-force (nghiệm chuẩn)", "running")
        t0 = time.time()
        bx, be = (brute_force(Q) if n <= 20 else (None, None))
        if bx is not None:
            methods["brute_force"] = {"label": "Brute-force (nghiệm đúng)",
                                      "energy": round(be, 4), "time_s": round(time.time() - t0, 2),
                                      **describe(bx)}
            step("Brute-force (nghiệm chuẩn)", "done", f"2^{n} tổ hợp · {methods['brute_force']['time_s']}s")
        else:
            step("Brute-force (nghiệm chuẩn)", "skip", f"n={n} > 20 — không khả thi")

        step("Simulated Annealing", "running")
        t0 = time.time()
        sx, se = simulated_annealing(Q)
        methods["simulated_annealing"] = {"label": "Quantum-inspired SA",
                                          "energy": round(se, 4), "time_s": round(time.time() - t0, 2),
                                          **describe(sx)}
        step("Simulated Annealing", "done", f"20k bước · {methods['simulated_annealing']['time_s']}s")

        if HAS_PENNYLANE and n <= _MAX_QAOA_N:
            step("QAOA (mô phỏng lượng tử)", "running", f"{n} qubit · PennyLane")
            t0 = time.time()
            try:
                qx, qe = qaoa_solve(Q)
                methods["qaoa"] = {"label": "QAOA (PennyLane simulator)",
                                   "energy": round(qe, 4), "time_s": round(time.time() - t0, 2),
                                   **describe(qx)}
                step("QAOA (mô phỏng lượng tử)", "done", f"{methods['qaoa']['time_s']}s")
            except Exception as e:
                step("QAOA (mô phỏng lượng tử)", "error", str(e)[:120])
        else:
            step("QAOA (mô phỏng lượng tử)", "skip",
                 "pennylane chưa cài" if not HAS_PENNYLANE else f"n={n} > {_MAX_QAOA_N} qubit")

        # optimality gap so với brute-force
        if bx is not None:
            for m in methods.values():
                m["optimality_gap_pct"] = (round(abs(m["energy"] - be) / abs(be) * 100, 2)
                                           if abs(be) > 1e-9 else None)

        job["result"] = {
            "universe": symbols, "k": k, "risk_aversion": lam,
            "methods": methods,
            "pennylane_available": HAS_PENNYLANE,
            "n_sessions": len(rets),
            "disclaimer": DISCLAIMER,
            "source": "market.db · price (P6) — lợi suất ngày annualized ×252",
        }
        job["status"] = "done"
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)[:300]


def start_lab(db_path: str, symbols: list[str], k: int, risk_aversion: float) -> str:
    symbols = [s.upper().strip() for s in symbols if s.strip()][:16]
    k = max(2, min(int(k), 10))
    lam = max(0.25, min(float(risk_aversion), 8.0))
    job_id = uuid.uuid4().hex[:12]
    job = {"status": "running", "steps": [], "result": None, "error": None,
           "started_at": time.time()}
    _jobs[job_id] = job
    threading.Thread(target=_run, args=(job, db_path, symbols, k, lam),
                     daemon=True).start()
    return job_id


def job_status(job_id: str) -> dict | None:
    return _jobs.get(job_id)
