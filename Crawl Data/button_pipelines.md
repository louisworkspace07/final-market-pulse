# Button Pipelines Documentation — Market Pulse System

Document cataloging 100% of UI buttons (29 cataloged buttons across Control Panel, Ticker Picker Modal, User Dashboard `user.html`, and Automated Pipeline).

---

## Tier 0: System Health & AI Config

### 1. Check Gemini Status Button (`#btnGem`)
- **Input**: Click event (`onclick="checkGemini(event)"`), no form input.
- **Python Endpoint/Function**: `POST /gemini_check` -> `gemini_check()` in `app.py`.
- **Background Processing**: Calls `cdp_available()` to verify Chrome Remote Debugging Port 9222 is listening. Initializes `GeminiCDP` context, executes `preflight()` on Gemini web tab to check DOM for login state / CAPTCHA block (error 1095) / readiness without initiating full analysis pass.
- **Output/UI State Returned**: Response JSON `{state: "ready"|"blocked"|"login"|"nocdp"|"error", ok: boolean, msg: string}`. DOM `#h_gemini` text and style updated (e.g. `✓ sẵn sàng` in green, `⛔ bị chặn CAPTCHA (1095)` in red). Toast alert displayed in top-right notification stack.

### 2. Save Delay Button (`setDelay`)
- **Input**: Click event (`onclick="setDelay(event)"`), number input `#delayInput` (0-120 seconds).
- **Python Endpoint/Function**: `POST /set_delay` -> `set_delay()` in `app.py`.
- **Background Processing**: Validates `delay` float range (0-120s), writes value to text configuration file `config/gemini_delay.txt`. Dynamic delay reader in `src.gemini_cdp` reads file live during runtime passes.
- **Output/UI State Returned**: Response JSON `{ok: true, delay: float}`. Toast message confirming delay setting (applied immediately for subsequent Gemini calls).

### 3. Launch Chrome CDP Button (`run('launch')`)
- **Input**: Click event (`onclick="run('launch')"`), payload `{task: "launch"}`.
- **Python Endpoint/Function**: `POST /run` with `{task: "launch"}` -> `run()` in `app.py` -> spawns background thread running `_run_task("launch", "scripts.launch_chrome", ...)`.
- **Background Processing**: Spawns python subprocess `-m scripts.launch_chrome` with UTF-8 environment variables. Subprocess launches Chrome browser with `--remote-debugging-port=9222` and profile directory `chrome_cdp_profile`. Streams stdout/stderr to `logs/run.log`.
- **Output/UI State Returned**: Response JSON `{ok: true}`. Control panel buttons disabled (`setBusy(true)`), status badge updated to `● Đang chạy` with spinner, log polling `/poll` initiated to stream stdout to log viewer `#log`, status indicator `#h_cdp` updated upon health poll.

### 4. Test Gemini API Button (`run('test_gemini')`)
- **Input**: Click event (`onclick="run('test_gemini')"`), payload `{task: "test_gemini"}`.
- **Python Endpoint/Function**: `POST /run` with `{task: "test_gemini"}` -> `run()` in `app.py` -> spawns background thread running `_run_task("test_gemini", "scripts.test_gemini", ...)`.
- **Background Processing**: Spawns subprocess `-m scripts.test_gemini`. Connects to Gemini web tab via CDP or API key, sends test prompt ("Ping"), parses response to confirm AI latency and model operationality.
- **Output/UI State Returned**: Response JSON `{ok: true}`. Control panel set to busy, status badge running, stdout polled & rendered to log terminal (`#log`), status badge updated to `● Hoàn tất` (rc=0) or `● Lỗi`.

---

## Tier 1: P0 Discovery & Symbol Selection

### 5. P0 Fetch Symbols Button (`run('p0')`)
- **Input**: Click event (`onclick="run('p0')"`), payload `{task: "p0"}`.
- **Python Endpoint/Function**: `POST /run` with `{task: "p0"}` -> `run()` in `app.py` -> background thread `_run_task("p0", "scripts.p0_symbols", ...)`.
- **Background Processing**: Executes `scripts.p0_symbols`. Connects to market data API (vnstock/SSI), fetches full listing of market symbols (HOSE, HNX, UPCOM), updates `database/symbols.json` and populates `companies` table in SQLite `database/market.db`.
- **Output/UI State Returned**: Response JSON `{ok: true}`. Log viewer streams live symbol counts, progress bar updates stage `P0`, header stats refreshed via `/stats`.

### 6. Manual Ticker Picker Button (`openPicker()`)
- **Input**: Click event (`onclick="openPicker()"`).
- **Python Endpoint/Function**: Client-side JS function -> fetches `GET /symbols?limit=80` & `GET /tickers`.
- **Background Processing**: `app.py` `symbols()` reads `database/symbols.json` and filters by search query `q`. `get_tickers()` reads `config/companies.txt`.
- **Output/UI State Returned**: Opens modal `#modal` (`display: block`). Populates symbol list in `#results` with checkboxes and `#chosen` chip list with count badges `#selcount` and `#chcount`.

---

## Tier 2 & 3: Data Ingestion

### 7. P3 Auto Batch Crawl Button (`runP3Group()`)
- **Input**: Click event (`onclick="runP3Group()"`), dropdown `#p3group` (VN30/VN100/HOSE/HNX/UPCOM/ALL/CUSTOM), checkbox `#p3recrawl`, input `#p3limit`.
- **Python Endpoint/Function**: `POST /run` with `{task: "p3", group: string, no_resume: bool, limit: int}` -> `run()` in `app.py` -> background thread `_run_task("p3", "scripts.p3_crawl_all", ...)`.
- **Background Processing**: Spawns subprocess `scripts.p3_crawl_all`. Resolves target symbols for chosen group via `src.board`. Crawls balance sheets, income statements, cash flows, ratios, company profiles, leadership, shareholders, prices, news, and events. Writes directly to SQLite `database/market.db` and json files under `companies/<SYM>/`. Updates `crawl_state` table with stage status.
- **Output/UI State Returned**: Response JSON `{ok: true}`. Log streaming to `#log`, real-time update of progress bar (`#pfill`, `#pnum`, `#pdone`, `#perr`), dynamic symbol grid `#grid` showing per-symbol breakdown columns (`balance_sheet`, `income_statement`, etc.), header stats periodically refreshed via `/stats`.

### 8. P1 Financials Button (`run('p1')`)
- **Input**: Click event (`onclick="run('p1')"`), payload `{task: "p1"}`.
- **Python Endpoint/Function**: `POST /run` with `{task: "p1"}` -> `run()` in `app.py` -> thread `_run_task("p1", "scripts.p1_financials", ...)`.
- **Background Processing**: Executes `scripts.p1_financials` for selected ticker sample (from `config/companies.txt`). Crawls quarterly and annual financial statements, cash flows, and price history. Saves to SQLite `financials` & `price` tables.
- **Output/UI State Returned**: Response JSON `{ok: true}`. UI locked to busy, status badge `● Đang chạy`, stdout line parsing (`[1/N] SYM`) updating progress bar and grid rows, completion badge `● Hoàn tất`.

### 9. P2 News & Events Button (`run('p2')`)
- **Input**: Click event (`onclick="run('p2')"`), payload `{task: "p2"}`.
- **Python Endpoint/Function**: `POST /run` with `{task: "p2"}` -> `run()` in `app.py` -> thread `_run_task("p2", "scripts.p2_company", ...)`.
- **Background Processing**: Executes `scripts.p2_company` for tickers in `config/companies.txt`. Crawls company profile, key executives, top shareholders, subsidiary info, and news events. Stores into SQLite `news`, `company` tables and `companies/<SYM>/company_profile.json`.
- **Output/UI State Returned**: Response JSON `{ok: true}`. Log stream outputting crawl progress, matrix grid updated for news/events columns, progress bar advancement.

---

## Tier 4: P4 AI Financial Analysis

### 10. P4 Resume Analysis Button (`runP4Resume()`)
- **Input**: Click event (`onclick="runP4Resume()"`), dropdown `#p4group`, select `#backend`, password input `#apikey`, input `#p4limit`.
- **Python Endpoint/Function**: `POST /run` with `{task: "p4", group: string, reanalyze: false, backend: string, apikey: string, limit: int}` -> `run()` in `app.py` -> thread `_run_task("p4", "scripts.p4_analyze", ...)`.
- **Background Processing**: Executes `scripts.p4_analyze`. Sets environment variables `AI_BACKEND` and `LOCAL_API_KEY`. Queries SQLite `ai_analysis` table for already analyzed symbols in group and skips them (`resume` mode). For remaining unanalyzed symbols, prepares prompt from financial statements & news, connects to Gemini via CDP browser session or API backend, streams prompt pass, receives JSON evaluation (F-Score, health score, business risks), saves debug logs in `companies/<SYM>/analysis/debug/`, and writes results to SQLite `ai_analysis`.
- **Output/UI State Returned**: Response JSON `{ok: true}`. Progress bar tracks AI evaluation status, grid `#grid` shows AI analysis ticks, `#ai_status_badge` counts updated after run.

### 11. P4 Reanalyze Button (`runP4Reanalyze()`)
- **Input**: Click event (`onclick="runP4Reanalyze()"`), JavaScript `confirm()` prompt ("⚠️ Bạn có chắc chắn muốn chạy lại phân tích AI từ đầu?..."), dropdown `#p4group`, select `#backend`, password input `#apikey`, input `#p4limit`.
- **Python Endpoint/Function**: `POST /run` with `{task: "p4", group: string, reanalyze: true, backend: string, apikey: string, limit: int}` -> `run()` in `app.py` -> thread `_run_task("p4", "scripts.p4_analyze", ...)` with `--reanalyze` flag.
- **Background Processing**: If user cancels `confirm()`, action terminates client-side. If confirmed, sends request with `reanalyze: true`. Backend passes `--reanalyze` flag to `scripts.p4_analyze`. Overwrites existing analysis entries in SQLite `ai_analysis` and forces fresh AI pass for every symbol in group regardless of previous state.
- **Output/UI State Returned**: Response JSON `{ok: true}`. Progress bar resets to 0% and begins tracking forced reanalysis across group, live stdout streamed to `#log`.

---

## Tier 5: P5 Publishing & UI Dashboard Launch

### 12. P5 Export JSON Button (`run('p5')`)
- **Input**: Click event (`onclick="run('p5')"`), payload `{task: "p5"}`.
- **Python Endpoint/Function**: `POST /run` with `{task: "p5"}` -> `run()` in `app.py` -> thread `_run_task("p5", "scripts.p5_export", ...)`.
- **Background Processing**: Executes `scripts.p5_export`. Queries SQLite database tables (`companies`, `financials`, `ai_analysis`, `news`, `price`), synthesizes compiled JSON payload per company into `web/data/detail/<SYM>.json` and index summary into `web/data/companies.json` for frontend consumption.
- **Output/UI State Returned**: Response JSON `{ok: true}`. Log viewer streams export status for each symbol, toast notification upon completion, UI dashboard data files refreshed.

### 13. Open UI Dashboard Button (`window.open('/app/', '_blank')`)
- **Input**: Click event (`onclick="window.open('/app/', '_blank')"`).
- **Python Endpoint/Function**: Endpoint `GET /app/` -> `comparison()` in `app.py`.
- **Background Processing**: Flask static file handler serves `web/user.html` (User Dashboard interface).
- **Output/UI State Returned**: Opens user dashboard (`user.html`) in a new browser tab with interactive financial stock view and AI summaries.

---

## Tier 6: Unified Automated Pipeline

### 14. 1-Click Run Pipeline Button (`runPipeline()`)
- **Input**: Click event (`onclick="runPipeline()"`), select `#pgroup`, select `#backend`, input `#apikey`, checkbox `#preanalyze`.
- **Python Endpoint/Function**: `POST /run` with `{task: "pipeline", group: string, backend: string, apikey: string, reanalyze: bool}` -> `run()` in `app.py` -> thread `_run_task("pipeline", "scripts.pipeline", ...)`.
- **Background Processing**: Spawns subprocess `-m scripts.pipeline` with `--group`, `--backend`, and optionally `--reanalyze`. Executes full sequence end-to-end: P1 Financial Crawl -> P2 News Crawl -> P4 AI Analysis -> P5 Data Export. Automatically manages rate-limits and batch pauses between stages.
- **Output/UI State Returned**: Response JSON `{ok: true}`. Control panel enters busy state, progress bar tracks overall pipeline stage (`=== STAGE financials ===`, `=== STAGE analyze ===`), stdout streamed to `#log`, status badge updates to `● Hoàn tất`.

---

## Control Panel Bottom Bar & Log Controls

### 15. Stop Task Button (`stop()`)
- **Input**: Click event (`onclick="stop()"`).
- **Python Endpoint/Function**: `POST /stop` -> `stop()` in `app.py`.
- **Background Processing**: Checks running subprocess `_proc`. Calls `_terminate_tree(pid)`: terminates process and all recursive child subprocesses (e.g. Chrome CDP / Playwright instances). If process does not exit in 3 seconds, forcefully executes `kill()`. Cleans up `logs/run.pid`.
- **Output/UI State Returned**: Response JSON `{ok: true, msg: string}`. Toast notification ("Đã gửi lệnh dừng"), UI unbusy (buttons re-enabled), status badge updated to `● Lỗi (mã -15/1)`.

### 16. Open Analytics Tab Button (`window.open('/app/','_blank')`)
- **Input**: Click event (`onclick="window.open('/app/','_blank')"`).
- **Python Endpoint/Function**: Endpoint `GET /app/` -> `comparison()` in `app.py`.
- **Background Processing**: Serves static file `web/user.html`.
- **Output/UI State Returned**: Opens `web/user.html` in new browser tab.

### 17. Open Price Board Button (`window.open('/app/board.html','_blank')`)
- **Input**: Click event (`onclick="window.open('/app/board.html','_blank')"`).
- **Python Endpoint/Function**: Endpoint `GET /app/board.html` -> `comparison("board.html")` in `app.py`.
- **Background Processing**: Serves static file `web/board.html`.
- **Output/UI State Returned**: Opens interactive price board (`board.html`) displaying market tickers, scores, and price tables.

### 18. Log Filter Button (`#btnErr`)
- **Input**: Click event (`onclick="toggleErr(event)"`).
- **Python Endpoint/Function**: Client-side JS function `toggleErr()`.
- **Background Processing**: Toggles boolean flag `errOnly`. Filters `LOG_LINES` array looking for error markers (`✗`, `[LỖI]`, `Traceback`, `Lỗi`). Re-renders log element `#log`.
- **Output/UI State Returned**: Button class toggles `.active`. `#log` content switches between showing full stdout and showing error-only lines.

### 19. Download Log Button
- **Input**: Click event (`onclick="downloadLog(event)"`).
- **Python Endpoint/Function**: Client-side JS function `downloadLog()`.
- **Background Processing**: Creates Blob from `LOG_LINES.join('\n')` text with `text/plain` MIME type. Generates temporary Object URL `URL.createObjectURL(blob)` and triggers hidden `<a>` download element.
- **Output/UI State Returned**: Triggers browser file download dialog saving `run-log-YYYY-MM-DD-HH-mm-ss.txt`.

---

## Ticker Picker Modal Buttons

### 20. Close Picker Button (`closePicker()`)
- **Input**: Click event (`onclick="closePicker()"`).
- **Python Endpoint/Function**: Client-side JS function `closePicker()`.
- **Background Processing**: None.
- **Output/UI State Returned**: Hides modal window `#modal` (`display: none`).

### 21. Add Typed Ticker Button (`addTyped()`)
- **Input**: Click event (`onclick="addTyped()"`), text input `#psearch`.
- **Python Endpoint/Function**: Client-side JS function `addTyped()`.
- **Background Processing**: Converts string in `#psearch` to uppercase, adds to JS `CHOSEN` Set object.
- **Output/UI State Returned**: Re-renders `#chosen` chip list, updates counter `#chcount`, updates symbol checkboxes in `#results`.

### 22. Clear Chosen Tickers Button (`clearChosen()`)
- **Input**: Click event (`onclick="clearChosen()"`).
- **Python Endpoint/Function**: Client-side JS function `clearChosen()`.
- **Background Processing**: Executes `CHOSEN.clear()`.
- **Output/UI State Returned**: Empties `#chosen` chip container, resets counter `#chcount` to 0, unchecks all symbol checkboxes in `#results`.

### 23. Save Tickers List Button (`saveTickers()`)
- **Input**: Click event (`onclick="saveTickers()"`), `CHOSEN` Set containing selected ticker symbols.
- **Python Endpoint/Function**: `POST /tickers` -> `set_tickers()` in `app.py`.
- **Background Processing**: Endpoint receives JSON array of tickers. Deduplicates symbols, formats header comments, and writes text payload to file `config/companies.txt`.
- **Output/UI State Returned**: Response JSON `{ok: true, count: int}`. Updates UI label `#tickcount` ("Đang chọn: N mã"), closes modal, displays toast alert ("Đã lưu N mã...").

---

## User Dashboard Buttons (`user.html`)

### 24. AI Dual-Company Comparison (`openCompare()` / `runCompare()`)
- **Input**: Click event (`onclick="openCompare()"`), dropdown selections `#selA` and `#selB`, trigger button click (`onclick="runCompare()"`).
- **Python Endpoint/Function**: `GET /api/compare?a=SYM1&b=SYM2` -> `api_compare()` in `app.py`.
- **Background Processing**: Endpoint validates ticker symbols. Uses thread lock `_compare_lock`. Connects to SQLite `market.db`, invokes `src.analyzer.compare_two(conn, a, b)`, prompts Gemini AI for side-by-side comparative analysis of financial metrics, moat, and risk, returning structured comparison dict.
- **Output/UI State Returned**: `openCompare()` opens modal `#cmodal` (`display: block`). `runCompare()` reads inputs `#selA` and `#selB`, calls `GET /api/compare?a=SYM1&b=SYM2`, and renders winner banner, head-to-head comparison cards, AI recommendation summary, and expert verdict inside `#cmodal` (`#cresult`).

### 25. Reanalyze / Refresh Symbol Button (`refbtn` / `refresh(sym)`)
- **Input**: Click event (`onclick="refresh('SYM')"` or `#refbtn`).
- **Python Endpoint/Function**: `GET /api/refresh_stream?sym=SYM` -> `refresh_stream()` in `app.py`.
- **Background Processing**: Checks 5-minute cooldown per symbol via SQLite `ai_analysis` timestamp. Sets lock `_refresh_lock`. Connects via Server-Sent Events (SSE). Concurrently triggers single-symbol financial crawl `crawler_financials.crawl_one`, company crawl `crawler_company.crawl_one`, AI re-analysis `analyzer.analyze_one`, and triggers `scripts.p5_export.main()`.
- **Output/UI State Returned**: Returns SSE stream (`text/event-stream`). Updates inline status message element `#refmsg` with step-by-step progress text (`⏳ Đang khởi tạo…`, `📊 Đang cào BCTC...`, `🤖 AI đang phân tích...`, etc.), and reloads page data upon receiving `DONE`.

### 26. Close Compare Modal Button (`closeCompare()`)
- **Input**: Click event (`onclick="closeCompare()"`), close button `✕` in modal header `#cmodal` or `Escape` key press.
- **Python Endpoint/Function**: None (Client-side JS function `closeCompare()`).
- **Background Processing**: None.
- **Output/UI State Returned**: Hides compare modal window `#cmodal` (`display: none`).

### 27. Close Debug Modal Button (`closeDbg()`)
- **Input**: Click event (`onclick="closeDbg()"`), close button `✕` in debug modal header `#dbgmodal`.
- **Python Endpoint/Function**: None (Client-side JS function `closeDbg()`).
- **Background Processing**: None.
- **Output/UI State Returned**: Hides debug modal window `#dbgmodal` (`display: none`).

### 28. View Debug Pass / Prompt Button (`viewPass(sym, key)`)
- **Input**: Click event (`onclick="viewPass('SYM', 'KEY')"`), button "Xem prompt/raw" in debug table inside `#dbgmodal` / `#debugCard`.
- **Python Endpoint/Function**: `GET /api/debug/<sym>/<key>` -> `api_debug_pass(sym, key)` in `app.py`.
- **Background Processing**: Reads debug JSON file located at `companies/<SYM>/analysis/debug/<KEY>.json` containing full prompt string, raw AI response, pass title, and backend metadata.
- **Output/UI State Returned**: Opens modal `#dbgmodal` (`display: block`), populates `#dbgTitle` with pass title/backend, and renders formatted prompt and raw AI output text into `#dbgBody`.

### 29. View Raw Source Data Button (`viewSource(sym, key)`)
- **Input**: Click event (`onclick="viewSource('SYM', 'KEY')"`), source link in manifest data table (`onclick="viewSource('SYM', 'KEY')"`).
- **Python Endpoint/Function**: `GET /api/source/<sym>/<key>` -> `api_source_content(sym, key)` in `app.py`.
- **Background Processing**: Looks up relative file path and label for dataset key in manifest `_SOURCES`. Reads JSON or JSONL content from `companies/<SYM>/<rel>`, formatting up to 400 rows or object payload.
- **Output/UI State Returned**: Opens modal `#dbgmodal` (`display: block`), sets `#dbgTitle` with source label and file path, and renders formatted JSON data or table rows into `#dbgBody`.
