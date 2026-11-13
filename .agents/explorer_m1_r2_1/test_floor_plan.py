# -*- coding: utf-8 -*-
import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

floor_plan = """
                                  [ BAN GIÁM KHẢO / HỘI ĐỒNG ]
                                         (Tọa độ: Y = 0.0m)

                                      ▲          ▲          ▲
                     Tầm nhìn 100%   ╱           │           ╲   Tầm nhìn 100%
                     thông suốt     ╱       Ánh mắt 60%       ╲  thông suốt
                     không vật cản ╱         trực diện         ╲ không vật cản
                                  ╱              │              ╲
┌────────────────────────────────┼───────────────┼───────────────┼──────────────────────────────┐
│ SÂN KHẤU CHÍNH (7.0m x 4.5m)   │               │               │                              │
│                                ▼               ▼               ▼                              │
│   [ GIÁ VẼ EASEL A0 ]                [ BỤC NÓI TIÊU ĐIỂM ]             [ ĐỘI HÌNH CÁNH CUNG MỞ ]      │
│   Poster A0 (841 x 1189 mm)          (Diễn giả đang nói)               (Asymmetric Open Crescent)     │
│   Xoay góc 35° hướng tâm             (Tọa độ: X=0, Y=2.5m)                                            │
│   (Tọa độ: X=-2.2m, Y=3.5m)                    │                                                      │
│   Chiều cao tâm: 1.5m (ngang mắt)              │ Bước lên 0.8m                                        │
│                                                ▲                                                      │
│           ▲                                    │ (Luân chuyển)        [SP 1: CEO] (Mở góc 20°)        │
│           │                                    ▼                           [SP 2: PRODUCT]            │
│           └─── Bàn tay mở neo 0.5s ────── [Điểm chuyển giao]                    [SP 3: MARKETING]     │
│                Quay đầu nhìn BGK & Giữ 2.5s                                          [SP 4: CX]       │
│                (Kỷ luật "Touch, Turn, Talk")                                      [SP 5: RISK]        │
│                Thân người mở 45° hướng BGK                                           [SP 6: PR]       │
│                                                                                                       │
│   ◄── 100% TẦM NHÌN TRỰC DIỆN POSTER ──►             ◄── 100% TẦM NHÌN TRỰC DIỆN 6 DIỄN GIẢ ──►       │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
    ◄── STAGE-RIGHT (Bên Phải Diễn Giả)                               STAGE-LEFT (Bên Trái Diễn Giả) ──►
    (Khán giả nhìn lên: Bên Trái Sân Khấu)                            (Khán giả nhìn lên: Bên Phải)
"""

lines = floor_plan.strip('\n').split('\n')
print(floor_plan)
print(f"Total lines: {len(lines)}")
print(f"Max line width: {max(len(l) for l in lines)}")
for i, l in enumerate(lines):
    if l.startswith("┌") or l.startswith("│") or l.startswith("└"):
        print(f"Line {i:2d} (len={len(l):3d}): {l}")
