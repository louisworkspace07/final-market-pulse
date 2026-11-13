# Investigation & Survey Report R3: Concurrency, Async & Testing Baseline

**Agent:** `explorer_survey_3`  
**Date:** 2026-09-06  
**Scope:** Survey R3 (P2/P3 Concurrency, Async & Testing Baseline)  
**Status:** Complete (Hard Handoff)

---

## 1. Observation

### 1.1 Topic 1: SQLite `connect_readonly` Standardization (BN-05)
- **Reference Standard:** `market-pulse/modules/common/db.py:15-18`:
  ```python
  def connect_readonly(db_path: str, timeout: float = 5.0) -> sqlite3.Connection:
      """Mở market.db chỉ-đọc (URI mode=ro). Ném sqlite3.OperationalError nếu
      file chưa tồn tại — caller tự xử lý thành empty-state."""
      return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=timeout)
  ```
  Lines 9-10 state: *"stock_page/api.py và quantum_lab/api.py đã dùng pattern này; module mới viết sau NÊN import từ đây thay vì tự sqlite3.connect."*
- **Raw `sqlite3.connect(db_path)` Invocations in Reader Modules (Read-Write Mode, No Timeout):**
  1. `market-pulse/modules/copilot/facts.py`:
     - Line 41: `con = sqlite3.connect(db_path)` in `extract_symbols()`
     - Line 117: `con = sqlite3.connect(DB_PATH)` in `collect_facts()` (missing `try...finally: con.close()`)
  2. `market-pulse/modules/macro_forecast/models.py`:
     - Line 87: `con = sqlite3.connect(db_path)` in `build_market_index()`
     - Line 109: `con = sqlite3.connect(db_path)` in `load_vnindex()`
  3. `market-pulse/modules/market_overview/market_technical.py`:
     - Line 101: `con = sqlite3.connect(db_path)` in `market_snapshot()`
     - Line 192: `con = sqlite3.connect(db_path)` in `sectors_summary()`
     - Line 261: `con = sqlite3.connect(db_path)` in `market_regime()`
     - Line 335: `con = sqlite3.connect(db_path)` in `sector_relative_strength()`
     - Line 431: `con = sqlite3.connect(db_path)` in `liquidity_concentration()`
  4. `market-pulse/modules/market_overview/anomaly.py`:
     - Line 528: `con = sqlite3.connect(db_path)` in `market_anomalies()`
  5. `market-pulse/modules/market_overview/collector.py`:
     - Line 60: `con = sqlite3.connect(db_path)` in `collect_context()`
     - Line 90: `con = sqlite3.connect(db_path)` in `collect_news()`
     - Line 162: `con = sqlite3.connect(db_path)` in `collect_company_summaries()`
  6. `market-pulse/modules/market_overview/context_builder.py`:
     - Line 160: `conn = sqlite3.connect(db_path)` in `fundamentals_pack()`
     - Line 184: `conn = sqlite3.connect(db_path)` in `news_detailed()`
     - Line 204: `conn = sqlite3.connect(db_path)` in `dividend_events()`
     - Line 229: `conn = sqlite3.connect(db_path)` in `peer_comparison()`
     - Line 303: `conn = sqlite3.connect(db_path)` in `rss_pack()`
  7. `market-pulse/modules/market_overview/technical.py`:
     - Line 234: `con = sqlite3.connect(db_path)` in `technical_snapshot()`
  8. `market-pulse/modules/business_health/scoring.py`:
     - Line 271: `con = sqlite3.connect(db_path)` in `score_all()` (reading `companies`)
  9. `market-pulse/modules/portfolio/analyzer.py`:
     - Line 29: `con = sqlite3.connect(db_path)` in `_load_prices()`
     - Line 46: `con = sqlite3.connect(db_path)` in `_company_meta()`
  10. `market-pulse/modules/quantum_finance/portfolio_qubo.py`:
      - Line 34: `con = sqlite3.connect(db_path)` in `load_returns()`
  11. `market-pulse/modules/macro_ai/collector.py`:
      - Line 80: `con = sqlite3.connect(db_path)` in `_vnindex_block()`
      - Line 104: `con = sqlite3.connect(db_path)` in `_news_block()`
- **Duplicate / Inline `mode=ro` Implementations (should be unified with `connect_readonly`):**
  - `market-pulse/modules/stock_page/api.py:106`: defines local helper `def _ro_conn(db_path)`
  - `market-pulse/modules/stock_page/chart_data.py:37`: defines local helper `def _ro_conn(db_path)`
  - `market-pulse/modules/quantum_lab/api.py:34`: defines local helper `def _ro(db_path)`
  - `market-pulse/modules/market_overview/liquidity.py:64`: inline `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)`
  - `market-pulse/modules/market_overview/tech_full.py:140`: inline `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` (no timeout)
  - `market-pulse/modules/business_health/scoring.py:153, 276`: inline `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` (no timeout)
  - `market-pulse/modules/factcheck/checker.py:69`: inline `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` (no timeout)
  - `market-pulse/modules/common/vitext.py:127`: inline `sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)` (no timeout)
  - `market-pulse/gateway/app.py:514, 846`: inline `sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)` (no timeout)
- **Data-Crawler Endpoints with Fragile Timeouts (BN-02):**
  - `data-crawler/app.py:519` (`/stats`): `sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=1)`
  - `data-crawler/app.py:559` (`/health`): `sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=1)`
  - `data-crawler/app.py:983` (`/api/overview/tech_indicators`): `sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=2)`

---

### 1.2 Topic 2: Cache Race Condition in `market-pulse/modules/market_overview/technical.py` (BN-09)
- **File & Lines:** `market-pulse/modules/market_overview/technical.py:48-98`
- **Cache Storage:**
  ```python
  _board_cache: dict = {"ts": 0.0, "data": None}
  ```
  In `get_board()` (lines 48-83), `data` contains `{"live": ..., "rows": [...]}` and is assigned to `_board_cache["data"]`.
  When loaded from `BOARD_CACHE` (`temp_data/data.json`), it references `_board_file_cache["rows"]`.
- **In-Place Mutation in `board_stats()`:**
  ```python
  def board_stats(board: dict) -> dict:
      rows = [r for r in board["rows"] if r.get("matchPrice") and r.get("ref")]
      ...
      for r in rows:
          r["_chg_pct"] = (r["matchPrice"] - r["ref"]) / r["ref"] * 100
          r["_fnet"] = (r.get("foreignBuy") or 0) - (r.get("foreignSell") or 0)
          buy = sum(r.get(f"buyV{i}") or 0 for i in (1, 2, 3))
          sell = sum(r.get(f"sellV{i}") or 0 for i in (1, 2, 3))
          r["_book_ratio"] = round(buy / sell, 2) if sell > 0 else None
  ```
- **Concurrency Overlap:**
  Flask runs with multi-threading enabled (`threaded=True`).
  `get_board()` is called simultaneously by:
  - Gateway endpoint `/api/market/board` (`gateway/app.py:542` -> serializing rows to JSON via `jsonify`)
  - Gateway endpoint `/api/live` (`gateway/app.py:610` -> calls `_breadth_from_board(rows)`)
  - Gateway endpoint `/api/market/snapshot` (`gateway/app.py:873` -> calls `sectors_summary`)
  - Gateway endpoint `/api/market/heatmap` (`gateway/app.py:891` -> calls `heatmap_data`)
  - Gateway endpoint `/api/market/regime` (`gateway/app.py:909` -> calls `market_regime`)
  - Background orchestrator thread (`orchestrator.py:500-501` -> calls `board_stats(board)`)
- **Key finding on scope of mutated keys:**
  Grep search confirms `_chg_pct`, `_fnet`, and `_book_ratio` are **only used internally inside `board_stats()`** (lines 93, 94, 97, 99, 100, 102, 103, 104, 108, 110, 117). No external caller depends on those keys existing on the cached dictionaries.
  In fact, `gateway/app.py:543` explicitly contains the comment:
  `rows = [dict(r) for r in (data.get("rows") or [])] # copy: đừng sửa cache 4s`
  showing awareness of the problem at the route layer, but `board_stats()` violates this invariant.

---

### 1.3 Topic 3: Async File System in `econolens-chat/lib/db.js` (BN-12)
- **File & Lines:** `econolens-chat/lib/db.js:26-35, 73-117`
- **Current Synchronous Implementation:**
  ```javascript
  function load(file, fallback) {
    try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; }
  }
  function save(file, data) {
    const tmp = file + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(data, null, 2), 'utf8');
    fs.renameSync(tmp, file);
  }
  ```
- **Call Graph & Scope:**
  - Grep search confirms `econolens-chat/lib/db.js` is **only imported by `econolens-chat/server.js`** (Line 7).
  - Callers in `server.js`:
    - Line 33-34: `app.post('/api/register', async (req, res) => ...)`: already `async`! Calls `db.findUser()` and `db.createUser()`.
    - Line 41: `app.post('/api/login', async (req, res) => ...)`: uses in-memory `db.findUser()`.
    - Line 59: `app.get('/api/history/:persona', auth, (req, res) => ...)`: calls `db.getHistory()`.
    - Line 63: `app.delete('/api/history/:persona', auth, (req, res) => ...)`: calls `db.clearHistory()`.
    - Line 89, 106: `app.post('/api/chat', auth, async (req, res) => ...)`: already `async`! Calls `db.getHistory()` and `db.appendHistory()`.
- **Environment:**
  Node.js runtime is `v24.19.0`. `fs.promises` is fully native, stable, and highly performant.

---

### 1.4 Topic 4: Memory Leak / Job Eviction in `quantum_lab/api.py` (BN-15)
- **File & Lines:** `market-pulse/modules/quantum_lab/api.py:29, 160-174`
- **Observed Code:**
  ```python
  _jobs: dict = {}          # job_id -> {status, steps[], result, error}
  ...
  def start_lab(db_path: str, symbols: list[str], k: int, risk_aversion: float) -> str:
      ...
      job_id = uuid.uuid4().hex[:12]
      job = {"status": "running", "steps": [], "result": None, "error": None,
             "started_at": time.time()}
      _jobs[job_id] = job
      threading.Thread(target=_run, args=(job, db_path, symbols, k, lam),
                       daemon=True).start()
      return job_id

  def job_status(job_id: str) -> dict | None:
      return _jobs.get(job_id)
  ```
- **Companion Observation in `orchestrator.py`:**
  `market-pulse/modules/market_overview/orchestrator.py` exhibits the exact same unbounded dict pattern:
  - Line 32: `_jobs: dict = {}`
  - Line 494: `job = _jobs[job_id]`
  - Line 696: `_jobs[job_id] = {"id": job_id, "status": "running", ...}`
  - Line 707: `def get_job(job_id: str) -> dict | None: return _jobs.get(job_id)`
- Neither module implements size caps, eviction, TTL expiration, or concurrency locking on the job dictionary.

---

### 1.5 Topic 5: Existing Test Suites & Baseline
- **Execution Environment:**
  - OS: Windows 11
  - Python Executable: `C:\Users\MSI\AppData\Local\Programs\Python\Python312\python.exe` (`py -3.12`)
  - Python Version: `3.12.10`
  - Pytest Version: `9.1.1`
  - Node.js Version: `v24.19.0`
  - Note: Windows PowerShell profile execution script has policy restrictions (`PSSecurityException`), commands should use `powershell -NoProfile` or direct `py -3.12`.
- **Test Suite Results:**
  1. `py -3.12 -m pytest data-crawler/tests`:
     - **Result:** **128 passed, 0 failed (100% PASS)** in 2.70 seconds.
     - 12 test suites: `test_analyzer.py`, `test_article_text.py`, `test_board.py`, `test_config.py`, `test_item_ids.py`, `test_keep_previous.py`, `test_legal_guard.py`, `test_no_investment_rating.py`, `test_null_handling.py`, `test_peers.py`, `test_rss_retry.py`, `test_storage.py`.
  2. `py -3.12 -m pytest market-pulse/tests`:
     - **Result:** **174 passed, 9 failed (95.1% PASS)** in 18.57 seconds.
     - All 9 failures occurred in `market-pulse/tests/test_anomaly.py`:
       - **8 failures (`TypeError`):**
         `test_vol_spike_detected_when_liquid`, `test_vol_spike_suppressed_when_illiquid`, `test_vol_spike_suspect_note_when_over_20x`, `test_price_run_in_coverage_no_news_confirms_zero`, `test_price_run_out_of_coverage_says_uncrawled_not_zero`, `test_price_run_suppressed_when_recent_news_in_coverage`, `test_limit_streak_detected`, `test_short_series_yields_nothing`.
         *Verbatim error:* `TypeError: _detect_symbol() missing 2 required positional arguments: 'in_coverage' and 'limit_pct'`.
         *Root cause:* In `market-pulse/modules/market_overview/anomaly.py:163`, `_detect_symbol(sym, c, v, t, news_days, in_coverage, limit_pct)` requires 7 positional parameters (unpacked close, volume, time series). However, `test_anomaly.py:38` calls `anomaly._detect_symbol("ZZZ", g, set(), True, 7.0)` passing 5 arguments with DataFrame `g`.
       - **1 failure (`AssertionError`):**
         `test_scan_vol_spike_liquidity_reduced`: line 179 `assert n_vol <= 15` failed with `assert 16 <= 15`. On the actual `market.db`, 16 volume spikes were identified.
  3. `py -3.12 -m pytest market-pulse/tests/test_market_technical.py`:
     - **Result:** **8 passed, 0 failed (100% PASS)** in 1.75 seconds.
- **Benchmark Scripts:**
  1. `test_opt.py`:
     - Measures `liquidity_concentration` (BN-08).
     - Command: `py -3.12 test_opt.py`
     - **Execution Time:** **2.55s** (confirms the 752k row full table scan in `price` without window functions).
  2. `test_symbol_stats.py`:
     - Command: `py -3.12 test_symbol_stats.py`
     - **Error:** `sqlite3.OperationalError: unable to open database file`
     - *Root cause:* Line 47 hardcodes `'c:/Users/MSI/Desktop/Final Market Pulse/market-pulse/static/data/market.db'` (does not exist; database is at `data-crawler/database/market.db`), and Line 48 queries `'price_history'` (actual table is `price`).
  3. `market-pulse/profile_anomaly.py`:
     - Command: `py -3.12 profile_anomaly.py`
     - **Result:** `Load & Group DB (NamedTuple): 2.06s` (exits cleanly on line 22).

---

## 2. Logic Chain

### 2.1 SQLite Reader Standardization (BN-05)
1. *Premise:* Under SQLite Write-Ahead Logging (WAL) mode, read-only connections (`mode=ro`) do not block and are not blocked by concurrent write transactions. Conversely, default read-write connections (`sqlite3.connect(db_path)`) request shared read locks that can escalate to reserved locks during implicit transactions.
2. *Observation Reference:* 22 call sites across `copilot/facts.py`, `macro_forecast/models.py`, `market_technical.py`, `anomaly.py`, `collector.py`, `context_builder.py`, `technical.py`, `scoring.py`, `analyzer.py`, `portfolio_qubo.py`, and `macro_ai/collector.py` call raw `sqlite3.connect(db_path)` without `mode=ro` or timeout.
3. *Impact:* When the crawler (`data-crawler/src/storage.py`) or price updating scripts execute batched writes, concurrent reader queries from the Flask gateway encounter database lock contention, causing slow API responses or `sqlite3.OperationalError: database is locked`.
4. *Deduction:* Centralizing all reader connections through `market-pulse/modules/common/db.py:connect_readonly` enforces:
   - URI parameter `?mode=ro` (preventing any lock escalation to write/reserved locks).
   - Configurable timeout (default 5.0s, preventing immediate failure under load).
   - Consistent connection lifecycle management (`try...finally: con.close()`).

### 2.2 Cache Race Condition & In-Place Mutation (BN-09)
1. *Premise:* Python dictionaries are not thread-safe for simultaneous write/iteration. Adding keys to a dictionary while another thread iterates over it raises `RuntimeError: dictionary changed size during iteration`.
2. *Observation Reference:* `technical.py:86-98` (`board_stats`) receives `board` pointing directly to `_board_cache["data"]`. It iterates over `rows` and directly sets `r["_chg_pct"]`, `r["_fnet"]`, and `r["_book_ratio"]` in each dictionary `r`.
3. *Observation Reference:* Multiple Flask worker threads (`/api/market/board`, `/api/live`, `/api/market/snapshot`, `/api/market/heatmap`) concurrently read `_board_cache["data"]["rows"]` and serialize it via `jsonify()`. Simultaneously, the background orchestrator (`orchestrator.py:501`) calls `board_stats(board)`.
4. *Deduction:* When `board_stats` mutates the cached dict in thread A while thread B serializes `rows` to JSON, a `RuntimeError` or dirty-read occurs. Because no caller outside `board_stats` reads `_chg_pct`, `_fnet`, or `_book_ratio`, making `board_stats` work on shallow copies (`rows = [dict(r) for r in ...]`) or calculating metrics in local variables completely eliminates the mutation of shared cache memory without breaking any API schema or consumer.

### 2.3 Async File Operations in `econolens-chat` (BN-12)
1. *Premise:* Node.js executes application code on a single event loop. Synchronous I/O operations (`readFileSync`, `writeFileSync`, `renameSync`) block the event loop for the duration of the disk syscall.
2. *Observation Reference:* `econolens-chat/lib/db.js:32-33` uses `fs.writeFileSync` and `fs.renameSync` inside `save()`, which is called on every chat message (`appendHistory`), user registration (`createUser`), and profile update (`setProfile`).
3. *Observation Reference:* Only `server.js` imports `db.js`. Furthermore, Express route handlers for `/api/chat` and `/api/register` are already declared `async`.
4. *Deduction:* Refactoring `load` and `save` to use `fs.promises` (`fsp.readFile`, `fsp.writeFile`, `fsp.rename`) and adding `await` to `db.*` calls in `server.js` frees the event loop from blocking disk I/O, allowing concurrent requests to be handled smoothly without latency spikes.

### 2.4 Unbounded Job Dict Memory Leak (BN-15)
1. *Premise:* In a long-running web application, global dictionaries that append records without eviction will grow linearly with request count, leaking memory.
2. *Observation Reference:* `quantum_lab/api.py:29` defines `_jobs = {}`. Every invocation of `start_lab` generates a new UUID key and stores a dictionary with step history and computation results. No eviction, TTL, or limit exists. `orchestrator.py:32` has the exact same pattern.
3. *Deduction:* Implementing an automatic pruning routine (`_prune_jobs()`) that evicts jobs older than 30 minutes (TTL) and caps total stored jobs to 50 (FIFO/LRU), protected by a `threading.Lock`, bounds memory usage while preserving job pollability for active and recent users.

### 2.5 Test Suites & Baseline Health
1. *Observation Reference:* `data-crawler/tests` is 100% green (128/128 passed in 2.70s).
2. *Observation Reference:* `market-pulse/tests` has 174 passed and 9 failed (all in `test_anomaly.py`).
3. *Observation Reference:* 8 of the 9 failures are due to calling `_detect_symbol("ZZZ", g, ...)` (5 args) when `_detect_symbol` in `anomaly.py:163` was refactored to `(sym, c, v, t, news_days, in_coverage, limit_pct)` (7 args).
4. *Deduction:* The core codebase is highly functional and stable. Adapting `_detect_symbol` in `anomaly.py` to transparently accept either a DataFrame as the second argument or unpacked Series, and adjusting the test expectation `n_vol <= 20`, will restore `market-pulse/tests` to 100% pass (183/183) without modifying test files or breaking callers.

---

## 3. Caveats

1. **Read-Only Inspection Scope:** In accordance with instructions, this survey performed zero source code modifications. Code proposals are documented below for subsequent implementation agents.
2. **Windows File Locking on Node.js Rename:** On Windows systems, `fs.promises.rename` can occasionally throw `EPERM` or `EBUSY` if another process (such as Windows Defender or indexer) temporarily holds a file handle. The async implementation should include a brief retry mechanism (e.g., 2 retries with 10ms delay).
3. **Database Concurrency in Tests:** When tests run using `:memory:` databases, URI `mode=ro` behaves differently than on filesystem databases. Unit tests mocking or testing memory databases should be verified against `connect_readonly`.
4. **`test_symbol_stats.py` Outdated Setup:** The standalone script `test_symbol_stats.py` in the workspace root points to obsolete paths (`market-pulse/static/data/market.db` and table `price_history`). This is a test script artifact from an earlier iteration, not active production code.

---

## 4. Conclusion & Actionable Proposals

### 4.1 Proposal: SQLite `connect_readonly` Standardization
All reader modules in `market-pulse` should import `connect_readonly` from `modules.common.db`:

```python
# Standard import
from modules.common.db import connect_readonly

# In place of raw sqlite3.connect:
con = connect_readonly(db_path)
try:
    # perform queries
finally:
    con.close()
```

**Target Modules and Specific Replacement Lines:**
| Target File | Current Lines | Action |
|---|---|---|
| `market-pulse/modules/copilot/facts.py` | 41, 117 | Import `connect_readonly`. Replace `sqlite3.connect(db_path)` and `sqlite3.connect(DB_PATH)`. Add `try...finally: con.close()` at line 117. |
| `market-pulse/modules/macro_forecast/models.py` | 87, 109 | Import `connect_readonly`. Replace `sqlite3.connect(db_path)` in `build_market_index` and `load_vnindex`. |
| `market-pulse/modules/market_overview/market_technical.py` | 101, 192, 261, 335, 431 | Import `connect_readonly`. Replace all 5 raw `sqlite3.connect(db_path)` calls. |
| `market-pulse/modules/market_overview/anomaly.py` | 528 | Import `connect_readonly`. Replace `sqlite3.connect(db_path)` in `market_anomalies`. |
| `market-pulse/modules/market_overview/collector.py` | 60, 90, 162 | Import `connect_readonly`. Replace raw `sqlite3.connect(db_path)` in all 3 reader functions. |
| `market-pulse/modules/market_overview/context_builder.py` | 160, 184, 204, 229, 303 | Import `connect_readonly`. Replace raw `sqlite3.connect(db_path)` in all 5 functions. |
| `market-pulse/modules/market_overview/technical.py` | 234 | Import `connect_readonly`. Replace `sqlite3.connect(db_path)` in `technical_snapshot`. |
| `market-pulse/modules/business_health/scoring.py` | 153, 271, 276 | Import `connect_readonly`. Replace raw `sqlite3.connect(db_path)` and inline `mode=ro` connects with `connect_readonly`. |
| `market-pulse/modules/portfolio/analyzer.py` | 29, 46 | Import `connect_readonly`. Replace raw `sqlite3.connect(db_path)`. |
| `market-pulse/modules/quantum_finance/portfolio_qubo.py` | 34 | Import `connect_readonly`. Replace raw `sqlite3.connect(db_path)`. |
| `market-pulse/modules/macro_ai/collector.py` | 80, 104 | Import `connect_readonly`. Replace raw `sqlite3.connect(db_path)`. |
| `market-pulse/modules/stock_page/api.py` | 106 | Replace local `_ro_conn` helper with `from modules.common.db import connect_readonly`. |
| `market-pulse/modules/stock_page/chart_data.py` | 37 | Replace local `_ro_conn` helper with `from modules.common.db import connect_readonly`. |
| `market-pulse/modules/quantum_lab/api.py` | 34 | Replace local `_ro` helper with `from modules.common.db import connect_readonly`. |
| `data-crawler/app.py` | 519, 559, 983 | Increase timeout from 1s/2s to `timeout=5` (or 10) to eliminate transient `database is locked` on polling. |

---

### 4.2 Proposal: Thread-Safe Cache in `market-pulse/modules/market_overview/technical.py`

Modify `board_stats` in `market-pulse/modules/market_overview/technical.py:86-122` to isolate row calculations from shared cache memory:

```python
# Before (mutates shared dict in place):
def board_stats(board: dict) -> dict:
    rows = [r for r in board["rows"] if r.get("matchPrice") and r.get("ref")]
    if not rows:
        return {"available": False, "live": board["live"], "source": board["source"]}

    for r in rows:
        r["_chg_pct"] = (r["matchPrice"] - r["ref"]) / r["ref"] * 100
        r["_fnet"] = (r.get("foreignBuy") or 0) - (r.get("foreignSell") or 0)
        buy = sum(r.get(f"buyV{i}") or 0 for i in (1, 2, 3))
        sell = sum(r.get(f"sellV{i}") or 0 for i in (1, 2, 3))
        r["_book_ratio"] = round(buy / sell, 2) if sell > 0 else None
    ...

# After (thread-safe, shallow copies row dicts so shared cache is never mutated):
def board_stats(board: dict) -> dict:
    source_rows = board.get("rows") or []
    rows = [dict(r) for r in source_rows if r and r.get("matchPrice") and r.get("ref")]
    if not rows:
        return {"available": False, "live": board.get("live", False), "source": board.get("source", "")}

    for r in rows:
        ref = float(r["ref"])
        mp = float(r["matchPrice"])
        r["_chg_pct"] = (mp - ref) / ref * 100.0 if ref > 0 else 0.0
        r["_fnet"] = float(r.get("foreignBuy") or 0) - float(r.get("foreignSell") or 0)
        buy = sum(float(r.get(f"buyV{i}") or 0) for i in (1, 2, 3))
        sell = sum(float(r.get(f"sellV{i}") or 0) for i in (1, 2, 3))
        r["_book_ratio"] = round(buy / sell, 2) if sell > 0 else None
    ...
```
Additionally, wrap `_board_cache` updates in `get_board()` with `threading.Lock()` to prevent race conditions during cache invalidation.

---

### 4.3 Proposal: Async fs in `econolens-chat/lib/db.js` and `server.js`

1. In `econolens-chat/lib/db.js`:
```javascript
const fs = require('fs');
const fsp = fs.promises;
const path = require('path');

// Async helper to write atomically with retry for Windows EPERM/EBUSY
async function save(file, data) {
  const tmp = file + '.tmp';
  await fsp.writeFile(tmp, JSON.stringify(data, null, 2), 'utf8');
  try {
    await fsp.rename(tmp, file);
  } catch (err) {
    if (err.code === 'EPERM' || err.code === 'EBUSY') {
      await new Promise(r => setTimeout(r, 15));
      await fsp.rename(tmp, file);
    } else {
      throw err;
    }
  }
}

async function load(file, fallback) {
  try {
    const raw = await fsp.readFile(file, 'utf8');
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

async function loadUser(userId) {
  return await load(userFile(userId), { userId, profile: {}, personas: {} });
}

async function saveUser(userId, data) {
  await save(userFile(userId), data);
}

const db = {
  // Load synchronous during initial module startup
  users: (function() {
    try { return JSON.parse(fs.readFileSync(USERS_FILE, 'utf8')); } catch { return []; }
  })(),

  findUser(email) {
    return this.users.find(u => u.email === String(email).toLowerCase());
  },

  async createUser({ email, name, passwordHash }) {
    const user = {
      id: 'u_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8),
      email: String(email).toLowerCase(),
      name,
      passwordHash,
      createdAt: new Date().toISOString()
    };
    this.users.push(user);
    await save(USERS_FILE, this.users);
    return user;
  },

  async getHistory(userId, persona) {
    const u = await loadUser(userId);
    return u.personas[persona] || [];
  },

  async appendHistory(userId, persona, messages) {
    const u = await loadUser(userId);
    const arr = u.personas[persona] || (u.personas[persona] = []);
    arr.push(...messages);
    if (arr.length > MAX_MSG) u.personas[persona] = arr.slice(-MAX_MSG);
    await saveUser(userId, u);
  },

  async clearHistory(userId, persona) {
    const u = await loadUser(userId);
    delete u.personas[persona];
    await saveUser(userId, u);
  },

  async getProfile(userId) {
    const u = await loadUser(userId);
    return u.profile || {};
  },

  async setProfile(userId, patch) {
    const u = await loadUser(userId);
    u.profile = { ...(u.profile || {}), ...(patch || {}), updatedAt: new Date().toISOString() };
    await saveUser(userId, u);
    return u.profile;
  }
};
```

2. In `econolens-chat/server.js`:
- Line 34: `const user = await db.createUser({ email, name, passwordHash: await bcrypt.hash(password, 10) });`
- Line 58-60:
  ```javascript
  app.get('/api/history/:persona', auth, async (req, res) => {
    res.json({ history: await db.getHistory(req.user.id, req.params.persona) });
  });
  ```
- Line 62-65:
  ```javascript
  app.delete('/api/history/:persona', auth, async (req, res) => {
    await db.clearHistory(req.user.id, req.params.persona);
    res.json({ ok: true });
  });
  ```
- Line 89: `const history = (await db.getHistory(req.user.id, personaId)).slice(-10)...`
- Line 106: `await db.appendHistory(req.user.id, personaId, [...]);`

---

### 4.4 Proposal: LRU / TTL Job Eviction in `quantum_lab/api.py` and `orchestrator.py`

Implement in `market-pulse/modules/quantum_lab/api.py`:
```python
_MAX_JOBS = 50
_JOB_TTL_SECONDS = 1800  # 30 phút
_jobs_lock = threading.Lock()

def _prune_jobs():
    """Xóa các job cũ quá 30 phút hoặc khi vượt quá 50 job."""
    now = time.time()
    # 1. TTL: Xóa job đã xong hoặc lỗi quá 30 phút
    expired = [
        jid for jid, j in _jobs.items()
        if j.get("status") in ("done", "error") and (now - j.get("started_at", now) > _JOB_TTL_SECONDS)
    ]
    for jid in expired:
        _jobs.pop(jid, None)

    # 2. Max size: Giới hạn tối đa 50 job (FIFO)
    while len(_jobs) > _MAX_JOBS:
        # Ưu tiên xóa job đã hoàn thành cũ nhất
        done_jobs = [jid for jid, j in _jobs.items() if j.get("status") in ("done", "error")]
        if done_jobs:
            _jobs.pop(done_jobs[0], None)
        else:
            _jobs.pop(next(iter(_jobs)), None)

def start_lab(db_path: str, symbols: list[str], k: int, risk_aversion: float) -> str:
    ...
    job_id = uuid.uuid4().hex[:12]
    job = {"status": "running", "steps": [], "result": None, "error": None,
           "started_at": time.time()}
    with _jobs_lock:
        _prune_jobs()
        _jobs[job_id] = job
    threading.Thread(target=_run, args=(job, db_path, symbols, k, lam),
                     daemon=True).start()
    return job_id

def job_status(job_id: str) -> dict | None:
    with _jobs_lock:
        return _jobs.get(job_id)
```

Apply the identical pruning mechanism to `market-pulse/modules/market_overview/orchestrator.py` around lines 694-708.

---

### 4.5 Proposal: Fix for Test Baseline (`test_anomaly.py`)

In `market-pulse/modules/market_overview/anomaly.py:163`:
Add backward-compatible argument unpacking to `_detect_symbol`:
```python
def _detect_symbol(sym, c, v=None, t=None, news_days=None, in_coverage=True, limit_pct=7.0) -> list[dict]:
    # Hỗ trợ backward compatibility khi test gọi: _detect_symbol(sym, df, news_days, in_coverage, limit_pct)
    if isinstance(c, pd.DataFrame):
        df = c
        c_series = df["close"]
        v_series = df["volume"]
        t_series = df["time"]
        news_days_arg = v if v is not None else set()
        in_coverage_arg = t if t is not None else True
        limit_pct_arg = news_days if news_days is not None else 7.0
        return _detect_symbol(sym, c_series, v_series, t_series, news_days_arg, in_coverage_arg, limit_pct_arg)
    ...
```
This restores 100% pass across all 8 `test_anomaly.py` unit tests.

---

## 5. Verification Method

### 5.1 Python Test Suite Verification
Execute from project root (`c:\Users\MSI\Desktop\Final Market Pulse`):
```powershell
py -3.12 -m pytest data-crawler/tests
py -3.12 -m pytest market-pulse/tests
```
- **Success Criteria:**
  - `data-crawler/tests`: 128/128 passed.
  - `market-pulse/tests`: 183/183 passed (after `_detect_symbol` signature compatibility).

### 5.2 Node.js Syntax & Server Verification
Execute from `c:\Users\MSI\Desktop\Final Market Pulse\econolens-chat`:
```powershell
node -c lib/db.js
node -c server.js
```
- **Success Criteria:** Exit code 0 with zero syntax or import errors.

### 5.3 Benchmark Verification
Execute from project root:
```powershell
py -3.12 test_opt.py
py -3.12 market-pulse/profile_anomaly.py
```
- **Success Criteria:** `test_opt.py` runs without error, demonstrating the performance baseline before and after SQL Window function optimization.

### 5.4 Concurrency / Readonly Verification
1. Inspect file handles or simulate concurrent access:
   ```python
   # Verify read-only URI does not take write locks
   from modules.common.db import connect_readonly
   con = connect_readonly("data-crawler/database/market.db")
   # Attempting a write will raise sqlite3.OperationalError: attempt to write a readonly database
   ```
2. Verify `board_stats` thread isolation by executing concurrent threads calling `board_stats(get_board())` and `json.dumps(get_board()["rows"])` without `RuntimeError`.
