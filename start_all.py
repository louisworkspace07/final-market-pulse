#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[DEPRECATED — fallback] Khởi động tất cả services bằng một lệnh.

Cách khuyến nghị hiện nay: chỉ chạy cổng gateway, nó tự spawn 3 app con:
    python market-pulse/gateway/app.py   (hoặc START_ALL.bat)

File này giữ lại làm fallback (spawn cả 4 tiến trình rời như trước). Khi dùng
fallback, gateway được đặt MP_NO_SPAWN=1 để KHÔNG tự spawn lần nữa (tránh spawn 2 lần).

Chạy:  python start_all.py
Dừng:  Ctrl+C  (tất cả tiến trình con được dừng gracefully)

Services được khởi động theo thứ tự phụ thuộc:
  1. data-crawler dashboard   → http://localhost:5000
  2. Bảng giá realtime      → http://localhost:5555
  3. EconoLens AI chat      → http://localhost:3333
  4. Market Pulse gateway   → http://localhost:9999  (cổng chính — mở cái này)
"""
from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Đảm bảo terminal in được tiếng Việt (mặc định trên Windows là cp1252 → lỗi).
# Chính launcher này in ra nhiều ký tự Unicode, nên phải ép UTF-8 cho stdout/stderr.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

# Định nghĩa mỗi service: tên, thư mục làm việc, lệnh, URL health-check, timeout
SERVICES: list[dict] = [
    {
        "id": "crawl",
        "name": "data-crawler (port 5000)",
        "cwd": ROOT / "data-crawler",
        "cmd": [PYTHON, "app.py"],
        "health_url": "http://localhost:5000/",
        "timeout": 20,
        "env_extra": {},
    },
    {
        "id": "banggia",
        "name": "Bảng giá realtime (port 5555)",
        "cwd": ROOT / "price-board",
        "cmd": [PYTHON, "server.py"],
        "health_url": "http://localhost:5555/",
        "timeout": 15,
        "env_extra": {},
    },
    {
        "id": "econolens",
        "name": "EconoLens AI chat (port 3333)",
        "cwd": ROOT / "econolens-chat",
        "cmd": ["node", "server.js"],
        "health_url": "http://localhost:3333/",
        "timeout": 20,
        "env_extra": {},
    },
    {
        "id": "gateway",
        "name": "Market Pulse gateway (port 9999)",
        "cwd": ROOT / "market-pulse",
        "cmd": [PYTHON, "gateway/app.py"],
        "health_url": "http://localhost:9999/api/services",
        "timeout": 15,
        # start_all.py đã tự spawn 3 app con -> tắt tự-spawn của gateway (tránh 2 lần).
        "env_extra": {"MP_NO_SPAWN": "1"},
    },
]

_procs: list[subprocess.Popen] = []

# ANSI colours (bỏ qua nếu terminal không hỗ trợ)
GREEN = "\033[32m"
RED   = "\033[31m"
CYAN  = "\033[36m"
BOLD  = "\033[1m"
RESET = "\033[0m"


def _ping(url: str, timeout: float = 1.5) -> bool:
    """Trả về True nếu URL phản hồi HTTP (bất kỳ status code nào)."""
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True   # Server phản hồi nhưng trả lỗi HTTP — vẫn là "đang chạy"
    except Exception:
        return False


def _port_of(svc: dict) -> int | None:
    """Trích số cổng từ health_url (vd http://localhost:5000/ → 5000)."""
    m = re.search(r":(\d+)", svc.get("health_url", ""))
    return int(m.group(1)) if m else None


def _free_port(port: int) -> None:
    """Giải phóng cổng bằng cách kill PID đang LISTENING trên đó (Windows).

    Đây là phần cốt lõi của 'khởi động sạch': bảo đảm start_all.py luôn chạy
    lại bản code mới nhất thay vì bám vào tiến trình cũ đang chiếm cổng.
    """
    if sys.platform != "win32":
        return  # non-Windows: no-op (môi trường thực tế của người dùng là win32)

    try:
        out = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except Exception:
        return

    # Chỉ nhận đúng địa chỉ local :PORT để không kill nhầm cổng chứa cùng chữ số.
    local = (f"0.0.0.0:{port}", f"127.0.0.1:{port}", f"[::]:{port}", f"[::1]:{port}")
    pids: set[str] = set()
    for line in out.splitlines():
        if "LISTENING" not in line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        if parts[1] in local:      # parts[1] = địa chỉ local, parts[-1] = PID
            pid = parts[-1]
            if pid.isdigit() and pid != "0":
                pids.add(pid)

    for pid in pids:
        try:
            subprocess.run(
                ["taskkill", "/F", "/PID", pid],
                capture_output=True, text=True, timeout=10,
            )
            print(f"  {CYAN}↳ giải phóng cổng {port} (PID {pid}){RESET}")
        except Exception:
            pass


def _wait_for_service(svc: dict) -> bool:
    """Chờ service lên trong svc['timeout'] giây. Trả về True nếu thành công."""
    deadline = time.time() + svc["timeout"]
    dots = 0
    while time.time() < deadline:
        if _ping(svc["health_url"]):
            return True
        print(f"  {'.' * (dots % 4 + 1)}", end="\r", flush=True)
        dots += 1
        time.sleep(1)
    return False


def _start_service(svc: dict) -> subprocess.Popen | None:
    """Khởi động một service trong subprocess. Trả về None nếu thư mục không tồn tại."""
    cwd = Path(svc["cwd"])
    if not cwd.exists():
        print(f"{RED}  [!] Thư mục không tồn tại: {cwd}{RESET}")
        return None

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(svc.get("env_extra", {}))

    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"{svc['id']}.log"

    with open(log_path, "w", encoding="utf-8") as log_f:
        proc = subprocess.Popen(
            svc["cmd"],
            cwd=cwd,
            env=env,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
    print(f"  → PID {proc.pid}  (log: logs/{svc['id']}.log)")
    return proc


def _shutdown(signum=None, frame=None):
    """Dừng tất cả tiến trình con khi nhận Ctrl+C hoặc tín hiệu kết thúc."""
    print(f"\n{BOLD}Đang dừng tất cả services...{RESET}")
    for proc in reversed(_procs):
        if proc and proc.poll() is None:
            try:
                if sys.platform == "win32":
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
    print(f"{GREEN}Đã dừng xong.{RESET}")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, _shutdown)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, _shutdown)

    print(f"\n{BOLD}{CYAN}=== Final Market Pulse — Unified Startup ==={RESET}\n")

    failed: list[str] = []
    started: list[str] = []

    for svc in SERVICES:
        print(f"{BOLD}[{svc['id']}]{RESET} Khởi động {svc['name']} ...")

        # Khởi động sạch: giải phóng cổng nếu còn tiến trình cũ chiếm,
        # để luôn chạy lại bản code mới nhất thay vì bám vào tiến trình cũ.
        port = _port_of(svc)
        if port is not None and _ping(svc["health_url"], timeout=0.8):
            _free_port(port)
            time.sleep(0.5)  # cho OS nhả cổng, tránh WinError 10048 (address in use)

        proc = _start_service(svc)
        _procs.append(proc)

        if proc is None:
            failed.append(svc["id"])
            print(f"  {RED}✗ Bỏ qua (không tìm thấy thư mục){RESET}")
            continue

        ok = _wait_for_service(svc)
        if ok:
            print(f"  {GREEN}✓ Sẵn sàng{RESET}")
            started.append(svc["id"])
        else:
            print(f"  {RED}✗ Không phản hồi trong {svc['timeout']}s — kiểm tra logs/{svc['id']}.log{RESET}")
            failed.append(svc["id"])

        print()

    # --- Tóm tắt ---
    print(f"\n{BOLD}{'='*45}{RESET}")
    print(f"  Đã khởi động : {GREEN}{len(started)}/{len(SERVICES)}{RESET} services")
    if failed:
        print(f"  Thất bại     : {RED}{', '.join(failed)}{RESET}")
    print(f"\n  {BOLD}Truy cập:{RESET}")
    print(f"  • Dashboard chính  →  {CYAN}http://localhost:9999{RESET}")
    print(f"  • AI Chat          →  {CYAN}http://localhost:3333{RESET}")
    print(f"  • data-crawler UI    →  {CYAN}http://localhost:5000{RESET}")
    print(f"  • Bảng giá         →  {CYAN}http://localhost:5555{RESET}")
    print(f"\n  Nhấn {BOLD}Ctrl+C{RESET} để dừng tất cả.\n")
    print(f"{'='*45}")

    # Giữ script chạy để có thể Ctrl+C
    try:
        while True:
            time.sleep(5)
            # Kiểm tra xem có proc nào chết bất ngờ không
            for i, (svc, proc) in enumerate(zip(SERVICES, _procs)):
                if proc and proc.poll() is not None:
                    print(f"{RED}[!] {svc['name']} đã dừng bất ngờ (exit {proc.returncode})"
                          f" — xem logs/{svc['id']}.log{RESET}")
                    _procs[i] = None  # đánh dấu đã xử lý
    except KeyboardInterrupt:
        _shutdown()


if __name__ == "__main__":
    main()
