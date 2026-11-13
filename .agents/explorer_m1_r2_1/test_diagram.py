# -*- coding: utf-8 -*-
import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

col1_w = 31  # width inside col 1
col2_w = 31  # width inside col 2
col3_w = 31  # width inside col 3

def make_line(c1, c2, c3):
    return f"│ {c1:<{col1_w}} │ {c2:<{col2_w}} │ {c3:<{col3_w}} │"

border_top = f"┌{'─'*(col1_w+2)}┬{'─'*(col2_w+2)}┬{'─'*(col3_w+2)}┐"
border_mid = f"├{'─'*(col1_w+2)}┼{'─'*(col2_w+2)}┼{'─'*(col3_w+2)}┤"
border_bot = f"└{'─'*(col1_w+2)}┴{'─'*(col2_w+2)}┴{'─'*(col3_w+2)}┘"

lines = [
    border_top,
    make_line("SÂN KHẤU CHÍNH (Rộng 7.0m)", "KHU VỰC TIÊU ĐIỂM (Focus)", "KHU VỰC ĐỒNG ĐỘI (Backing)"),
    border_mid,
    make_line("[ GIÁ VẼ EASEL POSTER A0 ]", "[ BỤC NÓI TIÊU ĐIỂM ]", "[ ĐỘI HÌNH CÁNH CUNG MỞ ]"),
    make_line("Poster A0: 841 x 1189 mm", "(Diễn giả đang phát biểu)", "(Asymmetric Open Crescent)"),
    make_line("Góc xoay: 35° hướng tâm", "Tọa độ: X = 0.0m, Y = 2.5m", "Độ cong: Cung lõm mở 20°"),
    make_line("Tọa độ: X = -2.2m, Y = 3.5m", "Tầm nhìn: Trực diện 100%", "Tọa độ: X=+1.2m..+3.4m"),
    make_line("Chiều cao tâm: 1.5m (ngang mắt)", "", ""),
    make_line("--- ĐẶC TÍNH THỊ GIÁC ---", "--- KỶ LUẬT PHÁT BIỂU ---", "--- VỊ TRÍ 5 THÀNH VIÊN ---"),
    make_line("• Tầm nhìn 100% không vật cản", "• Kỷ luật 'Touch, Turn, Talk':", "  [SP 1: CEO]"),
    make_line("• BGK nhìn rõ mọi phân vùng", "  - 0.5s: Chạm tay neo poster", "     [SP 2: PRODUCT]"),
    make_line("• Không bị che bởi cơ thể", "  - 2.5s: Quay mắt BGK & Giữ", "        [SP 3: MARKETING]"),
    make_line("• Góc nhìn tối ưu cho toàn hội", "• Ngực mở 45° hướng khán giả", "           [SP 4: CX]"),
    make_line("  trường và 6 thành viên", "• Ánh mắt: 60% BGK, 30% Phòng", "              [SP 5: RISK]"),
    make_line("", "• Luân chuyển: Bước tới 0.8m", "                 [SP 6: PR]"),
    make_line("[ĐIỂM TỰA DỮ LIỆU & BẰNG CHỨNG]", "[LÃNH ĐẠO THUYẾT PHỤC TRỰC DIỆN]", "[HỖ TRỢ ĐỒNG ĐỘI & TÔN TRỌNG]"),
    border_bot
]

diagram_header = """
                                  [ BAN GIÁM KHẢO / HỘI ĐỒNG ]
                                         (Tọa độ: Y = 0.0m)

                                      ▲          ▲          ▲
                     Tầm nhìn 100%   ╱           │           ╲   Tầm nhìn 100%
                     thông suốt     ╱       Ánh mắt 60%       ╲  thông suốt
                     không vật cản ╱       trực diện           ╲ không vật cản
                                  ╱              │              ╲
                                 ▲               ▼               ▲
"""

diagram_footer = """
              ◄── Stage-Right (Bên Phải Diễn Giả)              Stage-Left (Bên Trái Diễn Giả) ──►
              (Khán giả nhìn lên: Bên Trái Sân Khấu)           (Khán giả nhìn lên: Bên Phải Sân Khấu)
"""

full_diagram = diagram_header.strip('\n') + "\n" + "\n".join(lines) + "\n" + diagram_footer.strip('\n')
print(full_diagram)
print(f"Diagram max width: {max(len(l) for l in full_diagram.splitlines())}")
