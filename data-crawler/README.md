# Hệ thống Crawl & Phân tích Doanh nghiệp VN

Crawl dữ liệu từng doanh nghiệp (tài chính, dòng tiền, tin tức, sự kiện) → lưu JSON theo
công ty + SQLite tổng hợp → phân tích AI → web so sánh.

## Cài đặt
```powershell
pip install -r requirements.txt
$env:PYTHONUTF8 = 1     # cần cho tiếng Việt trên console Windows
```

## Cách dễ nhất — Bảng điều khiển web
```powershell
cd data-crawler
python app.py
```
Mở **http://localhost:5000**: bấm nút cho từng bước (P0–P5, mở Chrome/Gemini, chọn backend
phân tích), xem **log trực tiếp + trạng thái đang chạy**, và nút mở trang so sánh.
Trang so sánh nhúng tại `http://localhost:5000/app/`.

---

## Quy trình thủ công (chạy từng script)

| Bước | Lệnh | Việc |
|------|------|------|
| P0 | `python -m scripts.p0_symbols` | Lấy ~1.527 mã toàn thị trường → `database/symbols.json` + bảng `companies` |
| P1 | `python -m scripts.p1_financials` | Crawl BCĐKT/KQKD/dòng tiền/chỉ số cho mã trong `config/companies.txt` |
| P2 | `python -m scripts.p2_company` | Crawl hồ sơ + tin tức + sự kiện, sinh `insights/reasons.jsonl` |
| P3 | `python -m scripts.p3_crawl_all` | Bung crawl **toàn thị trường** (resume + rate-limit) |
| P4 | `python -m scripts.p4_analyze` | Phân tích AI → `analysis/ai_analysis.json` + bảng `ai_analysis` |
| P5 | `python -m scripts.p5_export` | Xuất `web/data/*.json` cho trang so sánh |
| verify | `python -m scripts.verify` | Kiểm tra nhanh dữ liệu |

### P3 — các tùy chọn
```powershell
python -m scripts.p3_crawl_all --limit 50            # 50 mã đầu (thử)
python -m scripts.p3_crawl_all                        # TOÀN BỘ, cả 2 stage
python -m scripts.p3_crawl_all --stage financials     # chỉ tài chính
python -m scripts.p3_crawl_all --delay 4              # giãn nhịp (mặc định 4s)
```
- Chạy lại sẽ **tự bỏ qua mã đã xong** (lưu ở bảng `crawl_state`).
- Bản vnstock community giới hạn **60 request/phút** và **4 kỳ báo cáo**. Full ~1.527 mã mất ~2–3 giờ.

### P4 — chọn backend phân tích

Đặt biến `AI_BACKEND` = `local_api` | `gemini` | `claude`. **Mặc định `local_api`** — mọi
luồng phân tích đi qua server AI local dùng chung (không set gì cũng chạy được, miễn có
`LOCAL_API_KEY`); chỉ tự rơi về `claude` nếu server local chưa cấu hình key nhưng có sẵn
`ANTHROPIC_API_KEY`.

**A. Local API Provider (mặc định — không cần tự lái Chrome/CDP):**
```powershell
$env:LOCAL_API_KEY = "<dán key lấy từ dashboard http://localhost:5000>"
python -m scripts.p4_analyze --all
```
- Key lấy trên Dashboard của server AI local (dự án API share community) — dán trực tiếp
  vào ô cạnh nút "Lưu" trên bảng điều khiển `:5000`, hoặc điền tay vào `.env`.
- Cấu hình khác (ít khi cần đổi, đã có default): `LOCAL_API_URL` (mặc định
  `http://localhost:4000/v1/chat/completions`), `LOCAL_API_MODEL` (mặc định `gemini-cdp`),
  `LOCAL_API_TIMEOUT` (giây, mặc định 300).

**B. Gemini web qua CDP (không cần API key — dùng tài khoản Google, tự lái Chrome):**
```powershell
python -m scripts.launch_chrome     # mở Chrome debug + profile riêng, đăng nhập Gemini 1 lần
python -m scripts.test_gemini       # kiểm tra kết nối (hỏi thử 1 câu)
$env:AI_BACKEND = "gemini"
python -m scripts.p4_analyze        # 5 mã mẫu
```
- Điều khiển Chrome qua Playwright `connect_over_cdp` (cổng 9222), gõ prompt vào ô chat
  Gemini và đọc câu trả lời khi text ngừng stream. Tái dùng 1 phiên cho cả lô.
- Profile riêng: `chrome_cdp_profile/` (tách khỏi Chrome chính). Giữ cửa sổ Chrome mở khi chạy.

**C. Claude API (cần key riêng):**
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:AI_BACKEND = "claude"
python -m scripts.p4_analyze --all
```
Model Claude mặc định: `claude-sonnet-4-6` (sửa trong `src/analyzer.py`).

### P5 — xem web
```powershell
cd web
python -m http.server 8765
# mở http://localhost:8765
```

## Mở rộng dữ liệu toàn thị trường (dùng cho gateway `:9999`)

| Script | Việc |
|---|---|
| `python -m scripts.p5_macro` | Crawl bối cảnh vĩ mô & thị trường dùng chung mọi mã (thêm `--force` để crawl lại ngay dù cache còn mới) |
| `python -m scripts.p6_market_prices` | Đổ OHLCV 1 năm cho **toàn bộ** mã HOSE+HNX (không chỉ ~33 mã VN30) qua VNDirect, phục vụ độ rộng/MA/S-R toàn thị trường |
| `python -m scripts.p7_market_context` | Chỉ số THẬT (VNINDEX/VN30/HNXINDEX) + tin cấp thị trường — thay cho proxy vốn hoá tự chế |
| `python -m scripts.p9_index_ohlc` | Crawl đủ O/H/L/C của các chỉ số (bảng `index_ohlc`) để vẽ nến thật, lịch sử dài hơn bảng `market_index` |

## Cấu trúc dữ liệu
```
companies/<MÃ>/
├── profile.json                  # hồ sơ + tóm tắt
├── financials/*.json             # 4 báo cáo (gồm cash_flow.json)
├── news/news.json                # tin tức
├── disclosures/events.json       # sự kiện/cổ tức
├── insights/reasons.jsonl        # nguyên nhân/lý do (đầu vào AI)
└── analysis/ai_analysis.json     # kết quả phân tích
database/market.db                # SQLite: companies, financials, news, events,
                                  #   ai_analysis, crawl_state, market_index, index_ohlc
web/data/                         # JSON cho trang so sánh
```

## Nguồn & lưu ý
- Dữ liệu qua **vnstock** (nguồn VCI). Tài chính & công bố thông tin là dữ liệu công khai.
- Tin tức có bản quyền nội dung — dùng để phân tích nội bộ.
- Giãn nhịp hợp lý để không bị chặn; tôn trọng rate-limit của nguồn.
