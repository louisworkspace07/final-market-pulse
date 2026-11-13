# Milestone 1 Remediation Review Report

**Agent:** `reviewer_m1_retry`  
**Roles:** reviewer, critic  
**Date:** 2026-09-06T14:02:00Z  
**Target Milestone:** M1 (P0 Hotfixes: `price-board/board_vnstock.py`, `data-crawler/app.py`, `market-pulse/modules/market_overview/tech_full.py`)  
**Verdict:** **REQUEST_CHANGES**

---

## 1. Review Summary

| Metric / Component | Requirement | Worker Claim | Independent Measurement | Verdict |
|--------------------|-------------|--------------|-------------------------|---------|
| `price-board/board_vnstock.py` Realtime Loop | < 5.0 ms (p95 < 5ms) | mean: 3.935 ms, p95: 4.888 ms (PASS) | **mean: 4.407 - 5.464 ms, p95: 5.941 - 7.073 ms** | **FAIL** |
| `data-crawler/app.py` `/stats` Cache Hit Latency | < 2.0 ms | mean: 0.167 ms (PASS) | **mean: 0.205 - 0.241 ms, p95: 0.326 - 0.396 ms** | **PASS** |
| `data-crawler/app.py` `/health` Latency | < 2.0 ms | mean: 0.147 ms (PASS) | **mean: 0.161 - 0.379 ms, p95: 0.198 - 0.505 ms** | **PASS** |
| `data-crawler/app.py` Concurrency (20 threads) | 100% HTTP 200 OK | 200/200 OK (PASS) | **200/200 OK (0 errors, 0 dropped)** | **PASS** |
| `data-crawler/app.py` Stale-While-Revalidate | Graceful fallback on SQLite lock | PASS | **PASS (served stale cache with HTTP 200 OK)** | **PASS** |
| `tech_full.py:one()` Latency (5 symbols) | < 50.0 ms | 9.17 - 11.78 ms (PASS) | **10.01 - 14.91 ms (p95: 12.21 - 24.44 ms)** | **PASS** |
| `tech_full.py:one()` Edge Cases & Injection | Robust error handling | 100% PASS | **100% PASS (10/10 edge cases handled)** | **PASS** |
| Unit Test Suite (`pytest data-crawler/tests`) | 100% Pass | 131 passed in 3.73s | **131 passed in 3.69s** | **PASS** |
| Live vnstock Pricing & Raw Array Shape | 27 elements, correct types | 27 elements (PASS) | **27 elements (PASS)** | **PASS** |

---

## 2. Findings

### [Major] Finding 1: `board_vnstock.py` Loop Exceeds < 5.0ms Performance Threshold in Independent Verification
- **What:** Benchmark execution of `test_board_vnstock` in `scripts/verify_m1_challenger.py` fails the performance guardrail. The test explicitly reports `VERDICT for board_vnstock loop (< 5ms): FAIL` and outputs `"passed": false`.
- **Where:** `price-board/board_vnstock.py:216-300` (`parse_board_df`).
- **Why:**
  1. In independent runs over 100 iterations of 726 rows, the loop execution time measures:
     - Run 1: `mean = 4.407 ms`, `median = 4.292 ms`, `p95 = 5.941 ms` (> 5.0 ms threshold).
     - Run 2: `mean = 5.464 ms`, `median = 5.323 ms`, `p95 = 7.073 ms` (> 5.0 ms threshold).
     - Consecutive runs: `mean = 4.75 - 6.85 ms`, `p95 = 6.53 - 8.95 ms`.
  2. Profiling reveals that inside `parse_board_df`, executing `pc.get(...)` and `vc.get(...)` 25 times per row generates **18,150 Python method activations per 726-row cycle**, consuming ~2.0ms (36% of total runtime) solely in dictionary lookups.
  3. Combined with 24 list-index accesses `col[i]` per row in pure Python, bare dictionary allocation, and 27-element list allocation, the execution time regularly spills over the 5.0ms p95 threshold under standard Windows CPU scheduling.
  4. Worker claimed a passing run with `p95 = 4.888 ms`. While an unloaded single run may occasionally touch ~4.8ms (minimum observed is 2.45ms), the implementation is on a fragile borderline and fails reproducible verification.
- **Suggestion:**
  1. Bind `pc.get` and `vc.get` to local variable function pointers before the loop (`pc_get = pc.get`, `vc_get = vc.get`) to eliminate 18,150 attribute resolution operations.
  2. Iterate rows using `zip(sym_col, ref_col, ...)` rather than indexing 24 separate lists with `col[i]`.
  3. Pre-allocate or streamline dictionary and list construction.

### [Minor] Finding 2: Direct Dict Lookup on Raw Column Values Lacks Type Guard
- **What:** Direct dictionary get `pc.get(ref_col[i])` in line 221 can throw `TypeError` if an unhashable object is present.
- **Where:** `price-board/board_vnstock.py:221-255`.
- **Why:** While `_get_p(v)` wraps `_P_CACHE.get(v)` inside `try ... except TypeError: return None, ""`, line 221 executes `pc.get(ref_col[i])` directly outside any `try/except`. If upstream vnstock or pandas ever outputs an unhashable object (e.g. list, nested structure) for an unexpected column, the entire price board parsing will crash with an unhandled `TypeError`.
- **Suggestion:** Rely on `_get_p(v)` or wrap the lookup in a type guard.

### [Minor] Finding 3: Concurrency Race in Probe Cache Updating Flag
- **What:** `_HEALTH_PROBE_UPDATING` flag is checked and modified outside the mutex `_HEALTH_PROBE_LOCK`.
- **Where:** `data-crawler/app.py:642-645`.
- **Why:** In `_get_health_probes()`:
  ```python
  if (expired or force) and not _HEALTH_PROBE_UPDATING:
      _HEALTH_PROBE_UPDATING = True
      t = threading.Thread(target=_probe_health_services, daemon=True)
      t.start()
  ```
  When cache expires and multiple concurrent requests arrive simultaneously across multiple Flask worker threads, multiple threads can observe `_HEALTH_PROBE_UPDATING == False` at the same time and spawn redundant background probe threads.
- **Suggestion:** Move the check and assignment of `_HEALTH_PROBE_UPDATING` inside the `with _HEALTH_PROBE_LOCK:` block.

---

## 3. Verified Claims

1. **`data-crawler/app.py` `/health` Latency (< 2.0 ms):**
   - **Claim:** Worker claimed background daemon probe caching reduced `/health` latency from 8,156ms to 0.147ms.
   - **Verified:** Independently executed 20 `/health` calls: mean = **0.161 - 0.379 ms**, p95 = **0.198 - 0.505 ms**.
   - **Status:** **PASS**. The Windows dual-stack IPv4/IPv6 socket blocking timeout is completely eliminated.

2. **`data-crawler/app.py` `/stats` Latency (< 2.0 ms):**
   - **Claim:** Worker claimed in-memory TTL caching reduced `/stats` latency to 0.167ms.
   - **Verified:** Independently executed 100 `/stats` calls: mean = **0.205 - 0.241 ms**, p95 = **0.326 - 0.396 ms**.
   - **Status:** **PASS**.

3. **`data-crawler/app.py` Stale-While-Revalidate & Concurrency:**
   - **Claim:** Under simulated SQLite lock (`sqlite3.OperationalError: database is locked`), `/stats` and `/health` serve stale cache without errors.
   - **Verified:** Under mocked `sqlite3.connect` raising `OperationalError` with expired timestamp, endpoints returned HTTP 200 OK with cached data. 20 concurrent threads running 200 requests executed with 100% HTTP 200 OK.
   - **Status:** **PASS**.

4. **`market-pulse/modules/market_overview/tech_full.py:one()` Latency (< 50.0 ms):**
   - **Claim:** Cold query for single symbol with 260-bar limit executes in ~9-11ms.
   - **Verified:** Tested 5 core symbols (FPT, HPG, VNM, VIC, SSI) with cold cache: mean = **10.01 - 14.91 ms**, p95 = **12.21 - 24.44 ms** (well below 50ms guardrail). Warm cache hit latency: **0.0008 ms**.
   - **Status:** **PASS**.

5. **`tech_full.py:one()` Edge Cases & SQL Injection:**
   - **Claim:** Safely handles non-existent symbols, SQL injection, empty/whitespace strings, symbols with < 60 bars, and corrupt data.
   - **Verified:** All 10 edge cases tested in `verify_m1_challenger.py` passed with expected outputs (None or skipped reasons).
   - **Status:** **PASS**.

6. **Unit Test Suite (`data-crawler/tests`):**
   - **Claim:** 131 tests pass.
   - **Verified:** Ran `py -3.12 -m pytest data-crawler/tests`: **131 passed in 3.69s**.
   - **Status:** **PASS**.

7. **Integrity Assessment:**
   - **Hardcoded results in source:** None found.
   - **Facade/Dummy implementations:** None found. Real optimizations were implemented.
   - **Shortcuts:** None found.
   - **Attestation/Verification:** Worker reported a borderline passing run (`p95: 4.888ms`), but did not adequately test for variance or multi-run reproducibility. Not classified as intentional fabrication, but as an unreproducible borderline pass that fails independent verification.

---

## 4. Adversarial Stress-Test Results

| Scenario | Input / Attack | Expected Behavior | Actual Behavior | Result |
|----------|----------------|-------------------|-----------------|--------|
| `board_vnstock` missing columns | DataFrame without `bid_3_price`, `foreign_buy_volume` | Fill with None / default | Filled [None] * n, returned 726 rows without crashing | PASS |
| `board_vnstock` empty DF | 0-row DataFrame | Return empty list | Returned `[]` immediately | PASS |
| `board_vnstock` NaN / None | NaN `match_price`, `ref_price`, `symbol` | Skip row if symbol is None, format NaNs | Valid rows processed, NaN symbol skipped | PASS |
| `board_vnstock` loop latency stability | 100 iterations x 726 rows under normal system conditions | mean < 5.0ms AND p95 < 5.0ms | mean: 4.41-5.46ms, p95: 5.94-7.07ms (exceeds 5ms) | **FAIL** |
| `tech_full` SQL Injection | `"FPT'; DROP TABLE price; --"` | Return None, do not execute injection | Returned None, `price` table intact | PASS |
| `tech_full` Real DB symbols < 60 bars | TAH (2), ANI (19), NHD (26), FUEMITEC (39), CLI (48) | Return skipped dictionary with reason | Returned `{"symbol": sym, "skipped": "... phiên < 60"}` | PASS |
| `tech_full` NULL prices | Synthetic 70 bars with high/low = NULL | Return skipped dictionary | Returned `{"symbol": sym, "skipped": "thiếu giá cao/thấp trong lịch sử"}` | PASS |
| `tech_full` Zero volume | Synthetic 70 bars with volume = 0 | Compute indicators without ZeroDivisionError | Computed without ZeroDivisionError | PASS |
| `/health` Offline external services | Local API & Chrome CDP offline | Respond in < 2.0ms using cached probes | Responded in 0.161 - 0.379 ms | PASS |
| `/stats` Database lock collision | SQLite OperationalError under expired cache | Serve stale cache with HTTP 200 | Served stale cache with HTTP 200 OK | PASS |

---

## 5. Logic Chain

1. Prompt constraint and Challenger benchmark specification require `price-board/board_vnstock.py` realtime loop execution time to achieve `< 5.0 ms for 726 rows` (with both `mean < 5.0ms` and `p95 < 5.0ms`).
2. Worker reported `p95 = 4.888 ms` in `worker_m1_retry/handoff.md`.
3. Independent execution of `scripts/verify_m1_challenger.py` across multiple runs produced:
   - Run 1: `mean = 4.407 ms`, `p95 = 5.941 ms` -> `VERDICT for board_vnstock loop (< 5ms): FAIL`
   - Run 2: `mean = 5.464 ms`, `p95 = 7.073 ms` -> `VERDICT for board_vnstock loop (< 5ms): FAIL`
4. Because the challenger test suite explicitly evaluates `passed = mean_t < 5.0 and p95_t < 5.0`, the test suite fails with `"passed": false`.
5. Although `data-crawler/app.py` `/health` and `/stats` optimizations and `tech_full.py:one()` optimizations are completely successful, high quality, and verified, the failure of `board_vnstock.py` to reliably meet the `< 5ms` guardrail requires a quick optimization turn.
6. Therefore, the verdict is **REQUEST_CHANGES**.

---

## 6. Caveats

- In the original user prompt (`ORIGINAL_REQUEST.md:45`), the high-level system requirement is: *"Vòng lặp price-board/board_vnstock.py tiêu thụ < 5% CPU trên mỗi chu kỳ làm mới 1s"*. An execution time of 5.5ms consumes ~0.55% CPU per 1,000ms cycle, which is well within the 5% system CPU budget. However, because Milestone 1 and the empirical Challenger verification script explicitly enforce the strict `< 5.0 ms` latency threshold (including p95), the benchmark currently records a failure.
- The optimization needed to push `board_vnstock.py` well under 4ms (e.g. down to 2.5 - 3.5ms) is straightforward: localizing method references (`pc_get = pc.get`, `vc_get = vc.get`) and iterating with `zip()` instead of 24 list index lookups.

---

## 7. Conclusion

**Verdict: REQUEST_CHANGES**

The remediation worker resolved the critical blocking socket issue in `data-crawler/app.py` (`/health` now responds in ~0.2ms instead of 8,156ms) and verified `tech_full.py:one()` with 100% test pass. However, `price-board/board_vnstock.py` realtime loop execution time is right on the boundary and fluctuates between 4.4ms and 5.5ms mean (p95: 5.9ms - 7.1ms), failing the `< 5.0 ms` challenger threshold in independent runs.

Worker must apply additional micro-optimizations to `parse_board_df` in `price-board/board_vnstock.py` (e.g. local function binding for `pc.get`/`vc.get`, row iteration via `zip()`) to bring the execution time stably below 4.0ms across all percentiles.

---

## 8. Verification Method

To reproduce:
```powershell
py -3.12 scripts/verify_m1_challenger.py
```
Observe that while Tests 2, 3, and 4 pass 100%, Test 1 prints:
`VERDICT for board_vnstock loop (< 5ms): FAIL` with `p95 > 5.0 ms`.
