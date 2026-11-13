## 2026-09-06T12:54:02Z
You are explorer_survey_3.
Your working directory is: c:\Users\MSI\Desktop\Final Market Pulse\.agents\explorer_survey_3

MANDATORY INSTRUCTIONS:
1. You MUST read the original request at: c:\Users\MSI\Desktop\Final Market Pulse\.agents\ORIGINAL_REQUEST.md before doing anything else.
2. Also read c:\Users\MSI\Desktop\Final Market Pulse\BOTTLENECKS.md (especially BN-05, BN-09, BN-12, BN-15).
3. Do NOT modify any source code files. You are a read-only exploration agent.
4. Maintain your progress in c:\Users\MSI\Desktop\Final Market Pulse\.agents\explorer_survey_3\progress.md.
5. Write your comprehensive investigation report in c:\Users\MSI\Desktop\Final Market Pulse\.agents\explorer_survey_3\handoff.md.
6. When finished, use send_message to report your findings to the orchestrator.

TASK SCOPE (Survey R3: P2/P3 Concurrency, Async & Testing Baseline):
Investigate the following areas:
1. SQLite `connect_readonly` standardization:
   - Check `market-pulse/modules/common/db.py:connect_readonly`.
   - Search for raw `sqlite3.connect` calls in reader modules: `copilot/facts.py`, `macro_forecast/models.py`, `market_overview/market_technical.py`, `market_overview/anomaly.py`, etc.
   - Identify which files should be updated to use `connect_readonly` (URI mode=ro with timeout).
2. Cache race condition in `market-pulse/modules/market_overview/technical.py`:
   - Inspect `get_board()` and `board_stats()` around lines 48-98.
   - Identify where `_board_cache["data"]` is mutated in place across threads and how to make it thread-safe (e.g. copying row dicts or precomputing attributes before caching).
3. Async fs in `econolens-chat/lib/db.js`:
   - Inspect `writeFileSync` and `renameSync` usages (lines ~26-35, 73-89).
   - Analyze how to convert to `fs.promises.writeFile` and `fs.promises.rename` (or handle async/await in callers). Check callers in Express routes.
4. Memory leak / Job eviction in `market-pulse/modules/quantum_lab/api.py`:
   - Inspect `_jobs = {}` around line 29.
   - Propose LRU or TTL eviction mechanism (e.g. keep max 50 recent jobs or expire after 30 mins).
5. Existing Test Suites & Baseline:
   - Run or inspect test runners for `pytest market-pulse/tests` and `pytest data-crawler/tests`.
   - Check benchmark scripts: `test_opt.py`, `test_symbol_stats.py`, `market-pulse/profile_anomaly.py`.
   - Document the current test environment, how tests are invoked, and any existing failures or prerequisites.
