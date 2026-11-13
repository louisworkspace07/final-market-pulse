import re

card2_test = """
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
│   [Khẩu lệnh & Cử chỉ]: Mở tay sang phải -> "Xin mời Giám đốc Tiếp thị!"       │
└──────────────────────────────────────────────────────────────────────────────┘
"""

bullets = re.findall(r'│\s*•\s*(BULLET\s*\d+.*?)(?=(?:│\s*•|│\s*───|│\s*➔))', card2_test, re.DOTALL)
neo = re.findall(r'│\s*•\s*ĐIỂM NEO.*', card2_test)
handover = re.findall(r'│\s*➔\s*(?:CÂU BÀN GIAO|LỜI TUYÊN BỐ).*', card2_test)
hook = re.findall(r'│\s*•\s*(?:VÀO BÀI|INCOMING HOOK).*', card2_test)

print("Bullets:", len(bullets))
print("Neo:", len(neo) > 0)
print("Handover:", len(handover) > 0)
print("Hook:", len(hook) > 0)
