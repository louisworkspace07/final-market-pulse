## 2026-09-06T12:54:02Z
<USER_REQUEST>
You are explorer_survey_2.
Your working directory is: c:\Users\MSI\Desktop\Final Market Pulse\.agents\explorer_survey_2

MANDATORY INSTRUCTIONS:
1. You MUST read the original request at: c:\Users\MSI\Desktop\Final Market Pulse\.agents\ORIGINAL_REQUEST.md before doing anything else.
2. Also read c:\Users\MSI\Desktop\Final Market Pulse\BOTTLENECKS.md (especially BN-01, BN-03, BN-04, BN-08).
3. Do NOT modify any source code files. You are a read-only exploration agent.
4. Maintain your progress in c:\Users\MSI\Desktop\Final Market Pulse\.agents\explorer_survey_2\progress.md.
5. Write your comprehensive investigation report in c:\Users\MSI\Desktop\Final Market Pulse\.agents\explorer_survey_2\handoff.md.
6. When finished, use send_message to report your findings to the orchestrator.

TASK SCOPE (Survey R2: P1 SQLite & N+1 Query Remediation):
Investigate the following 4 areas:
1. `data-crawler/src/storage.py`:
   - Check table creation and existing indexes on `financials` and `price`.
   - Inspect how to add `CREATE INDEX IF NOT EXISTS idx_fin_stmt_item_period ON financials(statement, item_id, period, value);` and `CREATE INDEX IF NOT EXISTS idx_price_time ON price(time);`.
   - Check if database migrations / auto-init exist when storage or app starts.
2. `market-pulse/modules/business_health/scoring.py`:
   - Inspect `score_all()` and `score_company()` around lines 270-290.
   - Analyze how 3,000 queries occur (looping over 1,500 companies with `pd.read_sql` on `financials` and `price`).
   - Detail how to replace this with a single batch query for 3 years of financial data + batch prices, group in memory, and vectorize/optimize scoring while preserving exact output dict schema.
   - Check callers and existing tests (e.g. `test_opt.py` or unit tests).
3. `data-crawler/src/peers.py`:
   - Inspect `compute(conn, symbol)` and `_peer_value`.
   - Analyze N+1 query loop when fetching metrics for all peers in the same sector.
   - Detail how to implement in-memory `sector_cache` (TTL 300s) and batch SQL query `WHERE symbol IN (...)` to eliminate 400-600 queries per stock view.
   - Check callers in `market-pulse` and `data-crawler`, and existing tests.
4. `market-pulse/modules/market_overview/market_technical.py`:
   - Inspect `_price_frame(con)` and `liquidity_concentration()` around lines 26-30 and 431-436.
   - Analyze how loading 752k rows into pandas can be replaced with SQLite Window Function (`ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC) WHERE rn = 1`) when `board_rows` is None.
   - Check test coverage and caller expectations.

Produce concrete implementation designs and exact diff recommendations in your handoff.md.
</USER_REQUEST>
