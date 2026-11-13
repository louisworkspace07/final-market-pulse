# Handoff Report — Survey R2: P1 SQLite & N+1 Query Remediation

## 1. Observation

### Area 1: `data-crawler/src/storage.py` (BN-01, BN-02)
- **File location**: `data-crawler/src/storage.py:177-270`
- **Current schema and indexes observed via SQLite DDL query**:
  - `financials` table:
    - Primary key: `PRIMARY KEY (symbol, statement, item_id, period)`
    - Index: `idx_fin_symbol ON financials(symbol)`
    - Duplicate unique index created dynamically in `merge_financials` (line 376): `idx_fin_key ON financials(symbol, statement, item_id, period)`
    - Row count: **2,551,632 rows**.
  - `price` table:
    - Primary key: `PRIMARY KEY (symbol, time)`
    - Index: `idx_price_symbol ON price(symbol)`
    - Duplicate index created dynamically: `idx_price_key ON price(symbol, time)`
    - Row count: **765,787 rows**.
- **Benchmark / Query Plan observations**:
  - Query: `EXPLAIN QUERY PLAN SELECT symbol, value FROM financials WHERE statement = 'ratio' AND item_id = 'roe'`
    - Result: `(2, 0, 216, 'SCAN financials')` — **Full Table Scan across 2.55 million rows**.
    - Execution time on `market.db`: **3.77 seconds** for a single query.
  - Query: `EXPLAIN QUERY PLAN SELECT MAX(time) FROM price`
    - Result: `(3, 0, 214, 'SEARCH price USING COVERING INDEX idx_price_key')` — scans 765k entries in index.
- **Migration / Auto-init status**:
  - `storage.connect()` (lines 262-270) runs `conn.executescript(SCHEMA)` and `_migrate(conn)`.
  - `_migrate()` only checks `companies` columns and `crawl_state.attempts`. It does NOT ensure composite performance indexes.
  - `data-crawler/app.py` directly opens SQLite connections with `sqlite3.connect(f"file:{DB_PATH}?mode=ro", ...)` on startup and does not trigger `storage.connect()`.

---

### Area 2: `market-pulse/modules/business_health/scoring.py` (BN-03)
- **File location**: `market-pulse/modules/business_health/scoring.py:190-290`
- **N+1 Query Loop observed**:
  - `score_all(db_path: str)` (lines 270-289):
    ```python
    for r in companies.itertuples():
        fin = pd.read_sql(
            "select item_en, period, value from financials where symbol=?",
            con, params=(r.symbol,))
        s = score_company(fin, r.symbol, r.organ_name, r.exchange)
        if s:
            s["flow_score"] = flow_score(price_con, r.symbol)
            out.append(s)
    ```
  - Total companies evaluated: **1,531 companies**.
  - Number of queries: **1,531 `pd.read_sql` queries** on `financials` + **1,531 queries** on `price` in `flow_score` = **3,062 individual SQLite round-trip queries**!
  - Creates **1,531 pandas DataFrame instances** sequentially inside the Python loop.
  - Total run time: **60 to 75 seconds**.
- **Batch Query & Vectorization observations**:
  - Aliases required by `ITEMS` (lines 28-41): 11 metrics with 16 distinct string aliases (`TOTAL ASSETS`, `Liabilities`, `Net sales`, etc.).
  - Batch query for all required financial items:
    ```sql
    SELECT symbol, item_en, period, value FROM financials
    WHERE item_en IN (?, ?, ...) AND length(period) = 4
    ```
    - Fetches **53,358 rows in 0.73s** for all 1,531 companies!
  - Grouping into an in-memory dictionary `fin_by_sym` takes **0.05s**.
  - Price data needed for `flow_score`: last 20 daily sessions per symbol.
    ```sql
    WITH ranked AS (
        SELECT symbol, close, volume,
               ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC) as rn
        FROM price
    )
    SELECT symbol, close, volume FROM ranked WHERE rn <= 20
    ```
    - Fetches **31,001 rows in 1.02s**!
  - Passing pre-computed pivots to scoring without DataFrame overhead completes all 1,531 companies in **< 0.1s**. Total runtime drops from 60s+ to **~1.8s**.
- **Callers and Tests**:
  - Callers: `market-pulse/run_pipeline.py:68` and `scoring.py:295`.
  - Tests: `market-pulse/tests/test_health_flags.py` (19 test cases covering `score_company`, `_f_score`, `flow_score`, `watch_flags`). All 19 pass.
  - Output dict schema has 17 fields: `symbol`, `name`, `exchange`, `year`, `group`, `total_assets_b`, `roa`, `roe`, `debt_ratio`, `z_score`, `z_zone`, `f_score`, `f_max`, `f_checks`, `health_score`, `watch_flags`, `flow_score`.

---

### Area 3: `data-crawler/src/peers.py` (BN-04)
- **File location**: `data-crawler/src/peers.py:120-203`
- **N+1 Query Loop observed**:
  - `compute(conn, symbol)` fetches peers for the sector: `peers = [r[0] for r in conn.execute("SELECT symbol FROM companies WHERE sector=?", (sector,)).fetchall()]`.
  - In sectors with 80-100 peers (e.g. Basic Resources has 103 peers):
    - Lines 156-167: For each peer `sym` (103) x each `RATIO_ITEMS` (5): calls `_peer_value` -> calls `_latest_ratio` = **515 queries**.
    - If ratio missing: calls `_raw_derived` = 3 raw BCTC queries.
    - Lines 176-178: Calls `_peer_value` 5 more times for target `symbol`.
    - Lines 187-190 (`n_with_data`):
      ```python
      n_with_data = sum(
          1 for p in peers
          if any(_peer_value(conn, p, k, it, raw_cache)[0] is not None
                 for k, it in RATIO_ITEMS.items()))
      ```
      Calls `_peer_value` **AGAIN for all peers x 5 items**! Because `_latest_ratio` is unmemoized, this triggers **another 515 queries**.
    - Total: **1,030+ queries** for a single stock view when sector has 100 peers!
- **Sector Batching & Caching observations**:
  - Notice that all sector-level aggregates (`benchmark`, `samples`, `raw_used`, `n_with_data`, `peer_values` pool) are **identical for all companies in the same sector**. Only `self_vals`, `position`, `peer_pts` (excluding self), and `pct` depend on the target symbol.
  - Single batch SQL query for all sector ratios:
    ```sql
    SELECT symbol, item_id, period, value FROM financials
    WHERE symbol IN (SELECT symbol FROM companies WHERE sector = ?)
      AND statement = 'ratio'
      AND item_id IN ('pe_ratio', 'pb_ratio', 'roe', 'net_margin', 'debt_to_equity')
      AND value IS NOT NULL
    ```
    - Execution time for Basic Resources (103 peers, 3,425 rows): **0.024s (24 milliseconds)**!
  - In-memory `_sector_cache` with TTL 300s reduces repeated calls for any stock in that sector to **0.0001s (0 queries)**.
- **Callers and Tests**:
  - Callers: `data-crawler/src/analyzer.py:1594`, `market-pulse/modules/stock_page/api.py:267, 708`, `market-pulse/modules/market_overview/context_builder.py:168, 234`.
  - Tests: `data-crawler/tests/test_peers.py` (7 test cases). Tests use `:memory:` SQLite connections with distinct test fixtures. All 7 pass.

---

### Area 4: `market-pulse/modules/market_overview/market_technical.py` (BN-08)
- **File location**: `market-pulse/modules/market_overview/market_technical.py:26-30, 417-461`
- **752k Full Scan observed**:
  - `liquidity_concentration(db_path: str, board_rows: list[dict] | None = None)` (lines 431-446):
    ```python
    if not turnover:
        con = sqlite3.connect(db_path)
        try:
            df = pd.read_sql_query(
                "SELECT symbol, time, close, volume FROM price ORDER BY symbol, time", con)
        finally:
            con.close()
            
        last_rows = {}
        for r in df.itertuples(index=False):
            last_rows[r.symbol] = r
            
        for sym, r in last_rows.items():
            if r.close and r.volume:
                turnover[sym] = float(r.close) * float(r.volume)
    ```
  - Reads **765,787 rows** into a Pandas DataFrame consuming ~300 MB RAM and **2.65 seconds** (measured in `test_opt.py`), only to discard 764,236 rows and keep 1,551 rows!
  - Also opens connection read-write (`sqlite3.connect(db_path)`), triggering lock conflicts (BN-05).
- **Window Function verification & critical filter discovery**:
  - SQLite Window Function tested:
    ```sql
    WITH ranked AS (
        SELECT symbol, close, volume,
               ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC) as rn
        FROM price
    )
    SELECT symbol, close, volume FROM ranked WHERE rn = 1;
    ```
  - Verification test:
    - If `WHERE close IS NOT NULL AND volume IS NOT NULL` is placed inside the CTE, 524 symbols produce mismatched results because symbols that had 0 volume in their latest session look back to older sessions weeks ago, altering the market turnover snapshot.
    - If the CTE takes `rn = 1` across all rows in `price`, and then filters `if close and vol:` in Python, **Discrepancies = 0 across all 984 symbols**! Exact 1:1 numerical parity with the existing pandas implementation.
  - Runtime drops from **2.65s to 1.14s**, data transferred drops from **765,787 rows to 1,551 rows (99.8% reduction)**, zero Pandas allocation.
- **Callers and Tests**:
  - Callers: `market-pulse/gateway/app.py:897`, `market-pulse/modules/market_overview/orchestrator.py:520`, `test_opt.py`.
  - Tests: `market-pulse/tests/test_market_technical.py` (`test_liquidity_concentration_from_price`, `test_liquidity_concentration_live_board`). All 8 pass.

---

## 2. Logic Chain

1. **Area 1 Index Logic**:
   - `financials` queries filtering by `statement` and `item_id` cannot use `PRIMARY KEY (symbol, statement, item_id, period)` because `symbol` is the leading column. Without an index starting with `statement`, SQLite must execute a full table scan over 2.55 million rows.
   - Adding `CREATE INDEX IF NOT EXISTS idx_fin_stmt_item_period ON financials(statement, item_id, period, value)` provides a covering composite index for ratio and statement filtering.
   - `price` table has PK `(symbol, time)`. To find `MAX(time)` across the whole market, SQLite must scan all 765,787 rows of the composite index. Adding `CREATE INDEX IF NOT EXISTS idx_price_time ON price(time)` allows an immediate $O(1)$ B-Tree lookup.
   - Adding these to `SCHEMA` and `_migrate()` ensures they are applied whenever `storage.connect()` runs. Calling `storage.connect().close()` on `data-crawler/app.py` startup guarantees automatic database initialization.

2. **Area 2 Scoring Logic**:
   - In `score_all()`, 1,531 individual queries on `financials` and 1,531 queries on `price` are executed. Network/file descriptor and cursor overhead dominate execution time.
   - All companies require the same 16 item aliases for 4-digit annual periods (`length(period) = 4`). A single SQL query with `item_en IN (...)` retrieves all required data (53k rows) in 0.73s.
   - Price data for `flow_score` only requires the latest 20 trading rows per symbol. A window function retrieves these (31k rows) in 1.02s.
   - Scoring arithmetic (Altman Z'', Piotroski F, ROA/ROE) only operates on scalar numbers in a `(year, item_en)` dictionary. By decomposing `score_company` into an in-memory core `_score_company_core(pivot, years, symbol, name, exchange)`, we avoid creating 1,531 DataFrame objects, dropping total execution time from 60s+ to ~1.8s while preserving exact schema.

3. **Area 3 Peer Comparison Logic**:
   - For a given sector, peer ratios and raw fundamentals are identical regardless of which company in that sector is being viewed.
   - Running 5 individual queries for each peer in `compute()`, plus re-running them in `n_with_data`, generates 400-1000+ queries per stock view.
   - An in-memory cache `_sector_cache` with a 300-second TTL stores the sector metrics. On a cache hit, `compute()` only performs local lookups for the target symbol and computes percentiles ($< 0.1$ms, 0 queries).
   - On a cache miss, replacing individual peer queries with a single batch query `WHERE symbol IN (SELECT symbol FROM companies WHERE sector = ?)` fetches all ratio data in 24ms.
   - Keying cache by `(db_path, sector)` and bypassing or isolating cache for `:memory:` connections ensures 100% test isolation for `test_peers.py`.

4. **Area 4 Liquidity Concentration Logic**:
   - `liquidity_concentration` only needs the single latest `(close, volume)` for each symbol.
   - Reading 765,787 rows into Pandas and iterating with `itertuples` to find the last row is an unnecessary $O(N)$ memory and CPU burden.
   - Using `ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC) as rn` inside SQLite offloads the deduplication to SQLite's native C implementation and transfers only 1,551 rows.
   - To match the existing semantics perfectly (handling 0-volume sessions), the `rn = 1` partition must not filter out NULL/zero volume in the CTE, but rather filter `if close and vol:` in Python. This achieves exact 0 discrepancies against the legacy implementation.

---

## 3. Caveats

- **SQLite Locking During Index Creation**: Creating `idx_fin_stmt_item_period` on 2.55 million rows and `idx_price_time` on 765k rows on `market.db` takes ~3-5 seconds of write time. It should be executed once via `storage.connect()` or a migration step while no crawler is actively holding an exclusive write lock.
- **SQLite Window Function Support**: Requires SQLite $\ge 3.25.0$. Verified: current Python environment uses SQLite 3.53.1, well above the requirement.
- **Cache Invalidation in `peers.py`**: A 300s TTL cache means that if BCTC crawler imports new ratios for a company, peer medians for that sector will reflect updates within 5 minutes. This is standard and fully aligned with BN-04 requirements. A `clear_sector_cache()` function should be exposed for tests and manual invalidation.
- **Read-Only Connections**: All query functions must use `connect_readonly` (`mode=ro`) to prevent SQLite reserved locks from blocking concurrent writers.

---

## 4. Conclusion & Concrete Implementation Recommendations

### Recommendation 1: `data-crawler/src/storage.py`
Add composite index and price time index to `SCHEMA` and `_migrate()`, and ensure auto-init on `app.py` startup:

```python
# Diff in data-crawler/src/storage.py:
# In SCHEMA (around line 197 & 223):
SCHEMA = """
...
CREATE TABLE IF NOT EXISTS financials (
    symbol     TEXT,
    statement  TEXT,
    item_id    TEXT,
    item       TEXT,
    item_en    TEXT,
    period     TEXT,
    value      REAL,
    PRIMARY KEY (symbol, statement, item_id, period)
);
CREATE INDEX IF NOT EXISTS idx_fin_symbol ON financials(symbol);
CREATE INDEX IF NOT EXISTS idx_fin_stmt_item_period ON financials(statement, item_id, period, value);
...
CREATE TABLE IF NOT EXISTS price (
    symbol  TEXT,
    time    TEXT,
    open    REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (symbol, time)
);
CREATE INDEX IF NOT EXISTS idx_price_symbol ON price(symbol);
CREATE INDEX IF NOT EXISTS idx_price_time ON price(time);
...
"""

# In _migrate(conn: sqlite3.Connection):
def _migrate(conn: sqlite3.Connection) -> None:
    existing = {r[1] for r in conn.execute("PRAGMA table_info(companies)")}
    for col, typ in _MIGRATE_COLS.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE companies ADD COLUMN {col} {typ}")
    state_cols = {r[1] for r in conn.execute("PRAGMA table_info(crawl_state)")}
    if "attempts" not in state_cols:
        conn.execute("ALTER TABLE crawl_state ADD COLUMN attempts INTEGER DEFAULT 0")
    # P1 Index migrations
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fin_stmt_item_period ON financials(statement, item_id, period, value)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_price_time ON price(time)")

# In data-crawler/app.py startup (around line 1805):
def _init_db_indexes():
    try:
        from src import storage
        storage.connect().close()
    except Exception as e:
        print(f"Warning: could not run storage.connect auto-init: {e}")
```

---

### Recommendation 2: `market-pulse/modules/business_health/scoring.py`
Refactor `score_company` to extract an in-memory core `_score_company_core`, batch-load 3 years of financial data + batch prices in `score_all()`:

```python
# Diff in market-pulse/modules/business_health/scoring.py:
from collections import defaultdict
from modules.common.db import connect_readonly

def _score_company_core(pivot: dict, years: list[int], symbol: str, name: str, exchange: str) -> dict | None:
    if not years:
        return None
    y1 = years[-1]
    y0 = years[-2] if len(years) >= 2 else None
    ym1 = years[-3] if len(years) >= 3 else None

    g = lambda k, y=y1: _get(pivot, y, k)
    ta, liab, equity = g("total_assets"), g("liabilities"), g("equity")
    if not ta or ta <= 0:
        return None

    ca, cl = g("current_assets"), g("current_liab")
    is_financial = ca is None or cl is None

    ni, cfo, ebit = g("net_income"), g("cfo"), g("ebit")
    retained, rev, gp = g("retained"), g("revenue"), g("gross_profit")

    roa = ni / ta if ni is not None else None
    roe = ni / equity if (ni is not None and equity) else None

    result = {
        "symbol": symbol, "name": name, "exchange": exchange,
        "year": int(y1), "group": "TCTC" if is_financial else "DN",
        "total_assets_b": round(ta / 1e9, 0),
        "roa": round(roa * 100, 2) if roa is not None else None,
        "roe": round(roe * 100, 2) if roe is not None else None,
        "debt_ratio": round(liab / ta * 100, 1) if liab is not None else None,
    }

    if not is_financial and liab and liab > 0:
        x1 = (ca - cl) / ta
        x2 = (retained or 0) / ta
        x3 = (ebit or 0) / ta
        x4 = (equity or 0) / liab
        z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
        result["z_score"] = round(z, 2)
        result["z_zone"] = "An toàn" if z > 2.6 else ("Xám" if z >= 1.1 else "Nguy hiểm")
    else:
        result["z_score"] = None
        result["z_zone"] = "N/A (tổ chức tài chính)"

    f, f_max, checks = _f_score(pivot, y1, y0, is_financial)
    result["f_score"] = f
    result["f_max"] = f_max
    result["f_checks"] = checks

    parts = []
    if result["z_score"] is not None:
        parts.append(min(max(result["z_score"] / 5.0, 0), 1) * 100)
    if f_max > 0:
        parts.append(f / f_max * 100)
    if roa is not None:
        parts.append(min(max(roa / 0.15, 0), 1) * 100)
    result["health_score"] = round(float(np.mean(parts)), 1) if parts else None

    prior_f = None
    if ym1 is not None:
        prev = _f_score(pivot, y0, ym1, is_financial)
        if prev is not None and prev[1] > 0:
            prior_f = prev[0]
    result["watch_flags"] = watch_flags(result["z_zone"], result["f_score"], prior_f)
    result["flow_score"] = None
    return result

def score_company(fin: pd.DataFrame, symbol: str, name: str, exchange: str) -> dict | None:
    fin = _latest_years(fin, 3)
    if fin.empty:
        return None
    pivot = {(r.year, r.item_en): r.value for r in fin.itertuples()}
    years = sorted({r.year for r in fin.itertuples()})
    return _score_company_core(pivot, years, symbol, name, exchange)

def score_all(db_path: str) -> list[dict]:
    con = connect_readonly(db_path)
    try:
        companies = con.execute(
            "SELECT symbol, organ_name, exchange FROM companies WHERE symbol IN "
            "(SELECT DISTINCT symbol FROM financials)"
        ).fetchall()

        alias_list = list({a for sub in ITEMS.values() for a in sub})
        ph = ",".join(["?"] * len(alias_list))
        fin_rows = con.execute(
            f"SELECT symbol, item_en, period, value FROM financials "
            f"WHERE item_en IN ({ph}) AND length(period) = 4",
            alias_list
        ).fetchall()

        price_rows = con.execute(
            "WITH ranked AS ("
            "    SELECT symbol, close, volume, "
            "           ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC) as rn "
            "    FROM price"
            ") SELECT symbol, close, volume FROM ranked WHERE rn <= 20"
        ).fetchall()
    finally:
        con.close()

    # Nhóm BCTC theo mã và năm
    fin_by_sym = defaultdict(lambda: defaultdict(dict))
    for sym, item_en, period, val in fin_rows:
        try:
            fin_by_sym[sym][int(period)][item_en] = val
        except ValueError:
            continue

    # Nhóm giá theo mã và tính flow_score trước
    price_by_sym = defaultdict(lambda: ([], []))
    for sym, close, vol in price_rows:
        price_by_sym[sym][0].append(close)
        price_by_sym[sym][1].append(vol)

    flow_scores = {
        sym: _flow_score(closes, vols)
        for sym, (closes, vols) in price_by_sym.items()
    }

    out = []
    for sym, organ_name, exchange in companies:
        years_dict = fin_by_sym.get(sym)
        if not years_dict:
            continue
        years = sorted(years_dict.keys())[-3:]
        pivot = {(y, item_en): val for y in years for item_en, val in years_dict[y].items()}
        s = _score_company_core(pivot, years, sym, organ_name, exchange)
        if s:
            s["flow_score"] = flow_scores.get(sym)
            out.append(s)

    out.sort(key=lambda x: (x["health_score"] is None, -(x["health_score"] or 0)))
    return out
```

---

### Recommendation 3: `data-crawler/src/peers.py`
Implement in-memory `_sector_cache` (TTL 300s) and batch SQL query for sector peers:

```python
# Diff in data-crawler/src/peers.py:
import time
from collections import defaultdict

_SECTOR_CACHE_TTL = 300.0  # 5 phút
_sector_cache: dict = {}   # (db_key, sector) -> {"ts": float, "data": dict}

def clear_sector_cache():
    """Xóa cache ngành (phục vụ test và refresh)."""
    _sector_cache.clear()

def _get_db_key(conn) -> str:
    try:
        rows = conn.execute("PRAGMA database_list").fetchall()
        for r in rows:
            if r[1] == "main" and r[2]:
                return r[2]
    except Exception:
        pass
    return f"mem_{id(conn)}"

def _load_sector_ratios_batch(conn, sector: str) -> dict[str, dict[str, float]]:
    """Nạp toàn bộ ratio mới nhất của các mã trong ngành bằng 1 query duy nhất."""
    rows = conn.execute(
        """SELECT symbol, item_id, period, value FROM financials
           WHERE symbol IN (SELECT symbol FROM companies WHERE sector = ?)
             AND statement = 'ratio'
             AND item_id IN ('pe_ratio', 'pb_ratio', 'roe', 'net_margin', 'debt_to_equity')
             AND value IS NOT NULL""",
        (sector,)).fetchall()
    
    # Gom theo (symbol, item_id) -> list of (period, value)
    grouped = defaultdict(lambda: defaultdict(list))
    for sym, item_id, period, val in rows:
        grouped[sym][item_id].append((period, val))

    latest = defaultdict(dict)
    for sym, item_dict in grouped.items():
        for item_id, pv_list in item_dict.items():
            years = [(p, v) for (p, v) in pv_list if _period_kind(p) == "year"]
            quarters = [(p, v) for (p, v) in pv_list if _period_kind(p) == "quarter"]
            chosen = years or quarters
            if chosen:
                chosen.sort(key=lambda pv: _period_key(pv[0]))
                latest[sym][item_id] = chosen[-1][1]
    return latest

def compute(conn, symbol: str) -> dict:
    row = conn.execute("SELECT sector FROM companies WHERE symbol=?", (symbol,)).fetchone()
    sector = row[0] if row and row[0] else None
    if not sector:
        return {"sector": None, "n_peers": 0, "benchmark": {}, "position": {}}

    db_key = _get_db_key(conn)
    cache_key = (db_key, sector)
    now = time.time()
    cached = _sector_cache.get(cache_key)

    if cached is None or (now - cached["ts"] >= _SECTOR_CACHE_TTL):
        peers = [r[0] for r in conn.execute(
            "SELECT symbol FROM companies WHERE sector=?", (sector,)).fetchall()]
        
        batch_ratios = _load_sector_ratios_batch(conn, sector)
        raw_cache: dict = {}
        samples: dict = {k: [] for k in RATIO_ITEMS}
        peer_pts_all: dict = {k: [] for k in RATIO_ITEMS}
        raw_used: dict = {k: 0 for k in RATIO_ITEMS}
        peer_values_map = defaultdict(dict)
        has_data_symbols = set()

        for sym in peers:
            for key, item in RATIO_ITEMS.items():
                v = batch_ratios.get(sym, {}).get(item)
                src = "ratio" if v is not None else None
                if v is not None and key in ("roe", "net_margin"):
                    v = _norm_pct(v)
                if v is None and key in _RAW_PATH:
                    rv = _raw_derived(conn, sym, raw_cache).get(key)
                    if rv is not None:
                        if key == "debt_to_equity":
                            rv = rv * 100.0
                        v, src = rv, "raw"

                peer_values_map[sym][key] = v
                if v is None:
                    continue
                has_data_symbols.add(sym)
                if key in ("pe", "pb") and v <= 0:
                    continue
                samples[key].append(v)
                peer_pts_all[key].append((sym, round(v, 2)))
                if src == "raw":
                    raw_used[key] += 1

        bench = {}
        for key, vals in samples.items():
            if vals:
                bench[key] = round(statistics.median(vals), 2)

        cached_data = {
            "peers": peers,
            "bench": bench,
            "samples": samples,
            "peer_pts_all": peer_pts_all,
            "raw_used": raw_used,
            "peer_values_map": peer_values_map,
            "n_peers": len(has_data_symbols),
        }
        _sector_cache[cache_key] = {"ts": now, "data": cached_data}
        cached = _sector_cache[cache_key]

    d = cached["data"]
    self_vals = d["peer_values_map"].get(symbol, {})
    position = {}
    for key, v in self_vals.items():
        if v is not None and key in d["bench"] and d["bench"][key]:
            if key in ("pe", "pb", "debt_to_equity"):
                position[key] = "thấp hơn ngành" if v < d["bench"][key] else "cao hơn ngành"
            else:
                position[key] = "cao hơn ngành" if v > d["bench"][key] else "thấp hơn ngành"

    peer_pts = {
        k: [{"sym": s, "value": v} for s, v in d["peer_pts_all"][k] if s != symbol]
        for k in RATIO_ITEMS
    }

    return {
        "sector": sector,
        "n_peers": d["n_peers"],
        "n_sector": len(d["peers"]),
        "benchmark": d["bench"],
        "self": self_vals,
        "position": position,
        "peer_values": {k: v for k, v in peer_pts.items() if v},
        "pct": _direction_pct(self_vals, d["samples"]),
        "sample_sizes": {k: len(v) for k, v in d["samples"].items()},
        "raw_derived_counts": d["raw_used"],
    }
```

---

### Recommendation 4: `market-pulse/modules/market_overview/market_technical.py`
Replace full scan in `liquidity_concentration()` with SQLite window function using `connect_readonly`:

```python
# Diff in market-pulse/modules/market_overview/market_technical.py:
from modules.common.db import connect_readonly

def liquidity_concentration(db_path: str, board_rows: list[dict] | None = None) -> dict:
    turnover = {}
    if board_rows:
        for r in board_rows:
            sym = r.get("symbol")
            mp, vol = r.get("matchPrice"), r.get("totalVol") or r.get("totalVolume")
            if sym and mp and vol:
                turnover[sym] = float(mp) * float(vol)
    if not turnover:
        con = connect_readonly(db_path)
        try:
            # Dùng Window Function lấy phiên mới nhất (rn = 1) cho mỗi mã,
            # tránh tải toàn bộ 752k dòng vào pandas DataFrame.
            rows = con.execute(
                "WITH ranked AS ("
                "    SELECT symbol, close, volume, "
                "           ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC) as rn "
                "    FROM price"
                ") SELECT symbol, close, volume FROM ranked WHERE rn = 1"
            ).fetchall()
        finally:
            con.close()

        for sym, close, vol in rows:
            if close and vol:
                turnover[sym] = float(close) * float(vol)

    if not turnover:
        return {"available": False}

    total = sum(turnover.values())
    top = sorted(turnover.items(), key=lambda kv: -kv[1])[:10]
    top10_val = sum(v for _, v in top)
    hhi = sum((v / total * 100) ** 2 for v in turnover.values()) if total else 0
    return {"available": True,
            "top10_pct": round(top10_val / total * 100, 1) if total else None,
            "hhi": round(hhi, 0),
            "n_symbols": len(turnover),
            "top10": [{"symbol": s, "pct": round(v / total * 100, 2)} for s, v in top],
            "live": bool(board_rows) and bool(turnover),
            "note": "% giá trị giao dịch top-10 mã trên toàn thị trường; cao = tiền dồn vào ít mã."}
```

---

## 5. Verification Method

### Test Commands to Run:
1. **Unit tests**:
   - `pytest market-pulse/tests/test_health_flags.py`
   - `pytest market-pulse/tests/test_market_technical.py`
   - `pytest data-crawler/tests/test_peers.py`
   - `pytest data-crawler/tests/test_storage.py`
   - Overall suite: `pytest market-pulse/tests` & `pytest data-crawler/tests`
2. **Benchmark scripts**:
   - `python test_opt.py`: verifies `liquidity_concentration` execution time drops from 2.65s to ~1.1s.
   - `python -c "import sys; sys.path.insert(0, 'market-pulse'); from modules.business_health.scoring import score_all; import time; t0=time.time(); scores=score_all('data-crawler/database/market.db'); print('score_all finished in', round(time.time()-t0, 2), 's, count:', len(scores))"`: verifies `score_all` drops from 60s+ to < 2s.
   - `python -c "import sys; sys.path.insert(0, 'data-crawler'); import sqlite3, time; from src import peers; c=sqlite3.connect('data-crawler/database/market.db'); t0=time.time(); [peers.compute(c, s) for s in ['HPG', 'VHM', 'FPT', 'SSI', 'MBB', 'DXG']]; print('6 stocks computed in', round(time.time()-t0, 4), 's')"`: verifies peer medians run in < 0.05s.
3. **Index Verification in SQLite**:
   - Run `EXPLAIN QUERY PLAN SELECT symbol, value FROM financials WHERE statement = 'ratio' AND item_id = 'roe'` and verify it prints `SEARCH financials USING INDEX idx_fin_stmt_item_period`.
   - Run `EXPLAIN QUERY PLAN SELECT MAX(time) FROM price` and verify it prints `SEARCH price USING INDEX idx_price_time`.
