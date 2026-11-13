# Original User Request

## 2026-09-06T12:52:32Z

Khắc phục toàn diện các điểm nghẽn hiệu năng (bottlenecks: SQLite full scans, N+1 query loops, CPU throttling trong realtime price loop, blocking sync proxy) đã được ghi nhận tại `BOTTLENECKS.md`, tối ưu hóa tốc độ phản hồi hệ thống và đảm bảo độ ổn định đa dịch vụ cho nền tảng Market Pulse.

Working directory: c:/Users/MSI/Desktop/Final Market Pulse
Integrity mode: development

Tài liệu tham chiếu điểm nghẽn & phân tích chi tiết:
`c:/Users/MSI/Desktop/Final Market Pulse/BOTTLENECKS.md`

## Requirements

### R1. Khắc phục các nút thắt cổ chai P0 (Hotfixes)
- Tối ưu hóa vòng lặp realtime trong `price-board/board_vnstock.py`: loại bỏ hoàn toàn việc gọi `list(F[k])[i]` lặp lại 18.000 lần/giây, chuyển sang xử lý cấu trúc dữ liệu phẳng hoặc giải nén mảng trước khi lặp qua các mã cổ phiếu.
- Tối ưu hóa tính toán chỉ số kỹ thuật 1 mã trong `market-pulse/modules/market_overview/tech_full.py:one()`: bổ sung hàm truy vấn chỉ báo riêng cho 1 symbol với giới hạn 260 phiên nến gần nhất, chấm dứt việc nạp 752k dòng của toàn bộ 1.541 mã cổ phiếu khi người dùng chỉ xem 1 mã.
- Tối ưu hóa endpoint `/health` & `/stats` của `data-crawler/app.py`: bổ sung index trên `price(time)`, thiết lập bộ đệm in-memory (TTL 30s) cho số liệu thống kê polling định kỳ và tăng timeout kết nối SQLite để triệt tiêu lỗi `database is locked`.

### R2. Tối ưu hóa Database SQLite & Triệt tiêu N+1 Query (P1)
- Bổ sung composite index trên bảng `financials` (`statement, item_id, period, value`) trong `data-crawler/src/storage.py` để tăng tốc toàn bộ các truy vấn tìm kiếm và lọc chỉ số BCTC.
- Tái cấu trúc `market-pulse/modules/business_health/scoring.py:score_all()`: thay thế 3.000 truy vấn `pd.read_sql` đơn lẻ bằng một batch query nạp dữ liệu BCTC 3 năm vào bộ nhớ, tính điểm toàn bộ doanh nghiệp dạng vector hóa.
- Tối ưu hóa tính toán so sánh ngành `data-crawler/src/peers.py:compute()`: áp dụng cơ chế cache in-memory theo ngành (`sector_cache`, TTL 300s) và batch query, xóa bỏ 400-600 truy vấn SQLite lặp khi người dùng xem trang chi tiết cổ phiếu.
- Tối ưu hóa `market_technical.py:liquidity_concentration()` bằng SQL Window Function (`ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC)`) khi bảng giá trực tiếp vắng mặt, tránh nạp 752k dòng vào pandas.

### R3. Ổn định Concurrency & Bất đồng bộ hóa (P2 & P3)
- Chuẩn hóa các kết nối reader trên toàn bộ các module sang dùng `connect_readonly` (URI mode=ro) để tránh xung đột lock với tiến trình crawl đang ghi.
- Khắc phục race condition trong cache bảng giá của gateway (`market-pulse/modules/market_overview/technical.py`), đảm bảo không sửa đổi (mutate) dữ liệu dùng chung giữa các luồng xử lý của Flask.
- Chuyển đổi các thao tác ghi file đồng bộ trong `econolens-chat/lib/db.js` sang bất đồng bộ (`fs.promises`).
- Bổ sung cơ chế dọn dẹp job cũ (LRU / TTL eviction) trong `quantum_lab/api.py`.

## Verification Resources

- Test suite tự động có sẵn của hệ thống:
  - `pytest market-pulse/tests` (16 test suites)
  - `pytest data-crawler/tests` (12 test suites)
- Profiling / Benchmark scripts:
  - `python test_opt.py`
  - `python test_symbol_stats.py`
  - `python market-pulse/profile_anomaly.py`

## Acceptance Criteria

### Performance & Latency Guardrails
- [ ] Vòng lặp `price-board/board_vnstock.py` tiêu thụ < 5% CPU trên mỗi chu kỳ làm mới 1s (giảm từ mức 80-90%).
- [ ] Thời gian phản hồi của endpoint `/api/stock/<sym>` và `/api/stock/<sym>/chart_ai` đạt < 50ms cho truy vấn đơn lẻ (giảm từ 13 giây).
- [ ] Thời gian thực thi `score_all` của `scoring.py` giảm từ 60s xuống dưới 2s.
- [ ] Thời gian tải trang cổ phiếu và tính toán trung vị ngành (`peers.compute`) giảm từ 3-5s xuống < 100ms.
- [ ] Không còn lỗi `database is locked` hoặc `timeout` khi giao diện frontend poll `/stats` và `/health`.
- [ ] Toàn bộ test suite hiện có của dự án (`pytest`) chạy pass 100%, không phát sinh lỗi hồi quy (regression) hay làm thay đổi định dạng schema dữ liệu trả về cho frontend.

## 2026-09-09T08:34:13Z

Comprehensive Business Communication Group Assignment Report, Global Expansion Strategy (Singapore, US, Japan), and A0 Watercolor Poster Blueprint for "FinTuition - Market Pulse", delivered in full bilingual format (English and Vietnamese).

Working directory: c:\Users\MSI\Desktop\Final Market Pulse\docs\assignment
Integrity mode: development

## Requirements

### R1. Complete 5W1H Business & Architectural Analysis for Market Pulse
Produce an exhaustive answer to all prompt questions from the assignment slide using the 5W1H framework, grounded in the real Market Pulse system:
- **What (Object & Value)**: Core SaaS FinTech product, anti-hallucination philosophy, modular components (crawler, price-board, gateway, quantum lab, econolens-chat, scoring engine), potential product extensions, and product roadmap choices.
- **Where (Location & Cloud)**: Production deployment (cloud VPS/serverless, edge computing, SQLite WAL mode), rationale for jurisdiction choice, data residency laws, and criteria for physical/digital workplaces.
- **When (Timing & Process Pipelines)**: Realtime vs. batch processing timelines, daily market closing ETL, caching lifecycles (stale-while-revalidate), historical data processing, and process reordering (e.g. pre-computing sector percentiles before query time).
- **Who (Organizational Structure & Human Capital)**: 6-member C-Suite startup structure (CEO, CTO, Head of AI/Quant, Head of Data Engineering, CFO/Legal Compliance, CMO/Global PR) with clearly assigned responsibilities. Concrete management strategy to handle an irresponsible or temperamental team member (objective KPIs, peer reviews, blameless retro, role re-allocation or phased separation).
- **Why (Rationale & Technical Parameters)**: Scientific and engineering justification for key technical parameters (Altman Z-score thresholds, Piotroski F-Score 9 criteria, PennyLane QAOA for QUBO portfolio optimization, 2-tier decoupled architecture, red-flag triggers, audit trail citations, and human vs. machine trade-offs).
- **How (Operational Methodology & Execution)**: End-to-end operational execution, RAG pipeline with grounded citations, API-first orchestration, error fallbacks, and verification loops.

### R2. Global Expansion Strategy & Deep Country Breakdown
Develop a realistic, high-impact global expansion plan for Market Pulse entering 3 target international markets:
1. **Singapore**: Regional headquarters, MAS FinTech Regulatory Sandbox, Southeast Asian financial gateway, institutional & retail wealth management adoption.
2. **United States**: Deep capital and retail trading market, SEC & FINRA compliance, AI/cloud compute scaling, integration with US brokerages and data feeds (SEC EDGAR, Polygon.io, Alpaca).
3. **Japan**: High-regulation East Asian market, FSA compliance, consumer financial education for retail investors, data localization, and Keiretsu market characteristics.
For each country, detail: Market opportunity & user persona, regulatory framework, financial data integration, competitive differentiation, and go-to-market execution.

### R3. A0 Watercolor Poster Visual Blueprint & Layout Architecture
Design an actionable blueprint for an A0 poster (841 x 1189 mm) to be hand-drawn with watercolor pens:
- **Layout Style**: Hub-and-Spoke Canvas with central branding and 6 surrounding thematic zones.
- **Spatial Grid**: Exact dimensional partition (percentages and cm measurements) across the A0 sheet.
- **Color Palette Guide**: Watercolor pen color codes (Deep Blue for AI/Tech, Emerald Green for Finance, Coral Red for Risk Radar, Purple for Quantum, Amber for Strategy, Charcoal for Typography).
- **Visual Assets**: Exact diagrams, flowchart layouts, iconography, and mind-map connectors ready for manual drawing.

### R4. Presentation Role Assignment & Flexible Script
Provide a 6-speaker division of labor with speech bullet points, transition cues, and key talking points that can flex according to the presentation time allotted by the instructor.

### R5. Complete Bilingual Deliverables (English & Vietnamese)
Deliver the comprehensive report, A0 poster guide, and presentation notes in two distinct, professionally written versions:
1. `MARKET_PULSE_GLOBAL_REPORT_VI.md` (Vietnamese)
2. `MARKET_PULSE_GLOBAL_REPORT_EN.md` (English)
3. `A0_POSTER_SKETCH_GUIDE.md` (Bilingual visual blueprint & layout guide)

## Acceptance Criteria

### Content Completeness & Rigor
- [ ] Every individual sub-question from Slide 51 and Slide 52 is answered with high technical and business depth.
- [ ] The 6-member team roles and the specific conflict/temperament resolution protocol are fully elaborated.
- [ ] All 3 target markets (Singapore, US, Japan) include specific regulatory bodies, data providers, and localized GTM plans.
- [ ] The A0 poster guide contains precise measurements, color-pen recommendations, and sketchable ASCII/diagram wireframes.
- [ ] Presentation scripts provide distinct speaking parts for all 6 members.
- [ ] Full bilingual delivery with complete parity between Vietnamese and English versions.

## 2026-09-09T13:57:36Z

Bộ kịch bản thuyết trình toàn diện (12 phút — 2 phút/thành viên) giới thiệu tổng quan về doanh nghiệp và dịch vụ tài chính cá nhân FinTuition - Market Pulse, áp dụng chuẩn mực 5W1H mô hình dịch vụ (Service Template), phân vai cho 6 thành viên đại diện các phòng ban ra mắt công chúng với phong cách giao tiếp kinh doanh lịch thiệp, dễ hiểu, tuyệt đối không dùng thuật ngữ kỹ thuật phức tạp.

Working directory: c:\Users\MSI\Desktop\Final Market Pulse\docs\assignment
Integrity mode: demo

## Requirements

### R1. Cấu trúc 5W1H chuẩn dịch vụ phân vai cho 6 thành viên
Xây dựng kịch bản chia đều cho 6 vai đại diện bộ mặt doanh nghiệp, mỗi bạn nói đúng ~2 phút (~240–280 từ ngữ điệu chuẩn):
- **Thành viên 1 — CEO (Khởi xướng & Sứ mệnh - WHO & Bối cảnh doanh nghiệp)**: Câu chuyện thành lập FinTuition, tầm nhìn vì cộng đồng nhà đầu tư trẻ, định vị là "Thông dịch viên dữ liệu trung thực", giải quyết nỗi đau lệch pha thông tin và tin đồn thất thiệt.
- **Thành viên 2 — Product Lead (Dịch vụ cốt lõi - WHAT)**: Giới thiệu dịch vụ số Market Pulse và 4 giá trị tiện ích cho khách hàng (Điểm sức khỏe tài chính 0–100, Radar cảnh báo rủi ro Đèn Giao Thông, Trợ lý hỏi đáp có trích dẫn nguồn số liệu, Bảng so sánh vị thế cùng ngành).
- **Thành viên 3 — Marketing Lead (Thời điểm & Kênh tiếp cận - WHEN & WHERE)**: Thời điểm khách hàng cần dịch vụ (trước khi ra quyết định đầu tư, theo dõi biến động định kỳ), kênh trải nghiệm đa nền tảng số (App di động, Web portal, kênh cộng đồng).
- **Thành viên 4 — Customer Experience (CX) Lead (Hành trình phục vụ - HOW)**: Quy trình phục vụ 3 bước tinh giản cho khách hàng (Đăng ký nhanh -> Nhận báo cáo trực quan tức thì -> Hỗ trợ tư vấn thông tin minh bạch 24/7), chăm sóc khách hàng tận tâm.
- **Thành viên 5 — Quality & Risk Lead (Lý do tin cậy - WHY)**: Tại sao khách hàng an tâm lựa chọn (Tính khách quan độc lập, tuyệt đối không "phím hàng" vụ lợi, tôn trọng bảo mật dữ liệu, cảnh báo rủi ro minh bạch).
- **Thành viên 6 — PR & Đối ngoại Lead (Tầm nhìn, Ưu đãi & Chốt bài)**: Gói trải nghiệm miễn phí cho sinh viên và người mới, định hướng lan tỏa giá trị văn minh tài chính, lời cảm ơn và chuyển tiếp sang phần hỏi đáp (Q&A).

### R2. Thiết kế định dạng tối ưu thực chiến cho buổi thuyết trình
- **Lời thoại chi tiết (Full Verbatim Script)**: Từng câu chữ viết hoa ngắt nghỉ, ngôn phong lịch sự, truyền cảm hứng, chuẩn mực giao tiếp kinh doanh.
- **Thẻ ghi nhớ (Flashcard / Cue Card)**: Tóm tắt 3–4 bullet points ngắn gọn cho từng thành viên cầm trên tay khi lên bục nói.
- **Khẩu lệnh chuyển tiếp (Transition Cue) & Hướng dẫn cử chỉ (Body Language)**: Ghi chú vị trí đứng, ánh mắt, nụ cười và hành động tương tác với người nghe hoặc slide/poster.

### R3. Xuất bản tài liệu kịch bản
- Tạo file kịch bản tiếng Việt chuyên nghiệp: `PRESENTATION_SCRIPT_5W1H_SERVICE.md` tại thư mục làm việc `docs/assignment/`.

## Acceptance Criteria

### Tính Chuẩn Mực & Giao Tiếp Kinh Doanh
- [ ] Tổng thời lượng kịch bản đạt đúng chuẩn 12 phút (mỗi thành viên từ 240 đến 280 từ, thời gian đọc trung bình 110–130 giây).
- [ ] Bao phủ đầy đủ và tự nhiên 6 yếu tố 5W1H loại hình dịch vụ (What, Where, When, Who, Why, How).
- [ ] Ngôn ngữ hoàn toàn là bề nổi đại chúng của doanh nghiệp dịch vụ, không chứa các thuật ngữ lập trình hay thuật toán backend.
- [ ] Có đầy đủ câu mở màn ấn tượng, 5 nhịp chuyển tiếp mượt mà giữa các thành viên, và phần kết thúc kêu gọi hành động (Call to Action) trang trọng.
