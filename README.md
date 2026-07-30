#  Market Pulse — Nền tảng ứng dụng AI phân tích dữ liệu tài chính

**Đội thi AQ2026-131-FinTuition** - Dự thi **AI-Quantum Challenge 2026** - Cuộc thi Trí tuệ nhân tạo và Lượng tử trong Kinh tế - Tài chính - Kế toán lần thứ I · Nhóm chủ đề: *AI cho Phân tích Kinh tế vĩ mô*.

Market Pulse là nền tảng công nghệ tài chính ra đời nhằm giải quyết tình trạng quá tải thông tin ở lực lượng nhà đầu tư mới (F0). Không đi theo lối mòn “phím hàng” hay đưa ra khuyến nghị mua bán từ các thuật toán mù mờ, dự án đóng vai trò là một hệ thống thông dịch dữ liệu, giúp người dùng dễ dàng nắm bắt các báo cáo phức tạp để tự chủ ra quyết định đầu tư mà không bị chi phối bởi tâm lý đám đông hay cảm xúc nhất thời.

> Sản phẩm chỉ mang *tinh thần giáo dục* và là *công cụ trực quan hóa thông tin* chứ *không đưa ra khuyến nghị mua/bán, giá mục tiêu hay cam kết lợi nhuận*. Hệ thống tự động quét và chặn các cụm từ mang tính khuyến nghị đầu tư trực tiếp trước khi trả kết quả cho người dùng.

---

## Mục lục

- [Các trụ cột công nghệ](#4-trụ-cột-công-nghệ)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Dự án thành phần](#5-dự-án-thành-phần)
- [Quy mô dữ liệu](#quy-mô-dữ-liệu)
- [Khởi chạy hệ thống](#chạy-nhanh-toàn-bộ-hệ-thống)
- [Công nghệ sử dụng](#công-nghệ-sử-dụng)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Tài liệu dự thi](#tài-liệu-dự-thi)
- [Giấy phép](#giấy-phép)

---

## 4 trụ cột công nghệ

| Trụ cột | Mô tả |
|---|---|
| **Hệ thống theo dõi sức khỏe doanh nghiệp** | Chuẩn hóa toàn bộ chỉ số tài chính đa chiều (P/E, P/B, ROE, Altman Z-Score, Piotroski F-Score…) về **một thang điểm duy nhất** dựa trên bách phân vị ngành, giúp người dùng nắm bắt sức khỏe doanh nghiệp chỉ trong vài giây — dữ liệu khuyết thiếu hiển thị màu xám minh bạch thay vì gán giá trị 0. |
| **Audit Trail** | Mọi nhận định do AI sinh ra đều **bắt buộc** đính kèm mã bằng chứng có thể nhấp vào để truy xuất ngược về đúng báo cáo/tin tức gốc ([N..] công bố thông tin, [E..] sự kiện, [M..] vĩ mô) — chống ảo giác số liệu. |
| **Pulse Chat** | Trợ lý AI hội thoại (kiến trúc RAG) — mọi câu trả lời phải neo vào dữ liệu thực tế, cấu trúc bắt buộc 3 phần: Luận điểm chính · Giả định sử dụng · Yếu tố rủi ro có thể khiến nhận định sai. |
| **Quantum Lab** | Mô phỏng tối ưu hóa danh mục Markowitz → QUBO → thuật toán QAOA trên PennyLane Simulator, đối chiếu Simulated Annealing/brute-force qua chỉ số **Optimality Gap** công khai. |

## Kiến trúc hệ thống

Gateway **market-pulse** (cổng `:9999`) là điểm vào duy nhất, hợp nhất 3 dự án còn lại thành một trải nghiệm liền mạch — tự động khởi động và theo dõi (health-check + auto-restart) từng service con:

```
┌──────────────────────────────── Market Pulse — ALL-IN-ONE (:9999) ────────────────────────────────┐
│  Hệ thống theo dõi sức khỏe doanh nghiệp · Pulse Chat (Audit Trail) · Radar rủi ro · Dự báo Vĩ mô │
│  Quantum Lab · So sánh doanh nghiệp                                                               │
└─────────┬───────────────────────┬─────────────────────────┬───────────────────────┬───────────────┘
          │                       │                         │                       │
   [data-crawler]          [price-board]            [econolens-chat]         [FinPulse-AI]
        :5000                   :5555                :3333 (EconoLens)       Electron/PyQt
   Thu thập + phân         Bảng giá realtime        Chatbox học kinh         desktop app
   tích BCTC/tin tức       (vnstock) + phiên        tế vĩ mô, 4 persona      RSS tài chính
   → market.db (SQLite,    Gemini Web dùng          + JWT auth               quốc tế + cây
   1.527 hồ sơ DN)         chung (CDP)                                       phân tích
```

Kiến trúc vận hành theo **đường ống 2 tầng khép kín**: tầng định lượng (Python/pandas/statsmodels, tính toán từ dữ liệu thật, kiểm chứng được) tách biệt hoàn toàn khỏi tầng diễn giải (LLM, bị ràng buộc JSON schema chặt chẽ — sai schema bị từ chối và bắt sinh lại; API lỗi thì tự chuyển sang chế độ rule-based offline có gắn nhãn minh bạch, không bao giờ im lặng trả dữ liệu giả).

## 5 dự án thành phần

| Dự án | Vai trò | Stack chính | Port |
|---|---|---|---|
| [`market-pulse`](market-pulse) | **Gateway chính** — hợp nhất toàn bộ hệ thống: One Bar (sức khỏe DN), Pulse Chat, Radar cảnh báo rủi ro kỹ thuật, Dự báo vĩ mô (SARIMAX), Quantum Lab (QAOA qua PennyLane), so sánh doanh nghiệp cùng ngành | Python, Flask, pandas, numpy, statsmodels, scikit-learn, pennylane | `9999` |
| [`data-crawler`](data-crawler) | Tầng dữ liệu nền tảng: crawl BCTC/tin tức/sự kiện công bố thông tin cho các mã CK Việt Nam, phân tích AI, lưu SQLite (`market.db`) | Python, Flask, vnstock, pandas, Playwright (CDP), Anthropic SDK | `5000` |
| [`price-board`](price-board) | Bảng giá realtime (vnstock price board) + hạ tầng phiên Gemini Web dùng chung qua Chrome CDP cho các module AI khác | Python, Flask, vnstock | `5555` |
| [`econolens-chat`](econolens-chat) (EconoLens) | Chatbox học kinh tế vĩ mô với 4 persona (Học sinh/Sinh viên, Nhà phân tích, Nhà đầu tư, Nhà hoạch định chính sách), phản hồi dạng block JSON động (chart/table/quiz/timeline...) | Node.js, Express, JWT, bcryptjs | `3333` |
| [`FinPulse-AI`](FinPulse-AI) | Ứng dụng desktop đọc tin tài chính quốc tế (RSS đa nguồn) + "cây phân tích" đào sâu chủ đề bằng AI, có 2 bản triển khai song song (Electron và PyQt6+CDP) | Electron, PyQt6, rss-parser | — (desktop) |

Mỗi dự án có README riêng với hướng dẫn cài đặt/chạy chi tiết — xem link ở bảng trên.

## Quy mô dữ liệu

Số liệu trích xuất thực tế từ `market.db`, không qua nội suy hay ước lượng:

| Nội dung | Số liệu |
|---|---|
| Hồ sơ doanh nghiệp | 1.527 doanh nghiệp niêm yết |
| Báo cáo tài chính | 2.543.606 bản ghi (2012 → hiện tại) |
| Biến động giá (OHLCV) | 752.923 bản ghi |
| Công bố thông tin (CBTT) | 75.623 bản tin |
| Sự kiện thị trường | 41.462 sự kiện |
| **Tổng bản ghi** | **3.423.040** |
| Doanh nghiệp chấm điểm One Bar | 1.506 DN (Altman Z-Score + Piotroski F-Score) |
| Mã cổ phiếu quét kỹ thuật (Radar) | 1.541 mã trên HOSE/HNX |
| Nguồn dữ liệu | vnstock (VCI/KBS), VNDirect REST, World Bank Open Data, Vietcombank/GSO/SBV, Google News RSS — 100% nguồn công khai |

## Chạy nhanh toàn bộ hệ thống

Cách đơn giản nhất — chỉ cần chạy gateway, các service còn lại sẽ **tự động được khởi động**:

```bash
START_ALL.bat
```

Script tự dò interpreter Python có sẵn Flask (`py -3.12` → `python` → `py`), khởi động `market-pulse/gateway/app.py`; `launcher.py` bên trong gateway sẽ tự spawn `data-crawler`, `price-board` và `econolens-chat` nếu chưa chạy (health-check trước, không giết process đã chạy sẵn), kèm watchdog tự khởi động lại nếu có service bị crash.

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
- **Dữ liệu:** SQLite + JSON pipeline, `vnstock` (VCI/KBS source)
- **AI:** RAG, NLP, LLM (Anthropic Claude, Google Gemini — API + phiên Web qua Chrome CDP cho các tác vụ không cần API key, xAI Grok)
- **Phân tích định lượng:** pandas, numpy, statsmodels (SARIMAX), scikit-learn
- **Quantum computing (mô phỏng):** PennyLane (QAOA) + Simulated Annealing
- **Desktop:** Electron, PyQt6
- **Frontend:** HTML/CSS/JS thuần (Chart.js cho biểu đồ), không dùng framework nặng — tối ưu tốc độ tải
- **Kiểm thử:** ~190 unit/integration test tự động (pytest), chạy offline

## Cấu trúc thư mục

```
Final Market Pulse/
├── market-pulse/           # Gateway chính (:9999)
├── data-crawler/           # Thu thập + phân tích dữ liệu DN (:5000)
├── price-board/            # Bảng giá realtime + hạ tầng Gemini CDP (:5555)
├── econolens-chat/         # EconoLens — chatbox học kinh tế (:3333)
├── FinPulse-AI/            # Desktop app tin tức tài chính quốc tế
├── docs/                   # Hồ sơ đề xuất & báo cáo dự án chính thức
├── MarketPulse-PLAN.md     # Roadmap & định vị sản phẩm gốc
├── START_ALL.bat           # Khởi động toàn hệ thống (khuyến nghị)
├── START_4_TERMINAL.bat    # Khởi động từng service ở terminal riêng
└── STOP_ALL.bat            # Dừng toàn bộ service
```

## Tài liệu dự thi

- [`docs/FinTuition_Ho-so-de-xuat-y-tuong_AI-Quantum-Challenge-2026.docx`](docs/FinTuition_Ho-so-de-xuat-y-tuong_AI-Quantum-Challenge-2026.docx) — Hồ sơ đề xuất ý tưởng và bài toán (Vòng 1). *Bảng thông tin thành viên (họ tên, CCCD, email, số điện thoại) đã được lược bỏ khỏi bản công khai vì lý do riêng tư — bản đầy đủ đã nộp cho ban tổ chức.*
- [`docs/FinTuition_Bao-cao-du-an-Market-Pulse.docx`](docs/FinTuition_Bao-cao-du-an-Market-Pulse.docx) — Báo cáo dự án đầy đủ: phân tích thị trường (PESTEL, Five Forces), định vị sản phẩm, quản trị rủi ro (WBS/RBS/FMEA).
- [`market-pulse/docs/y-tuong-du-thi.md`](market-pulse/docs/y-tuong-du-thi.md) — Bản tóm tắt ý tưởng dự thi, gồm sơ đồ AI working flow.
- [`MarketPulse-PLAN.md`](MarketPulse-PLAN.md) — Định vị sản phẩm, ranh giới pháp lý, roadmap MVP theo từng phase.

## Giấy phép

Phát hành theo giấy phép [MIT](LICENSE).
