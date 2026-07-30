"""Kiểm tra kênh AI đang dùng (mặc định: server AI local ở :4000).

  python -m scripts.test_gemini              # thử backend đang hiệu lực
  python -m scripts.test_gemini --backend gemini   # ép thử kênh CDP cũ

Backend `gemini` (CDP) chỉ chạy được sau khi đã: python -m scripts.launch_chrome
và đăng nhập Gemini trong cửa sổ Chrome đó.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config  # bật UTF-8  # noqa: F401
from src import local_api
from src.analyzer import resolve_backend

QUESTION = "Trả lời đúng 1 dòng: thủ đô Việt Nam là gì?"


def _test_local_api() -> None:
    st = local_api.status()
    print(f"→ Local API: {st['url']} (model {st['model']})")
    if not st["has_key"]:
        print("✗ Thiếu LOCAL_API_KEY — điền vào data-crawler/.env hoặc ô 'API key' "
              "trên bảng điều khiển :5000.")
        return
    if not st["up"]:
        print(f"✗ Server local không phản hồi ở {st['url']} — hãy bật server rồi thử lại.")
        return
    print("  Server sống. Đang hỏi thử 1 câu...")
    ans = local_api.ask(QUESTION, retries=0)
    print("\n--- AI trả lời ---")
    print(ans[:500] if ans else "(rỗng)")


def _test_cdp() -> None:
    from src.gemini_cdp import GeminiCDP
    print("→ Kết nối Chrome (CDP) và hỏi thử Gemini...")
    with GeminiCDP() as g:
        print("  Đã kết nối Chrome. Mở tab mới hỏi Gemini...")
        ans = g.ask(QUESTION, timeout=90)
    print("\n--- Gemini trả lời ---")
    print(ans[:500] if ans else "(rỗng — kiểm tra đã đăng nhập & selector chưa)")


def _test_claude() -> None:
    from src.analyzer import _raw_claude
    print("→ Hỏi thử Claude API...")
    print("\n--- Claude trả lời ---")
    print(_raw_claude(QUESTION)[:500])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="", help="local_api | gemini | claude")
    args = ap.parse_args()
    backend = (args.backend or "").strip().lower() or resolve_backend()
    print(f"Backend đang kiểm tra: {backend}")
    try:
        {"gemini": _test_cdp, "claude": _test_claude}.get(backend, _test_local_api)()
    except Exception as exc:
        print(f"✗ Lỗi: {exc}")
        if backend == "gemini":
            print("  Gợi ý: chạy launch_chrome, đăng nhập Gemini, giữ cửa sổ Chrome mở.")
        else:
            print("  Gợi ý: bật server AI local ở :4000 và kiểm tra LOCAL_API_KEY trong .env.")


if __name__ == "__main__":
    main()
