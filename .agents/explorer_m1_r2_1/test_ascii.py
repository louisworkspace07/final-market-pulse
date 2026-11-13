# -*- coding: utf-8 -*-
import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

diagram = """
                                  [ BAN GIÁM KHẢO / HỘI ĐỒNG ]
                                         (Tọa độ: Y = 0.0m)

                                      ▲          ▲          ▲
                     Tầm nhìn 100%   ╱           │           ╲   Tầm nhìn 100%
                     thông suốt     ╱       Ánh mắt 60%       ╲  thông suốt
                                   ╱             │             ╲
                                  ╱              ▼              ╲
┌────────────────────────────────┼───────────────────────────────┼──────────────────────────────┐
│ SÂN KHẤU CHÍNH (Rộng 7.0m)     │                               │                              │
│                                │     [ BỤC NÓI TIÊU ĐIỂM ]     │    [ ĐỘI HÌNH CÁNH CUNG MỞ ] │
│   [ GIÁ VẼ EASEL A0 ]          │    (Diễn giả đang phát biểu)  │      (Asymmetric Crescent)   │
│   Poster A0 (841 x 1189 mm)    │         (X = 0, Y = 2.5m)     │                              │
│   (Góc xoay 35° hướng tâm)    │                ▲              │      [SP 1: CEO]             │
│   (X = -2.2m, Y = 3.5m)        │                │ Luân chuyển  │           [SP 2: PRODUCT]    │
│                                │                │ 1 bước 0.8m  │                [SP 3: MKT]   │
│              ▲                 │                │ dứt khoát    │                     [SP 4]   │
│              │                 │                ▼              │                       [SP 5] │
│              └─── Chạm 0.5s ───┴─────────────── [Lối về vị trí]┴──────────────────────── [SP 6]│
│                   Quay mắt lại BGK & Giữ 2.5s                  │   (5 Diễn giả lắng nghe     │
│                   (Kỷ luật "Touch, Turn, Talk")                 │    chủ động, ngực mở 15°)    │
└────────────────────────────────────────────────────────────────┴──────────────────────────────┘
              ◄── Stage-Right (Bên Phải Diễn Giả)              Stage-Left (Bên Trái Diễn Giả) ──►
              (Khán giả nhìn lên: Bên Trái Sân Khấu)           (Khán giả nhìn lên: Bên Phải)
"""

print(diagram)
lines = diagram.strip().split('\n')
print("Total lines:", len(lines))
print("Max line width:", max(len(l) for l in lines))
