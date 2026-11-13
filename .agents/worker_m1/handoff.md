# BÁO CÁO BÀN GIAO TOÀN DIỆN (HANDOFF REPORT) — WORKER M1
## DỰ ÁN: FINTUITION - DỊCH VỤ SỐ MARKET PULSE
### TÀI LIỆU BÀN GIAO: KỊCH BẢN THUYẾT TRÌNH 12 PHÚT MÔ HÌNH DỊCH VỤ 5W1H

- **Mã phân nhiệm**: Worker M1 (`worker_m1`)
- **Đối tượng tiếp nhận**: Parent Orchestrator (`orchestrator_3` / Conversation ID: `2af7c86d-101e-4459-bbff-90ef4fda8ca2`)
- **Tập tin sản phẩm bàn giao**: `c:\Users\MSI\Desktop\Final Market Pulse\docs\assignment\PRESENTATION_SCRIPT_5W1H_SERVICE.md`
- **Thời gian hoàn tất**: 2026-09-09T14:08:00Z

---

## 1. OBSERVATION (QUAN SÁT THỰC TRỨNG)

1. **Yêu cầu nhiệm vụ tại `ORIGINAL_REQUEST.md` (phiên bản `2026-09-09T13:57:36Z`)**:
   - Dòng 106: *"Bộ kịch bản thuyết trình toàn diện (12 phút — 2 phút/thành viên) giới thiệu tổng quan về doanh nghiệp và dịch vụ tài chính cá nhân FinTuition - Market Pulse, áp dụng chuẩn mực 5W1H mô hình dịch vụ (Service Template), phân vai cho 6 thành viên đại diện các phòng ban ra mắt công chúng với phong cách giao tiếp kinh doanh lịch thiệp, dễ hiểu, tuyệt đối không dùng thuật ngữ kỹ thuật phức tạp."*
   - Dòng 114–120: Phân định chi tiết 6 vai trò:
     * Thành viên 1 — CEO (WHO & Bối cảnh doanh nghiệp): 13 triệu tài khoản, bão tin đồn, sáng lập FinTuition, "Thông dịch viên dữ liệu trung thực", trị 4 nỗi đau.
     * Thành viên 2 — Product Lead (WHAT & Dịch vụ cốt lõi): Ẩn dụ "Bác sĩ tài chính", 4 tiện ích (Điểm 0–100, Radar Đèn Giao Thông, Trợ lý trích dẫn nguồn, Bảng so sánh cùng ngành).
     * Thành viên 3 — Marketing Lead (WHEN & WHERE): 4 khoảnh khắc vàng & Đa kênh số (Mobile App, Web Portal, Cộng đồng).
     * Thành viên 4 — CX Lead (HOW & Hành trình): 3 bước tinh giản (<1 phút onboarding, báo cáo trực quan tức thì, hỗ trợ 24/7), thấu cảm nỗi sợ F0.
     * Thành viên 5 — Quality & Risk Lead (WHY & Trụ cột niềm tin): Khách quan độc lập (0% hoa hồng), tuyệt đối không phím hàng (Điều 71 Luật Chứng khoán 2019), bảo mật thông tin (Nghị định 13/2023/NĐ-CP), cảnh báo rủi ro minh bạch.
     * Thành viên 6 — PR & Comms Lead (Tầm nhìn, Ưu đãi & Chốt bài): Văn minh tài chính, Gói trải nghiệm 0 đồng sinh viên, Tri ân, CTA Quét mã QR, Đồng loạt cúi chào 15 độ trong 3 giây và chuyển tiếp Q&A.
   - Dòng 133–136: Định mức từ: Mỗi thành viên từ **240 đến 280 từ tiếng Việt**, đọc trung bình 110–130 giây. Tuyệt đối không chứa thuật ngữ backend.

2. **Phát hiện kiểm toán bất thường từ báo cáo của Explorer M1_3**:
   - Tại `explorer_m1_3/handoff.md` dòng 451–459, báo cáo tuyên bố Diễn giả 5 có 277–278 từ.
   - Tuy nhiên, khi kiểm tra thực tế chuỗi `s5` bằng Python `len(s5.split())`, văn bản thực tế dài **315 từ** (vượt trần 280 từ tới 35 từ, tương đương cháy giáo án hơn 15 giây).
   - Nhóm Worker M1 đã trực tiếp phát hiện và tinh chỉnh văn bản Diễn giả 5 xuống **261–265 từ**, bảo toàn 100% nội dung pháp lý (Điều 71 Luật Chứng khoán, Nghị định 13/2023/NĐ-CP, 0% hoa hồng, Đèn Giao Thông) và đảm bảo nằm trọn vẹn trong khung 240–280 từ.

3. **Thực trạng tập tin đã xuất bản**:
   - Đã tạo lập thành công tập tin: `docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md`.
   - Quy mô tập tin: **582 dòng, 52.733 ký tự**, bao phủ trọn vẹn 6 phần lớn.

---

## 2. LOGIC CHAIN (CHUỖI LẬP LUẬN TỪ QUAN SÁT ĐẾN GIẢI PHÁP)

1. **Chuẩn hóa khung cấu trúc 5W1H định hướng dịch vụ đại chúng**:
   - Khác với báo cáo kỹ thuật nội bộ trước đây (tập trung vào SQLite WAL, Hotfix BN-06, QAOA 14 qubits), bài thuyết trình ra mắt công chúng đòi hỏi ngôn ngữ dịch vụ đời thường, chạm vào cảm xúc người nghe.
   - Cấu trúc 5W1H được ánh xạ hoàn hảo:
     * **WHO** (CEO): Ai đứng sau dịch vụ? Giá trị đạo đức của người sáng lập.
     * **WHAT** (Product Lead): Dịch vụ cung cấp những giá trị thiết thực nào?
     * **WHEN & WHERE** (Marketing Lead): Sử dụng vào lúc nào và ở đâu tiện nhất?
     * **HOW** (CX Lead): Hành trình trải nghiệm diễn ra như thế nào?
     * **WHY** (Quality & Risk Lead): Tại sao người dùng trao gửi trọn vẹn niềm tin?
     * **VISION & CTA** (PR Lead): Tầm nhìn tương lai, ưu đãi phụng sự và hành động ngay.

2. **Kiểm soát dung lượng từ (Word Count Guardrail: 240 – 280 từ/người)**:
   - Tốc độ phát biểu chuẩn tiếng Việt giao tiếp kinh doanh là 125–135 từ/phút. Một bài nói 2 phút yêu cầu tối thiểu 240 từ và tối đa 280 từ để vừa đủ truyền tải luận điểm, vừa có các khoảng lặng 1–2 giây giao lưu cảm xúc với hội trường.
   - Toàn bộ 6 đoạn thoại đều được đo đạc chính xác bằng lệnh Python phân tích chuỗi ký tự UTF-8 trực tiếp từ file đĩa:
     * Speaker 1: 271 từ.
     * Speaker 2: 279 từ.
     * Speaker 3: 274 từ.
     * Speaker 4: 273 từ.
     * Speaker 5: 265 từ.
     * Speaker 6: 272 từ.
     * Tổng số từ toàn đội: **1.634 từ** (trung bình 272 từ/người, thời lượng đúng 12 phút).

3. **Triệt tiêu hoàn toàn thuật ngữ kỹ thuật backend (Zero Backend Jargon Guardrail)**:
   - Danh sách đen gồm 21 thuật ngữ công nghệ backend (`sqlite`, `wal`, `qaoa`, `pennylane`, `piotroski`, `altman`, `microservice`, `backend`, `rag`, `api`, `gateway`, `qubit`, `hamiltonian`, `pauli`, `python`, `hotfix`, `bn-06`, `bn-07`, `sarimax`, `tokenizer`, `json`) được kiểm tra tự động và đạt **0 kết quả trùng khớp** trong toàn bộ các đoạn thoại.
   - Thay vào đó là ngôn ngữ dịch vụ: "bác sĩ tài chính", "điểm sức khỏe 0-100", "radar đèn giao thông", "nguồn dữ liệu kiểm toán", "bảng so sánh vị thế ngành".

4. **Đồng bộ hóa với Poster A0 và Nghệ thuật biểu diễn sân khấu**:
   - Tích hợp 6 Thẻ ghi nhớ cầm tay (Master Cue Cards A6) với 3–4 bullet points ngắn gọn kích hoạt trí nhớ, điểm neo Poster A0 và câu bàn giao chính xác.
   - Thiết lập Động cơ chuyển tiếp 5 nhịp cầu hai chiều (Outgoing Lead và Incoming Hook) kết nối tự nhiên giữa các thành viên.
   - Quy chuẩn sân khấu: Đội hình chữ V mở (Open V-Formation), Bục tiêu điểm bước lên 1 bước, Tư thế lắng nghe chủ động, Quy tắc tam giác thị giác 40-30-30, Bàn tay mở, Dừng thị giác 3 giây và Nghi thức cúi chào đồng bộ 15 độ trong 3 giây.

---

## 3. CAVEATS (GIỚI HẠN & LƯU Ý ĐẶC BIỆT)

1. **Phân biệt Lời thoại nguyên văn vs. Hướng dẫn cử chỉ**:
   - Số lượng từ được kiểm toán trên phần **lời thoại nguyên văn được phát âm ra tiếng**. Các chỉ dẫn cử chỉ trong ngoặc vuông đậm (như `**[Dừng 1 giây, ánh mắt đồng cảm]**`, `**[Chỉ tay vào thước đo ba màu trên poster]**`) là ghi chú diễn xuất cho diễn giả, không tính vào số từ phát biểu.
2. **Kỷ luật bám sát Thẻ ghi nhớ khi lên bục**:
   - Diễn giả khi lên sân khấu chỉ cầm Thẻ ghi nhớ A6 với các từ khóa ngắn gọn, không cầm cả tập kịch bản dài để tránh việc cúi đầu đọc tài liệu làm mất kết nối thị giác với Ban giám khảo.
3. **Phạm vi chỉnh sửa tập tin**:
   - Worker M1 tuân thủ nghiêm ngặt chỉ thị về quyền ghi: Chỉ tạo lập và cập nhật duy nhất tập tin bàn giao `docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md` và các tài liệu metadata trong thư mục `.agents/worker_m1/`. Tuyệt đối không can thiệp vào các tập tin mã nguồn hoặc tài liệu khác.

---

## 4. CONCLUSION (KẾT LUẬN)

Tập tin `docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md` đã được hoàn thành trọn vẹn, đáp ứng xuất sắc và vượt trên mọi tiêu chí nghiệm thu của đề bài:
- Đầy đủ 6 phần lớn: Tổng quan điều hành & Ma trận 5W1H; Lời thoại nguyên văn 6 diễn giả; Hệ thống Thẻ ghi nhớ A6; Động cơ chuyển tiếp 5 nhịp cầu; Nghệ thuật điều phối sân khấu; và Báo cáo kiểm toán chất lượng.
- Phân vai cân bằng tuyệt đối cho 6 vị trí lãnh đạo phòng ban (CEO, Product, Marketing, CX, Quality & Risk, PR & Comms).
- 100% diễn giả đạt chuẩn số từ nghiêm ngặt (240–280 từ) với nhịp độ chuẩn xác cho bài thuyết trình 12 phút.
- Loại bỏ 100% thuật ngữ kỹ thuật backend; chuyển tải trọn vẹn tinh thần "Thông dịch viên dữ liệu trung thực", "Văn minh tài chính", Gói ưu đãi sinh viên 0 đồng và bảo vệ an toàn vốn theo quy định pháp lý.

---

## 5. VERIFICATION METHOD (PHƯƠNG PHÁP KIỂM CHỨNG ĐỘC LẬP)

Kiểm toán viên độc lập hoặc Parent Orchestrator có thể chạy lệnh kiểm chứng trực tiếp từ dòng lệnh Powershell/CMD tại thư mục gốc dự án:

```bash
python -c "
import re, sys
sys.stdout.reconfigure(encoding='utf-8')

filepath = r'docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'### 2\.[1-6] Diễn Giả [1-6].*?\n#### B\. Lời Thoại Thực Chiến Nguyên Văn \(Full Verbatim Script\)\s*\n\n(>.*?)(?=\n#### C|\n---|\Z)'
matches = re.findall(pattern, content, re.DOTALL)
assert len(matches) == 6, f'Expected 6 scripts, found {len(matches)}'

speaker_names = ['Speaker 1 (CEO)', 'Speaker 2 (Product Lead)', 'Speaker 3 (Marketing Lead)', 'Speaker 4 (CX Lead)', 'Speaker 5 (Quality & Risk Lead)', 'Speaker 6 (PR & Comms Lead)']
banned_jargon = ['sqlite', 'wal', 'qaoa', 'pennylane', 'piotroski', 'altman', 'microservice', 'backend', 'rag', 'api', 'gateway', 'qubit', 'hamiltonian', 'pauli', 'python', 'hotfix', 'bn-06', 'bn-07', 'sarimax', 'tokenizer', 'json']

for idx, (name, raw_script) in enumerate(zip(speaker_names, matches)):
    clean = re.sub(r'\[.*?\]', '', raw_script).replace('>', ' ').replace('*', ' ').replace('\'', ' ')
    words = [w for w in clean.split() if w.strip()]
    wc = len(words)
    assert 240 <= wc <= 280, f'{name} out of bounds: {wc}'
    for bj in banned_jargon:
        assert bj not in clean.lower(), f'{name} contains {bj}'
    print(f'PASS: {name} -> {wc} words, ZERO forbidden jargon')
print('ALL 6 SPEAKERS PASS 100%')
"
```

**Điều kiện vô hiệu hóa (Invalidation Conditions)**:
- Nếu bất kỳ diễn giả nào có số từ ngoài khung 240–280 từ.
- Nếu xuất hiện bất kỳ từ khóa nào trong danh sách cấm thuật ngữ backend trong lời thoại.
- Nếu thiếu bất kỳ một trong 6 vai diễn 5W1H hoặc thiếu 5 nhịp cầu chuyển tiếp.
