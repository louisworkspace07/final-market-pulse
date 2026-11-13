# Project: Market Pulse Performance Optimization & Bottleneck Remediation

## Architecture
Market Pulse consists of 4 main multi-process services and an underlying SQLite database (`market.db`, 840MB, 3.4M+ records):
- **`market-pulse` (Gateway :9999)**: Flask API, unified dashboard, quantitative analytics (SARIMAX, QAOA PennyLane, Technical Analysis, Business Health Scoring).
- **`data-crawler` (:5000)**: Ingests BCTC, financial statements, news, events, price history; writes to `market.db`.
- **`price-board` (:5555)**: Realtime price board (vnstock / Playwright) + CDP Gemini.
- **`econolens-chat` (:3333)**: Express Node.js chat service with personas & JWT.

### Data Flow & Shared Interfaces
- Readers query `market.db` using read-only WAL mode (`mode=ro`).
- Writers (data crawler ingest & price updates) commit transactions to `market.db`.
- Gateway aggregates endpoints from `price-board` (:5555), `data-crawler` (:5000), and `econolens-chat` (:3333).

---

## Feature Inventory
Every feature and bottleneck remediation task identified in Survey phase mapped to a milestone:

| # | Feature / Remediation Task | Description | Milestone | Source |
|---|----------------------------|-------------|-----------|--------|
| 1 | `board_vnstock.py` Realtime Loop (BN-06) | Replace 18,150 calls/sec to `list(Series)[i]` with `.tolist()` extraction before loop | M1 | Survey / BN-06 |
| 2 | `tech_full.py:one()` 260-Bar Query (BN-07) | Dedicated query for single symbol with 260 bars limit instead of 752k full market scan | M1 | Survey / BN-07 |
| 3 | `data-crawler/app.py` /stats & /health Caching (BN-02) | In-memory 30s TTL cache with stale-while-revalidate and timeout=5s to eliminate locked error | M1 | Survey / BN-02 |
| 4 | `storage.py` Composite Indexes (BN-01, BN-02) | Add `idx_fin_stmt_item_period` and `idx_price_time` to SCHEMA, `_migrate()`, and startup | M2 | Survey / BN-01, BN-02 |
| 5 | `scoring.py:score_all()` Vectorized Batch Query (BN-03) | Replace 3,062 N+1 queries with single batch query for 3-year BCTC and price window function | M2 | Survey / BN-03 |
| 6 | `peers.py:compute()` In-Memory Sector Cache (BN-04) | Add `_sector_cache` (TTL 300s) + batch SQL `WHERE symbol IN (...)` to remove 400-1000 queries/view | M2 | Survey / BN-04 |
| 7 | `market_technical.py:liquidity_concentration()` (BN-08) | Use SQLite Window Function `ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC)` | M2 | Survey / BN-08 |
| 8 | Reader SQLite `connect_readonly` Standardization (BN-05) | Standardize 22 raw `sqlite3.connect` calls across reader modules to `connect_readonly(mode=ro)` | M3 | Survey / BN-05 |
| 9 | `technical.py` Cache Race Condition (BN-09) | Shallow-copy rows in `board_stats` and add threading locks around `_board_cache` updates | M3 | Survey / BN-09 |
| 10 | `econolens-chat/lib/db.js` Async File I/O (BN-12) | Convert synchronous `fs.writeFileSync` / `renameSync` to `fs.promises` with Windows retry | M3 | Survey / BN-12 |
| 11 | `quantum_lab/api.py` Job Eviction (BN-15) | Thread-safe LRU/TTL eviction (max 50 jobs, TTL 30 mins) in `quantum_lab` and `orchestrator.py` | M3 | Survey / BN-15 |
| 12 | Test Suite Baseline & Anomaly Signature Fix | Fix `_detect_symbol` parameter compatibility in `anomaly.py` and verify 100% pytest pass | M3 | Survey / Baseline |
| 13 | Comprehensive Verification & Benchmarking | Execute all test suites (`market-pulse`, `data-crawler`) and benchmark scripts (`test_opt.py`, etc.) | M4 | Survey / Acceptance |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | P0 Hotfixes (Realtime & Latency) | `price-board/board_vnstock.py`, `tech_full.py:one()`, `data-crawler/app.py` (/stats, /health) | None | IN_PROGRESS |
| M2 | P1 SQLite Optimization & N+1 Remediation | `storage.py` indexes, `scoring.py:score_all()`, `peers.py:compute()`, `market_technical.py:liquidity_concentration()` | M1 | PLANNED |
| M3 | P2/P3 Concurrency, Async & Leak Prevention | `connect_readonly` in readers, `technical.py` cache race, `db.js` async fs, `quantum_lab` job eviction, `anomaly.py` test fix | M2 | PLANNED |
| M4 | Final Verification & Benchmarks | Full test suite execution (100% pass), benchmark runs, latency & CPU verification | M3 | PLANNED |

---

## Interface Contracts

### `tech_full.py:one(db_path: str, symbol: str) -> dict | None`
- **Input**: `db_path: str`, `symbol: str`
- **Output**: Dictionary with exact 15 canonical keys: `symbol`, `price`, `bars`, `sr`, `vbp`, `rsi14`, `ma20`, `ma50`, `above_ma20`, `vol_vs_20`, `hi52`, `lo52`, `pct_from_hi52`, `pct_from_lo52`, `pos`.
- **Fallback**: When < 60 bars or missing data: `{"symbol": sym, "skipped": reason}`.

### `scoring.py:score_all(db_path: str) -> list[dict]`
- **Input**: `db_path: str`
- **Output**: List of dictionaries sorted by `health_score` descending.
- **Fields per dict**: `symbol`, `name`, `exchange`, `year`, `group`, `total_assets_b`, `roa`, `roe`, `debt_ratio`, `z_score`, `z_zone`, `f_score`, `f_max`, `f_checks`, `health_score`, `watch_flags`, `flow_score`.

### `peers.py:compute(conn: sqlite3.Connection, symbol: str) -> dict`
- **Input**: `conn: sqlite3.Connection`, `symbol: str`
- **Output**: Dictionary with keys: `sector`, `n_peers`, `n_sector`, `benchmark`, `self`, `position`, `peer_values`, `pct`, `sample_sizes`, `raw_derived_counts`.

### `market_technical.py:liquidity_concentration(db_path: str, board_rows: list[dict] | None = None) -> dict`
- **Input**: `db_path: str`, `board_rows: list[dict] | None`
- **Output**: Dictionary with keys: `available`, `top10_pct`, `hhi`, `n_symbols`, `top10`, `live`, `note`.

---

## Code Layout (Exclusive Write Boundaries)

To prevent file collision during parallel/sequential iterations:
- **M1 Worker**:
  - `price-board/board_vnstock.py`
  - `market-pulse/modules/market_overview/tech_full.py`
  - `market-pulse/gateway/app.py` (lines 800-815 for single-symbol tech_full proxy)
  - `data-crawler/app.py`
- **M2 Worker**:
  - `data-crawler/src/storage.py`
  - `market-pulse/modules/business_health/scoring.py`
  - `data-crawler/src/peers.py`
  - `market-pulse/modules/market_overview/market_technical.py`
- **M3 Worker**:
  - `market-pulse/modules/common/db.py`
  - `market-pulse/modules/copilot/facts.py`
  - `market-pulse/modules/macro_forecast/models.py`
  - `market-pulse/modules/market_overview/anomaly.py`
  - `market-pulse/modules/market_overview/collector.py`
  - `market-pulse/modules/market_overview/context_builder.py`
  - `market-pulse/modules/market_overview/technical.py`
  - `market-pulse/modules/portfolio/analyzer.py`
  - `market-pulse/modules/quantum_finance/portfolio_qubo.py`
  - `market-pulse/modules/macro_ai/collector.py`
  - `market-pulse/modules/stock_page/api.py`
  - `market-pulse/modules/stock_page/chart_data.py`
  - `market-pulse/modules/quantum_lab/api.py`
  - `market-pulse/modules/market_overview/orchestrator.py`
  - `econolens-chat/lib/db.js`
  - `econolens-chat/server.js`
