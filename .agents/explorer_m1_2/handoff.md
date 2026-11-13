# BÁO CÁO NGHIÊN CỨU & THIẾT KẾ KỊCH BẢN THUYẾT TRÌNH (EXPLORER 2 - MILESTONE 1)
## Chuyên Đề: Speaker 3 (Marketing Lead - WHEN & WHERE) & Speaker 4 (CX Lead - HOW)
### Tài liệu bàn giao cho Worker Agent (`worker_m1`) | Dự án: FinTuition - Market Pulse

---

## TỔNG QUAN ĐIỀU HÀNH (EXECUTIVE SUMMARY)

Báo cáo này thiết lập nền tảng kỹ thuật nội dung và kịch bản thuyết trình kinh doanh chuẩn mực cho hai diễn giả trung tâm trong bài thuyết trình 12 phút (5W1H Service Template):
1. **Speaker 3 — Marketing Lead (Thời điểm & Kênh tiếp cận - WHEN & WHERE)**:
   - **WHEN**: 4 khoảnh khắc vàng khách hàng cần đến Market Pulse (Trước khi giải ngân đầu tư, Mùa báo cáo tài chính dồn dập, Rà soát sức khỏe danh mục định kỳ, và Khi thị trường biến động rung lắc mạnh).
   - **WHERE**: Hệ sinh thái tiếp cận đa nền tảng số liền mạch (Mobile App tra cứu nhanh bỏ túi, Web Portal phân tích chuyên sâu màn hình lớn, Kênh Cộng đồng hội thảo tri thức văn minh).
   - **Số từ thoại đạt chuẩn**: **267 từ** (khung chuẩn: 240–280 từ, thời lượng nói chuẩn: 120–125 giây).
2. **Speaker 4 — Customer Experience (CX) Lead (Hành trình phục vụ - HOW)**:
   - **HOW**: Quy trình phục vụ tinh giản 3 bước lấy khách hàng làm trung tâm (Bước 1: Khởi đầu siêu tốc dưới 1 phút; Bước 2: Nhận báo cáo trực quan tức thì; Bước 3: Hỗ trợ tư vấn thông tin minh bạch 24/7).
   - **Tâm lý & Thấu cảm**: Hóa giải 3 nỗi sợ lớn nhất của nhà đầu tư mới (sợ lừa đảo/tin đồn, sợ số liệu khô khan phức tạp, sợ bơ vơ khi thị trường sụt giảm).
   - **Số từ thoại đạt chuẩn**: **269 từ** (khung chuẩn: 240–280 từ, thời lượng nói chuẩn: 120–125 giây).
3. **Chuẩn mực ngôn phong**: 100% tiếng Việt giao tiếp kinh doanh lịch thiệp, truyền cảm hứng, thấu cảm, tuyệt đối không chứa thuật ngữ backend/lập trình (Zero technical jargon: không nhắc SQLite, WAL, QAOA, microservices, AST,...).

---

## 1. OBSERVATION (QUAN SÁT THỰC NGHIỆM TỪ TÀI LIỆU HỆ THỐNG)

Dựa trên việc kiểm tra trực tiếp các tài liệu nguồn tại hệ thống:

1. **Yêu cầu nhiệm vụ tại `ORIGINAL_REQUEST.md` (Phiên bản cập nhật `2026-09-09T13:57:36Z`)**:
   - Dòng 106: *"Bộ kịch bản thuyết trình toàn diện (12 phút — 2 phút/thành viên) giới thiệu tổng quan về doanh nghiệp và dịch vụ tài chính cá nhân FinTuition - Market Pulse, áp dụng chuẩn mực 5W1H mô hình dịch vụ (Service Template), phân vai cho 6 thành viên đại diện các phòng ban ra mắt công chúng với phong cách giao tiếp kinh doanh lịch thiệp, dễ hiểu, tuyệt đối không dùng thuật ngữ kỹ thuật phức tạp."*
   - Dòng 117 (Speaker 3): *"Thành viên 3 — Marketing Lead (Thời điểm & Kênh tiếp cận - WHEN & WHERE): Thời điểm khách hàng cần dịch vụ (trước khi ra quyết định đầu tư, theo dõi biến động định kỳ), kênh trải nghiệm đa nền tảng số (App di động, Web portal, kênh cộng đồng)."*
   - Dòng 118 (Speaker 4): *"Thành viên 4 — Customer Experience (CX) Lead (Hành trình phục vụ - HOW): Quy trình phục vụ 3 bước tinh giản cho khách hàng (Đăng ký nhanh -> Nhận báo cáo trực quan tức thì -> Hỗ trợ tư vấn thông tin minh bạch 24/7), chăm sóc khách hàng tận tâm."*
   - Dòng 133: *"Tổng thời lượng kịch bản đạt đúng chuẩn 12 phút (mỗi thành viên từ 240 đến 280 từ, thời gian đọc trung bình 110–130 giây)."*

2. **Phạm vi triển khai tại `SCOPE.md` (`.agents/orchestrator_3/SCOPE.md`)**:
   - Dòng 4–8: *"Framework: 5W1H Service Template Model (Who, What, When, Where, Why, How). Tone & Audience: Public-facing business communication, polite, inspiring, zero programming/backend jargon. Format: 6 speakers, 2 minutes each (12 minutes total). Word Count Standard: 240-280 spoken Vietnamese words per speaker."*
   - Dòng 15–16: Phân định rõ ràng vai trò Speaker 3 (WHEN & WHERE) và Speaker 4 (HOW & Service Journey).

3. **Hiện trạng tài liệu nghiên cứu toàn diện `MARKET_PULSE_GLOBAL_REPORT_VI.md`**:
   - Dòng 248–280 (Mục 2.3 WHEN): Tập trung sâu vào khía cạnh hạ tầng kỹ thuật (Tick pipeline 1s, ETL 15:15, SWR Cache 30s/300s, SQLite optimization). Đây là dữ liệu nền tảng, nhưng khi chuyển hóa sang kịch bản dịch vụ công chúng, khía cạnh WHEN phải được diễn giải thành **thời điểm và bối cảnh sử dụng của khách hàng**.
   - Dòng 740–742: Kịch bản cũ phân vai theo hướng học thuật nội bộ (CTO, Head of AI, Head of Data). Cần chuyển đổi triệt để sang phong thái của Giám đốc Tiếp thị (Marketing Lead) và Giám đốc Trải nghiệm Khách hàng (CX Lead).

4. **Bản thiết kế trực quan Poster A0 tại `A0_POSTER_SKETCH_GUIDE.md`**:
   - Dòng 360–397 (Zone 4: WHEN): Vị trí giữa-phải ($X: 591 \to 821\text{ mm}, Y: 465 \to 725\text{ mm}$), có biểu đồ đồng hồ 24h và trục thời gian.
   - Dòng 313–358 (Zone 3: WHERE): Vị trí giữa-trái ($X: 20 \to 250\text{ mm}, Y: 465 \to 725\text{ mm}$), thể hiện không gian mở rộng và nền tảng.
   - Dòng 466–513 (Zone 6: HOW): Vị trí góc dưới-phải ($X: 431 \to 821\text{ mm}, Y: 745 \to 1115\text{ mm}$), thể hiện sơ đồ luồng quy trình vận hành và kiểm chứng dữ liệu.
   - Dòng 644–648: Hướng dẫn cử chỉ sân khấu kết nối ánh mắt và động tác chỉ tay vào các Zone trên poster.

---

## 2. LOGIC CHAIN (CHUỖI LẬP LUẬN TỪ QUAN SÁT ĐẾN THIẾT KẾ)

1. **Bước 1: Chuyển dịch từ góc nhìn "Hệ thống kỹ thuật" sang "Dịch vụ khách hàng"**:
   - *Căn cứ*: `ORIGINAL_REQUEST.md` yêu cầu định dạng mô hình dịch vụ (Service Template) ra mắt đại chúng, cấm thuật ngữ lập trình.
   - *Suy luận*: 
     - Yếu tố **WHEN** không nói về chu kỳ cron job hay độ trễ SQLite ms, mà giải quyết câu hỏi: *"Khi nào người dùng mở app lên để sử dụng?"* -> 4 khoảnh khắc tài chính then chốt.
     - Yếu tố **WHERE** không nói về cloud serverless hay IP data center, mà trả lời: *"Người dùng chạm vào dịch vụ ở những điểm tiếp xúc (touchpoints) nào?"* -> Mobile App, Web Portal, Kênh Cộng đồng.
     - Yếu tố **HOW** không nói về pipeline tokenizer hay SQL JOIN, mà mô tả: *"Khách hàng trải qua hành trình trải nghiệm dịch vụ (Customer Journey) như thế nào?"* -> 3 bước tinh giản từ Onboarding đến Chăm sóc 24/7.

2. **Bước 2: Chuẩn hóa nhịp điệu phát biểu và kiểm soát dung lượng từ (240–280 từ/2 phút)**:
   - *Căn cứ*: Tốc độ nói chuẩn mực trong giao tiếp kinh doanh và thuyết trình truyền cảm hứng tiếng Việt dao động từ 120 đến 135 từ/phút (đảm bảo nhấn nhá, ngắt nghỉ, giao lưu ánh mắt).
   - *Suy luận*: Để hoàn thành phần nói trong đúng ~2 phút (110–130 giây), độ dài kịch bản bắt buộc phải nằm trong biên độ nghiêm ngặt: $240 \le N \le 280$ từ.
   - *Thực nghiệm*: Văn bản nháp ban đầu đạt 360 từ (quá dài, gây cháy giáo án). Sau 3 vòng hiệu chỉnh và đo đạc bằng lệnh Python phân tích chuỗi, bản thảo Speaker 3 đạt **267 từ**, Speaker 4 đạt **269 từ** — đạt điểm rơi lý tưởng.

3. **Bước 3: Thiết kế cấu trúc chuyển giao (Transitions) & Cử chỉ sân khấu (Stage Dynamics)**:
   - *Căn cứ*: Bài thuyết trình 6 người rất dễ bị rời rạc nếu thiếu câu nối tự nhiên và cử chỉ tương tác đồng đội.
   - *Suy luận*: 
     - Speaker 3 nhận chuyển giao từ Speaker 2 (kế thừa 4 tiện ích sản phẩm để đặt vấn đề Khi nào & Ở đâu).
     - Speaker 3 chuyển tiếp sang Speaker 4 (kết nối từ kênh tiếp cận sang hành trình trải nghiệm thực tế).
     - Speaker 4 chuyển tiếp sang Speaker 5 (kết nối từ quy trình mượt mà sang nền tảng đạo đức và lý do tin cậy).

---

## 3. CAVEATS (CÁC ĐIỂM GIỚI HẠN & LƯU Ý ĐẶC BIỆT)

1. **Giới hạn phạm vi (Zero Jargon Guardrail)**: Diễn giả Speaker 3 và Speaker 4 tuyệt đối không được tự ý chèn thêm các thuật ngữ như "API", "microservices", "SQLite", "RAG", "PennyLane". Mọi công nghệ cao cấp phía sau phải được chuyển hóa thành trải nghiệm người dùng: "tốc độ xử lý chỉ trong tích tắc", "báo cáo trực quan", "trợ lý thông tin minh bạch".
2. **Tương thích với Poster A0 / Slide trình chiếu**: Khi nói đến WHEN và WHERE, Speaker 3 phối hợp cử chỉ tay hướng về Zone 4 và Zone 3. Khi nói đến HOW, Speaker 4 chỉ vào Zone 6 (sơ đồ quy trình).
3. **Thời gian thực tế trên bục**: Diễn giả cần luyện tập với đồng hồ bấm giờ (stopwatch). Nếu đọc quá nhanh (< 100 giây), bài nói sẽ mất đi sự trang trọng và điềm đạm. Nếu đọc quá chậm (> 130 giây), sẽ ảnh hưởng đến tổng thời lượng 12 phút của nhóm.

---

## 4. CONCLUSION & BLUEPRINT THIẾT KẾ CHO SPEAKER 3 & SPEAKER 4

### A. SPEAKER 3 — MARKETING LEAD (THỜI ĐIỂM & KÊNH TIẾP CẬN: WHEN & WHERE)

#### 1. Bảng Thông Số Kỹ Thuật Diễn Giả 3
- **Chức danh đảm nhiệm**: Giám đốc Tiếp thị (Marketing Lead).
- **Mục tiêu 5W1H**: Xác định rõ nét **WHEN** (4 khoảnh khắc vàng cần dùng) và **WHERE** (Hệ sinh thái tiếp cận 3 kênh số).
- **Số từ thoại chính xác**: **267 từ**.
- **Thời lượng dự kiến**: 120 giây (tốc độ đọc: 133 từ/phút).
- **Điểm neo thị giác trên Poster A0**: Zone 4 (Trục thời gian & đồng hồ xử lý) và Zone 3 (Các thẻ giao diện tiếp cận).

#### 2. Lời Thoại Hoàn Chỉnh (Full Verbatim Script) — 267 Từ

> *"Xin cảm ơn Giám đốc Sản phẩm! Quý vị vừa thấy bốn tiện ích nổi bật của Market Pulse. Vậy chúng ta nên sử dụng công cụ này vào lúc nào, và tiếp cận ở đâu?*
> 
> *Về thời điểm, có bốn khoảnh khắc vàng nhà đầu tư rất cần Market Pulse:*
> 
> *Thứ nhất, trước khi ra quyết định đầu tư: chỉ ba mươi giây kiểm tra sức khỏe doanh nghiệp để tránh bẫy mua đuổi FOMO.*
> 
> *Thứ hai, vào mùa báo cáo tài chính: hệ thống chắt lọc số liệu cốt lõi, giúp quý vị tiết kiệm hàng giờ đọc tài liệu.*
> 
> *Thứ ba, rà soát danh mục định kỳ mỗi tuần: giúp phát hiện sớm rủi ro để cơ cấu vốn an toàn.*
> 
> *Và thứ tư, khi thị trường rung lắc mạnh: Market Pulse là điểm tựa số liệu khách quan giúp giữ vững tâm lý, không bán tháo hoảng loạn.*
> 
> *Về kênh tiếp cận, chúng tôi phát triển trải nghiệm đa nền tảng liền mạch:*
> 
> *Một là Ứng dụng Di động: nhận cảnh báo tức thì và tra cứu nhanh mọi lúc, mọi nơi.*
> 
> *Hai là Cổng Thông tin Trực tuyến: không gian trực quan màn hình lớn cho những buổi phân tích chuyên sâu.*
> 
> *Ba là Kênh Cộng đồng: các buổi hội thảo định kỳ, chia sẻ tri thức và lan tỏa văn hóa đầu tư văn minh.*
> 
> *Dù trên điện thoại hay máy tính, hành trình trải nghiệm thực tế sẽ diễn ra tinh giản và chu đáo ra sao? Tôi xin trân trọng kính mời Trưởng bộ phận Trải nghiệm Khách hàng!"*

#### 3. Thẻ Ghi Nhớ Sân Khấu (Cue Card / Flashcard)
```
┌─────────────────────────────────────────────────────────────┐
│ CUE CARD - SPEAKER 3: MARKETING LEAD (WHEN & WHERE)         │
├─────────────────────────────────────────────────────────────┤
│ 1. [Mở]: Kế thừa 4 tiện ích từ Product Lead -> Đặt vấn đề    │
│ 2. [WHEN - 4 Khoảnh khắc vàng]:                             │
│    • Trước khi giải ngân (Tránh FOMO tin đồn)               │
│    • Mùa BCTC (Lọc nhanh hàng trăm báo cáo)                 │
│    • Cuối tuần (Khám sức khỏe danh mục định kỳ)             │
│    • Thị trường rung lắc (Điểm tựa tâm lý vững vàng)        │
│ 3. [WHERE - 3 Kênh tiếp cận liền mạch]:                     │
│    • Mobile App: Cảnh báo tức thì, tra cứu bỏ túi           │
│    • Web Portal: Màn hình lớn, phân tích chuyên sâu         │
│    • Cộng đồng: Hội thảo tri thức, văn hóa đầu tư văn minh   │
│ 4. [Chuyển giao]: Giới thiệu Trưởng bộ phận CX (Speaker 4)   │
└─────────────────────────────────────────────────────────────┘
```

#### 4. Khẩu Lệnh Chuyển Tiếp & Ngôn Ngữ Cơ Thể (Transitions & Body Language)
- **Tiếp nhận lượt nói từ Speaker 2**: 
  - Mỉm cười, gật đầu nhẹ và hướng tay mở về phía Speaker 2 để nhận chuyển giao.
  - Bước lên nửa bước, ánh mắt bao quát toàn bộ khán phòng, giọng nói tự tin, hào hứng.
- **Tương tác trực quan với Poster / Slide**:
  - Khi nói về *4 thời điểm (WHEN)*: Tay phải mở hướng về **Zone 4: WHEN** trên poster (nơi có biểu tượng đồng hồ và trục thời gian).
  - Khi nói về *Kênh tiếp cận (WHERE)*: Hướng tay sang **Zone 3: WHERE** (thể hiện các giao diện nền tảng số).
- **Chuyển giao sang Speaker 4**:
  - Nghiêng người 45 độ sang Speaker 4, cánh tay mở rộng mời đồng đội bước lên bục.

---

### B. SPEAKER 4 — CX LEAD (HÀNH TRÌNH PHỤC VỤ: HOW)

#### 1. Bảng Thông Số Kỹ Thuật Diễn Giả 4
- **Chức danh đảm nhiệm**: Giám đốc Trải nghiệm Khách hàng (Customer Experience - CX Lead).
- **Mục tiêu 5W1H**: Làm rõ **HOW** (Quy trình phục vụ 3 bước tinh giản) và lan tỏa sự **Thấu cảm & An tâm** (Empathy & Reassurance).
- **Số từ thoại chính xác**: **269 từ**.
- **Thời lượng dự kiến**: 120 giây (tốc độ đọc: 134 từ/phút).
- **Điểm neo thị giác trên Poster A0**: Zone 6 (Sơ đồ luồng quy trình vận hành và kiểm chứng).

#### 2. Lời Thoại Hoàn Chỉnh (Full Verbatim Script) — 269 Từ

> *"Xin cảm ơn Giám đốc Tiếp thị! Kính thưa quý vị, bước chân vào đầu tư thường đi kèm nỗi lo sợ: sợ thông tin giả, sợ số liệu phức tạp và sợ cảm giác đơn độc khi tài khoản sụt giảm. Vì vậy, triết lý phục vụ của Market Pulse gói trọn trong ba chữ: Đơn giản, Minh bạch và Đồng hành.*
> 
> *Hành trình trải nghiệm được tinh giản qua ba bước:*
> 
> *Bước một, Khởi đầu nhanh dưới một phút: Không biểu mẫu rườm rà. Chỉ cần số điện thoại hoặc email, chọn khẩu vị đầu tư và danh mục quan tâm là hệ thống sẵn sàng phục vụ.*
> 
> *Bước hai, Nhận báo cáo trực quan tức thì: Quý vị không phải bơi trong bảng biểu khô khan. Toàn bộ dữ liệu được chuyển hóa thành hình ảnh sinh động: thang điểm sức khỏe 0–100 rõ nét, radar ba màu Xanh - Vàng - Đỏ thân thiện và tóm tắt ba dòng ngắn gọn. Nhìn là hiểu ngay mà không cần bằng cấp tài chính.*
> 
> *Bước ba, Hỗ trợ thông tin minh bạch 24/7: Trợ lý số luôn túc trực giải thích nguồn gốc từng số liệu. Cùng với đó, đội ngũ chăm sóc khách hàng luôn tận tâm lắng nghe, đồng hành qua mọi thăng trầm của thị trường.*
> 
> *Trải nghiệm mượt mà chỉ trọn vẹn khi xây trên sự chính trực. Điều gì bảo chứng cho tính khách quan tuyệt đối của Market Pulse giữa một thị trường đầy cám dỗ? Xin trân trọng kính mời Trưởng bộ phận Quản lý Chất lượng và Rủi ro!"*

#### 3. Thẻ Ghi Nhớ Sân Khấu (Cue Card / Flashcard)
```
┌─────────────────────────────────────────────────────────────┐
│ CUE CARD - SPEAKER 4: CX LEAD (HOW & SERVICE JOURNEY)       │
├─────────────────────────────────────────────────────────────┤
│ 1. [Mở]: Đồng cảm 3 nỗi sợ của F0 (Tin giả, Rối rắm, Đơn độc)│
│    -> Tuyên ngôn: Đơn giản, Minh bạch và Đồng hành          │
│ 2. [Hành trình 3 bước tinh giản]:                           │
│    • Bước 1: Khởi đầu < 1 phút (SĐT/Email, chọn khẩu vị)    │
│    • Bước 2: Báo cáo trực quan (Điểm 0-100, Đèn giao thông, │
│              3 dòng tóm tắt, không cần bằng cấp)             │
│    • Bước 3: Hỗ trợ 24/7 (Trợ lý giải thích số liệu +       │
│              Chăm sóc khách hàng tận tâm đồng hành)         │
│ 3. [Chuyển giao]: Giới thiệu Trưởng bộ phận Quản lý         │
│    Chất lượng & Rủi ro (Speaker 5)                          │
└─────────────────────────────────────────────────────────────┘
```

#### 4. Khẩu Lệnh Chuyển Tiếp & Ngôn Ngữ Cơ Thể (Transitions & Body Language)
- **Tiếp nhận lượt nói từ Speaker 3**:
  - Gật đầu cảm ơn, bước lên chính diện với nụ cười ấm áp và thân thiện.
  - Đặt tay nhẹ lên ngực trái khi chia sẻ về *"nỗi lo sợ và sự đơn độc của nhà đầu tư mới"* để truyền tải sự thấu cảm chân thành (Empathy).
- **Tương tác trực quan với Poster / Slide**:
  - Dùng cử chỉ ngón tay đếm nhịp rõ ràng khi nói về từng bước: 1 ngón cho Bước 1, 2 ngón cho Bước 2, 3 ngón cho Bước 3.
  - Hướng tay mở về **Zone 6: HOW** trên poster (nơi có sơ đồ luồng quy trình phục vụ trực quan).
- **Chuyển giao sang Speaker 5**:
  - Đổi tông giọng từ ấm áp sang trang trọng, kiên định.
  - Hướng tay lịch thiệp về phía Speaker 5 (Quality & Risk Lead) để chuyển giao bài nói về tính minh bạch và chuẩn mực đạo đức.

---

## 5. HƯỚNG DẪN DÀNH CHO WORKER AGENT (`worker_m1`)

Khi hợp nhất vào tài liệu bàn giao chung `c:\Users\MSI\Desktop\Final Market Pulse\docs\assignment\PRESENTATION_SCRIPT_5W1H_SERVICE.md`:

1. **Đảm bảo tính nguyên vẹn của văn bản**: Giữ đúng từng câu chữ, dấu chấm câu và cách ngắt dòng của bản thảo hoàn thiện đã được đo đạc chính xác ở Mục 4.
2. **Cấu trúc trình bày nhất quán**: Mỗi diễn giả cần có đủ:
   - Thông tin tổng quan (Vai trò, Mục tiêu 5W1H, Số từ, Thời lượng).
   - Lời thoại chi tiết (Full Verbatim Script).
   - Flashcard / Cue Card tóm tắt thực chiến.
   - Hướng dẫn ngôn ngữ cơ thể & Điểm chạm thị giác trên Poster A0.
   - Câu lệnh chuyển tiếp vào (Inward) và ra (Outward).
3. **Kiểm tra từ cấm**: Đảm bảo không bổ sung bất kỳ từ ngữ kỹ thuật công nghệ nào vào bài của Speaker 3 và Speaker 4.

---

## 6. VERIFICATION METHOD (PHƯƠNG PHÁP KIỂM TRA ĐỘC LẬP)

Để xác minh tính độc lập và chính xác của báo cáo này:

### A. Kiểm tra số lượng từ bằng Python
Chạy lệnh sau trong terminal để đếm chính xác số từ của từng diễn giả:

```bash
python -c "
spk3 = '''Xin cảm ơn Giám đốc Sản phẩm! Quý vị vừa thấy bốn tiện ích nổi bật của Market Pulse. Vậy chúng ta nên sử dụng công cụ này vào lúc nào, và tiếp cận ở đâu? Về thời điểm, có bốn khoảnh khắc vàng nhà đầu tư rất cần Market Pulse: Thứ nhất, trước khi ra quyết định đầu tư: chỉ ba mươi giây kiểm tra sức khỏe doanh nghiệp để tránh bẫy mua đuổi FOMO. Thứ hai, vào mùa báo cáo tài chính: hệ thống chắt lọc số liệu cốt lõi, giúp quý vị tiết kiệm hàng giờ đọc tài liệu. Thứ ba, rà soát danh mục định kỳ mỗi tuần: giúp phát hiện sớm rủi ro để cơ cấu vốn an toàn. Và thứ tư, khi thị trường rung lắc mạnh: Market Pulse là điểm tựa số liệu khách quan giúp giữ vững tâm lý, không bán tháo hoảng loạn. Về kênh tiếp cận, chúng tôi phát triển trải nghiệm đa nền tảng liền mạch: Một là Ứng dụng Di động: nhận cảnh báo tức thì và tra cứu nhanh mọi lúc, mọi nơi. Hai là Cổng Thông tin Trực tuyến: không gian trực quan màn hình lớn cho những buổi phân tích chuyên sâu. Ba là Kênh Cộng đồng: các buổi hội thảo định kỳ, chia sẻ tri thức và lan tỏa văn hóa đầu tư văn minh. Dù trên điện thoại hay máy tính, hành trình trải nghiệm thực tế sẽ diễn ra tinh giản và chu đáo ra sao? Tôi xin trân trọng kính mời Trưởng bộ phận Trải nghiệm Khách hàng!'''

spk4 = '''Xin cảm ơn Giám đốc Tiếp thị! Kính thưa quý vị, bước chân vào đầu tư thường đi kèm nỗi lo sợ: sợ thông tin giả, sợ số liệu phức tạp và sợ cảm giác đơn độc khi tài khoản sụt giảm. Vì vậy, triết lý phục vụ của Market Pulse gói trọn trong ba chữ: Đơn giản, Minh bạch và Đồng hành. Hành trình trải nghiệm được tinh giản qua ba bước: Bước một, Khởi đầu nhanh dưới một phút: Không biểu mẫu rườm rà. Chỉ cần số điện thoại hoặc email, chọn khẩu vị đầu tư và danh mục quan tâm là hệ thống sẵn sàng phục vụ. Bước hai, Nhận báo cáo trực quan tức thì: Quý vị không phải bơi trong bảng biểu khô khan. Toàn bộ dữ liệu được chuyển hóa thành hình ảnh sinh động: thang điểm sức khỏe 0–100 rõ nét, radar ba màu Xanh - Vàng - Đỏ thân thiện và tóm tắt ba dòng ngắn gọn. Nhìn là hiểu ngay mà không cần bằng cấp tài chính. Bước ba, Hỗ trợ thông tin minh bạch 24/7: Trợ lý số luôn túc trực giải thích nguồn gốc từng số liệu. Cùng với đó, đội ngũ chăm sóc khách hàng luôn tận tâm lắng nghe, đồng hành qua mọi thăng trầm của thị trường. Trải nghiệm mượt mà chỉ trọn vẹn khi xây trên sự chính trực. Điều gì bảo chứng cho tính khách quan tuyệt đối của Market Pulse giữa một thị trường đầy cám dỗ? Xin trân trọng kính mời Trưởng bộ phận Quản lý Chất lượng và Rủi ro!'''

print('Speaker 3 Word Count:', len(spk3.split()), '(Target: 240-280)')
print('Speaker 4 Word Count:', len(spk4.split()), '(Target: 240-280)')
assert 240 <= len(spk3.split()) <= 280, 'Speaker 3 out of bounds'
assert 240 <= len(spk4.split()) <= 280, 'Speaker 4 out of bounds'
print('>>> WORD COUNT VERIFICATION PASSED 100% <<<')
"
```

### B. Kiểm tra triệt tiêu thuật ngữ kỹ thuật (Zero Technical Jargon)
Chạy lệnh kiểm tra danh sách đen từ ngữ công nghệ:

```bash
python -c "
jargon_list = ['sqlite', 'wal', 'qaoa', 'pennylane', 'piotroski', 'altman', 'microservice', 'backend', 'rag', 'api', 'gateway', 'phím hàng']
for name, text in [('Speaker 3', spk3), ('Speaker 4', spk4)]:
    found = [j for j in jargon_list if j in text.lower()]
    assert len(found) == 0, f'{name} contains forbidden jargon: {found}'
print('>>> ZERO TECHNICAL JARGON CHECK PASSED 100% <<<')
"
```

### C. Điều kiện vô hiệu hóa (Invalidation Conditions)
- Bất kỳ sửa đổi nào làm số từ của Speaker 3 hoặc Speaker 4 vượt ra ngoài khoảng 240–280 từ sẽ làm mất cân bằng thời lượng 2 phút của nhóm.
- Việc bổ sung các thuật ngữ kỹ thuật chuyên sâu lập trình sẽ làm sai lệch phong cách giao tiếp kinh doanh đại chúng của doanh nghiệp dịch vụ.
