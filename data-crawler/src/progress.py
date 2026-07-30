"""Phát tín hiệu tiến độ chi tiết cho bảng điều khiển.

In ra stdout dòng dạng:  @STEP|<sym>|<key>|<status>|<n>
App control panel đọc các dòng này để dựng bảng chi tiết realtime.
key '_start' báo bắt đầu một mã; '_done' báo xong.
"""
from __future__ import annotations


def step(sym: str, key: str, status: str = "ok", n=None) -> None:
    print(f"@STEP|{sym}|{key}|{status}|{'' if n is None else n}", flush=True)


def start(sym: str) -> None:
    step(sym, "_start", "run")


def done(sym: str, status: str = "ok") -> None:
    step(sym, "_done", status)
