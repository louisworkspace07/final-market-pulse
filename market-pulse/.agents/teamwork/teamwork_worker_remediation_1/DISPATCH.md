# Dispatch for Worker 1: System Remediation

## Objective
Implement surgical fixes across `price-board`, `gateway`, `econolens-chat`, and `data-crawler` based on Explorer findings:
1. Eliminate all mock data in `price-board/server.py` lines 298-310.
2. Fix Mixed Content and hardcoded `http://127.0.0.1:5555` in `price-board/static/app.js`.
3. Fix relative CSS link in `price-board/static/index.html`.
4. Fix API routing in `econolens-chat/public/app.js`.
5. Add CORS headers, board caching, and graceful non-DB ticker handling in `market-pulse/gateway/app.py`.
6. Fix `data-crawler` vnstock import issue.
7. Verify all changes, run tests, test local & Vercel live endpoints, and restart services if needed.

## Reference Reports
- `C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_explorer_survey_1\handoff.md`
- `C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_explorer_survey_2\handoff.md`
- `C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_explorer_survey_3\handoff.md`
- `C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\orchestrator\PROJECT.md`

## 2026-11-13T12:33:32Z
Sender: fee1831e-1466-4cf6-b268-630c4ca4c37c
Message:
You are Worker 1 (Archetype: teamwork_worker).
Your working directory is: C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_worker_remediation_1

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Read ORIGINAL_REQUEST.md at: C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\ORIGINAL_REQUEST.md
Also read your task instructions at: C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_worker_remediation_1\DISPATCH.md
Read the 3 Explorer handoff reports:
- C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_explorer_survey_1\handoff.md
- C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_explorer_survey_2\handoff.md
- C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_explorer_survey_3\handoff.md
And PROJECT.md at: C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\orchestrator\PROJECT.md

Your Task:
Implement the required fixes and verify:
1. `price-board/server.py`:
   - Remove lines 298-310 mock fallback (hardcoded prices [22.40..22.75] and random.randint). Ensure genuine calculation or clean empty list when external feed has no data. Strictly NO fake/mock data!
2. `price-board/static/app.js`:
   - Replace hardcoded `http://127.0.0.1:5555` with relative paths (`/api/...`) or origin-based URLs so that when viewed over HTTPS on Vercel (`https://vercel-full-deployment.vercel.app`), there are zero Mixed Content errors and API calls work whether accessed standalone or embedded in Vercel.
3. `price-board/static/index.html`:
   - Change line 8 `<link rel="stylesheet" href="/style.css?v=8">` to `href="style.css?v=8"` (or `./style.css?v=8`) so it doesn't 404 under `/embed_banggia/`.
4. `econolens-chat/public/app.js`:
   - Ensure API endpoints correctly prefix with `/embed_econolens/api` or relative routing when running inside Gateway/Vercel.
5. `market-pulse/gateway/app.py`:
   - Add CORS headers (via `@app.after_request` adding `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Headers: *`, `Access-Control-Allow-Methods: *`).
   - Add caching for `/api/market/board` (cache in memory with 15-30 second TTL) to prevent 6-second compute lag and Vercel 502 proxy timeouts.
   - For `/api/stock/<sym>`, if a ticker is not in `market.db` (such as active board tickers 'DMX', 'LPS', 'KAI', 'V68', 'ULG', 'PCB'), handle it gracefully by providing basic live data or profile so clicking any stock on the board never crashes or dead-ends.
6. `data-crawler`:
   - Fix any `from vnstock import Listing` import error so `/health` and crawler endpoints work cleanly.
7. Restart/reload affected services (Gateway PID 29176, Price Board PID 1816, etc.) if modified so the running processes reflect your changes.
8. Execute verification commands against local endpoints and Vercel public endpoints (`https://vercel-full-deployment.vercel.app`).
9. Document your exact diffs, test commands, and verification evidence in:
   C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_worker_remediation_1\handoff.md
When done, message parent orchestrator.
