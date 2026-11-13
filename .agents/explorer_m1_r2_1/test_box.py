# -*- coding: utf-8 -*-
import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Let's verify line lengths of the box part
box_lines = [
"┌────────────────────────────────┬───────────────────────────────┬──────────────────────────────┐",
"│ SÂN KHẤU CHÍNH (Rộng 7.0m)     │                               │                              │",
"│                                │     [ BỤC NÓI TIÊU ĐIỂM ]     │    [ ĐỘI HÌNH CÁNH CUNG MỞ ] │",
"│   [ GIÁ VẼ EASEL A0 ]          │    (Diễn giả đang phát biểu)  │      (Asymmetric Crescent)   │",
"│   Poster A0 (841 x 1189 mm)    │       (Tọa độ: X=0, Y=2.5m)   │                              │",
"│   (Góc xoay 35° hướng tâm)     │                ▲              │      [SP 1: CEO]             │",
"│   (Tọa độ: X=-2.2m, Y=3.5m)    │                │ Luân chuyển  │           [SP 2: PRODUCT]    │",
"│                                │                │ 1 bước 0.8m  │                [SP 3: MKT]   │",
"│              ▲                 │                │ dứt khoát    │                     [SP 4]   │",
"│              │                 │                ▼              │                       [SP 5] │",
"│              └─── Chạm 0.5s ───┼─────────────── [Lối về vị trí]┼─────────────────────── [SP 6]│",
"│                   Quay mắt lại │                               │   (5 Diễn giả lắng nghe      │",
"│                   BGK & Giữ 2.5s                               │    chủ động, ngực mở 15°)    │",
"└────────────────────────────────┴───────────────────────────────┴──────────────────────────────┘",
]

for i, l in enumerate(box_lines):
    print(f"Line {i:2d}: len={len(l)} | {l}")
