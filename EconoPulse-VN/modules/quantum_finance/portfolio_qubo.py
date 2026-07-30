# -*- coding: utf-8 -*-
"""Tối ưu danh mục đầu tư bằng mô hình QUBO — chạy được cả 2 chế độ:

1. QAOA thật trên mô phỏng lượng tử (PennyLane `default.qubit`) — nếu đã cài
   pennylane. Đây là thuật toán lượng tử đúng nghĩa chạy trên simulator,
   đúng khuyến nghị của BTC (Qiskit/PennyLane/Cirq, không cần phần cứng).
2. Simulated Annealing trên cùng QUBO (quantum-inspired, fallback) — để demo
   không phụ thuộc thư viện, và làm baseline so sánh chất lượng lời giải.

Bài toán: chọn K trong N cổ phiếu tối đa hoá (lợi suất kỳ vọng − λ·rủi ro):
    minimize  x^T Q x,   x ∈ {0,1}^N
    Q = λ·Σ (hiệp phương sai) − diag(μ) + phạt ràng buộc (Σx = K)

Kết quả 2 phương pháp được đối chiếu với nghiệm brute-force (N ≤ 20) để
báo cáo "optimality gap" — minh chứng định lượng cho BGK.
"""
import itertools
import json
import sqlite3

import numpy as np
import pandas as pd

try:
    import pennylane as qml
    HAS_PENNYLANE = True
except ImportError:
    HAS_PENNYLANE = False


# ---------------------------------------------------------------- dữ liệu
def load_returns(db_path: str, top_n: int = 12) -> pd.DataFrame:
    """Lợi suất ngày của top_n mã thanh khoản nhất trong market.db."""
    con = sqlite3.connect(db_path)
    px = pd.read_sql("select symbol, time, close from price", con)
    con.close()
    px["date"] = pd.to_datetime(px["time"].str[:10])
    wide = px.pivot_table(index="date", columns="symbol", values="close")

    from modules.macro_forecast.models import _align_panel
    wide = _align_panel(wide)
    # ưu tiên mã có biến động dữ liệu đầy đủ nhất, bỏ mã đứng giá
    rets = wide.pct_change().dropna()
    live = rets.std().sort_values(ascending=False)
    cols = live.index[:top_n]
    return rets[cols]


# ---------------------------------------------------------------- QUBO
def build_qubo(returns: pd.DataFrame, k: int, risk_aversion: float = 2.0,
               penalty: float = 4.0) -> np.ndarray:
    mu = returns.mean().values * 252          # lợi suất kỳ vọng / năm
    cov = returns.cov().values * 252          # hiệp phương sai / năm
    n = len(mu)
    Q = risk_aversion * cov - np.diag(mu)
    # ràng buộc Σx = k:  penalty*(Σx − k)² → QUBO: penalty*(11^T − 2k·I)
    # (vì x_i² = x_i nên −2kΣx nằm trên đường chéo; hằng số k² bỏ qua)
    return Q + penalty * (np.ones((n, n)) - 2 * k * np.eye(n))


def qubo_energy(Q: np.ndarray, x: np.ndarray) -> float:
    return float(x @ Q @ x)


def brute_force(Q: np.ndarray) -> tuple[np.ndarray, float]:
    n = len(Q)
    best_x, best_e = None, np.inf
    for bits in itertools.product([0, 1], repeat=n):
        x = np.array(bits)
        e = qubo_energy(Q, x)
        if e < best_e:
            best_x, best_e = x, e
    return best_x, best_e


# ------------------------------------------------- simulated annealing
def simulated_annealing(Q: np.ndarray, n_iter: int = 20000,
                        seed: int = 42) -> tuple[np.ndarray, float]:
    rng = np.random.default_rng(seed)
    n = len(Q)
    x = rng.integers(0, 2, n)
    e = qubo_energy(Q, x)
    best_x, best_e = x.copy(), e
    for t in range(n_iter):
        temp = max(0.01, 2.0 * (1 - t / n_iter))
        i = rng.integers(n)
        x2 = x.copy()
        x2[i] ^= 1
        e2 = qubo_energy(Q, x2)
        if e2 < e or rng.random() < np.exp((e - e2) / temp):
            x, e = x2, e2
            if e < best_e:
                best_x, best_e = x.copy(), e
    return best_x, best_e


# ---------------------------------------------------------------- QAOA
def qaoa_solve(Q: np.ndarray, layers: int = 2, steps: int = 120,
               seed: int = 42) -> tuple[np.ndarray, float]:
    """QAOA trên simulator PennyLane. QUBO → Ising, tối ưu tham số γ/β."""
    if not HAS_PENNYLANE:
        raise RuntimeError("pennylane chua duoc cai — dung simulated_annealing")

    n = len(Q)
    # QUBO -> Ising: x = (1 - z)/2
    J = Q / 4.0
    h = -(Q.sum(axis=1)) / 2.0 / 2.0

    dev = qml.device("default.qubit", wires=n)

    def cost_h():
        coeffs, ops = [], []
        for i in range(n):
            coeffs.append(h[i]); ops.append(qml.PauliZ(i))
            for j in range(i + 1, n):
                if abs(J[i, j] + J[j, i]) > 1e-12:
                    coeffs.append(J[i, j] + J[j, i])
                    ops.append(qml.PauliZ(i) @ qml.PauliZ(j))
        return qml.Hamiltonian(coeffs, ops)

    H = cost_h()

    @qml.qnode(dev)
    def circuit(params):
        for i in range(n):
            qml.Hadamard(wires=i)
        for l in range(layers):
            qml.templates.ApproxTimeEvolution(H, params[2 * l], 1)
            for i in range(n):
                qml.RX(2 * params[2 * l + 1], wires=i)
        return qml.expval(H)

    @qml.qnode(dev)
    def sample_circuit(params):
        for i in range(n):
            qml.Hadamard(wires=i)
        for l in range(layers):
            qml.templates.ApproxTimeEvolution(H, params[2 * l], 1)
            for i in range(n):
                qml.RX(2 * params[2 * l + 1], wires=i)
        return qml.probs(wires=range(n))

    rng = np.random.default_rng(seed)
    params = qml.numpy.array(rng.uniform(0, np.pi, 2 * layers), requires_grad=True)
    opt = qml.AdamOptimizer(0.1)
    for _ in range(steps):
        params = opt.step(circuit, params)

    probs = sample_circuit(params)
    best_state = int(np.argmax(probs))
    x = np.array([(best_state >> (n - 1 - i)) & 1 for i in range(n)])
    return x, qubo_energy(Q, x)


# ---------------------------------------------------------------- pipeline
def optimize_portfolio(db_path: str, k: int = 5, top_n: int = 12,
                       risk_aversion: float = 2.0) -> dict:
    returns = load_returns(db_path, top_n)
    symbols = list(returns.columns)
    n = len(symbols)
    Q = build_qubo(returns, k, risk_aversion)

    exact_x, exact_e = brute_force(Q) if n <= 20 else (None, None)
    sa_x, sa_e = simulated_annealing(Q)

    methods = {
        "simulated_annealing": {"x": sa_x, "energy": sa_e,
                                "label": "Quantum-inspired (SA trên QUBO)"},
    }
    if HAS_PENNYLANE and n <= 14:
        try:
            qa_x, qa_e = qaoa_solve(Q)
            methods["qaoa"] = {"x": qa_x, "energy": qa_e,
                               "label": "QAOA (PennyLane simulator)"}
        except Exception as e:
            print(f"  [QAOA] loi: {e}")

    mu = returns.mean() * 252
    cov = returns.cov() * 252

    def describe(x):
        picked = [s for s, b in zip(symbols, x) if b]
        if not picked:
            return {"symbols": [], "exp_return": 0, "volatility": 0}
        w = np.array([1 / len(picked)] * len(picked))
        sub_mu = mu[picked].values
        sub_cov = cov.loc[picked, picked].values
        return {
            "symbols": picked,
            "exp_return": round(float(w @ sub_mu) * 100, 2),
            "volatility": round(float(np.sqrt(w @ sub_cov @ w)) * 100, 2),
        }

    out = {
        "universe": symbols,
        "k": k,
        "risk_aversion": risk_aversion,
        "methods": {},
        "exact_energy": round(exact_e, 4) if exact_e is not None else None,
    }
    for name, m in methods.items():
        gap = None
        if exact_e is not None and abs(exact_e) > 1e-9:
            gap = round(abs(m["energy"] - exact_e) / abs(exact_e) * 100, 2)
        out["methods"][name] = {
            "label": m["label"],
            **describe(m["x"]),
            "energy": round(m["energy"], 4),
            "optimality_gap_pct": gap,
        }
    if exact_x is not None:
        out["exact_portfolio"] = describe(exact_x)
    out["pennylane_available"] = HAS_PENNYLANE
    return out


if __name__ == "__main__":
    import sys
    db = sys.argv[1] if len(sys.argv) > 1 else r"..\..\..\data-crawler\database\market.db"
    res = optimize_portfolio(db)
    print(json.dumps(res, ensure_ascii=False, indent=1))
