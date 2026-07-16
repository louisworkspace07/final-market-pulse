# BẢN MÔ TẢ Ý TƯỞNG DỰ THI

**Cuộc thi AI-Quantum Challenge 2026 — Học viện Tài chính**
*(Hồ sơ Vòng 1 — Sơ loại, soạn theo Điều 5 Thể lệ ban hành kèm Công văn số 683/HVTC-VP ngày 08/5/2026)*

---

## 1. Tên dự án và nhóm chủ đề

**Tên dự án:** **EconoPulse VN — AI Đồng hành Quyết định Đầu tư (Investment Decision Copilot)**

**Nhóm chủ đề chính:** Nhóm 1 — *AI cho Phân tích Kinh tế vĩ mô* (dự báo GDP, lạm phát, thị trường chứng khoán, phân tích sức khỏe doanh nghiệp từ dữ liệu BCTC).

**Giao thoa có chủ đích với:** Nhóm 2 (*AI cho Dịch vụ Tài chính thông minh* — robo-advisor, quản lý tài chính cá nhân) và Nhóm 4 (*Quantum Computing cho Tài chính* — tối ưu danh mục bằng thuật toán lượng tử). Thể lệ cuộc thi (Điều 7) cho phép đội thi tự đề xuất bài toán trong hoặc ngoài các nhóm chủ đề; chúng em chọn cách tiếp cận **liên ngành** vì nỗi đau thực tế của người dùng không nằm gọn trong một nhóm: nhà đầu tư cá nhân cần *đồng thời* bức tranh vĩ mô, sức khỏe doanh nghiệp, và công cụ ra quyết định trên danh mục của chính mình.

---

## 2. Vấn đề cần giải quyết

### 2.1. Nỗi đau: nhà đầu tư cá nhân thiếu khả năng TỔNG HỢP thông tin và RA QUYẾT ĐỊNH

Thị trường chứng khoán Việt Nam có quy mô thông tin vượt xa khả năng xử lý của một cá nhân. Số liệu minh họa **từ chính hệ thống dữ liệu chúng em đã thu thập và chuẩn hóa** (không phải ước tính):

| Khối lượng thông tin | Con số thực đo được |
|---|---|
| Số doanh nghiệp niêm yết/đăng ký giao dịch (HOSE + HNX + UPCOM) | **1.527 mã** |
| Số dòng chỉ tiêu báo cáo tài chính đã chuẩn hóa (CĐKT, KQKD, LCTT, chỉ số) | **145.276 dòng** |
| Tin công bố thông tin (CBTT) đã thu thập | **1.963 tin** |
| Sự kiện doanh nghiệp (cổ tức, ĐHĐCĐ, giao dịch nội bộ...) | **1.147 sự kiện** |
| Dữ liệu giá giao dịch (2024 – 06/2026) | **16.317 quan sát** |

Một nhà đầu tư cá nhân đọc trung bình 2 phút/tin thì riêng lượng tin CBTT trên đã cần **~65 giờ đọc liên tục** — chưa tính phân tích BCTC. Kết quả thực tế: đa số nhà đầu tư cá nhân ra quyết định theo tin đồn, hội nhóm, cảm tính — không phải vì thiếu dữ liệu, mà vì **không thể tổng hợp dữ liệu thành quyết định**.

### 2.2. Khoảng trống của các giải pháp hiện có

Hỏi trực tiếp các chatbot AI tổng quát (ChatGPT, Gemini, Copilot) về đầu tư chứng khoán Việt Nam gặp 5 vấn đề cố hữu:

1. **Không neo vào số liệu Việt Nam cụ thể** — trả lời chung chung, số liệu thường lỗi thời hoặc bịa (hallucination), đặc biệt nguy hiểm với số liệu tài chính.
2. **Không minh bạch nguồn** — người dùng không biết con số lấy từ báo cáo nào, thời điểm nào, hay do model "tự nghĩ ra".
3. **Không phân biệt giả định và sự thật** — đưa kết luận một chiều, không nêu giả định đang dùng làm căn cứ, không chỉ ra yếu tố có thể khiến nhận định sai.
4. **Không có tư duy xác suất** — trả lời "nên/không nên" nhị phân thay vì các kịch bản kèm xác suất.
5. **Không biết danh mục của người hỏi** — không thể phân tích rủi ro tập trung ngành, tương quan tài sản hay gợi ý tái cân bằng cho chính danh mục người dùng đang nắm giữ.

Đây chính là khoảng trống mà **tính minh bạch trong tài chính** — giá trị cốt lõi của ngành — đòi hỏi phải lấp: nhà đầu tư cần biết **số liệu lấy từ đâu, cập nhật khi nào, đáng tin đến đâu** trước khi đặt tiền theo lời khuyên của bất kỳ AI nào.

### 2.3. Định vị sản phẩm

> **Thay vì chỉ "phân tích doanh nghiệp", EconoPulse VN là AI HỖ TRỢ RA QUYẾT ĐỊNH ĐẦU TƯ:**
> biết phân tích **+** biết phản biện **+** đưa nhiều kịch bản kèm xác suất **+** phân tích rủi ro danh mục **+** giải thích và trích nguồn cho mọi luận điểm.

---

## 3. Giải pháp: 4 trụ cột "Decision Copilot"

### Trụ cột 1 — Lớp Minh bạch (Transparency Layer)

Mọi câu trả lời của AI đều gắn nhãn ba thông tin bắt buộc:

```
[Nguồn dữ liệu] · [Thời điểm cập nhật] · [Độ tin cậy: Cao / Trung bình / Thấp]
```

**Cơ chế kỹ thuật:** AI ngôn ngữ (LLM) **không được phép tự sinh số liệu**. Mọi con số trong câu trả lời được truy xuất từ tầng định lượng đã tính sẵn (retrieval-grounded): BCTC chuẩn hóa trong cơ sở dữ liệu, kết quả mô hình dự báo có backtest, giá giao dịch thực. Mỗi con số có "audit trail" — người dùng bấm vào là truy ngược được về đúng bảng dữ liệu/API nguồn. Độ tin cậy được gán theo quy tắc rõ ràng: số đo trực tiếp từ BCTC = Cao; kết quả mô hình có backtest = Trung bình (kèm sai số cụ thể); suy luận định tính của LLM = Thấp (ghi rõ "nhận định, không phải dữ kiện").

### Trụ cột 2 — Động cơ Phản biện (Critique Engine) → *Tư duy phản biện*

Với **mỗi** khuyến nghị, hệ thống bắt buộc sinh đủ 3 phần theo schema cứng (ràng buộc cấu trúc ở tầng prompt + kiểm tra JSON schema ở tầng ứng dụng, không phải "tùy model"):

1. **Luận điểm chính** — vì sao nên / không nên đầu tư, dẫn số liệu cụ thể có nguồn.
2. **Giả định đang sử dụng** — những điều kiện phải đúng thì luận điểm mới đứng vững (ví dụ: "giả định biên lợi nhuận gộp duy trì ≥ 11% như 4 quý gần nhất").
3. **Yếu tố có thể khiến nhận định sai + rủi ro người dùng dễ bỏ qua** — mặt trái của chính luận điểm vừa đưa (ví dụ: "dòng tiền HĐKD quý gần nhất âm 55,7 tỷ dù lợi nhuận dương — lợi nhuận có thể không chuyển thành tiền").

Câu trả lời một chiều (chỉ có phần 1) bị tầng kiểm tra schema từ chối và yêu cầu sinh lại — **phản biện là tính năng bắt buộc, không phải tùy chọn.**

### Trụ cột 3 — Động cơ Kịch bản (Scenario Engine) → *Tư duy xác suất*

Mỗi nhận định đi kèm tối thiểu 3 kịch bản:

| Kịch bản | Nội dung | Xác suất | Điều kiện kích hoạt |
|---|---|---|---|
| **Base Case** | Diễn biến cơ sở | ~P% | ... |
| **Bull Case** | Kịch bản thuận lợi | ~P% | ... |
| **Bear Case** | Kịch bản bất lợi | ~P% | ... |

**Điểm khác biệt:** xác suất không do AI "đoán suông" mà được neo vào nền định lượng — khoảng tin cậy 80% từ mô hình dự báo chuỗi thời gian SARIMAX của hệ thống (ví dụ dự báo tăng trưởng GDP 2026: trung vị 7,19%, khoảng 80%: 5,26–9,11% — chính khoảng này định khung Base/Bull/Bear cho các nhận định vĩ mô). LLM chỉ diễn giải điều kiện kích hoạt và hệ quả từng kịch bản bằng ngôn ngữ tự nhiên.

### Trụ cột 4 — Phân tích Danh mục (Portfolio Analyzer)

Người dùng nhập danh mục đang nắm giữ (mã + khối lượng). Hệ thống tính và trả về:

- **Tỷ trọng theo ngành** (từ dữ liệu phân ngành 1.527 công ty) → cảnh báo rủi ro tập trung.
- **Ma trận tương quan** giữa các mã trong danh mục (từ 16.317 quan sát giá) → chỉ ra các cặp tài sản "tưởng đa dạng mà thực ra cùng nhịp".
- **Rủi ro danh mục** (độ biến động, đóng góp rủi ro biên của từng mã).
- **Gợi ý tái cân bằng** bằng động cơ tối ưu hóa lượng tử: bài toán chọn danh mục Markowitz được đưa về dạng QUBO và giải bằng **thuật toán QAOA chạy trên trình mô phỏng lượng tử PennyLane** (đúng khuyến nghị của BTC — không cần phần cứng lượng tử thật), có đối chiếu nghiệm brute-force để báo cáo *optimality gap* định lượng.

---

## 4. Phương pháp AI/Lượng tử dự kiến áp dụng và lý do lựa chọn

### 4.1. Kiến trúc lai 2 tầng (Hybrid Quantitative + LLM)

```
┌─────────────────────────────────────────────────────────────────┐
│ TẦNG A — ĐỊNH LƯỢNG XÁC ĐỊNH (kiểm chứng được, có backtest)      │
│  · SARIMAX: dự báo GDP, CPI (World Bank, 41 năm dữ liệu)         │
│    + chỉ số thị trường 30 phiên (backtest RMSE tốt hơn naive 3,6×)│
│  · Altman Z''-score + Piotroski F-score: chấm điểm sức khỏe DN   │
│    từ 145.276 dòng BCTC chuẩn hóa                                │
│  · QUBO + QAOA (PennyLane simulator): tối ưu danh mục,           │
│    optimality gap đo được (thử nghiệm hiện tại: 3,27%)           │
├─────────────────────────────────────────────────────────────────┤
│ TẦNG B — LLM DIỄN GIẢI (Gemini API, JSON schema bắt buộc)        │
│  · CHỈ diễn giải + phản biện + kịch bản hóa số liệu của Tầng A   │
│  · KHÔNG được tự sinh số → loại trừ hallucination số liệu        │
│  · Output theo schema: {luận điểm, giả định, rủi ro, 3 kịch bản  │
│    kèm xác suất, nhãn nguồn/độ tin cậy}                          │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2. Lý do lựa chọn

- **LLM thuần không đủ:** dễ bịa số liệu tài chính — không chấp nhận được khi người dùng đặt tiền thật theo câu trả lời. Đây là rủi ro đạo đức mà thể lệ cuộc thi (tiêu chí "Tác động xã hội và đạo đức", Vòng 3) yêu cầu xử lý nghiêm túc.
- **Mô hình định lượng thuần không đủ:** cho ra con số đúng nhưng không giải thích được bằng ngôn ngữ tự nhiên, không tự nêu giả định/rủi ro, không đối thoại được với người dùng phổ thông.
- **Kiến trúc lai giải quyết đúng nỗi đau:** tầng A đảm bảo *đúng số*, tầng B đảm bảo *hiểu được và phản biện được* — khớp chính xác với định nghĩa "tổng hợp thông tin + hỗ trợ ra quyết định".
- **Lượng tử có vai trò thật, không trang trí:** tối ưu danh mục là bài toán tổ hợp NP-hard kinh điển mà QAOA được thiết kế để giải; chúng em đo và công khai optimality gap so với nghiệm chính xác — đúng tinh thần Điều 10 thể lệ: *"công nghệ phức tạp không phải tiêu chí tự thân... BGK ưu tiên kết quả thực"*.

### 4.3. Bằng chứng khả thi — prototype ĐÃ chạy được (không phải ý tưởng trên giấy)

Tại thời điểm nộp hồ sơ, nhóm đã có hệ thống demo chạy thật trên máy cá nhân:

- Pipeline dữ liệu 6 bước (P0–P5) đã crawl **toàn bộ 1.527 mã**; dữ liệu mẫu sâu cho 73 công ty (BCTC 4 báo cáo × nhiều kỳ), 33 mã có chuỗi giá 2 năm.
- Dashboard web hợp nhất hiển thị: dự báo GDP/CPI kèm khoảng tin cậy và **backtest walk-forward công khai** (kể cả năm sai nhiều do COVID — minh bạch cả điểm yếu); chỉ số thị trường + dự báo 30 phiên (MAPE 5,9%); bảng xếp hạng sức khỏe 71 doanh nghiệp; kết quả tối ưu danh mục QAOA thật trên PennyLane.
- Toàn bộ mã nguồn có cấu trúc module, chạy lại được bằng 2 lệnh (`python run_pipeline.py` → `python gateway/app.py`).

---

## 5. Nguồn dữ liệu dự kiến

| Nguồn | Nội dung | Trạng thái | Tính hợp pháp |
|---|---|---|---|
| vnstock (dữ liệu công khai TTCK VN) | BCTC, giá, hồ sơ, tin CBTT, sự kiện của 1.527 mã | **Đã thu thập** vào SQLite (145.276 dòng BCTC) | Dữ liệu công bố công khai theo quy định CBTT |
| World Bank Open Data API | GDP, CPI, thất nghiệp, xuất khẩu VN 1985–2025 | **Đã kết nối**, cache tự động | Dữ liệu mở, giấy phép CC BY-4.0 |
| Bảng giá VNDirect (HOSE/HNX/UPCOM) | Giá khớp realtime, 3 mức mua/bán, khối ngoại | **Đã crawl được** qua module riêng | Dữ liệu hiển thị công khai |
| RSS tài chính quốc tế (CNBC, MarketWatch, Yahoo Finance, Investing...) | Tin vĩ mô toàn cầu làm ngữ cảnh | **Đã tích hợp** trong module tin tức | RSS công khai, miễn phí |
| Danh mục người dùng tự nhập | Mã + khối lượng nắm giữ | Thiết kế ở Vòng 2 | Người dùng tự nguyện cung cấp; không thu thập dữ liệu cá nhân nhạy cảm |

Toàn bộ nguồn là **dữ liệu mở hoặc tự thu thập hợp pháp** — đáp ứng Điều 6.8 thể lệ. Quy mô dữ liệu đủ lớn để huấn luyện/kiểm chứng mô hình (tiêu chí "Tính khả thi của dữ liệu" — trọng số 15% Vòng 1).

---

## 6. Tính mới và tính khả thi

### 6.1. Tính mới

1. **Không phải "thêm một chatbot tài chính"** — điểm mới nằm ở chỗ *quy trình ra quyết định đúng* (phản biện bắt buộc + kịch bản xác suất + minh bạch nguồn) được **mã hóa thành ràng buộc kỹ thuật** (JSON schema + grounding layer), không phụ thuộc thiện chí của model. Cùng một câu hỏi, hỏi thẳng ChatGPT/Gemini sẽ không bao giờ tự động có: nhãn nguồn từng con số, mục "giả định của tôi là gì", "điều gì khiến tôi sai", và 3 kịch bản kèm xác suất neo vào mô hình thống kê.
2. **Kết hợp AI–Lượng tử có ý nghĩa thực chất:** QAOA giải đúng một bài toán NP-hard có giá trị ứng dụng (tối ưu danh mục), có số đo chất lượng nghiệm công khai — phù hợp giải phụ "Ứng dụng Lượng tử xuất sắc".
3. **Minh bạch cả điểm yếu:** hệ thống công khai backtest kể cả khi mô hình thua naive ở giai đoạn sốc COVID — một lựa chọn thiết kế hiếm thấy ở sản phẩm thương mại, đúng tinh thần học thuật và đạo đức AI có trách nhiệm.

### 6.2. Tính khả thi triển khai thực tiễn

- **Chi phí vận hành thấp:** tầng định lượng chạy trên máy tính phổ thông; LLM dùng API theo lượt gọi (chi phí ước tính < 500đ/câu trả lời với Gemini Flash); mô phỏng lượng tử không cần phần cứng chuyên dụng.
- **Lộ trình sản phẩm hóa rõ:** Vòng 2 hoàn thiện 4 trụ cột trên nền prototype sẵn có (6 tuần xây dựng theo lịch BTC); sau cuộc thi có thể triển khai pilot cho CLB chứng khoán sinh viên các trường khối kinh tế — đối tượng đúng của Học viện Tài chính.
- **Đội ngũ đã chứng minh năng lực thực thi:** 4 sản phẩm thành phần (hệ thống crawl toàn thị trường, bảng giá realtime, nền tảng chat AI đa persona, ứng dụng tin tức + phân tích nhánh) đều đã chạy được — dự án dự thi là bước hợp nhất có định hướng, không phải khởi đầu từ số 0.

### 6.3. Trả lời câu hỏi phản biện then chốt: *"AI của nhóm có bị thay thế bởi AI của các 'ông lớn' nếu họ train trên nguồn dữ liệu y hệt không?"*

Chúng em chủ động trả lời câu hỏi này ngay trong hồ sơ vì nó là phép thử sống còn của mọi sản phẩm AI ứng dụng:

**a) Khác biệt về mô hình kinh doanh, không phải cuộc đua về model.** Google/OpenAI bán *mô hình nền tảng ngang* (horizontal foundation model) phục vụ mọi ngành, mọi quốc gia. Xây một ứng dụng dọc (vertical) cho nhà đầu tư cá nhân Việt Nam — thị trường ngách xét trên quy mô toàn cầu của họ — không nằm trong động cơ kinh doanh của Big Tech. Lịch sử ngành đã chứng minh: Bloomberg Terminal và Refinitiv vẫn đứng vững hàng chục năm không phải vì NLP của họ mạnh hơn Google, mà vì **dữ liệu ngành đã chuẩn hóa + quy trình nghiệp vụ đóng gói** mà model ngang không thay thế được.

**b) Tài sản của chúng em không phải model — là pipeline dữ liệu và tầng định lượng đã kiểm định.** 145.276 dòng BCTC đã ETL theo đúng cấu trúc kế toán Việt Nam (phân biệt doanh nghiệp phi tài chính / ngân hàng / công ty chứng khoán), các mô hình có backtest công khai, engine QUBO có số đo chất lượng nghiệm. Một LLM dù train trên dữ liệu thô y hệt vẫn không tự có tầng định lượng kiểm chứng này — nó chỉ có thể *bắt chước văn phong*, không thể *bảo đảm con số*.

**c) Ràng buộc phản biện + minh bạch nguồn là thiết kế sản phẩm, không phải năng lực model.** Cùng một model Gemini, hỏi trực tiếp sẽ không có audit trail nguồn số liệu; chạy qua kiến trúc của chúng em thì bắt buộc có. Giá trị nằm ở **lớp kiến trúc bao quanh model** — thứ chúng em sở hữu và kiểm soát, có thể thay model nền bên dưới (Gemini → Claude → model mã nguồn mở) mà sản phẩm không đổi.

**d) Data flywheel tích lũy theo thời gian.** Danh mục người dùng, câu hỏi thực tế, phản hồi đúng/sai của các kịch bản đã đưa — tích lũy thành dữ liệu huấn luyện và hiệu chỉnh riêng mà đối thủ đến sau không thể có, kể cả khi dùng chung nguồn dữ liệu công khai ban đầu.

**Kết luận:** chiến lược của nhóm là *"vertical AI application xây trên nền LLM ngang"* — không cạnh tranh với Big Tech ở tầng model (cuộc đua không thể thắng), mà ở tầng **dữ liệu ngành + quy trình ra quyết định + niềm tin từ minh bạch** (cuộc đua Big Tech không tham gia).

---

## 7. Sơ đồ AI Working Flow (Roadmap luồng xử lý)

Luồng đầy đủ từ lúc người dùng bắt đầu sử dụng đến khi nhận kết quả:

```
 NGƯỜI DÙNG
 │  (đặt câu hỏi đầu tư / nhập danh mục đang nắm giữ)
 ▼
┌────────────────────────────────────────────────────────────────────┐
│ BƯỚC 1 · COLLECT — Thu thập gì?                                    │
│  • BCTC + giá + tin CBTT + sự kiện: market.db (1.527 mã, cập nhật  │
│    theo pipeline crawl P0–P5, tự động bỏ qua mã đã crawl)          │
│  • Vĩ mô: World Bank API (GDP/CPI/thất nghiệp, cache cục bộ)       │
│  • Realtime: bảng giá VNDirect (giá khớp, mua-bán 3 mức, khối ngoại)│
│  • Ngữ cảnh toàn cầu: RSS CNBC/MarketWatch/Investing               │
│  • Đầu vào người dùng: câu hỏi + danh mục (mã, khối lượng)         │
└────────────────────────────────────────────────────────────────────┘
 ▼
┌────────────────────────────────────────────────────────────────────┐
│ BƯỚC 2 · ANALYZE — Phân tích như thế nào? (tầng định lượng)        │
│  • SARIMAX → dự báo GDP/CPI/chỉ số thị trường + khoảng tin cậy 80% │
│    + backtest walk-forward công khai sai số                        │
│  • Altman Z'' + Piotroski F → điểm sức khỏe từng doanh nghiệp      │
│  • Ma trận tương quan + tỷ trọng ngành → hồ sơ rủi ro danh mục     │
│  • QUBO/QAOA (PennyLane) → phương án tái cân bằng tối ưu           │
└────────────────────────────────────────────────────────────────────┘
 ▼
┌────────────────────────────────────────────────────────────────────┐
│ BƯỚC 3 · DISTILL — Chắt lọc insight ra sao? (tầng LLM có ràng buộc)│
│  • LLM nhận: câu hỏi + TOÀN BỘ số liệu đã tính ở Bước 2 (không     │
│    được tự sinh số mới)                                            │
│  • Bắt buộc trả về đúng JSON schema:                               │
│    { luận_điểm[], giả_định[], yếu_tố_có_thể_sai[],                 │
│      kịch_bản: [Base/Bull/Bear + xác_suất + điều_kiện],            │
│      nguồn + thời_điểm + độ_tin_cậy cho TỪNG con số }              │
│  • Schema sai → từ chối, yêu cầu sinh lại (validation tự động)     │
└────────────────────────────────────────────────────────────────────┘
 ▼
┌────────────────────────────────────────────────────────────────────┐
│ BƯỚC 4 · OUTPUT — Kết quả người dùng nhận được                     │
│  • Thẻ khuyến nghị 3 phần: Luận điểm → Giả định → Rủi ro/phản biện │
│  • 3 kịch bản Base/Bull/Bear kèm xác suất và điều kiện kích hoạt   │
│  • Báo cáo danh mục: tập trung ngành, tương quan, gợi ý cân bằng   │
│  • Mọi con số bấm được → truy ngược về bảng dữ liệu/API nguồn      │
│    (audit trail) — người dùng tự kiểm chứng, không phải tin suông  │
└────────────────────────────────────────────────────────────────────┘
```

**Vòng lặp cải tiến:** phản hồi người dùng + kết quả thực tế của các kịch bản đã đưa → được ghi lại làm dữ liệu hiệu chỉnh xác suất và cải thiện prompt schema (data flywheel — mục 6.3d).

---

## 8. Khai báo sử dụng công cụ AI hỗ trợ (theo Điều 5.2 và Điều 14 Thể lệ)

Nhóm khai báo minh bạch: trong quá trình phát triển prototype có sử dụng công cụ AI hỗ trợ lập trình (kiểm tra lỗi, gợi ý cấu trúc mã) và soạn thảo tài liệu. Toàn bộ **ý tưởng sản phẩm, định vị, kiến trúc hệ thống, lựa chọn mô hình, dữ liệu và kiểm định kết quả do các thành viên nhóm thực hiện, hiểu và bảo vệ được từng chi tiết**. Các mô hình AI tạo sinh không tạo ra toàn bộ bài dự thi mà chỉ đóng vai trò công cụ hỗ trợ có kiểm soát của con người — đúng quy định Điều 14.

---

## 9. Tóm tắt một trang (Executive Summary)

- **Bài toán:** nhà đầu tư cá nhân VN chìm trong 145 nghìn dòng BCTC + 2 nghìn tin CBTT nhưng thiếu công cụ **tổng hợp thành quyết định** — các chatbot AI hiện có trả lời không nguồn, không phản biện, không xác suất, không biết danh mục người hỏi.
- **Giải pháp:** Decision Copilot 4 trụ cột — *Minh bạch nguồn/độ tin cậy · Phản biện bắt buộc · Kịch bản Base/Bull/Bear kèm xác suất · Phân tích danh mục cá nhân* — trên kiến trúc lai: tầng định lượng có backtest (SARIMAX, Z''/F-score, QUBO/QAOA) + tầng LLM bị ràng buộc schema, không được tự sinh số.
- **Bằng chứng:** prototype đã chạy — dashboard demo với dữ liệu thật 1.527 mã, dự báo GDP 2026 = 7,19% [5,26–9,11], backtest chỉ số thị trường tốt hơn naive 3,6×, QAOA đạt optimality gap 3,27%.
- **Vì sao khó bị thay thế:** tài sản là pipeline dữ liệu chuẩn VN + tầng định lượng kiểm định + thiết kế quy trình ra quyết định — không phải model; chiến lược vertical AI trên nền LLM ngang.
- **Đề xuất:** dự thi Nhóm 1 (AI Phân tích Kinh tế vĩ mô), ứng viên giải phụ "Ứng dụng Lượng tử xuất sắc".
