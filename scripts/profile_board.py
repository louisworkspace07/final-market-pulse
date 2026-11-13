import sys
import os
import time
import cProfile
import pstats
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "price-board"))
import board_vnstock

n_rows = 726
data = {
    "symbol": [f"SYM{i:04d}" for i in range(n_rows)],
    "ref_price": [50.0 + (i % 50) for i in range(n_rows)],
    "ceiling": [53.5 + (i % 50) for i in range(n_rows)],
    "floor": [46.5 + (i % 50) for i in range(n_rows)],
    "match_price": [51.2 + (i % 50) for i in range(n_rows)],
    "match_vol": [15000 + i * 10 for i in range(n_rows)],
    "accumulated_volume": [500000 + i * 100 for i in range(n_rows)],
    "avg_match_price": [50.8 + (i % 50) for i in range(n_rows)],
    "highest": [52.0 + (i % 50) for i in range(n_rows)],
    "lowest": [49.5 + (i % 50) for i in range(n_rows)],
    "foreign_buy_volume": [20000 for _ in range(n_rows)],
    "foreign_sell_volume": [15000 for _ in range(n_rows)],
    "bid_1_price": [51.0 for _ in range(n_rows)],
    "bid_1_volume": [5000 for _ in range(n_rows)],
    "bid_2_price": [50.8 for _ in range(n_rows)],
    "bid_2_volume": [6000 for _ in range(n_rows)],
    "bid_3_price": [50.5 for _ in range(n_rows)],
    "bid_3_volume": [7000 for _ in range(n_rows)],
    "ask_1_price": [51.3 for _ in range(n_rows)],
    "ask_1_volume": [5500 for _ in range(n_rows)],
    "ask_2_price": [51.5 for _ in range(n_rows)],
    "ask_2_volume": [6500 for _ in range(n_rows)],
    "ask_3_price": [51.8 for _ in range(n_rows)],
    "ask_3_volume": [7500 for _ in range(n_rows)],
}
df = pd.DataFrame(data)
ex_map = {f"SYM{i:04d}": "HOSE" for i in range(n_rows)}

FIELDS = (
    "symbol", "ref_price", "ceiling", "floor", "match_price",
    "match_vol", "accumulated_volume", "avg_match_price",
    "highest", "lowest", "foreign_buy_volume", "foreign_sell_volume",
    "bid_1_price", "bid_1_volume", "bid_2_price", "bid_2_volume",
    "bid_3_price", "bid_3_volume", "ask_1_price", "ask_1_volume",
    "ask_2_price", "ask_2_volume", "ask_3_price", "ask_3_volume",
)

def benchmark_breakdown():
    # 1. Extraction of F
    t0 = time.perf_counter()
    F = {}
    n = len(df)
    for f in FIELDS:
        col = board_vnstock._flat_col(df, f)
        if col is not None:
            F[f] = col.tolist() if hasattr(col, "tolist") else list(col)
        else:
            F[f] = [None] * n
    t_extract = (time.perf_counter() - t0) * 1000.0

    # 2. Loop
    t0 = time.perf_counter()
    out = []
    for i in range(n):
        g = lambda k, idx=i: F[k][idx]
        sym = g("symbol")
        if not sym:
            continue
        ref = board_vnstock._num(g("ref_price")); mp = board_vnstock._num(g("match_price"))
        change = (mp - ref) if (mp is not None and ref) else None
        du_mua = sum(board_vnstock._num(g(k)) or 0 for k in ("bid_1_volume", "bid_2_volume", "bid_3_volume"))
        du_ban = sum(board_vnstock._num(g(k)) or 0 for k in ("ask_1_volume", "ask_2_volume", "ask_3_volume"))
        raw = [
            str(sym),
            board_vnstock._price_txt(g("ref_price")),
            board_vnstock._price_txt(g("ceiling")),
            board_vnstock._price_txt(g("floor")),
            board_vnstock._vol_txt(g("accumulated_volume")),
            board_vnstock._price_txt(g("bid_3_price")), board_vnstock._vol_txt(g("bid_3_volume")),
            board_vnstock._price_txt(g("bid_2_price")), board_vnstock._vol_txt(g("bid_2_volume")),
            board_vnstock._price_txt(g("bid_1_price")), board_vnstock._vol_txt(g("bid_1_volume")),
            board_vnstock._price_txt(g("match_price")),
            board_vnstock._vol_txt(g("match_vol")),
            (f"{change/1000:+.2f}" if change is not None else ""),
            board_vnstock._price_txt(g("ask_1_price")), board_vnstock._vol_txt(g("ask_1_volume")),
            board_vnstock._price_txt(g("ask_2_price")), board_vnstock._vol_txt(g("ask_2_volume")),
            board_vnstock._price_txt(g("ask_3_price")), board_vnstock._vol_txt(g("ask_3_volume")),
            board_vnstock._price_txt(g("highest")),
            board_vnstock._price_txt(g("avg_match_price")),
            board_vnstock._price_txt(g("lowest")),
            board_vnstock._vol_txt(du_mua), board_vnstock._vol_txt(du_ban),
            board_vnstock._vol_txt(g("foreign_buy_volume")),
            board_vnstock._vol_txt(g("foreign_sell_volume")),
        ]
        out.append({
            "symbol": sym, "exchange": ex_map.get(sym, ""),
            "ref": ref, "ceil": board_vnstock._num(g("ceiling")), "floor": board_vnstock._num(g("floor")),
            "matchPrice": mp, "matchVol": board_vnstock._num(g("match_vol")),
            "totalVol": board_vnstock._num(g("accumulated_volume")),
            "buyP3": board_vnstock._num(g("bid_3_price")), "buyV3": board_vnstock._num(g("bid_3_volume")),
            "buyP2": board_vnstock._num(g("bid_2_price")), "buyV2": board_vnstock._num(g("bid_2_volume")),
            "buyP1": board_vnstock._num(g("bid_1_price")), "buyV1": board_vnstock._num(g("bid_1_volume")),
            "sellP1": board_vnstock._num(g("ask_1_price")), "sellV1": board_vnstock._num(g("ask_1_volume")),
            "sellP2": board_vnstock._num(g("ask_2_price")), "sellV2": board_vnstock._num(g("ask_2_volume")),
            "sellP3": board_vnstock._num(g("ask_3_price")), "sellV3": board_vnstock._num(g("ask_3_volume")),
            "high": board_vnstock._num(g("highest")), "avg": board_vnstock._num(g("avg_match_price")),
            "low": board_vnstock._num(g("lowest")),
            "foreignBuy": board_vnstock._num(g("foreign_buy_volume")) or 0,
            "foreignSell": board_vnstock._num(g("foreign_sell_volume")) or 0,
            "raw": raw,
        })
    t_loop = (time.perf_counter() - t0) * 1000.0
    return t_extract, t_loop

print("Warming up...")
for _ in range(5):
    benchmark_breakdown()

extracts, loops = [], []
for _ in range(50):
    te, tl = benchmark_breakdown()
    extracts.append(te)
    loops.append(tl)

print(f"F extraction time: mean={np.mean(extracts):.3f}ms, median={np.median(extracts):.3f}ms")
print(f"Loop body time:    mean={np.mean(loops):.3f}ms, median={np.median(loops):.3f}ms")
print(f"Total time:        mean={np.mean(extracts)+np.mean(loops):.3f}ms")

# Run cProfile on loop
profiler = cProfile.Profile()
profiler.enable()
for _ in range(20):
    benchmark_breakdown()
profiler.disable()
stats = pstats.Stats(profiler).sort_stats('cumulative')
stats.print_stats(25)
