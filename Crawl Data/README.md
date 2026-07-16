# Hệ thống Crawl & Phân tích Doanh nghiệp VN

Crawl dữ liệu từng doanh nghiệp (tài chính, dòng tiền, tin tức, sự kiện) → lưu JSON theo
công ty + SQLite tổng hợp → phân tích bằng Claude API → web so sánh.

## Cài đặt
```powershell
pip install vnstock pandas requests anthropic
$env:PYTHONUTF8 = 1     # cần cho tiếng Việt trên console Windows
```

## ⭐ Cách dễ nhất — Bảng điều khiển web
```powershell
cd "C:\Users\MSI\Desktop\Crawl Data"
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
Đặt biến `AI_BACKEND` = `gemini` | `claude` | `mock` (mặc định: có key Claude → claude, không → mock).

**A. Gemini web qua CDP (không cần API key — dùng tài khoản Google):**
```powershell
python -m scripts.launch_chrome     # mở Chrome debug + profile riêng, đăng nhập Gemini 1 lần
python -m scripts.test_gemini       # kiểm tra kết nối (hỏi thử 1 câu)
$env:AI_BACKEND = "gemini"
python -m scripts.p4_analyze        # 5 mã mẫu
```
- Điều khiển Chrome qua Playwright `connect_over_cdp` (cổng 9222), gõ prompt vào ô chat
  Gemini và đọc câu trả lời khi text ngừng stream. Tái dùng 1 phiên cho cả lô.
- Profile riêng: `chrome_cdp_profile/` (tách khỏi Chrome chính). Giữ cửa sổ Chrome mở khi chạy.

**B. Claude API (cần key):**
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:AI_BACKEND = "claude"
python -m scripts.p4_analyze --all
```
Model Claude mặc định: `claude-sonnet-4-6` (sửa trong `src/analyzer.py`).

**C. Mock** (không cần gì, phân tích theo luật): `$env:AI_BACKEND = "mock"`.

### P5 — xem web
```powershell
cd web
python -m http.server 8765
# mở http://localhost:8765
```

## Cấu trúc dữ liệu
```
companies/<MÃ>/
├── profile.json                  # hồ sơ + tóm tắt
├── financials/*.json             # 4 báo cáo (gồm cash_flow.json)
├── news/news.json                # tin tức
├── disclosures/events.json       # sự kiện/cổ tức
├── insights/reasons.jsonl        # nguyên nhân/lý do (đầu vào AI)
└── analysis/ai_analysis.json     # kết quả phân tích
database/market.db                # SQLite: companies, financials, news,
                                  #   events, ai_analysis, crawl_state
web/data/                         # JSON cho trang so sánh
```

## Nguồn & lưu ý
- Dữ liệu qua **vnstock** (nguồn VCI). Tài chính & công bố thông tin là dữ liệu công khai.
- Tin tức có bản quyền nội dung — dùng để phân tích nội bộ.
- Giãn nhịp hợp lý để không bị chặn; tôn trọng rate-limit của nguồn.
