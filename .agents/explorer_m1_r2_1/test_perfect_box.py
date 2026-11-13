# -*- coding: utf-8 -*-
import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

TOTAL_INNER = 104

def pad_line(content):
    spaces = TOTAL_INNER - len(content)
    if spaces < 0:
        raise ValueError(f"Content too long ({len(content)}): {content}")
    return f"│ {content}{' ' * (spaces - 1)}│"

top_border = f"┌{'─' * TOTAL_INNER}┐"
bot_border = f"└{'─' * TOTAL_INNER}┘"

raw_inner_lines = [
    "SÂN KHẤU CHÍNH (Kích thước: Rộng 7.0m × Sâu 4.5m)",
    " ",
    "   [ GIÁ VẼ EASEL A0 ]                [ BỤC NÓI TIÊU ĐIỂM ]             [ ĐỘI HÌNH CÁNH CUNG MỞ ]",
    "   Poster A0 (841 x 1189 mm)          (Diễn giả đang phát biểu)         (Asymmetric Open Crescent)",
    "   Xoay góc 35° hướng tâm             (Tọa độ: X = 0.0m, Y = 2.5m)                                ",
    "   (Tọa độ: X = -2.2m, Y = 3.5m)                 ▲                                                ",
    "   Chiều cao tâm: 1.5m (ngang mắt)               │ Luân chuyển 0.8m        [SP 1: CEO] (Góc 20°)  ",
    "                                                 │ bước dứt khoát               [SP 2: PRODUCT]   ",
    "           ▲                                     ▼                                   [SP 3: MKT]  ",
    "           │                                [Điểm chuyển giao]                            [SP 4]  ",
    "           └─── Bàn tay mở neo 0.5s ─────────────┘                                           [SP 5]",
    "                Quay đầu nhìn BGK & Giữ 2.5s                                                  [SP 6]",
    "                (Kỷ luật \"Touch, Turn, Talk\")                                (5 Diễn giả lắng nghe",
    "                Ngực mở 45° hướng Ban Giám Khảo                                 chủ động, ngực mở)",
    " ",
    "   ◄── 100% TẦM NHÌN TRỰC DIỆN POSTER ──►             ◄── 100% TẦM NHÌN TRỰC DIỆN 6 DIỄN GIẢ ──►"
]

formatted_box = [top_border]
for line in raw_inner_lines:
    formatted_box.append(pad_line(line))
formatted_box.append(bot_border)

diagram_header = """
                                      [ BAN GIÁM KHẢO / HỘI ĐỒNG ]
                                             (Tọa độ: Y = 0.0m)

                                          ▲          ▲          ▲
                         Tầm nhìn 100%   ╱           │           ╲   Tầm nhìn 100%
                         thông suốt     ╱       Ánh mắt 60%       ╲  thông suốt
                         không vật cản ╱         trực diện         ╲ không vật cản
                                      ╱              │              ╲
                                     ▼               ▼               ▼
"""

diagram_footer = """
        ◄── STAGE-RIGHT (Bên Phải Diễn Giả)                               STAGE-LEFT (Bên Trái Diễn Giả) ──►
        (Khán giả nhìn lên: Bên Trái Sân Khấu)                            (Khán giả nhìn lên: Bên Phải)
"""

full_diagram = diagram_header.strip('\n') + "\n" + "\n".join(formatted_box) + "\n" + diagram_footer.strip('\n')
print(full_diagram)
print(f"Max line width: {max(len(l) for l in full_diagram.splitlines())}")

# verify box lines
for idx, bl in enumerate(formatted_box):
    if len(bl) != TOTAL_INNER + 2:
        print(f"Mismatch line {idx}: len={len(bl)}")
print("All box lines verified uniform length:", len(formatted_box[0]))
