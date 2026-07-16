# -*- coding: utf-8 -*-
"""Quét từ cấm pháp lý (khuyến nghị mua/bán) trên toàn sản phẩm Market Pulse.

Chạy:  python scripts/check_legal_wording.py            # quét UI tĩnh + prompt nguồn
       python scripts/check_legal_wording.py out.json   # quét thêm file output AI đã lưu
Exit code 1 nếu có vi phạm — dùng được trong CI/pre-commit.
"""
import json
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))
from modules.common.legal import check_text, check_payload  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
STATIC = os.path.join(ROOT, "gateway", "static")

# File giao diện + JS render — người dùng đọc trực tiếp
SCAN_UI = [os.path.join(STATIC, f) for f in os.listdir(STATIC) if f.endswith(".html")]
SCAN_UI += [os.path.join(STATIC, "js", f)
            for f in os.listdir(os.path.join(STATIC, "js")) if f.endswith(".js")]

violations = 0

for path in SCAN_UI:
    with open(path, encoding="utf-8") as f:
        hits = check_text(f.read())
    if hits:
        violations += 1
        print(f"[UI]  {os.path.relpath(path, ROOT)} -> {hits}")

# Output AI đã lưu (tuỳ chọn, truyền đường dẫn json)
for arg in sys.argv[1:]:
    with open(arg, encoding="utf-8") as f:
        hits = check_payload(json.load(f))
    if hits:
        violations += 1
        print(f"[AI]  {arg} -> {hits}")

if violations:
    print(f"\nFAIL: {violations} file vi phạm wording pháp lý.")
    sys.exit(1)
print(f"OK: {len(SCAN_UI)} file UI + {len(sys.argv) - 1} output AI — không có từ cấm.")
