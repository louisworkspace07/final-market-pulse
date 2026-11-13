import re

cards_text = """
┌──────────────────────────────────────────────────────────────────────────────┐
│ [CUE CARD 1] — CEO: KHỞI XƯỚNG & SỨ MỆNH (WHO & BỐI CẢNH)                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ • MỞ MÀN (OPENING CUE): Cả đội cúi chào 15° (1s) -> Bước lên bục tiêu điểm:   │
│   "Kính thưa quý vị và các bạn trẻ!"                                         │
│ • ĐIỂM NEO POSTER: Đứng trung tâm, chỉ vào Khối Lõi Trung Tâm (Central Hub). │
│ • BULLET 1 (0:00-0:30): 13 triệu tài khoản; nỗi đau tin đồn & bão thua lỗ.   │
│ • BULLET 2 (0:30-1:00): Trăn trở sáng lập FinTuition; giải cứu bạn bè khỏi   │
│   ma trận báo cáo tài chính đánh đố.                                         │
│ • BULLET 3 (1:00-1:30): "Thông dịch viên dữ liệu trung thực" — Đập tan 4     │
│   nỗi đau: lệch pha, nhiễu loạn, bầy đàn, tin đồn ác ý.                      │
│ • BULLET 4 (1:30-2:00): Sứ mệnh trao quyền tự chủ bằng dữ liệu minh bạch.    │
│ ──────────────────────────────────────────────────────────────────────────── │
│ ➔ CÂU BÀN GIAO: [Ý niệm]: Sứ mệnh minh bạch -> Hiện thực hóa bằng dịch vụ.   │
│   [Khẩu lệnh & Cử chỉ]: Mở tay sang phải ➔ "Xin mời Giám đốc Sản phẩm!"      │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ [CUE CARD 2] — PRODUCT LEAD: DỊCH VỤ CỐT LÕI (WHAT & 4 TIỆN ÍCH)             │
├──────────────────────────────────────────────────────────────────────────────┤
│ • VÀO BÀI (INCOMING HOOK): Gật đầu mỉm cười, đáp: "Xin cảm ơn CEO!"          │
│ • ĐIỂM NEO POSTER: Đứng góc Trên-Trái, chỉ vào Zone 1 & Thước đo ba màu.     │
│ • BULLET 1 (0:00-0:25): Market Pulse — Ẩn dụ "Bác sĩ tài chính" gia đình.   │
│ • BULLET 2 (0:25-1:00): Tiện ích 1 & 2: Điểm sức khỏe 0-100 (Khỏe >70,       │
│   Nguy hiểm <40) + Radar Đèn Giao Thông rung chuông cảnh báo rủi ro.         │
│ • BULLET 3 (1:00-1:35): Tiện ích 3 & 4: Trợ lý hỏi đáp có trích dẫn BCTC gốc │
│   + Bảng so sánh vị thế cùng ngành đặt lên bàn cân năng lực.                 │
│ • BULLET 4 (1:35-2:00): Mang lại sự an tâm tuyệt đối cho danh mục đầu tư.   │
│ ──────────────────────────────────────────────────────────────────────────── │
│ ➔ CÂU BÀN GIAO: [Ý niệm]: 4 tiện ích an tâm -> Khi nào & Ở đâu thuận tiện?    │
│   [Khẩu lệnh & Cử chỉ]: Mở tay sang phải ➔ "Xin mời Giám đốc Tiếp thị!"      │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ [CUE CARD 3] — MARKETING LEAD: THỜI ĐIỂM & KÊNH TIẾP CẬN (WHEN & WHERE)      │
├──────────────────────────────────────────────────────────────────────────────┤
│ • VÀO BÀI (INCOMING HOOK): Gật đầu mỉm cười: "Xin cảm ơn Giám đốc Sản phẩm!" │
│ • ĐIỂM NEO POSTER: Đứng giữa-phải, chỉ vào Zone 4 (WHEN) & Zone 3 (WHERE).   │
│ • BULLET 1 (0:00-0:30): Kế thừa 4 tiện ích -> Đặt vấn đề Khi nào & Ở đâu?    │
│ • BULLET 2 (0:30-1:00): WHEN — 4 khoảnh khắc vàng: Trước khi xuống tiền      │
│   (chống FOMO), Mùa BCTC (lọc nhanh), Rà soát cuối tuần, Thị trường rung lắc.│
│ • BULLET 3 (1:00-1:35): WHERE — 3 kênh tiếp cận: App di động (bỏ túi),       │
│   Web Portal (màn hình lớn), Kênh cộng đồng (hội thảo tri thức văn minh).    │
│ • BULLET 4 (1:35-2:00): Trải nghiệm đa nền tảng liền mạch mọi lúc mọi nơi.  │
│ ──────────────────────────────────────────────────────────────────────────── │
│ ➔ CÂU BÀN GIAO: [Ý niệm]: Đa nền tảng số -> Hành trình thực tế diễn ra ra sao?│
│   [Khẩu lệnh & Cử chỉ]: Mở tay mời ➔ "Kính mời Trưởng BP Trải nghiệm KH!"    │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ [CUE CARD 4] — CX LEAD: HÀNH TRÌNH PHỤC VỤ (HOW & 3 BƯỚC TINH GIẢN)          │
├──────────────────────────────────────────────────────────────────────────────┤
│ • VÀO BÀI (INCOMING HOOK): Gật đầu mỉm cười: "Xin cảm ơn Giám đốc Tiếp thị!" │
│ • ĐIỂM NEO POSTER: Đứng góc Dưới-Phải, chỉ vào sơ đồ luồng Zone 6 (HOW).     │
│ • BULLET 1 (0:00-0:25): Thấu cảm 3 nỗi sợ F0 (tin giả, rối rắm, đơn độc) ->  │
│   Tuyên ngôn: Đơn giản, Minh bạch và Đồng hành.                              │
│ • BULLET 2 (0:25-1:00): BƯỚC 1 & 2: Khởi đầu siêu tốc < 1 phút (chọn khẩu vị)│
│   -> Nhận báo cáo trực quan tức thì (thang 0-100, đèn 3 màu, 3 dòng tóm tắt).│
│ • BULLET 3 (1:00-1:35): BƯỚC 3: Hỗ trợ thông tin 24/7 (Trợ lý số giải thích   │
│   dữ liệu + Đội ngũ chăm sóc khách hàng tận tâm đồng hành).                  │
│ • BULLET 4 (1:35-2:00): Trải nghiệm mượt mà phải xây trên nền tảng chính trực.│
│ ──────────────────────────────────────────────────────────────────────────── │
│ ➔ CÂU BÀN GIAO: [Ý niệm]: Trải nghiệm mượt mà -> Bảo chứng tính khách quan?  │
│   [Khẩu lệnh & Cử chỉ]: Mở tay mời ➔ "Kính mời Trưởng BP Quản lý Rủi ro!"   │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ [CUE CARD 5] — QUALITY & RISK LEAD: LÝ DO TIN CẬY (WHY & TRỤ CỘT NIỀM TIN)   │
├──────────────────────────────────────────────────────────────────────────────┤
│ • VÀO BÀI (INCOMING HOOK): Gật đầu: "Xin cảm ơn Trưởng BP Trải nghiệm KH!"   │
│ • ĐIỂM NEO POSTER: Đứng giữa-trái, chỉ vào Biểu tượng Khiên Liêm Chính.      │
│ • BULLET 1 (0:00-0:25): Đặt câu hỏi bản lề: "Tại sao tôi nên tin tưởng?"     │
│ • BULLET 2 (0:25-1:00): TRỤ CỘT 1 & 2: Khách quan độc lập (0% hoa hồng môi   │
│   giới) + Kiên quyết nói KHÔNG với 'phím hàng' (Điều 71 Luật Chứng khoán).   │
│ • BULLET 3 (1:00-1:35): TRỤ CỘT 3 & 4: Bảo mật thông tin tối thượng (Nghị    │
│   định 13 Chính phủ) + Cảnh báo rủi ro minh bạch (chỉ rõ Đèn Đỏ, không lãi ảo)│
│ • BULLET 4 (1:35-2:00): Bảo chứng sự an tâm tuyệt đối cho vốn của nhà đầu tư.│
│ ──────────────────────────────────────────────────────────────────────────── │
│ ➔ CÂU BÀN GIAO: [Ý niệm]: An tâm bảo chứng -> Lan tỏa giá trị đến cộng đồng.  │
│   [Khẩu lệnh & Cử chỉ]: Mở tay mời ➔ "Trân trọng giới thiệu Trưởng phòng PR!"│
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ [CUE CARD 6] — PR & COMMS LEAD: TẦM NHÌN, ƯU ĐÃI & CHỐT BÀI (VISION & CLOSE)  │
├──────────────────────────────────────────────────────────────────────────────┤
│ • VÀO BÀI (INCOMING HOOK): Gật đầu: "Xin cảm ơn Trưởng phòng Quản lý Rủi ro!"│
│ • ĐIỂM NEO POSTER: Đứng góc Dưới-Phải / Chân trang, chỉ vào Khung Mã QR.     │
│ • BULLET 1 (0:00-0:30): Tầm nhìn xã hội: Kiến tạo nền "Văn minh tài chính"   │
│   cho người Việt trẻ — Kỹ năng sinh tồn thiết yếu, bài trừ tư duy cờ bạc.    │
│ • BULLET 2 (0:30-1:05): Ưu đãi cộng đồng: Công bố "Gói Trải Nghiệm 0 Đồng"    │
│   cho sinh viên & F0 — Miễn phí 4 tiện ích cốt lõi & dữ liệu thực nghiệm.    │
│ • BULLET 3 (1:05-1:30): Lời tri ân chân thành tới Ban giám khảo & Hội trường. │
│ • BULLET 4 (1:30-2:00): CTA: Quét mã QR trải nghiệm -> Mời cả đội bước lên   │
│   hàng ngang chuẩn bị nghi thức cúi chào 15 độ đồng bộ.                      │
│ ──────────────────────────────────────────────────────────────────────────── │
│ ➔ LỜI TUYÊN BỐ KẾT THÚC: [Ý niệm]: Hướng mắt poster quét QR -> Mở phiên Q&A.  │
│   [Khẩu lệnh & Cử chỉ]: Chỉ tay QR 3s ➔ "Sẵn sàng hỏi đáp. Xin cảm ơn!"      │
└──────────────────────────────────────────────────────────────────────────────┘
"""

cards = re.findall(r'(\[CUE CARD \d+\].*?)(?=(?:\[CUE CARD \d+\]|$))', cards_text, re.DOTALL)
print(f"Total Cue Cards parsed: {len(cards)}")

for i, card in enumerate(cards, 1):
    header = card.strip().split('\n')[0]
    bullets = re.findall(r'│\s*•\s*(BULLET\s*\d+.*?)(?=(?:│\s*•|│\s*───|│\s*➔))', card, re.DOTALL)
    neo = re.findall(r'│\s*•\s*ĐIỂM NEO.*', card)
    handover = re.findall(r'│\s*➔\s*(?:CÂU BÀN GIAO|LỜI TUYÊN BỐ).*', card)
    hook = re.findall(r'│\s*•\s*(?:VÀO BÀI|INCOMING HOOK|MỞ MÀN).*', card)
    print(f"Card {i}: Bullets={len(bullets)}, Neo={len(neo)>0}, Handover={len(handover)>0}, Hook={len(hook)>0}")
