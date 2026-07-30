"""Mở Chrome với cổng remote-debugging + profile riêng cho CDP.

Lần đầu: cửa sổ Chrome mới hiện ra → ĐĂNG NHẬP Google và mở Gemini.
Lần sau profile nhớ đăng nhập, không cần làm lại.

  python -m scripts.launch_chrome
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config  # noqa

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9222
PROFILE_DIR = config.ROOT / "chrome_cdp_profile"   # profile riêng, tách Chrome chính


def main() -> None:
    if not Path(CHROME).exists():
        print(f"Không thấy Chrome tại: {CHROME}"); return
    PROFILE_DIR.mkdir(exist_ok=True)
    args = [
        CHROME,
        f"--remote-debugging-port={DEBUG_PORT}",
        "--remote-allow-origins=*",   # Chrome >=111 cần cờ này để CDP websocket kết nối (mọi dự án gắn tab qua đây)
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://gemini.google.com/app",
    ]
    print(f"→ Mở Chrome (debug port {DEBUG_PORT}, profile {PROFILE_DIR.name})")
    print("  Lần đầu: hãy ĐĂNG NHẬP Google + mở được Gemini, rồi giữ cửa sổ này.")
    subprocess.Popen(args)
    print("✓ Đã khởi chạy. Kiểm tra: http://localhost:9222/json/version")


if __name__ == "__main__":
    main()
