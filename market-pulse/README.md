# ⚡ Market Pulse — Nền tảng ứng dụng AI phân tích dữ liệu tài chính

Đội **FinTuition** (mã đội AQ2026-131) dự thi **AI-Quantum Challenge 2026** · Nhóm chủ đề:
AI cho Phân tích Kinh tế vĩ mô. Gateway hợp nhất 3 dự án thành phần thành 1 nền tảng, xoay
quanh 4 trụ cột — **One Bar** (thang điểm 0–100) · **Audit Trail** (truy vết nguồn) ·
**Pulse Chat** (trợ lý AI có phản biện) · **Quantum Lab** (tối ưu danh mục mô phỏng lượng tử).

## Chạy nhanh

```powershell
# 1. Sinh dữ liệu phân tích (World Bank + market.db → JSON)
python run_pipeline.py            # thêm --refresh để tải lại dữ liệu vĩ mô mới

# 2. Mở dashboard ALL-IN-ONE
python gateway/app.py             # → http://localhost:9999
```

Yêu cầu: Python 3.12, `pip install -r requirements.txt`.
Gemini API key đọc từ `../econolens-chat/.env` (biến `GEMINI_API_KEY`).

## Tính năng chính

| Tính năng | Mô tả | Backend |
|---|---|---|
| 🌐 **Tổng quan Thị trường** (1 luồng duy nhất) | Bấm 1 nút → 5 bước tự chạy: thu thập (bảng giá price-board + BCTC/tin data-crawler) → kỹ thuật thuần Python (RSI/SMA/MACD/breadth) → AI Task 1 *phân tích thuần* → AI Task 2 *phân tích nguyên nhân + trích bằng chứng [N..][E..]* → AI Task 3 *tổng hợp + kịch bản xác suất*. Kênh AI ưu tiên **Gemini Web qua CDP** (dùng chung `gemini_profile` của price-board, không tốn API key), fallback API. | `modules/market_overview/` |
| 🧭 **Decision Copilot** | Hỏi bằng tiếng Việt → AI trả lời có cấu trúc: luận điểm (trích fact ID) + giả định + rủi ro khiến nhận định sai + 3 kịch bản Base/Bull/Bear kèm xác suất. Audit trail đầy đủ: mọi con số truy ngược được nguồn + thời điểm + độ tin cậy. LLM **không được bịa số** — chỉ dùng facts từ tầng định lượng. | `modules/copilot/` (Gemini + schema validation + fallback offline) |
| 💼 **Phân tích Danh mục** | Nhập mã + khối lượng → tỷ trọng ngành (HHI, cảnh báo tập trung), ma trận tương quan, đóng góp rủi ro biên từng mã, gợi ý tái cân bằng bằng QUBO. | `modules/portfolio/analyzer.py` |
| 📈 **Dự báo Vĩ mô** | GDP/CPI Việt Nam 3 năm tới, khoảng tin cậy 80%, backtest walk-forward công khai. | `modules/macro_forecast/` (SARIMAX, World Bank) |
| 📊 **Thị trường** | Chỉ số vốn hoá 30+ mã lớn (proxy VN-Index) + dự báo 30 phiên (backtest RMSE tốt hơn naive 3,6×). | `modules/macro_forecast/models.py` |
| 🏢 **Sức khỏe DN** | Altman Z''-score + Piotroski F-score cho 1.506 doanh nghiệp niêm yết từ BCTC thật. | `modules/business_health/` |
| ⚛️ **Quantum** | Tối ưu danh mục Markowitz → QUBO → QAOA (PennyLane simulator) + SA, đối chiếu brute-force (optimality gap 3,27%). | `modules/quantum_finance/` |

## Kiến trúc — hợp nhất 3 dự án gốc

```
┌──────────────── Market Pulse — ALL IN ONE (:9999) ───────────┐
│  Decision Copilot · Danh mục · Vĩ mô · Thị trường · DN · Quantum │
└──────┬─────────────┬──────────────┬───────────────┘
       │             │              │
 [data-crawler] [price-board] [econolens-chat]
  market.db      bảng giá      Gemini API key
  1.527 mã       realtime      + persona/schema
  145k BCTC      :5555         (tầng LLM)
  (nguồn số      (dữ liệu
   liệu chính)    sống)
```

- **API:** `POST /api/copilot/ask` `{question, portfolio?}` · `POST /api/portfolio/analyze`
  `{holdings:[{symbol,qty}]}` · `GET /api/data/<name>` · `POST /api/refresh`
- **Nguyên tắc thiết kế:** tầng định lượng (Python, kiểm chứng được) tách khỏi tầng diễn giải
  (LLM, bị ràng buộc JSON schema — sai schema bị từ chối và yêu cầu sinh lại, tối đa 3 lần;
  API lỗi → tự chuyển chế độ offline rule-based có gắn nhãn minh bạch).

## Tài liệu dự thi

- [docs/y-tuong-du-thi.md](docs/y-tuong-du-thi.md) — Bản mô tả ý tưởng theo Điều 5 thể lệ
  (nộp Vòng 1, hạn 30/07/2026), gồm sơ đồ AI working flow và phần trả lời câu hỏi
  "có bị Big Tech thay thế không".
