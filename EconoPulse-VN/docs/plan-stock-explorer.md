# PLAN — Stock Explorer: gộp 4 hệ thống quanh trải nghiệm "chọn nhóm → chọn mã → phân tích sâu"

> Mục tiêu (lời khách hàng): xem **tổng quan theo nhóm** (HOSE, VN30, VN100, theo ngành) →
> **bấm vào 1 mã** → thấy ngay phân tích kỹ thuật + tin tức liên quan + tin ngành →
> có **luồng AI riêng cho mã đó**: chia NHIỀU lần gửi Gemini (web chat giới hạn input/output),
> AI phải chỉ ra **điểm mù** và lý do đằng sau tin tức, đạt độ chi tiết lý tưởng.

Mỗi phase tự chứa, thực thi được trong 1 phiên chat mới. Base dir:
`C:\Users\MSI\Desktop\Final AI Analyze VN All market Stock\EconoPulse-VN`

---

## Phase 0 — Sự thật đã kiểm chứng (KHÔNG cần khám phá lại)

> **Phân tích chi tiết TỪNG FILE của 4 dự án: xem `docs/phan-tich-4-du-an.md`** (khảo sát
> 2026-07-06). Tóm tắt tài sản làm thay đổi plan: `Crawl Data/src/board.py` (nhóm VN30/VN100/
> HOSE/HNX/UPCOM + bảng giá mọi nhóm qua vnstock), Test tool `/api/history/<symbol>` (OHLC 3
> năm mọi mã), `categories.json`/`industries.json` (rổ chỉ số + 19 ngành offline),
> `fundamentals.py`/`peers.py`/`compare_two` (cơ bản + so ngành + so 2 mã), EconoLens
> `/api/clarify` (AI hỏi lại), FinPulse `branchPrompt`/`parseBranches` (phân rã nhánh).

Dữ liệu thật (đã query trực tiếp 2026-07-06):

| Nguồn | Có gì | Giới hạn |
|---|---|---|
| `../Crawl Data/database/market.db` | `companies(symbol, organ_name, exchange, sector, market_cap, current_price)` — 1.527 mã, 13 ngành; `price(symbol,time,close,volume)`; `news(symbol,title,public_date)`; `events`; `ai_analysis(symbol,analysis,updated_at)` [CD-mã] | ⚠️ **`exchange` RỖNG toàn bộ** (giá trị `''`); giá lịch sử chỉ **33 mã**; news chỉ **40 mã** |
| Test tool `:5555/api/stocks` + cache `temp_data/data.json` | Bảng giá realtime ~29 mã lớn (khớp, sổ lệnh 3 mức, khối ngoại) | chỉ nhóm VN30-ish |
| Test tool `temp_data/ai_cache.json` | Phân tích S/R từng mã của Gemini [TT-mã]: trend, support_resistance, chart_lines | chỉ mã đã quét |
| API entrade (pattern sẵn ở `../Test tool dự án/gemini_worker.py:516-517`) | Nến 1D/1W **bất kỳ mã nào**: `https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol=X&resolution=1D&from=..&to=..` | cần internet |
| API vndirect (pattern `gemini_worker.py:520`) | `https://bdcapi.vndirect.com.vn/api/v1/stock/stock?symbols=X` — thông tin sàn/giá 1 mã | cần internet |

Hạ tầng tái dùng (đường dẫn chính xác):
- Job engine 5 bước + polling: `modules/market_overview/orchestrator.py` (hàm `start_overview`, `_set_step`, `get_job`, `_ask_json` retry JSON)
- Kênh AI CDP→API: `modules/market_overview/gemini_transport.py` (`ask_gemini`, `parse_json_answer`, backoff 429/503)
- S/R + VBP thuần Python: `modules/market_overview/technical.py` (`support_resistance`, `_swing_levels`, `_vbp_nodes`)
- Bằng chứng có ID [N..][E..][TT..][CD..]: `modules/market_overview/collector.py` (`collect_news`, `collect_flow_outputs`)
- UI steps progress: `gateway/static/js/overview.js` (`renderSteps`, `startOverview` polling 2.5s)
- Trang mẫu + nav: `gateway/static/market.html`, `js/market.js` (bảng lọc/tìm kiếm health)

**Anti-patterns (cấm):**
- KHÔNG group theo `companies.exchange` (rỗng) khi chưa seed.
- KHÔNG gửi cả bundle dữ liệu 1 mã trong 1 prompt — web chat giới hạn; mỗi task 1 prompt gọn (<8.000 ký tự), chỉ chuyển tiếp JSON đã chưng cất của task trước.
- KHÔNG để LLM tự bịa số — mọi claim phải tham chiếu ID bằng chứng, giữ đúng luật của `_prompt_task2` hiện có.
- KHÔNG tạo bảng mới trong market.db (db của dự án Crawl Data — chỉ đọc).

---

## Phase 1 — Universe & Groups: `modules/stocks/universe.py`

> ĐÃ SỬA sau khảo sát file (xem `docs/phan-tich-4-du-an.md`): KHÔNG cần seed vndirect —
> `../Crawl Data/src/board.py` đã có sẵn `group_symbols()` + `get_board()` cho mọi nhóm.

**Làm gì:**
1. `modules/stocks/universe.py`:
   - Nguồn nhóm 3 lớp fallback:
     a) **`Crawl Data/src/board.py:28` `group_symbols("VN30"|"VN100"|"HOSE"|"HNX"|"UPCOM")`**
        (vnstock `Listing().symbols_by_group`, cache TTL sẵn) — thêm `sys.path` tới
        `../Crawl Data` rồi `from src.board import group_symbols, get_board`;
     b) offline: **`../Test tool dự án/static/categories.json`** (vn100/hnx30/vnallshare...)
        + **`static/industries.json`** (19 ngành curated);
     c) `companies.sector` trong market.db (13 ngành, phủ 1.527 mã).
   - `list_groups()` → [{id, label, n}] gồm: VN30, VN100, HOSE, HNX, UPCOM, 19 ngành.
   - `group_overview(group_id)` → bảng giá cả nhóm qua **`get_board(group)` (board.py:57,
     vnstock Trading VCI — mọi nhóm, không chỉ VN30)**; fallback board Test tool/cache;
     enrich: điểm sức khỏe (health_scores.json), vị trí S/R nếu thuộc 33 mã có price;
     breadth tăng/giảm nhóm.
   - ⚠️ Rate-limit: vnstock gọi nhiều dễ 429 — cache kết quả nhóm 120s (noi theo
     `_GROUP_CACHE`/`_BOARD_CACHE` trong board.py, xem thêm `src/httpguard.py`).
2. Routes trong `gateway/app.py`: `GET /api/stocks/groups`,
   `GET /api/stocks/list?group=vn30|vn100|hose|sector:<tên>`.

**Verify:** `curl :9999/api/stocks/list?group=vn100` trả ~100 mã trùng ≥90% với
`categories.json.vn100`; `group=sector:Dầu khí` trả GAS/PVD/BSR...; rút mạng → fallback
categories.json vẫn trả nhóm.

---

## Phase 2 — Trang chi tiết mã: `modules/stocks/detail.py`

**Làm gì:** `get_stock_detail(symbol)` trả bundle JSON (mọi phần đều kèm `source`, `updated_at`):
- `profile`: từ `companies` (tên, ngành, vốn hoá); bổ sung P/E, P/B từ
  `Crawl Data/src/vndirect.py:103` `valuation(symbol)` (REST, có timeout).
- `candles`: ưu tiên Test tool **`GET :5555/api/history/<symbol>`** (OHLC 1D 3 năm, cache 60s
  — `server.py:163-195`); server tắt → gọi entrade trực tiếp cùng URL; cuối cùng → bảng
  `price` market.db (33 mã). Lỗi hết → `candles: null`.
- `technical`: `support_resistance()` + RSI trên candles vừa lấy (import từ
  `modules/market_overview/technical.py`). ⚠️ KHÔNG dùng `:5555/api/vbp/<symbol>` — endpoint
  đó trả MOCK random khi lỗi (`server.py:224-236`); tự tính VBP bằng `_vbp_nodes` từ candles.
- `fundamentals`: gọi `Crawl Data/src/fundamentals.py:62` `compute(symbol)` (chuỗi doanh thu/
  LN YoY, Piotroski, health 0-100, valuation verdict) + `src/peers.py:30` `compute()` so ngành.
- `board`: dòng bảng giá live nếu có (lọc từ `get_board()`).
- `news`: `news where symbol=?` (id N..) + `sector_news`: tin của các mã cùng `sector` 30 ngày
  gần nhất (id SN..). ⚠️ news chỉ phủ 40 mã — mã ngoài phủ: ghi rõ "chưa crawl tin mã này,
  chỉ có tin ngành" (transparency, không im lặng).
- `events`, `health` (health_scores.json), `tt_analysis` (ai_cache.json [TT]), `cd_analysis`
  (ai_analysis [CD]).
- Route: `GET /api/stocks/<symbol>` (validate symbol chỉ A-Z0-9, 3-4 ký tự).
- So sánh 2 mã (tài sản sẵn): route `GET /api/stocks/compare?a=X&b=Y` →
  `Crawl Data/src/analyzer.py:268` `compare_two(conn, a, b)`.

**Verify:** `curl :9999/api/stocks/FPT` đủ 9 khối trên; `curl :9999/api/stocks/BCM` (không có trong bảng price) vẫn có candles từ entrade; mã sai `curl :9999/api/stocks/XXXX` → 404 JSON sạch.

---

## Phase 3 — Deep-dive AI chain per-mã: `modules/stocks/deep_dive.py` (TRỌNG TÂM)

**Nguyên tắc:** web chat giới hạn input/output → **chia 5 lần gửi**, mỗi lần 1 nhiệm vụ hẹp,
input chỉ gồm (a) dữ liệu thô ĐÚNG mảng đó đã format gọn + (b) JSON chưng cất của các task trước.
Copy khung job (`_jobs`, `STEPS`, `_set_step`, thread, `start_*`/`get_job`) và `_ask_json`
retry từ `modules/market_overview/orchestrator.py` — đổi state riêng, không dùng chung `_jobs`.

Chuỗi 5 task (mỗi task 1 prompt, JSON_RULE giữ nguyên văn từ orchestrator.py):
1. **T1 Kỹ thuật**: input = candles rút gọn (đóng cửa 60 phiên + 24 tuần, format `dd/mm:giá` như `gemini_worker.py:573-589`) + S/R/VBP/RSI Python + sổ lệnh board. Output schema: `{xu_huong, vung_ho_tro:[], vung_khang_cu:[], cung_cau, tin_hieu:[]}`.
2. **T2 Cơ bản**: input = health score, Z''/F, ROA/ROE, vốn hoá, [CD-mã] nếu có. Output: `{suc_khoe, dinh_gia, diem_manh:[], diem_yeu:[]}`.
3. **T3 Tin tức & nguyên nhân**: input = news [N..] + sector_news [SN..] + events [E..] (tối đa 20 dòng) + T1/T2 JSON. LUẬT trích ID như `_prompt_task2`. Output: `{tac_dong:[{tin, id, tac_dong, ly_do}], tin_nganh_anh_huong:[]}`.
4. **T4 Điểm mù & câu hỏi phản biện** (yêu cầu riêng của khách): input = T1+T2+T3 JSON, KHÔNG dữ liệu thô. Prompt ép vai "nhà đầu tư hoài nghi": liệt kê điểm mù dữ liệu chưa trả lời được (pha loãng/ESOP, sở hữu lớn, kiểm toán, thanh khoản thật, rủi ro ngành/chu kỳ, tin chưa được xác nhận), mỗi điểm kèm **vì sao quan trọng** + **cần tìm dữ liệu gì ở đâu**. Output: `{diem_mu:[{van_de, vi_sao_quan_trong, can_kiem_tra}], cau_hoi_nen_hoi:[]}`. Pattern tham khảo có sẵn: EconoLens `server.js:117` `/api/clarify` (AI sinh câu hỏi làm rõ) và FinPulse `src/ai.js:34` `branchPrompt`/`parseBranches` (phân rã chủ đề thành nhánh — mỗi nhánh 1 lần gửi tiếp).
5. **T5 Tổng hợp**: input = 4 JSON trước. Output: verdict + 3 kịch bản xác suất (schema `kich_ban` giống `_prompt_task3`) + checklist theo dõi.

- Routes: `POST /api/stocks/<symbol>/deepdive` → job_id; `GET /api/stocks/deepdive/<job_id>`.
- Hỏi tiếp theo mã: `POST /api/stocks/<symbol>/ask` — 1 prompt = câu hỏi + T1..T5 JSON đã cache của job gần nhất (đủ gọn cho 1 lần gửi).
- Kênh AI: `ask_gemini(prompt, prefer="auto")` — CDP trước, API sau (đã có sẵn).

**Verify:** chạy deep-dive FPT bằng script CLI (in tiến độ như test cũ của orchestrator); đủ 5 JSON đúng schema; T3 có ID bằng chứng thật; T4 trả ≥4 điểm mù có "vì sao"; đo mỗi prompt `len() < 8000`; `/ask` trả lời có tham chiếu T-JSON.

---

## Phase 4 — Frontend: `stocks.html` (nhóm) + `stock.html` (chi tiết)

**Làm gì:**
1. `gateway/static/stocks.html` + `js/stocks.js`: tab nhóm (VN30 / VN100 / HOSE / HNX / 13 ngành — từ `/api/stocks/groups`), KPI breadth nhóm, bảng mã (giá, ±%, điểm SK, vị trí S/R, có tin mới?) với ô tìm kiếm — copy cấu trúc bảng + filter từ `js/market.js` (`drawHealthTable`). Click dòng → `stock.html?symbol=XXX`.
2. `gateway/static/stock.html` + `js/stock.js`:
   - Header mã + giá + nhóm/ngành; chart Chart.js line từ `candles` + vẽ đường S/R (`chart_lines` style — annotation bằng dataset ngang).
   - 2 cột: kỹ thuật (S/R, RSI, VBP, [TT] nếu có) | tin tức (tab "Tin của mã" / "Tin ngành").
   - Nút **"🔬 Phân tích sâu 5 bước"** → progress steps (copy `renderSteps` từ `js/overview.js`) → render 5 khối kết quả, khối T4 "Điểm mù" nổi bật màu cảnh báo.
   - Khung chat hỏi tiếp về mã (input + lịch sử ngắn, gọi `/api/stocks/<symbol>/ask`).
3. Nav: thêm link "Cổ phiếu" vào 6 trang hiện có (7 file HTML) + `index.html` giữ active đúng.

**Verify (preview :9999):** vào `/stocks.html` → tab VN30 hiện ~29 mã; click FPT → chart + tin hiện; bấm phân tích sâu → 5 bước chạy xong, khối điểm mù có nội dung; console 0 lỗi; mobile 375px không vỡ bảng (bọc `.table-wrap`).

---

## Phase 5 — Verification tổng & chống anti-pattern

1. `grep -rn "exchange" modules/stocks/` — không được đọc trực tiếp cột exchange của db (chỉ groups.json).
2. Kiểm tra prompt budget: log `len(prompt)` cả 5 task với mã nhiều tin nhất (HPG/VCB) — tất cả < 8.000.
3. Chạy full: seed_groups → gateway :9999 → stocks.html → FPT deep-dive qua **CDP** (bật worker) và lặp lại qua **API** (tắt worker) — cả 2 kênh cùng hoàn thành.
4. Regression: 6 trang cũ vẫn chạy (Tổng quan 5 bước, Copilot, Danh mục, Thị trường, Vĩ mô, Hệ sinh thái).
5. Cập nhật `README.md` + `docs/y-tuong-du-thi.md` (thêm luồng Stock Explorer vào sơ đồ AI working flow).
