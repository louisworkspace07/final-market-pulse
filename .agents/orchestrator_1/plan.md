# Execution Plan — Market Pulse Optimization

## Overview
Decomposed into 4 sequential milestones:
1. **Milestone 1 (M1)**: P0 Hotfixes (Realtime loop CPU throttling, single stock calculation trap, crawler polling locks).
2. **Milestone 2 (M2)**: P1 SQLite Optimization & N+1 Query Remediation (indexes, vectorized batch scoring, sector caching, window functions).
3. **Milestone 3 (M3)**: P2/P3 Concurrency, Async & Leak Prevention (`connect_readonly`, technical cache race, async db.js, quantum_lab job eviction, test baseline fix).
4. **Milestone 4 (M4)**: Verification & Guardrails (100% pytest pass across `market-pulse/tests` and `data-crawler/tests`, benchmark execution).

---

## Milestone 1: P0 Hotfixes
- **Worker 1 (`worker_m1`)**:
  - Implement `.tolist()` pre-extraction in `price-board/board_vnstock.py`.
  - Implement 260-bar single-symbol query in `market-pulse/modules/market_overview/tech_full.py:one()`.
  - Add single-symbol proxy shortcut in `market-pulse/gateway/app.py` for `/api/tech_full?symbols=...`.
  - Add in-memory 30s TTL cache with stale-while-revalidate and timeout=5s in `data-crawler/app.py`.
- **Reviewers (`reviewer_m1_1`, `reviewer_m1_2`)**:
  - Verify code correctness, backward compatibility, and test passing.
- **Challengers (`challenger_m1_1`, `challenger_m1_2`)**:
  - Verify performance speedup and latency guardrails empirically.
- **Auditor (`auditor_m1`)**:
  - Perform forensic integrity check (ensure genuine implementation, no dummy data).
- **Gate Check**: If all pass, mark M1 DONE and advance to M2.

---

## Milestone 2: P1 SQLite & N+1 Remediation
- **Worker 2 (`worker_m2`)**:
  - Add `idx_fin_stmt_item_period` and `idx_price_time` in `data-crawler/src/storage.py` (SCHEMA, `_migrate`, auto-init).
  - Implement batch vectorized scoring in `market-pulse/modules/business_health/scoring.py:score_all()`.
  - Implement `_sector_cache` and batch query in `data-crawler/src/peers.py:compute()`.
  - Implement SQLite window function in `market_technical.py:liquidity_concentration()`.
- **Reviewers, Challengers, Auditor, Gate Check**.

---

## Milestone 3: P2/P3 Concurrency, Async & Leak Prevention
- **Worker 3 (`worker_m3`)**:
  - Replace raw `sqlite3.connect` in reader modules with `modules.common.db.connect_readonly`.
  - Fix in-place cache mutation in `technical.py:board_stats`.
  - Implement async `fs.promises` in `econolens-chat/lib/db.js` and `server.js`.
  - Implement job eviction in `quantum_lab/api.py` and `orchestrator.py`.
  - Fix backward-compatible argument unpacking in `anomaly.py:_detect_symbol`.
- **Reviewers, Challengers, Auditor, Gate Check**.

---

## Milestone 4: Final Verification & Benchmarks
- Run full pytest suites:
  - `pytest market-pulse/tests` (183 tests)
  - `pytest data-crawler/tests` (128 tests)
- Run benchmark scripts:
  - `test_opt.py`
  - `market-pulse/profile_anomaly.py`
  - Measure latencies against all Acceptance Criteria.
- Produce Final Victory Report to Sentinel.
