# ⚡ Market Pulse — AI Đồng Hành Quyết Định Đầu Tư

**Dự án dự thi AI-Quantum Challenge 2026 (Học viện Tài chính) — Nhóm 1: AI cho Phân tích Kinh tế vĩ mô.**

Market Pulse là một nền tảng AI giúp nhà đầu tư cá nhân Việt Nam (đặc biệt là F0 — người mới) hiểu và tự phân tích thị trường chứng khoán, thay vì chạy theo "phím hàng" thiếu căn cứ. Toàn bộ hệ thống được xây dựng quanh **4 trụ cột**: Minh bạch nguồn dữ liệu · Phản biện & cảnh báo rủi ro bắt buộc · Kịch bản xác suất (không dự đoán tuyệt đối) · Phân tích danh mục định lượng.

> ⚠️ **Nguyên tắc bất biến:** sản phẩm chỉ mang tính **giáo dục & thông tin**, không đưa ra khuyến nghị mua/bán hay giá mục tiêu cho bất kỳ mã cổ phiếu cụ thể nào, nhằm không bị xem là "tư vấn đầu tư" theo quy định của UBCKNN. Mọi phản hồi AI đều đi kèm tuyên bố miễn trừ trách nhiệm.

---

## Mục lục

- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [4 dự án thành phần](#4-dự-án-thành-phần)
- [Chạy nhanh toàn bộ hệ thống](#chạy-nhanh-toàn-bộ-hệ-thống)
- [Công nghệ sử dụng](#công-nghệ-sử-dụng)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Tài liệu dự thi](#tài-liệu-dự-thi)
- [Giấy phép](#giấy-phép)

---

## Kiến trúc hệ thống

Gateway **EconoPulse-VN** (cổng `:9999`) là điểm vào duy nhất, hợp nhất 3 dự án còn lại thành một trải nghiệm liền mạch — tự động khởi động và theo dõi (health-check + auto-restart) từng service con:

```
┌──────────────────── Market Pulse — ALL-IN-ONE (:9999) ─────────────────────┐
│  Tổng quan thị trường · Decision Copilot · Phân tích danh mục · Dự báo Vĩ mô │
│  Thị trường · Sức khỏe DN · Quantum Lab                                     │
└──────┬────────────────┬─────────────────────┬───────────────────┬──────────┘
       │                │                     │                   │
 [Crawl Data]     [Test tool dự án]    [AI Analyze Economic] [FinPulse-AI]
  :5000                :5555               :3333 (EconoLens)   Electron/PyQt
  Thu thập + phân       Bảng giá realtime    Chatbox AI 4         desktop app
  tích BCTC/tin tức     (vnstock) + phiên    persona, JSON-       RSS quốc tế
  → market.db (SQLite,  Gemini Web dùng      schema block,        + cây phân
  1.527 mã, ~145k       chung (CDP)          JWT auth             tích chủ đề
  dòng BCTC)
```

Nguyên tắc thiết kế xuyên suốt: **tầng định lượng** (Python, tính toán từ dữ liệu thật, kiểm chứng được) luôn tách khỏi **tầng diễn giải** (LLM, bị ràng buộc JSON schema chặt chẽ — sai schema bị từ chối và bắt sinh lại; API lỗi thì tự chuyển sang chế độ rule-based offline có gắn nhãn minh bạch, không bao giờ im lặng trả dữ liệu giả).

## 4 dự án thành phần

| Dự án | Vai trò | Stack chính | Port |
|---|---|---|---|
| [`EconoPulse-VN`](EconoPulse-VN) | **Gateway chính** — hợp nhất toàn bộ hệ thống: Tổng quan thị trường, Decision Copilot, Phân tích danh mục (HHI, ma trận tương quan, QUBO rebalancing), Dự báo vĩ mô (SARIMAX), Sức khỏe DN (Altman Z''/Piotroski F), Quantum Lab (QAOA qua PennyLane) | Python, Flask, pandas, numpy, statsmodels, scikit-learn, pennylane | `9999` |
| [`Crawl Data`](Crawl%20Data) | Tầng dữ liệu nền tảng: crawl BCTC/tin tức/sự kiện công bố thông tin cho các mã CK Việt Nam, phân tích AI (health score, risk level), lưu SQLite (`market.db`) | Python, Flask, vnstock, pandas, Playwright (CDP), Anthropic SDK | `5000` |
| [`Test tool dự án`](Test%20tool%20dự%20án) | Bảng giá realtime (vnstock price board) + hạ tầng phiên Gemini Web dùng chung qua Chrome CDP cho các module AI khác | Python, Flask, vnstock | `5555` |
| [`AI Analyze Economic`](AI%20Analyze%20Economic) (EconoLens) | Chatbox học kinh tế vĩ mô với 4 persona (Học sinh/Sinh viên, Nhà phân tích, Nhà đầu tư, Nhà hoạch định chính sách), phản hồi dạng block JSON động (chart/table/quiz/timeline...), hỗ trợ 4 AI backend (Claude, Gemini API, Grok, Gemini Web/CDP) | Node.js, Express, JWT, bcryptjs | `3333` |
| [`FinPulse-AI`](FinPulse-AI) | Ứng dụng desktop đọc tin tài chính quốc tế (RSS đa nguồn) + "cây phân tích" đào sâu chủ đề bằng AI, có 2 bản triển khai song song (Electron và PyQt6+CDP) | Electron, PyQt6, rss-parser | — (desktop) |

Mỗi dự án có README riêng với hướng dẫn cài đặt/chạy chi tiết — xem link ở bảng trên.

## Chạy nhanh toàn bộ hệ thống

Cách đơn giản nhất — chỉ cần chạy gateway, các service còn lại sẽ **tự động được khởi động**:

```bash
START_ALL.bat
```

Script tự dò interpreter Python có sẵn Flask (`py -3.12` → `python` → `py`), khởi động `EconoPulse-VN/gateway/app.py`; `launcher.py` bên trong gateway sẽ tự spawn `Crawl Data`, `Test tool dự án` và `AI Analyze Economic` nếu chưa chạy (health-check trước, không giết process đã chạy sẵn), kèm watchdog tự khởi động lại nếu có service bị crash.

Mở từng service trong cửa sổ terminal riêng (hữu ích khi debug):

```bash
START_4_TERMINAL.bat
```

Dừng toàn bộ hệ thống:

```bash
STOP_ALL.bat
```

> `FinPulse-AI` là ứng dụng desktop độc lập, không được các script trên tự khởi động — chạy thủ công bằng `npm start` (Electron) hoặc `python app_pyqt.py` (PyQt6) trong thư mục dự án.

## Công nghệ sử dụng

- **Backend:** Python (Flask), Node.js (Express)
- **Dữ liệu thị trường:** `vnstock` (VCI source), SQLite
- **AI:** Anthropic Claude, Google Gemini (API + phiên Web qua Chrome CDP cho các tác vụ không cần API key), xAI Grok
- **Phân tích định lượng:** pandas, numpy, statsmodels (SARIMAX), scikit-learn
- **Quantum computing:** PennyLane (QAOA mô phỏng, đối chiếu brute-force)
- **Desktop:** Electron, PyQt6
- **Frontend:** HTML/CSS/JS thuần (Chart.js cho biểu đồ), không dùng framework nặng — tối ưu tốc độ tải

## Cấu trúc thư mục

```
Final Market Pulse/
├── EconoPulse-VN/          # Gateway chính (:9999)
├── Crawl Data/             # Thu thập + phân tích dữ liệu DN (:5000)
├── Test tool dự án/        # Bảng giá realtime + hạ tầng Gemini CDP (:5555)
├── AI Analyze Economic/    # EconoLens — chatbox học kinh tế (:3333)
├── FinPulse-AI/            # Desktop app tin tức tài chính quốc tế
├── MarketPulse-PLAN.md     # Roadmap & định vị sản phẩm gốc
├── START_ALL.bat           # Khởi động toàn hệ thống (khuyến nghị)
├── START_4_TERMINAL.bat    # Khởi động từng service ở terminal riêng
└── STOP_ALL.bat            # Dừng toàn bộ service
```

## Tài liệu dự thi

- [`EconoPulse-VN/docs/y-tuong-du-thi.md`](EconoPulse-VN/docs/y-tuong-du-thi.md) — Bản mô tả ý tưởng dự thi theo thể lệ cuộc thi, gồm sơ đồ AI working flow.
- [`MarketPulse-PLAN.md`](MarketPulse-PLAN.md) — Định vị sản phẩm, ranh giới pháp lý, roadmap MVP theo từng phase.

## Giấy phép

Phát hành theo giấy phép [MIT](LICENSE).
