# Phân tích chi tiết 4 dự án thành phần — từng file, giá trị tái dùng

> Khảo sát trực tiếp mã nguồn 2026-07-06 (không suy đoán). Mỗi bảng: file → chức năng thật
> → giá trị cho hệ thống gộp (Stock Explorer + Tổng quan :9999).
> Ký hiệu: ⭐ = tài sản quan trọng nên tái dùng ngay; ⚠️ = lưu ý/giới hạn.

---

## 1. Crawl Data (`../Crawl Data`) — Flask :5000, pipeline P0→P5

**Vai trò tổng:** tầng dữ liệu nền. Điểm bất ngờ: `src/` là một THƯ VIỆN dữ liệu thị trường
hoàn chỉnh (vnstock + vndirect) chứ không chỉ crawler.

| File | Chức năng thật | Giá trị cho hệ gộp |
|---|---|---|
| `app.py` | Bảng điều khiển web :5000: chạy từng bước P0..P5 qua subprocess, bóc log → progress, SSE. `TASKS` map: p0 symbols, p1 BCTC, p2 tin tức/sự kiện, p3 bung toàn thị trường, p4 phân tích AI, p5 export | Panel vận hành dữ liệu — giữ nguyên, link từ trang Hệ sinh thái |
| `src/board.py` ⭐⭐ | `group_symbols(group)` — **vnstock `Listing().symbols_by_group()`: VN30/VN100/HOSE/HNX/UPCOM native**, cache TTL, tự giới hạn (HOSE 300, HNX 250, UPCOM 200). `get_board(group)` — **bảng giá vnstock Trading VCI cho BẤT KỲ nhóm nào**, cache | **Giải trọn Phase 1 Stock Explorer**: khỏi seed vndirect, khỏi phụ thuộc Test tool cho danh sách nhóm. Import trực tiếp |
| `src/vndirect.py` ⭐ | REST vndirect: `price_history(symbol, start, end)`, `quotes(symbols)` THEO LÔ, `valuation(symbol)` (P/E, P/B), `profile(symbol)` | Giá + định giá cho mã ngoài 33 mã có price trong db |
| `src/fundamentals.py` ⭐ | `compute(symbol)` từ BCTC đã crawl: chuỗi doanh thu/LN, YoY, margins, Piotroski `_piotroski()`, `_health_score()` 0-100, `_valuation_verdict()` | Input chuẩn cho Task 2 (Cơ bản) của deep-dive — khỏi tự tính lại |
| `src/analyzer.py` ⭐ | `_build_prompt()` phân tích cơ bản 1 mã (metrics + peer + reasons block), `analyze_one()`, `compare_two(a,b)` so sánh 2 mã, backend resolve claude/gemini-CDP/mock | `compare_two` = tính năng so sánh mã có sẵn; prompt block pattern tái dùng cho Task 2 |
| `src/peers.py` | `compute(conn, symbol)` — so ROE/ROA/nợ với mã cùng ngành | Khối "so với ngành" trong trang chi tiết mã |
| `src/gemini_cdp.py` | class `GeminiCDP` — client CDP thứ 2 (connect_over_cdp :9222, profile `chrome_cdp_profile/`) | Đã có transport riêng ở :9999 — chỉ tham khảo |
| `src/storage.py` | Schema + upsert companies/news/events/price/financials, `_migrate` | Tài liệu schema chuẩn của market.db (CHỈ ĐỌC từ :9999) |
| `src/httpguard.py`, `ratelimit.py`, `runner.py` | TokenBucket rate-limit toàn cục vá vào requests, retry khi 429 | ⚠️ Bài học: khi :9999 gọi vnstock/vndirect nhiều phải rate-limit tương tự |
| `src/crawler_financials.py`, `crawler_company.py` | Crawl BCTC/tin/sự kiện từng mã (vnstock) | Nguồn dữ liệu — chạy qua panel :5000 |
| `scripts/p0..p5, pipeline.py` | Các bước pipeline gọi src/* | Vận hành |
| `database/market.db` | companies 1.527 (⚠️ exchange RỖNG), price 33 mã, news 40 mã, events, ai_analysis [CD-mã], financials 145k dòng | Nguồn chính. ⚠️ Giới hạn phủ → bù bằng board.py/vndirect.py |

## 2. Test tool dự án (`../Test tool dự án`) — Flask :5555, bảng giá + Gemini worker

**Vai trò tổng:** thị trường sống + phân tích kỹ thuật AI từng mã. Điểm bất ngờ: đã có sẵn
API OHLC 3 năm cho mọi mã + VBP intraday + danh sách chỉ số/ngành đã scrape.

| File | Chức năng thật | Giá trị cho hệ gộp |
|---|---|---|
| `server.py` ⭐ | Routes: `/api/stocks` (bảng giá VN30 realtime); **`/api/history/<symbol>` — OHLC 1D 3 NĂM entrade, cache 60s, MỌI mã**; **`/api/vbp/<symbol>` — Volume-by-Price intraday nến 1 phút 5 ngày** (⚠️ lỗi → MOCK data random!); `/api/analyze` POST; cụm `/api/gemini/*` điều khiển worker | `/api/history` = nguồn nến cho trang chi tiết mã (thay gọi entrade trực tiếp); ⚠️ VBP mock khi lỗi — phải kiểm tra trước khi tin |
| `gemini_worker.py` ⭐ | Worker thread Playwright persistent (profile `gemini_profile`), queue+Future, auto-scan VN30 theo giờ, chụp chart `chart_only.html` đính kèm prompt, `generate_prompt_for_symbol()` (sổ lệnh 3 mức + VBP + nến tuần 2 năm + nến ngày 6 tháng, JSON schema S/R) | Pattern gốc của kênh CDP :9999. Prompt per-symbol là mẫu chuẩn cho Task 1 deep-dive; auto-scan là "nhà máy" sinh [TT-mã] |
| `static/categories.json` ⭐ | **vn100 (100), hnx30 (30), vnallshare (427), vnxallshare (726), vnsmallcap (327), etf (22), hose_lo_le (500)** — đã scrape sẵn | Fallback offline cho nhóm khi vnstock lỗi; nguồn VN100 tức thì |
| `static/industries.json` ⭐ | 19 ngành → 124 mã tiêu biểu | Nhóm "theo ngành" curated (gọn hơn 13 sector của db) |
| `fetch_categories.py`, `fetch_indices.py`, `scrape_industries.py` | Script sinh 2 JSON trên | Chạy lại khi cần cập nhật rổ chỉ số |
| `scrape_banggia.py`, `scrape_history.py` | Crawler bảng giá → `temp_data/data.json` | Nguồn cache board khi server tắt (đang dùng ở :9999) |
| `static/chart_only.html` | Trang chart thuần để worker chụp ảnh gửi Gemini | Nếu deep-dive muốn đính ảnh chart qua CDP — pattern có sẵn |
| `static/index.html`, `app.js` | UI bảng giá + panel phân tích AI | Tham khảo UX |
| `temp_data/ai_cache.json` | Kết quả S/R từng mã [TT-mã]: trend/support_resistance/supply_demand/conclusion/strategy/chart_lines | Đang dùng làm bằng chứng [TT] ở :9999 |
| `auto_analyze.py`, `gemini_cdp.py`, `check_*.py`, `test*.py` | Script thử nghiệm/debug DOM Gemini | Không tái dùng |

## 3. AI Analyze Economic — EconoLens (`../AI Analyze Economic`) — Node :3000

**Vai trò tổng:** tầng AI hội thoại đa persona + auth. Điểm bất ngờ: có sẵn endpoint
`/api/clarify` — pattern "AI hỏi lại người dùng" đúng yêu cầu deep-dive.

| File | Chức năng thật | Giá trị cho hệ gộp |
|---|---|---|
| `server.js` | Express: register/login (auth token), `/api/meta`, `/api/history/:persona` (lịch sử chat theo persona), `/api/chat`, **`/api/clarify`** ⭐ — AI sinh CÂU HỎI LÀM RÕ trước khi trả lời | Pattern `/clarify` = mẫu cho bước "AI hỏi thêm về mã" trong deep-dive; auth + lịch sử chat nếu :9999 cần đa người dùng |
| `lib/personas.js` ⭐ | 4 persona (học sinh/phân tích/đầu tư/chính sách) — mỗi persona: system prompt + JSON block schema riêng (giao diện động render theo block) | Kỹ thuật "schema blocks render động" — nguồn gốc cách ép JSON của :9999 |
| `lib/providers.js` | Trừu tượng hoá LLM provider: Gemini API (key từ `.env`) + Chrome bridge | Pattern transport 2 kênh — :9999 đã có bản Python |
| `lib/chrome_bridge.js` | CDP client Node (Gemini web qua Chrome debug) | Bản Node của kênh CDP — tham khảo |
| `lib/db.js` | users.json + chats.json (file-based) | Nhẹ, đủ cho demo đa người dùng |
| `public/app.js`, `index.html`, `style.css` | SPA chat: render block động theo schema persona | Tham khảo UX render block |
| `.env` ⭐ | `GEMINI_API_KEY`, `GEMINI_MODEL` | :9999 đang đọc làm kênh API fallback |

## 4. FinPulse-AI (`../FinPulse-AI`) — Electron desktop

**Vai trò tổng:** tin tức RSS quốc tế + cây phân tích chủ đề. Điểm bất ngờ: có
`parseBranches` — pattern phân rã chủ đề thành nhánh, hợp với "phân tích nhiều lần gửi".

| File | Chức năng thật | Giá trị cho hệ gộp |
|---|---|---|
| `src/feeds.js` ⭐ | Danh mục RSS tài chính quốc tế (CNBC, MarketWatch, CoinDesk...) theo nhóm | Nguồn "tin chuyên ngành quốc tế" cho trang chi tiết mã (ngành XK, hàng hoá) |
| `src/ai.js` ⭐ | `articlePrompt` (tóm tắt bài báo), **`branchPrompt` (phân rã chủ đề → nhánh con), `finalPrompt` (tổng hợp theo path đã chọn), `parseBranches`**; `callApi` (Anthropic) + `callGemini` | Pattern "cây phân tích": mẫu tư duy cho chuỗi task chia nhỏ — mỗi nhánh 1 lần gửi |
| `main.js`, `preload.js` | Electron shell + IPC | Không tái dùng ở web |
| `renderer/*` | UI dashboard tin + cây nhánh + webview | Tham khảo UX cây phân tích |
| `chrome_bridge.py`, `bridge/gemini_bridge.py` | CDP client thứ 3 (Python) cho Gemini web | Trùng chức năng — không dùng thêm |
| `app_pyqt.py` | Bản PyQt cũ | Bỏ |

---

## Tổng hợp: tài sản ⭐ quyết định thay đổi plan Stock Explorer

1. **`Crawl Data/src/board.py`** thay toàn bộ phương án seed nhóm bằng vndirect:
   `group_symbols("VN30"|"VN100"|"HOSE"|"HNX"|"UPCOM")` + `get_board(group)` bảng giá mọi nhóm.
   Fallback offline: `Test tool/static/categories.json` + `industries.json`.
2. **`Test tool /api/history/<symbol>`** (OHLC 3 năm mọi mã, cache) thay việc tự gọi entrade;
   nếu :5555 tắt → gọi entrade trực tiếp theo đúng URL trong file đó.
3. **`Crawl Data/src/fundamentals.py` + `peers.py` + `analyzer.compare_two`** = sẵn khối
   "cơ bản + so ngành + so sánh 2 mã" cho trang chi tiết.
4. **EconoLens `/api/clarify`** = mẫu cho bước AI đặt câu hỏi làm rõ (T4 điểm mù).
5. **FinPulse `branchPrompt`/`parseBranches`** = mẫu chia nhỏ phân tích thành nhánh nhiều lần gửi.
6. ⚠️ Cạm bẫy đã phát hiện: VBP endpoint của Test tool trả **mock random khi lỗi** — hệ gộp
   phải tự tính VBP từ OHLC thật (đã có `_vbp_nodes` ở :9999) hoặc đánh dấu nguồn mock;
   `companies.exchange` rỗng; news chỉ phủ 40 mã (mã khác → chỉ có tin ngành).
