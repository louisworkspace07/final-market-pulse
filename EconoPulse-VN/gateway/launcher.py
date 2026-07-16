# -*- coding: utf-8 -*-
"""Launcher tiến trình con cho gateway :9999.

Gateway tự spawn 3 app thành phần (crawl :5000, banggia :5555, econolens :3333)
khi khởi động, để người dùng chỉ cần chạy MỘT lệnh:

    python EconoPulse-VN/gateway/app.py

Nguyên tắc:
  * App nào đã chạy sẵn (người dùng tự mở) → REUSE, không spawn, không kill.
  * App nào chưa chạy → dọn xác cổng rồi spawn, ghi log ra logs/<id>.log.
  * Chỉ tiến trình DO GATEWAY spawn mới bị dừng khi gateway thoát (atexit).
  * Đặt MP_NO_SPAWN=1 để tắt hoàn toàn việc tự spawn (chạy gateway đơn lẻ).

Port lại các hàm đã chạy ổn định từ start_all.py: _ping, _free_port,
_start_service (Popen + log file + CREATE_NEW_PROCESS_GROUP + PYTHONUTF8).
"""
from __future__ import annotations

import atexit
import os
import signal
import subprocess
import sys
import threading

# Ép UTF-8 cho stdout/stderr: launcher in tên/chú thích tiếng Việt, nếu console
# ở cp1252 (Windows, khi chạy qua preview/CI) print sẽ ném UnicodeEncodeError và
# làm CHẾT cả gateway lúc khởi động. errors='replace' để không bao giờ crash vì log.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import time
from pathlib import Path

import urllib.error
import urllib.request

# gateway/ → EconoPulse-VN/ → <project root> (chứa "Crawl Data", "Test tool dự án"…)
GATEWAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GATEWAY_DIR.parent.parent
PYTHON = sys.executable

# Mỗi child: id, cwd (thư mục app), cmd, port, health-url, timeout chờ (giây).
CHILDREN: list[dict] = [
    {
        "id": "crawl",
        "name": "Crawl Data (port 5000)",
        "cwd": PROJECT_ROOT / "Crawl Data",
        "cmd": [PYTHON, "app.py"],
        "port": 5000,
        "health": "http://127.0.0.1:5000/",
        "timeout": 20,
    },
    {
        "id": "banggia",
        "name": "Bảng giá realtime (port 5555)",
        "cwd": PROJECT_ROOT / "Test tool dự án",
        "cmd": [PYTHON, "server.py"],
        "port": 5555,
        "health": "http://127.0.0.1:5555/",
        "timeout": 15,
    },
    {
        "id": "econolens",
        "name": "EconoLens AI chat (port 3333)",
        "cwd": PROJECT_ROOT / "AI Analyze Economic",
        "cmd": ["node", "server.js"],
        "port": 3333,
        "health": "http://127.0.0.1:3333/",
        "timeout": 20,
    },
]

_BY_ID = {c["id"]: c for c in CHILDREN}

# Chỉ chứa tiến trình DO GATEWAY spawn. Giá trị None = app đã chạy sẵn (reuse) →
# không được kill khi gateway thoát.
_procs: dict[str, subprocess.Popen | None] = {}
_lock = threading.Lock()

LOG_DIR = GATEWAY_DIR / "logs"


def _ping(url: str, timeout: float = 1.5) -> bool:
    """True nếu URL phản hồi HTTP (bất kỳ status code nào)."""
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True  # server phản hồi nhưng trả lỗi HTTP — vẫn coi là "đang chạy"
    except Exception:
        return False


def _free_port(port: int) -> None:
    """Giải phóng cổng bằng cách kill PID đang LISTENING (Windows).

    Chỉ match đúng địa chỉ local :PORT để không kill nhầm cổng chứa cùng chữ số.
    """
    if sys.platform != "win32":
        return
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10
        ).stdout
    except Exception:
        return

    local = (f"0.0.0.0:{port}", f"127.0.0.1:{port}", f"[::]:{port}", f"[::1]:{port}")
    pids: set[str] = set()
    for line in out.splitlines():
        if "LISTENING" not in line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        if parts[1] in local:  # parts[1] = local addr, parts[-1] = PID
            pid = parts[-1]
            if pid.isdigit() and pid != "0":
                pids.add(pid)

    for pid in pids:
        try:
            subprocess.run(
                ["taskkill", "/F", "/PID", pid],
                capture_output=True, text=True, timeout=10,
            )
        except Exception:
            pass


def _spawn(child: dict) -> "subprocess.Popen | None":
    """Spawn 1 tiến trình con. Trả None nếu thư mục làm việc không tồn tại."""
    cwd = Path(child["cwd"])
    if not cwd.exists():
        print(f"  [launcher] skip {child['id']}: dir not found {cwd}")
        return None

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"{child['id']}.log"
    with open(log_file, "w", encoding="utf-8") as log_f:
        proc = subprocess.Popen(
            child["cmd"],
            cwd=str(cwd),
            env=env,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            ),
        )
    print(f"  [launcher] {child['id']} -> PID {proc.pid} (log: logs/{child['id']}.log)")
    return proc


def _wait_healthy(child: dict) -> None:
    """Chờ (trong thread nền, không block) child phản hồi health-check."""
    deadline = time.time() + child["timeout"]
    while time.time() < deadline:
        if _ping(child["health"], timeout=1.2):
            print(f"  [launcher] {child['id']} ready.")
            return
        time.sleep(1)
    print(f"  [launcher] {child['id']} no response after {child['timeout']}s "
          f"- see logs/{child['id']}.log")


def _terminate(proc: subprocess.Popen) -> None:
    """Dừng graceful (Ctrl-Break trên Windows) rồi kill nếu quá 5s."""
    try:
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public API (dùng bởi gateway/app.py)
# ---------------------------------------------------------------------------
def start_children() -> None:
    """Spawn các app con còn thiếu. App đã chạy sẵn -> reuse (không spawn/kill).

    Đặt MP_NO_SPAWN=1 để bỏ qua toàn bộ (chạy gateway đơn lẻ).
    Health-check chạy trong thread nền nên KHÔNG chặn gateway khởi động.
    """
    if os.environ.get("MP_NO_SPAWN") == "1":
        print("  [launcher] MP_NO_SPAWN=1 -> bỏ qua tự spawn app con.")
        return

    with _lock:
        for child in CHILDREN:
            cid = child["id"]
            if _ping(child["health"], timeout=0.8):
                _procs[cid] = None  # đã chạy sẵn -> reuse, không sở hữu
                print(f"  [launcher] {cid} đã chạy sẵn -> reuse (không spawn).")
                continue
            _free_port(child["port"])  # dọn xác tiến trình cũ chiếm cổng
            time.sleep(0.3)            # cho OS nhả cổng (tránh WinError 10048)
            _procs[cid] = _spawn(child)
            if _procs[cid] is not None:
                threading.Thread(
                    target=_wait_healthy, args=(child,), daemon=True
                ).start()

    atexit.register(stop_children)
    start_watchdog()


# --------------------------------------------------------------- watchdog
# Con CHẾT giữa chừng (crash Playwright, hết RAM...) → tự restart, tối đa
# WD_MAX_RESTARTS lần / WD_WINDOW giây mỗi con (tránh vòng lặp crash).
# Chỉ trông con do gateway TỰ spawn — app chạy ngoài không bị can thiệp.
WD_INTERVAL = int(os.environ.get("MP_WATCHDOG_INTERVAL_S", "15"))
WD_MAX_RESTARTS = 3
WD_WINDOW = 600
_wd_history: dict[str, list[float]] = {}
_wd_started = [False]


def start_watchdog() -> None:
    if _wd_started[0] or os.environ.get("MP_NO_WATCHDOG") == "1":
        return
    _wd_started[0] = True

    def _loop():
        while True:
            time.sleep(WD_INTERVAL)
            for child in CHILDREN:
                cid = child["id"]
                proc = _procs.get(cid)
                if proc is None:          # không sở hữu (reuse/exterior) -> bỏ qua
                    continue
                dead = proc.poll() is not None and not _ping(child["health"], 1.0)
                if not dead:
                    continue
                now = time.time()
                hist = [t for t in _wd_history.get(cid, []) if now - t < WD_WINDOW]
                if len(hist) >= WD_MAX_RESTARTS:
                    continue              # crash-loop -> dừng auto, chờ can thiệp tay
                hist.append(now)
                _wd_history[cid] = hist
                print(f"  [watchdog] {cid} chết -> auto-restart "
                      f"({len(hist)}/{WD_MAX_RESTARTS} trong {WD_WINDOW}s)", flush=True)
                try:
                    restart_child(cid)
                except Exception as e:
                    print(f"  [watchdog] restart {cid} lỗi: {e}", flush=True)

    threading.Thread(target=_loop, daemon=True).start()


def watchdog_status() -> dict:
    now = time.time()
    return {"enabled": _wd_started[0], "interval_s": WD_INTERVAL,
            "recent_restarts": {c: len([t for t in ts if now - t < WD_WINDOW])
                                for c, ts in _wd_history.items()}}


def child_status() -> dict:
    """Trạng thái từng app con: {id: {running, pid, port, spawned_by_gateway}}."""
    out: dict[str, dict] = {}
    for child in CHILDREN:
        cid = child["id"]
        proc = _procs.get(cid)
        pid = proc.pid if (proc is not None and proc.poll() is None) else None
        out[cid] = {
            "name": child["name"],
            "running": _ping(child["health"], timeout=1.0),
            "pid": pid,
            "port": child["port"],
            "spawned_by_gateway": cid in _procs and _procs[cid] is not None,
        }
    return out


def restart_child(cid: str) -> dict:
    """Restart 1 app con theo id (chỉ id hợp lệ). Trả {ok, pid} hoặc {ok:False}."""
    child = _BY_ID.get(cid)
    if child is None:
        return {"ok": False, "error": f"id không hợp lệ: {cid}"}
    with _lock:
        old = _procs.get(cid)  # nếu gateway đang sở hữu proc cũ -> dừng trước
        if old is not None and old.poll() is None:
            _terminate(old)
        _free_port(child["port"])
        time.sleep(0.3)
        proc = _spawn(child)
        _procs[cid] = proc
    if proc is None:
        return {"ok": False, "error": "spawn thất bại (thiếu thư mục?)"}
    threading.Thread(target=_wait_healthy, args=(child,), daemon=True).start()
    return {"ok": True, "pid": proc.pid}


def log_path(cid: str) -> "Path | None":
    """Đường dẫn log cố định cho 1 id hợp lệ (không nhận path từ client)."""
    if cid not in _BY_ID:
        return None
    return LOG_DIR / f"{cid}.log"


def tail_log(cid: str, n: int = 100) -> list[str]:
    """Trả n dòng cuối của log 1 app con (rỗng nếu id lạ / chưa có log)."""
    p = log_path(cid)
    if p is None or not p.exists():
        return []
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()[-n:]
    except Exception:
        return []


def stop_children() -> None:
    """Dừng CHỈ các tiến trình do gateway spawn. Proc reuse (None) không đụng."""
    with _lock:
        for cid, proc in list(_procs.items()):
            if proc is not None and proc.poll() is None:
                _terminate(proc)
                print(f"  [launcher] đã dừng {cid} (PID {proc.pid}).")
