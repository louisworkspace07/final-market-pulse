"""Bảng điều khiển web trực quan cho hệ thống Crawl Data.

Chạy:  python app.py   →  http://localhost:5000

Nút bấm chạy từng bước (P0..P5, Chrome/Gemini). Backend bóc tách tiến độ từ log
→ frontend hiện thanh tiến độ, lưới mã (đang/xong/lỗi), số liệu DB cập nhật, log chi tiết.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request, send_from_directory, Response

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DB_PATH = ROOT / "database" / "market.db"
SYMBOLS_JSON = ROOT / "database" / "symbols.json"
COMPANIES_TXT = ROOT / "config" / "companies.txt"
LOGS_DIR = ROOT / "logs"
RUN_LOG = LOGS_DIR / "run.log"
RUN_PID = LOGS_DIR / "run.pid"

# Dòng NHIỄU từ thư viện bên thứ ba làm rối log (không phải lỗi thật) → lọc bỏ.
_LOG_NOISE = (
    "Downcasting object dtype arrays",              # cảnh báo pandas (fillna/ffill/bfill)
    "future.no_silent_downcasting",
    "result.infer_objects(copy=False)",
    "vnstocks.com/insiders-program",                # quảng cáo gói trả phí vnstock
    "Phiên bản cộng đồng: Dữ liệu báo cáo tài chính",
    "Community edition: Financial statements",
    "Vnai ",                                        # nag phiên bản: "📦 Vnai 2.5.0 is available"
    "pip install vnai",
    "pypi.org/project/vnai",
    "Release: https://pypi.org",
)

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────── lớp pháp lý
# Hệ thống KHÔNG phát ra khuyến nghị đầu tư: không xếp hạng mua/bán, không giá
# mục tiêu, không "chọn mã nào". Crawl Data là project độc lập nên tự định nghĩa
# drop-list ở đây (không import chéo từ EconoPulse-VN), giữ đồng bộ về nội dung
# với modules/common/legal.py BANNED_KEYS.
_BANNED_KEYS = frozenset({
    "investment_rating", "target_price", "upside_to_target_percent",
    "rating", "recommendation", "winner",
})


def _scrub(obj, extra_keys=()):
    """Bản sao của obj đã loại mọi khoá bị cấm ở mọi độ sâu (kể cả list of dict).

    extra_keys: khoá cấm thêm chỉ áp cho riêng một call site (vd "verdict" ở
    route so sánh 2 mã).
    """
    drop = _BANNED_KEYS | frozenset(k.lower() for k in extra_keys)

    def _walk(o):
        if isinstance(o, dict):
            return {k: _walk(v) for k, v in o.items()
                    if not (isinstance(k, str) and k.strip().lower() in drop)}
        if isinstance(o, list):
            return [_walk(v) for v in o]
        return o

    return _walk(obj)


# Allow-list các trường hồ sơ doanh nghiệp ĐƯỢC PHÉP trả ra /api/source/<sym>/profile.
# VÌ SAO ALLOW-LIST chứ không phải deny-list: profile.json do vnstock trả về gồm
# cả khuyến nghị của CTCK (rating BUY/HOLD, target_price, upside_to_target_percent
# — đã xác nhận 84 hồ sơ có đủ 3 trường này). Deny-list sẽ rò rỉ ngay khi nhà
# cung cấp thêm trường mới; allow-list thì mặc định đóng.
#
# Đã đối chiếu schema thật (companies/ACB/profile.json): overview chứa rating
# "BUY", target_price, upside_to_target_percent, analyst, rating_as_of,
# projected_tsr_percentage, VÀ prev_insight = {targetPrice, rating, ratingAsOf,
# analyst} ở dạng camelCase — tức deny-list theo snake_case sẽ trượt prev_insight.
_SAFE_PROFILE_KEYS = frozenset({
    # định danh & phân loại
    "symbol", "organ_code", "organ_name", "organ_short_name", "exchange",
    "com_type_code", "com_group_code", "sector", "industry", "icb_name",
    "icb_code_lv2", "icb_code_lv4", "is_bank", "bank", "listing", "in_cu",
    # cấu trúc vốn & sở hữu
    "issue_share", "charter_capital", "outstanding_share",
    "free_float", "free_float_percentage",
    "foreigner_percentage", "maximum_foreign_percentage", "state_percentage",
    # thống kê giao dịch (dữ kiện, không phải nhận định)
    "current_price", "market_cap", "listing_date",
    "average_match_value1_month", "average_match_volume1_month",
    "highest_price1_year", "lowest_price1_year",
    # mô tả doanh nghiệp
    "company_profile", "history", "business_strategies", "business_risk",
    "key_developments", "website", "established_year", "no_employees",
})


def _safe_profile(data):
    """Lọc profile.json qua allow-list, giữ nguyên cấu trúc lồng nhau.

    Giữ lại metadata cấp gốc (symbol/updated_at) để UI biết tuổi dữ liệu.
    """
    if not isinstance(data, dict):
        return {}
    out = {}
    for section, val in data.items():
        if isinstance(val, dict):
            kept = {k: v for k, v in val.items() if k in _SAFE_PROFILE_KEYS}
            if kept:
                out[section] = kept
        elif isinstance(val, list):
            kept_rows = [
                {k: v for k, v in row.items() if k in _SAFE_PROFILE_KEYS}
                for row in val if isinstance(row, dict)
            ]
            kept_rows = [r for r in kept_rows if r]
            if kept_rows:
                out[section] = kept_rows
        elif section in _SAFE_PROFILE_KEYS or section in ("updated_at", "as_of"):
            out[section] = val
    # Lớp 2: nếu một trường được phép lại chứa dict lồng có khoá cấm → vẫn loại.
    return _scrub(out)


# Đọc dotenv
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

_lock = threading.Lock()


def _new_progress():
    return {"stage": None, "current": 0, "total": 0,
            "done": 0, "errors": 0, "cur_sym": None, "items": [],
            "detail": {}, "order": []}


STATE = {"running": False, "task": None, "rc": None,
         "started_at": None, "progress": _new_progress()}
_proc: subprocess.Popen | None = None
_pending: dict = {"sym": None, "idx": None}

def _append_log(line: str):
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

TASKS = {
    "p0":          ("scripts.p0_symbols",   "Lấy danh sách mã toàn thị trường"),
    "p1":          ("scripts.p1_financials","Crawl tài chính + dòng tiền (mã mẫu)"),
    "p2":          ("scripts.p2_company",   "Crawl tin tức + sự kiện (mã mẫu)"),
    "p3":          ("scripts.p3_crawl_all", "Bung crawl toàn thị trường"),
    "launch":      ("scripts.launch_chrome","Mở Chrome (CDP) — chỉ cần cho backend gemini"),
    "test_gemini": ("scripts.test_gemini",  "Kiểm tra kênh AI đang dùng (mặc định Local API)"),
    "p4":          ("scripts.p4_analyze",   "Phân tích AI"),
    "p5":          ("scripts.p5_export",    "Xuất dữ liệu cho trang so sánh"),
    "pipeline":    ("scripts.pipeline",     "Chạy 1 mạch theo nhóm (tối ưu rate-limit)"),
}

# ------------------------------------------------------------------ validate đầu vào
ALLOWED_BACKENDS = {"gemini", "claude", "local_api"}
ALLOWED_GROUPS = {"VN30", "VN100", "HOSE", "HNX", "UPCOM", "ALL", "CUSTOM"}
RE_SYM = re.compile(r"^[A-Z0-9]{2,6}$")       # mã hợp lệ sau khi .upper()


def _safe_limit(raw):
    """Ép limit về int an toàn: sai/âm → 0 (nghĩa là không giới hạn)."""
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return 0
    return n if n > 0 else 0


def _valid_sym(sym: str) -> bool:
    """Mã hợp lệ: 2-6 ký tự A-Z0-9 (đã .upper() trước khi gọi)."""
    return bool(RE_SYM.match(sym or ""))


def _check_origin() -> bool:
    """Chặn cross-site cơ bản cho các endpoint POST.

    Cho phép khi KHÔNG có Origin (fetch cùng origin đôi khi không gửi header này).
    Nếu có Origin thì phải trỏ về 127.0.0.1/localhost, ngược lại từ chối.
    """
    origin = request.headers.get("Origin")
    if not origin:
        return True
    return origin.startswith(("http://127.0.0.1:", "http://localhost:",
                              "http://127.0.0.1", "http://localhost"))

# ------------------------------------------------------------------ bóc tách tiến độ
RE_TOTAL = re.compile(r"(?:cho|Phân tích|stage|STAGE)\s+(\d+)\s+mã")
RE_STAGE = re.compile(r"=== STAGE (\w+) ===.*?cần làm\s+(\d+)")
RE_COMBINED = re.compile(r"\[(\d+)/(\d+)\]\s*([✓✗~])\s*([A-Z0-9]{2,6})[:\s]?(.*)")
RE_START = re.compile(r"^\[(\d+)/(\d+)\]\s+([A-Z0-9]{2,6})\s*$")
RE_RESOLVE = re.compile(r"^\s*([✓✗~])\s*(.*)")


def _add_item(sym, status, detail=""):
    p = STATE["progress"]
    p["items"].append({"sym": sym, "status": status, "detail": detail[:140]})
    if len(p["items"]) > 400:
        p["items"] = p["items"][-400:]
    if status == "ok":
        p["done"] += 1
    elif status == "error":
        p["errors"] += 1
    elif status == "partial":
        p["done"] += 1


def _parse_step(line: str):
    """Xử lý dòng @STEP|sym|key|status|n → cập nhật bảng chi tiết."""
    parts = line.split("|")
    if len(parts) < 5:
        return
    _, sym, key, status, n = parts[0], parts[1], parts[2], parts[3], parts[4]
    p = STATE["progress"]
    d = p["detail"]
    if sym not in d:
        d[sym] = {"steps": {}, "status": "run"}
        p["order"].append(sym)
        if len(p["order"]) > 400:
            old = p["order"].pop(0)
            d.pop(old, None)
    p["cur_sym"] = sym
    if key == "_start":
        d[sym]["status"] = "run"
    elif key == "_done":
        d[sym]["status"] = status
    else:
        d[sym]["steps"][key] = {"status": status, "n": n}


def _parse(line: str):
    p = STATE["progress"]
    m = RE_STAGE.search(line)
    if m:
        p.update(stage=m.group(1), total=int(m.group(2)),
                 current=0, done=0, errors=0, cur_sym=None, items=[])
        return
    m = RE_TOTAL.search(line)
    if m and p["total"] == 0:
        p["total"] = int(m.group(1))
        return
    m = RE_COMBINED.search(line)          # P3 / P4: index + tick + sym cùng dòng
    if m:
        i, n, tick, sym, rest = m.groups()
        st = {"✓": "ok", "✗": "error", "~": "partial"}[tick]
        p.update(current=int(i), total=int(n), cur_sym=sym)
        _add_item(sym, st, rest.strip())
        _pending.update(sym=None, idx=None)
        return
    m = RE_START.match(line)              # P1 / P2: dòng "[i/N] SYM", kết quả dòng sau
    if m:
        i, n, sym = m.groups()
        p.update(current=int(i), total=int(n), cur_sym=sym)
        _pending.update(sym=sym, idx=int(i))
        _add_item(sym, "run", "")
        return
    m = RE_RESOLVE.match(line)            # dòng kết quả ✓/✗ cho mã đang chờ
    if m and _pending["sym"] and p["items"]:
        tick, rest = m.groups()
        st = {"✓": "ok", "✗": "error", "~": "partial"}[tick]
        last = p["items"][-1]
        if last["sym"] == _pending["sym"] and last["status"] == "run":
            last["status"] = st
            last["detail"] = rest.strip()[:140]
            if st in ("ok", "partial"):
                p["done"] += 1
            elif st == "error":
                p["errors"] += 1
        _pending.update(sym=None, idx=None)


def _run_task(task, module, extra_args, env_extra):
    global _proc
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"; env["PYTHONIOENCODING"] = "utf-8"
    env.update(env_extra)
    cmd = [sys.executable, "-u", "-m", module, *extra_args]

    with _lock:
        STATE.update(running=True, task=task, rc=None, started_at=time.time(),
                     progress=_new_progress())
        _pending.update(sym=None, idx=None)
        RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
        RUN_LOG.write_text("", encoding="utf-8")
        _append_log(f"$ {' '.join(cmd)}")
    try:
        _proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                 errors="replace", bufsize=1)
        RUN_PID.write_text(str(_proc.pid), encoding="utf-8")
        for line in _proc.stdout:
            line = line.rstrip("\n")
            if line.startswith("@STEP"):
                with _lock:
                    _parse_step(line)
                continue
            if line.strip().startswith(("┃", "┏", "┗", "━")) or "INSIDERS" in line:
                continue
            # Lọc dòng NHIỄU của thư viện (vnstock nag gói trả phí, cảnh báo pandas,
            # nag phiên bản vnai) — làm rối log, không phải lỗi thật.
            if any(s in line for s in _LOG_NOISE):
                continue
            with _lock:
                _append_log(line)
                _parse(line)
        _proc.wait(); rc = _proc.returncode
    except Exception as exc:
        with _lock:
            _append_log(f"[LỖI] {exc}")
        rc = -1
    finally:
        _proc = None
        if RUN_PID.exists():
            RUN_PID.unlink(missing_ok=True)
        with _lock:
            STATE.update(running=False, rc=rc)
            STATE["progress"]["cur_sym"] = None
            _append_log(f"--- Kết thúc (mã thoát {rc}) ---")


@app.post("/run")
def run():
    if not _check_origin():
        return jsonify(ok=False, msg="Nguồn không hợp lệ"), 403
    data = request.get_json(force=True)
    task = data.get("task")
    if task not in TASKS:
        return jsonify(ok=False, msg="Tác vụ không hợp lệ"), 400
    with _lock:
        if STATE["running"]:
            return jsonify(ok=False, msg="Đang chạy một tác vụ khác"), 409
    module, _ = TASKS[task]
    extra_args, env_extra = [], {}
    if task == "p4":
        backend = str(data.get("backend", "local_api")).lower()
        if backend not in ALLOWED_BACKENDS:
            return jsonify(ok=False, msg="Backend không hợp lệ"), 400
        env_extra["AI_BACKEND"] = backend
        apikey = str(data.get("apikey", "")).strip()
        if apikey:
            env_extra["LOCAL_API_KEY"] = apikey
            
        group = str(data.get("group", "CUSTOM")).upper()
        if group not in ALLOWED_GROUPS:
            group = "CUSTOM"
        if data.get("all") or group == "ALL":
            extra_args.append("--all")
        elif group:
            extra_args += ["--group", group]

        if data.get("reanalyze") or data.get("no_resume"):
            extra_args.append("--reanalyze")

        limit = _safe_limit(data.get("limit"))
        if limit:
            extra_args += ["--limit", str(limit)]

    if task == "p3":
        group = str(data.get("group", "ALL")).upper()
        if group not in ALLOWED_GROUPS:
            group = "ALL"
        extra_args += ["--group", group]

        if data.get("no_resume") or data.get("recrawl"):
            extra_args.append("--no-resume")

        limit = _safe_limit(data.get("limit"))
        if limit:
            extra_args += ["--limit", str(limit)]

    if task == "pipeline":
        group = str(data.get("group", "VN30")).upper()
        if group not in ALLOWED_GROUPS:
            return jsonify(ok=False, msg="Nhóm không hợp lệ"), 400
        backend = str(data.get("backend", "local_api")).lower()
        if backend not in ALLOWED_BACKENDS:
            return jsonify(ok=False, msg="Backend không hợp lệ"), 400
        apikey = str(data.get("apikey", "")).strip()
        if apikey:
            env_extra["LOCAL_API_KEY"] = apikey
        extra_args += ["--group", group, "--backend", backend]
        if data.get("no_resume") or data.get("recrawl"):
            extra_args.append("--no-resume")
        if data.get("reanalyze"):
            extra_args.append("--reanalyze")   # start lại từ đầu (bỏ resume stage analyze)
        limit = _safe_limit(data.get("limit"))
        if limit:
            extra_args += ["--limit", str(limit)]
    threading.Thread(target=_run_task, args=(task, module, extra_args, env_extra),
                     daemon=True).start()
    return jsonify(ok=True)



def _terminate_tree(pid: int):
    """Dừng tiến trình + cả cây con (Chrome...). Nếu terminate 3s chưa chết → kill cứng.

    Có psutil: kill đệ quy cả con cháu. Thiếu psutil: fallback terminate/kill tiến trình gốc.
    Bọc an toàn tuyệt đối, không ném lỗi ra ngoài.
    """
    try:
        import psutil
    except Exception:
        psutil = None

    if psutil is not None:
        try:
            parent = psutil.Process(pid)
            procs = parent.children(recursive=True) + [parent]
            for pr in procs:
                try:
                    pr.terminate()
                except Exception:
                    pass
            # Chờ tối đa ~3s, ai chưa chết thì kill() cứng.
            gone, alive = psutil.wait_procs(procs, timeout=3)
            for pr in alive:
                try:
                    pr.kill()
                except Exception:
                    pass
            return
        except Exception:
            pass

    # Fallback không có psutil / có lỗi: thao tác trên tiến trình gốc.
    try:
        proc = _proc
        if proc is not None and proc.pid == pid and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
    except Exception:
        pass


@app.post("/stop")
def stop():
    if not _check_origin():
        return jsonify(ok=False, msg="Nguồn không hợp lệ"), 403
    with _lock:
        p = _proc
    if p and p.poll() is None:
        _terminate_tree(p.pid)
        return jsonify(ok=True)

    if RUN_PID.exists():
        try:
            pid = int(RUN_PID.read_text(encoding="utf-8").strip())
            _terminate_tree(pid)
            RUN_PID.unlink(missing_ok=True)
            return jsonify(ok=True, msg="Đã kill zombie process")
        except Exception:
            pass
    return jsonify(ok=False, msg="Không có tiến trình đang chạy")


@app.get("/poll")
def poll():
    # Con trỏ dòng client đã nhận (đọc toàn log, chỉ trả các dòng MỚI kể từ `since`).
    try:
        since = max(0, int(request.args.get("since", 0)))
    except (TypeError, ValueError):
        since = 0
    all_lines = []
    if RUN_LOG.exists():
        try:
            with open(RUN_LOG, "r", encoding="utf-8") as f:
                all_lines = f.read().splitlines()
        except Exception:
            pass
    total_lines = len(all_lines)
    # Nếu log bị cắt/reset (since vượt tổng số) → gửi lại từ đầu.
    if since > total_lines:
        since = 0
    new_lines = all_lines[since:]
    with _lock:
        started = STATE["started_at"]
        elapsed = round(time.time() - started, 1) if started else 0
        # ETA: dựa trên số mã đã xong / tổng và thời gian đã trôi.
        pr = STATE["progress"]
        done = (pr.get("done", 0) + pr.get("errors", 0)) or pr.get("current", 0)
        total = pr.get("total", 0)
        eta = None
        if STATE["running"] and done > 0 and total > done and elapsed > 0:
            eta = round(elapsed / done * (total - done))
        return jsonify(running=STATE["running"], task=STATE["task"], rc=STATE["rc"],
                       total=total_lines, since=since, elapsed=elapsed, eta=eta,
                       lines=new_lines, progress=STATE["progress"])


@app.get("/stats")
def stats():
    out = {"companies": 0, "fin_symbols": 0, "news": 0, "analyzed": 0,
           "fin_done": 0, "co_done": 0}
    if DB_PATH.exists():
        try:
            c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=1)
            q = lambda s: c.execute(s).fetchone()[0]
            out["companies"] = q("SELECT COUNT(*) FROM companies")
            out["fin_symbols"] = q("SELECT COUNT(DISTINCT symbol) FROM financials")
            out["news"] = q("SELECT COUNT(*) FROM news")
            out["analyzed"] = q("SELECT COUNT(*) FROM ai_analysis")
            out["fin_done"] = q("SELECT COUNT(*) FROM crawl_state WHERE stage='financials' AND status='ok'")
            out["co_done"] = q("SELECT COUNT(*) FROM crawl_state WHERE stage='company' AND status='ok'")
            c.close()
        except Exception:
            pass
    return jsonify(out)


@app.get("/health")
def health():
    """Trạng thái backend SỐNG cho UI (poll nhẹ): Chrome CDP, cấu hình, độ tươi DB.

    KHÔNG mở tab Gemini ở đây (nặng) — chỉ kiểm CDP qua HTTP. Muốn biết Gemini đã
    đăng nhập / bị chặn CAPTCHA thì bấm nút → /gemini_check."""
    out = {"cdp_up": False, "backend": "local_api", "request_delay": 0.0,
           "local_api": {}, "db": {}, "fresh": {}}
    try:
        from src.analyzer import resolve_backend
        out["backend"] = resolve_backend()
    except Exception:
        out["backend"] = (os.environ.get("AI_BACKEND") or "local_api")
    try:
        from src import local_api as _lapi
        out["local_api"] = _lapi.status()   # {url, model, up, has_key} — không lộ key
    except Exception:
        pass
    try:
        from src.gemini_cdp import cdp_available, current_delay
        out["cdp_up"] = cdp_available()
        out["request_delay"] = current_delay()
    except Exception:
        pass
    if DB_PATH.exists():
        try:
            c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=1)
            q = lambda s: c.execute(s).fetchone()[0]
            out["db"] = {
                "companies": q("SELECT COUNT(*) FROM companies"),
                "fin_symbols": q("SELECT COUNT(DISTINCT symbol) FROM financials"),
                "analyzed": q("SELECT COUNT(*) FROM ai_analysis"),
                "news": q("SELECT COUNT(*) FROM news"),
            }
            # Độ tươi: mốc dữ liệu mới nhất từng loại
            out["fresh"] = {
                "price": q("SELECT MAX(time) FROM price"),
                "analyzed": q("SELECT MAX(updated_at) FROM ai_analysis"),
                "crawl": q("SELECT MAX(updated_at) FROM crawl_state"),
            }
            c.close()
        except Exception:
            pass
    return jsonify(out)


@app.post("/gemini_check")
def gemini_check():
    """Kiểm tra kênh AI ĐANG dùng theo YÊU CẦU.

    - backend local_api (mặc định): ping /health server local + xem có API key chưa.
    - backend gemini: mở 1 tab CDP → sẵn sàng / bị chặn CAPTCHA (1095) / chưa
      đăng nhập / Chrome chưa mở."""
    if not _check_origin():
        return jsonify(ok=False, msg="Nguồn không hợp lệ"), 403

    backend = (request.get_json(silent=True) or {}).get("backend") or ""
    backend = str(backend).strip().lower()
    if backend not in ALLOWED_BACKENDS:
        try:
            from src.analyzer import resolve_backend
            backend = resolve_backend()
        except Exception:
            backend = "local_api"

    if backend == "claude":
        has = bool(os.environ.get("ANTHROPIC_API_KEY"))
        return jsonify(state=("ready" if has else "nokey"), ok=has, backend=backend,
                       msg=("Có ANTHROPIC_API_KEY — Claude API sẵn sàng." if has else
                            "Thiếu ANTHROPIC_API_KEY trong Crawl Data/.env."))

    if backend != "gemini":
        from src import local_api as _lapi
        st = _lapi.status()
        if not st["has_key"]:
            return jsonify(state="nokey", ok=False, backend=backend,
                           msg="Chưa có LOCAL_API_KEY — điền vào ô 'API key' hoặc "
                               "Crawl Data/.env rồi thử lại.")
        if not st["up"]:
            return jsonify(state="nolocal", ok=False, backend=backend,
                           msg=f"Server AI local không phản hồi ở {st['url']}. "
                               f"Hãy bật server rồi thử lại.")
        return jsonify(state="ready", ok=True, backend=backend,
                       msg=f"Server AI local sẵn sàng ({st['url']}, model {st['model']}).")

    try:
        from src.gemini_cdp import cdp_available, GeminiCDP
    except Exception as exc:
        return jsonify(state="error", ok=False, msg=f"Không nạp được module CDP: {exc}"), 200
    if not cdp_available():
        return jsonify(state="nocdp", ok=False,
                       msg="Chrome CDP :9222 chưa mở. Bấm 'Mở Chrome cho Gemini' rồi thử lại.")
    try:
        with GeminiCDP() as g:
            ok, msg = g.preflight()
    except Exception as exc:
        msg = str(exc); ok = False
    low = (msg or "").lower()
    if ok:
        state = "ready"
    elif "chặn" in low or "/sorry/" in low or "captcha" in low or "1095" in low:
        state = "blocked"
    elif "đăng nhập" in low or "login" in low or "signin" in low:
        state = "login"
    else:
        state = "error"
    return jsonify(state=state, ok=ok, msg=(msg or "")[:240])


@app.post("/set_delay")
def set_delay():
    """Đặt độ trễ giữa 2 lần gọi Gemini (giây) — ghi vào config/gemini_delay.txt.
    Tiến trình phân tích đọc ĐỘNG file này nên chỉnh được NGAY GIỮA CHỪNG."""
    if not _check_origin():
        return jsonify(ok=False, msg="Nguồn không hợp lệ"), 403
    data = request.get_json(force=True) or {}
    try:
        d = max(0.0, min(120.0, float(data.get("delay"))))
    except (TypeError, ValueError):
        return jsonify(ok=False, msg="Giá trị delay không hợp lệ"), 400
    try:
        p = ROOT / "config" / "gemini_delay.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(d), encoding="utf-8")
    except Exception as exc:
        return jsonify(ok=False, msg=str(exc)[:120]), 500
    return jsonify(ok=True, delay=d)


@app.post("/set_local_api_key")
def set_local_api_key():
    """Ghi LOCAL_API_KEY vào Crawl Data/.env — nguồn key DÙNG CHUNG cho cả 4 dự án.

    Các client local_api (Python & Node) đều đọc env trước, rồi mới tới file này,
    nên lưu 1 lần là gateway :9999, bảng giá :5555 và EconoLens :3000 cùng dùng
    được. Chỉ ghi/sửa đúng dòng LOCAL_API_KEY, giữ nguyên phần còn lại của .env."""
    if not _check_origin():
        return jsonify(ok=False, msg="Nguồn không hợp lệ"), 403
    key = str((request.get_json(force=True) or {}).get("apikey", "")).strip()
    if not key or len(key) > 400 or any(c in key for c in "\r\n"):
        return jsonify(ok=False, msg="API key không hợp lệ"), 400
    env_path = ROOT / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
        for i, ln in enumerate(lines):
            if ln.strip().startswith("LOCAL_API_KEY="):
                lines[i] = f"LOCAL_API_KEY={key}"
                break
        else:
            lines.append(f"LOCAL_API_KEY={key}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as exc:
        return jsonify(ok=False, msg=str(exc)[:120]), 500
    # Tiến trình hiện tại dùng ngay, không cần restart dashboard.
    os.environ["LOCAL_API_KEY"] = key
    return jsonify(ok=True)


@app.get("/tasks")
def tasks():
    return jsonify({k: v[1] for k, v in TASKS.items()})


@app.get("/api/analysis_status")
def api_analysis_status():
    group = (request.args.get("group") or "VN30").strip().upper()
    try:
        from src import board, storage
        conn = storage.connect()
        try:
            if group == "ALL":
                syms = [r[0] for r in conn.execute("SELECT DISTINCT symbol FROM companies").fetchall()]
                if not syms:
                    syms = board.resolve_symbols(group)
            else:
                syms = board.resolve_symbols(group)
                
            done_ai = {r[0] for r in conn.execute("SELECT symbol FROM ai_analysis")}
            done_fin = storage.get_done(conn, "financials")
            done_co = storage.get_done(conn, "company")

            total = len(syms)
            sym_set = set(syms)
            analyzed_cnt = len(sym_set & done_ai)
            remaining_ai = total - analyzed_cnt
            fin_cnt = len(sym_set & done_fin)
            co_cnt = len(sym_set & done_co)
        finally:
            conn.close()

        return jsonify(
            ok=True,
            group=group,
            total=total,
            analyzed=analyzed_cnt,
            remaining_ai=remaining_ai,
            crawled_fin=fin_cnt,
            crawled_co=co_cnt,
        )
    except Exception as exc:
        return jsonify(ok=False, msg=str(exc)[:200]), 500



@app.get("/api/group_members")
def api_group_members():
    """Danh sách mã thuộc 1 nhóm (để lọc trang phân tích theo mục)."""
    from src import board
    group = (request.args.get("group") or "VN30").strip().upper()
    try:
        if group == "ALL":
            syms = sorted(set(board.group_symbols("HOSE")) | set(board.group_symbols("HNX"))
                          | set(board.group_symbols("UPCOM")))
        else:
            syms = board.group_symbols(group)
        return jsonify(ok=True, group=group, symbols=list(syms))
    except Exception as exc:
        return jsonify(ok=False, msg=str(exc)[:120]), 500


_compare_lock = threading.Lock()


@app.get("/api/compare")
def api_compare():
    a = (request.args.get("a") or "").strip().upper()
    b = (request.args.get("b") or "").strip().upper()
    if not a or not b or a == b:
        return jsonify(ok=False, msg="Cần 2 mã khác nhau"), 400
    if not _valid_sym(a) or not _valid_sym(b):
        return jsonify(ok=False, msg="Mã không hợp lệ"), 400
    if not _compare_lock.acquire(blocking=False):
        return jsonify(ok=False, msg="Đang có một so sánh khác chạy, thử lại sau."), 409
    try:
        from src import storage
        from src.analyzer import compare_two, close_gemini
        conn = storage.connect()
        try:
            result = compare_two(conn, a, b)
        finally:
            conn.close()
            if (os.environ.get("AI_BACKEND") or "").lower() == "gemini":
                close_gemini()
        # _scrub() bỏ "winner"; riêng route so sánh còn phải bỏ "verdict" vì
        # schema của compare_two() định nghĩa nó là "nên chọn mã nào và vì sao"
        # — tức khuyến nghị chọn mã. (CHỈ áp cho compare: "verdict" ở phân tích
        # 1 mã là kết luận mô tả tình trạng doanh nghiệp, ngoài phạm vi.)
        return jsonify(ok=True, result=_scrub(result, extra_keys=("verdict",)))
    except Exception as exc:
        return jsonify(ok=False, msg=str(exc)[:200]), 500
    finally:
        _compare_lock.release()


# ------------------------------------------------------------------ manifest & debug (minh bạch dữ liệu)
COMPANIES_DIR = ROOT / "companies"


@app.get("/api/manifest/<sym>")
def api_manifest(sym):
    """Bảng kê 'crawl được gì' cho 1 mã: nguồn nào có/thiếu, số bản ghi, %."""
    sym = (sym or "").strip().upper()
    if not _valid_sym(sym):
        return jsonify(ok=False, msg="Mã không hợp lệ"), 400
    try:
        from src import manifest
        # build tại chỗ (không ghi) để luôn phản ánh dữ liệu mới nhất
        return jsonify(ok=True, manifest=manifest.build(sym, write=False))
    except Exception as exc:
        return jsonify(ok=False, msg=str(exc)[:200]), 500


@app.get("/api/debug/<sym>")
def api_debug_index(sym):
    """Danh sách các lượt phân tích AI đã lưu (prompt/raw) cho 1 mã."""
    sym = (sym or "").strip().upper()
    if not _valid_sym(sym):
        return jsonify(ok=False, msg="Mã không hợp lệ"), 400
    idx_path = COMPANIES_DIR / sym / "analysis" / "debug" / "index.json"
    if not idx_path.exists():
        return jsonify(ok=True, sym=sym, passes=[], msg="Chưa có debug (chạy phân tích AI để sinh)")
    try:
        data = json.loads(idx_path.read_text(encoding="utf-8"))
        data.pop("ok", None)   # tránh đụng khóa 'ok' của API (file debug có field ok riêng)
        return jsonify(ok=True, **data)
    except Exception as exc:
        return jsonify(ok=False, msg=str(exc)[:200]), 500


_RE_KEY = re.compile(r"^[a-z_]{2,20}$")


@app.get("/api/debug/<sym>/<key>")
def api_debug_pass(sym, key):
    """Chi tiết 1 lượt: prompt đầy đủ + raw text AI trả về + JSON đã parse."""
    sym = (sym or "").strip().upper()
    key = (key or "").strip().lower()
    if not _valid_sym(sym):
        return jsonify(ok=False, msg="Mã không hợp lệ"), 400
    if not _RE_KEY.match(key):
        return jsonify(ok=False, msg="Khóa lượt không hợp lệ"), 400
    p = COMPANIES_DIR / sym / "analysis" / "debug" / f"{key}.json"
    if not p.exists():
        return jsonify(ok=False, msg="Không có lượt này"), 404
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # File debug lưu field "ok" (lượt AI thành công hay không) — đổi tên để
        # không đụng khóa 'ok' báo trạng thái API (bug: jsonify multiple values).
        data["pass_ok"] = data.pop("ok", None)
        return jsonify(ok=True, **data)
    except Exception as exc:
        return jsonify(ok=False, msg=str(exc)[:200]), 500


# ------------------------------------------------------------------ xem nội dung nguồn
@app.get("/api/source/<sym>/<key>")
def api_source_content(sym, key):
    """Nội dung THẬT bên trong 1 nguồn dữ liệu đã crawl (cho user soi trên UI).

    key = khóa nguồn trong manifest (_SOURCES). Trả:
    - rows: list bản ghi (records/items/dòng JSONL), cắt tối đa 400 dòng;
    - data: object gốc khi nguồn không phải dạng list (profile, snapshot...).
    """
    sym = (sym or "").strip().upper()
    key = (key or "").strip().lower()
    if not _valid_sym(sym):
        return jsonify(ok=False, msg="Mã không hợp lệ"), 400
    from src.manifest import _SOURCES
    smap = {k: (rel, label) for k, rel, label in _SOURCES}
    if key not in smap:
        return jsonify(ok=False, msg="Nguồn không hợp lệ"), 400
    rel, label = smap[key]
    p = COMPANIES_DIR / sym / rel
    if not p.exists():
        return jsonify(ok=False, msg="Chưa có dữ liệu nguồn này"), 404
    try:
        if p.suffix == ".jsonl":
            rows = []
            for ln in p.read_text(encoding="utf-8").splitlines():
                if ln.strip():
                    try:
                        rows.append(json.loads(ln))
                    except Exception:
                        pass
            total, meta = len(rows), {}
        else:
            data = json.loads(p.read_text(encoding="utf-8"))
            rows = None
            if isinstance(data, dict):
                for k in ("records", "items"):
                    if isinstance(data.get(k), list):
                        rows = data[k]
                        break
                meta = {k: v for k, v in data.items()
                        if not isinstance(v, (list, dict))}
            if rows is None:
                # Nguồn dạng object (profile/snapshot/ai_analysis).
                # KHÔNG trả nguyên văn: profile.json chứa khuyến nghị CTCK
                # (rating BUY, target_price, upside_to_target_percent) — phải
                # qua allow-list; các nguồn object khác qua scrub tên khoá.
                if key == "profile":
                    data = _safe_profile(data)
                else:
                    data = _scrub(data)
                return jsonify(ok=True, sym=sym, key=key, label=label, path=rel,
                               kind="object", data=data)
            total = len(rows)
        return jsonify(ok=True, sym=sym, key=key, label=label, path=rel,
                       kind="table", total=total, truncated=total > 400,
                       meta=_scrub(meta), rows=_scrub(rows[:400]))
    except Exception as exc:
        return jsonify(ok=False, msg=str(exc)[:200]), 500


# ------------------------------------------------------------------ chọn mã
def _load_symbols() -> list[dict]:
    if not SYMBOLS_JSON.exists():
        return []
    try:
        data = json.loads(SYMBOLS_JSON.read_text(encoding="utf-8"))
        return data.get("symbols", [])
    except Exception:
        return []


@app.get("/symbols")
def symbols():
    q = (request.args.get("q") or "").strip().lower()
    limit = int(request.args.get("limit", 60))
    syms = _load_symbols()
    if q:
        syms = [s for s in syms
                if q in str(s.get("symbol", "")).lower()
                or q in str(s.get("organ_name", "")).lower()]
    return jsonify(total=len(syms), items=syms[:limit])


@app.get("/tickers")
def get_tickers():
    out = []
    if COMPANIES_TXT.exists():
        for ln in COMPANIES_TXT.read_text(encoding="utf-8").splitlines():
            ln = ln.strip().upper()
            if ln and not ln.startswith("#"):
                out.append(ln)
    return jsonify(tickers=out)


@app.post("/tickers")
def set_tickers():
    if not _check_origin():
        return jsonify(ok=False, msg="Nguồn không hợp lệ"), 403
    data = request.get_json(force=True)
    tickers = [str(t).strip().upper() for t in data.get("tickers", []) if str(t).strip()]
    # khử trùng, giữ thứ tự
    seen, uniq = set(), []
    for t in tickers:
        if t not in seen:
            seen.add(t); uniq.append(t)
    body = ("# Danh sách mã cần crawl. Mỗi dòng 1 mã. Dòng bắt đầu bằng # bị bỏ qua.\n"
            + "\n".join(uniq) + "\n")
    COMPANIES_TXT.parent.mkdir(parents=True, exist_ok=True)
    COMPANIES_TXT.write_text(body, encoding="utf-8")
    return jsonify(ok=True, count=len(uniq))


@app.get("/app/")
@app.get("/app/<path:fn>")
def comparison(fn="user.html"):        # trang user mới làm mặc định
    # /app/FPT — không có đuôi file mà là mã CK → trang chi tiết 1 mã, hiện
    # TOÀN BỘ những gì AI trả về (4 lượt + tổng hợp + prompt gốc từng lượt).
    if "." not in fn and _valid_sym(fn.upper()):
        return send_from_directory(WEB_DIR, "symbol.html")
    return send_from_directory(WEB_DIR, fn)


@app.get("/")
def index():
    return render_template_string(PANEL)


REFRESH_COOLDOWN = 300        # giây — chống spam refresh 1 mã (5 phút)
_refresh_lock = threading.Lock()
_refreshing: set = set()      # các mã đang refresh (tránh chạy song song cùng mã)


def _last_analysis_ts(sym: str):
    """Thời điểm phân tích gần nhất của mã (epoch giây) hoặc None."""
    try:
        from datetime import datetime
        c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=2)
        row = c.execute("SELECT updated_at FROM ai_analysis WHERE symbol=?",
                        (sym.upper(),)).fetchone()
        c.close()
        if row and row[0]:
            return datetime.fromisoformat(row[0]).timestamp()
    except Exception:
        pass
    return None


@app.get("/api/refresh_stream")
def refresh_stream():
    import time as _t
    sym = (request.args.get("sym") or "").strip().upper()
    if not sym:
        return jsonify(ok=False, msg="Thiếu mã"), 400
    if not _valid_sym(sym):
        return jsonify(ok=False, msg="Mã không hợp lệ"), 400

    # Giới hạn 5 phút/mã (chống spam).
    ts = _last_analysis_ts(sym)
    if ts is not None:
        elapsed = _t.time() - ts
        if elapsed < REFRESH_COOLDOWN:
            wait = int(REFRESH_COOLDOWN - elapsed)
            return jsonify(ok=False, cooldown=wait,
                           msg=f"Vừa phân tích {int(elapsed)}s trước. Chờ {wait}s nữa để tránh spam."), 429

    with _refresh_lock:
        if sym in _refreshing:
            return jsonify(ok=False, msg=f"{sym} đang được làm mới."), 409
        _refreshing.add(sym)

    def generate():
        from src import storage
        from src.runner import guard
        from src.crawler_financials import crawl_one as c1
        from src.crawler_company import crawl_one as c2
        from src.analyzer import analyze_one, resolve_backend
        import scripts.p5_export as p5
        backend = resolve_backend()
        t_all = _t.time()
        try:
            yield " " * 4096 + "\n"        # chống đệm của Werkzeug
            yield "data: Bắt đầu lấy dữ liệu thực...\n\n"
            conn = storage.connect()
            yield "data: 📊 Đang cào báo cáo tài chính (năm + quý)...\n\n"
            t0 = _t.time()
            try: guard(c1, conn, sym)
            except Exception as e: yield f"data: ⚠️ Tài chính lỗi: {str(e)[:60]}\n\n"
            yield f"data: ✓ Tài chính xong ({_t.time() - t0:.0f}s)\n\n"

            yield "data: 📰 Đang cào hồ sơ, cổ đông, tin tức, giá...\n\n"
            t0 = _t.time()
            try: guard(c2, conn, sym)
            except Exception as e: yield f"data: ⚠️ Hồ sơ lỗi: {str(e)[:60]}\n\n"
            yield f"data: ✓ Hồ sơ xong ({_t.time() - t0:.0f}s)\n\n"

            yield (f"data: 🤖 AI đang phân tích lại ({backend}) — 5 lượt, "
                   f"thường mất 2–3 phút...\n\n")
            t0 = _t.time()
            try:
                res = analyze_one(conn, sym, backend)
                yield (f"data: ✓ AI xong ({res.get('duration_s') or round(_t.time() - t0)}s"
                       f" · {res.get('n_passes') or 1} lượt)\n\n")
            except Exception as e:
                yield f"data: ⚠️ AI lỗi: {str(e)[:60]}\n\n"
            conn.close()

            # Chỉ xuất lại ĐÚNG mã này (trước đây xuất cả 576 mã → ~12 phút chờ vô ích).
            yield "data: 💾 Cập nhật giao diện...\n\n"
            t0 = _t.time()
            try: p5.main([sym])
            except Exception: pass
            yield f"data: ✓ Cập nhật giao diện xong ({_t.time() - t0:.1f}s)\n\n"
            yield f"data: 🏁 Tổng cộng {_t.time() - t_all:.0f}s\n\n"
            yield "data: DONE\n\n"
        except Exception as e:
            yield f"data: LỖI: {str(e)}\n\n"
        finally:
            with _refresh_lock:
                _refreshing.discard(sym)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

PANEL = r"""<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Crawl Data — Bảng điều khiển</title>
 <style>
  :root{
    --bg:#0b1120; --bg2:#151e2f; --panel:#151e2f; --panel-hover:#1e293b; --line:#273752; --line-soft:rgba(255,255,255,0.05);
    --text:#f8fafc; --muted:#94a3b8; --soft:#64748b;
    --accent:#00d8ff; --accent-hover:#00b4d8; --accent-bg:rgba(0, 216, 255, 0.15);
    --ok:#10b981; --ok-txt:#34d399; --run:#f59e0b; --run-txt:#fbbf24; --err:#ef4444; --err-txt:#f87171;
    --r:8px; --r-lg:12px; --glass:blur(16px);
  }
  *{box-sizing:border-box}
  html,body{height:100%}
  body{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,-apple-system,sans-serif;margin:0;padding:0;
    display:flex;flex-direction:column;height:100vh;overflow:hidden;
    -webkit-font-smoothing:antialiased;
    background-image:radial-gradient(circle at top center, rgba(59,130,246,0.08), transparent 600px)}
  ::-webkit-scrollbar{width:6px;height:6px}
  ::-webkit-scrollbar-track{background:transparent}
  ::-webkit-scrollbar-thumb{background:#3f3f46;border-radius:6px}
  ::-webkit-scrollbar-thumb:hover{background:#52525b}
  
  /* ---- header ---- */
  header{padding:14px 24px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:16px;
    background:rgba(9, 9, 11, 0.8);backdrop-filter:var(--glass);flex:none;z-index:40}
  h1{font-size:16px;margin:0;font-weight:600;display:flex;align-items:center;gap:10px;color:var(--text)}
  .status{font-size:11px;padding:4px 10px;border-radius:20px;font-weight:600;display:inline-flex;
    align-items:center;gap:6px;border:1px solid transparent;text-transform:uppercase;letter-spacing:0.5px}
  .s-idle{background:#27272a;color:var(--muted);border-color:#3f3f46}
  .s-run{background:rgba(245, 158, 11, 0.1);color:var(--run-txt);border-color:rgba(245, 158, 11, 0.2)}
  .s-ok{background:rgba(34, 197, 94, 0.1);color:var(--ok-txt);border-color:rgba(34, 197, 94, 0.2)}
  .s-err{background:rgba(239, 68, 68, 0.1);color:var(--err-txt);border-color:rgba(239, 68, 68, 0.2)}
  
  /* ---- layout ---- */
  .wrap{display:flex;flex:1;overflow:hidden;min-height:0}
  .side{width:360px;max-width:360px;flex:0 0 360px;border-right:1px solid var(--line);overflow-y:auto;overflow-x:hidden;padding:16px;
    background:rgba(9, 9, 11, 0.5);backdrop-filter:var(--glass)}
  .main{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0;background:var(--bg)}
  .sec{margin-bottom:20px;background:var(--panel);border:1px solid var(--line);
    border-radius:var(--r-lg);padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.2)}
  .sec h3{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;
    font-weight:600;margin:0 0 16px;display:flex;align-items:center;gap:8px}
  
  /* ---- buttons ---- */
  button{display:block;width:100%;text-align:left;background:var(--bg2);
    border:1px solid var(--line);color:var(--text);padding:10px 14px;border-radius:var(--r);margin-bottom:8px;cursor:pointer;
    font-size:13px;font-weight:500;transition:all .15s ease}
  button:last-child{margin-bottom:0}
  button:hover:not(:disabled){border-color:#3f3f46;background:var(--panel-hover)}
  button:active:not(:disabled){transform:scale(0.99)}
  button:disabled{opacity:.5;cursor:not-allowed}
  button b{color:var(--text);font-weight:600;font-size:13px;margin-right:6px}
  button small{display:block;color:var(--muted);font-size:11px;margin-top:4px;font-weight:400}
  
  .btn-primary{background:var(--accent);color:#0b1120;border-color:var(--accent-hover);text-align:center}
  .btn-primary:hover:not(:disabled){background:var(--accent-hover);border-color:var(--accent)}
  .btn-primary b{color:#0b1120;font-weight:700}
  .btn-primary small{color:rgba(11, 17, 32, 0.7)}
  
  .row{display:flex;gap:10px;align-items:center;margin-bottom:12px;font-size:13px;color:var(--muted)}
  .row:last-child{margin-bottom:0}
  
  /* Inputs */
  select,input{background:var(--bg);border:1px solid var(--line);color:var(--text);padding:8px 10px;
    border-radius:6px;font-size:13px;outline:none;transition:border-color .15s;flex:1;min-width:0}
  select:focus,input:focus{border-color:var(--accent)}
  select{cursor:pointer;appearance:none;background-image:url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3E%3Cpath stroke='%23a1a1aa' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='m6 8 4 4 4-4'/%3E%3C/svg%3E");background-position:right 8px center;background-repeat:no-repeat;background-size:16px;padding-right:28px}
  input[type=checkbox]{flex:none;width:16px;height:16px;accent-color:var(--accent);cursor:pointer;border-radius:4px}
  label{cursor:pointer;display:inline-flex;align-items:center;gap:8px;user-select:none;transition:color .2s;font-size:13px}
  label:hover{color:var(--text)}
  
  /* ---- stats ---- */
  .stats{display:flex;flex-wrap:nowrap;overflow-x:auto;gap:16px;padding:16px 24px;border-bottom:1px solid var(--line);background:var(--bg);flex:none}
  .stat{background:var(--panel);border:1px solid var(--line);border-radius:var(--r-lg);padding:16px;min-width:140px;flex:0 0 auto;
    box-shadow:0 1px 2px rgba(0,0,0,0.1)}
  .stat .v{font-size:20px;font-weight:600;font-variant-numeric:tabular-nums;letter-spacing:-0.5px;color:var(--text)}
  .stat .k{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-top:4px;font-weight:500}
  
  /* ---- progress ---- */
  .prog{padding:12px 24px 16px;border-bottom:1px solid var(--line);background:var(--panel);flex:none}
  .pbar{height:6px;background:var(--bg);border-radius:6px;overflow:hidden;border:1px solid var(--line);position:relative}
  .pfill{height:100%;width:0;border-radius:6px;background:var(--accent);transition:width .3s ease}
  .pmeta{display:flex;justify-content:space-between;font-size:12px;margin-bottom:8px;color:var(--muted);flex-wrap:wrap;gap:8px}
  .pmeta b{color:var(--text);font-weight:600;font-variant-numeric:tabular-nums} 
  .cur{color:var(--accent);font-weight:500}
  
  /* ---- grid ---- */
  .grid{padding:0;overflow:auto;max-height:40vh;flex:none;border-bottom:1px solid var(--line);background:var(--bg)}
  .dtable{width:100%;border-collapse:separate;border-spacing:0;font-size:12px;font-variant-numeric:tabular-nums;}
  .dtable th,.dtable td{padding:8px 16px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
  .dtable th:first-child,.dtable td:first-child{text-align:left;position:sticky;left:0;background:var(--panel)}
  .dtable th{color:var(--muted);font-weight:500;position:sticky;top:0;background:var(--panel);text-align:right;
    font-size:11px;text-transform:uppercase;letter-spacing:0.5px;z-index:1}
  .dtable th:first-child{z-index:3}
  .dtable tbody tr:hover td{background:var(--panel-hover)}
  .dtable tbody tr:hover td:first-child{background:var(--panel-hover)}
  .dtable td.sym{color:var(--text);font-weight:600}
  .dtable td.muted{color:var(--soft)}
  .dtable td.c-ok2{color:var(--ok-txt)} .dtable td.c-err2{color:var(--err-txt)}
  .dtable tr.r-run td{background:var(--accent-bg)!important}
  
  /* ---- chips ---- */
  .chip{font-size:10px;font-weight:600;padding:2px 8px;border-radius:12px;letter-spacing:0.5px;
    display:inline-flex;align-items:center;gap:4px;text-transform:uppercase}
  .c-ok{background:rgba(34,197,94,0.1);color:var(--ok-txt);border:1px solid rgba(34,197,94,0.2)}
  .c-error{background:rgba(239,68,68,0.1);color:var(--err-txt);border:1px solid rgba(239,68,68,0.2)}
  .c-partial{background:rgba(245,158,11,0.1);color:var(--run-txt);border:1px solid rgba(245,158,11,0.2)}
  .c-run{background:var(--accent-bg);color:var(--accent);border:1px solid rgba(59,130,246,0.3)}
  
  /* ---- log ---- */
  .logwrap{flex:1;display:flex;flex-direction:column;min-height:0;overflow:hidden;background:var(--bg)}
  details.logwrap[open]{display:flex;flex-direction:column;flex:1;min-height:0;overflow:hidden}
  .logwrap summary{cursor:pointer;padding:10px 24px;color:var(--muted);font-size:12px;user-select:none;
    font-weight:600;list-style:none;display:flex;align-items:center;gap:12px;background:var(--panel);border-bottom:1px solid var(--line);flex:none}
  .logwrap summary:hover{color:var(--text)}
  .logwrap summary::-webkit-details-marker{display:none}
  .log{flex:1;margin:0;padding:16px 24px;overflow:auto;min-height:0;
    font-family:"JetBrains Mono",Consolas,monospace;font-size:12px;line-height:1.5;white-space:pre-wrap;color:#d1d5db}
  .log .cmd{color:#60a5fa} .log .end{color:#34d399} .log .err{color:#f87171}
  
  /* ---- bottom bar ---- */
  .bar{padding:12px 24px;border-top:1px solid var(--line);display:flex;gap:12px;align-items:center;background:var(--panel)}
  .stop{width:auto;background:rgba(239,68,68,0.1);border-color:rgba(239,68,68,0.2);color:var(--err-txt);margin:0;}
  .stop:hover:not(:disabled){background:rgba(239,68,68,0.2);border-color:var(--err)}
  .open{width:auto;background:var(--bg2);margin:0;}
  .spin{width:12px;height:12px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;
    display:inline-block;animation:r .75s linear infinite;vertical-align:-2px}
  @keyframes r{to{transform:rotate(360deg)}}
  .empty{color:var(--muted);font-size:13px;padding:32px;text-align:center}
  
  /* ---- toast ---- */
  #toasts{position:fixed;right:24px;bottom:24px;z-index:100;display:flex;flex-direction:column;gap:8px;pointer-events:none}
  .toast{background:var(--panel);border:1px solid var(--line);
    color:var(--text);padding:12px 16px;border-radius:var(--r);font-size:13px;max-width:340px;
    box-shadow:0 4px 6px rgba(0,0,0,0.1);animation:tin .2s ease-out;
    display:flex;align-items:flex-start;gap:10px;pointer-events:auto}
  .toast::before{content:"";display:block;width:3px;border-radius:3px;align-self:stretch}
  .toast.ok::before{background:var(--ok)} .toast.err::before{background:var(--err)} .toast.warn::before{background:var(--run)}
  .toast.info::before{background:var(--accent)}
  @keyframes tin{from{transform:translateY(16px);opacity:0}to{transform:translateY(0);opacity:1}}
  .logbtn{width:auto;margin:0;padding:4px 10px;font-size:11px;font-weight:500;border-radius:6px;background:var(--bg);border:1px solid var(--line)}
  .logbtn:hover{background:var(--panel-hover)}
  .logbtn.active{background:var(--accent-bg);color:var(--accent);border-color:rgba(59,130,246,0.3)}
  /* Highlight sections for focus */
  .sec.highlight{background:linear-gradient(180deg, rgba(59, 130, 246, 0.05), transparent), var(--panel); border-color:rgba(59, 130, 246, 0.2)}
  .sec.highlight h3{color:var(--accent)}
  
  @media(max-width:900px){
    .wrap{flex-direction:column;height:auto}
    .side{width:100%;max-width:100%;flex:none;border-right:none;border-bottom:1px solid var(--line);max-height:50vh}
    .main{height:auto; display: flex; flex-direction: column; order: -1} 
    .grid{max-height:30vh}
  }
  @media(max-width:768px){
    header{padding:10px 14px;flex-wrap:wrap}
    .stats{padding:10px 14px;gap:8px}
    .stat{min-width:110px;padding:10px}
    .stat .v{font-size:16px}
    .prog{padding:10px 14px}
    .side{padding:12px;max-height:60vh}
    .bar{padding:8px 14px;flex-wrap:wrap}
  }
</style></head><body>
<div id="toasts"></div>
<div class="wrap">
  <div class="side">
    <!-- TIER 0: SYSTEM HEALTH & AI CONFIG -->
    <div class="sec">
      <h3 style="margin-bottom:12px;color:var(--text)">🩺 TIER 0: TRẠNG THÁI HỆ THỐNG & CẤU HÌNH AI
        <button class="logbtn" id="btnGem" onclick="checkGemini(event)" style="margin-left:auto">Kiểm tra</button>
      </h3>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
        <div style="background:var(--bg);padding:8px 10px;border-radius:6px;border:1px solid var(--line);display:flex;flex-direction:column;gap:4px">
          <span style="font-size:11px;color:var(--muted)">Local API (:4000)</span><b id="h_local" style="color:var(--accent);font-size:13px;word-break:break-all">—</b></div>
        <div style="background:var(--bg);padding:8px 10px;border-radius:6px;border:1px solid var(--line);display:flex;flex-direction:column;gap:4px">
          <span style="font-size:11px;color:var(--muted)">Kênh AI</span><b id="h_gemini" style="color:var(--muted);font-size:13px;word-break:break-all">—</b></div>
        <div style="background:var(--bg);padding:8px 10px;border-radius:6px;border:1px solid var(--line);display:flex;flex-direction:column;gap:4px">
          <span style="font-size:11px;color:var(--muted)">Backend</span><b id="h_backend" style="color:var(--muted);font-size:13px;word-break:break-all">—</b></div>
        <div style="background:var(--bg);padding:8px 10px;border-radius:6px;border:1px solid var(--line);display:flex;flex-direction:column;gap:4px">
          <span style="font-size:11px;color:var(--muted)">Database</span><b id="h_db" style="color:var(--muted);font-size:13px;word-break:break-all">—</b></div>
        <div style="background:var(--bg);padding:8px 10px;border-radius:6px;border:1px solid var(--line);display:flex;flex-direction:column;gap:4px;grid-column:1/-1">
          <span style="font-size:11px;color:var(--muted)">CDP (Chrome) — chỉ dùng khi chọn backend Gemini</span><b id="h_cdp" style="color:var(--muted);font-size:13px;word-break:break-all">—</b></div>
      </div>
      <div class="row" style="margin-top:12px;margin-bottom:8px">Nguồn AI:
        <select id="backend"><option value="local_api">Local API (mặc định)</option>
        <option value="gemini">Gemini (CDP)</option>
        <option value="claude">Claude API</option></select>
      </div>
      <div class="row" style="margin-bottom:8px">API Key:
        <input type="password" id="apikey" placeholder="(để trống = dùng key trong .env)">
        <button class="logbtn" onclick="saveKey(event)" title="Lưu vào Crawl Data/.env để mọi service dùng chung">Lưu</button>
      </div>
      <div style="display:flex;gap:8px;margin-bottom:8px">
        <button onclick="run('launch')" style="margin:0;flex:1;text-align:center;padding:8px"><b>Mở Chrome</b></button>
        <button onclick="run('test_gemini')" style="margin:0;flex:1;text-align:center;padding:8px"><b>Test API</b></button>
      </div>
      <div class="row" style="margin-top:4px;margin-bottom:0">
        <span>Delay AI (s)</span>
        <span style="display:flex;gap:4px;flex:1"><input type="number" id="delayInput" min="0" max="120" step="1">
        <button class="logbtn" onclick="setDelay(event)">Lưu</button></span>
      </div>
    </div>

    <!-- TIER 1: P0 DISCOVERY & SYMBOL SELECTION -->
    <div class="sec">
      <h3 style="color:var(--text)">🔍 TIER 1: KHÁM PHÁ & CHỌN MÃ</h3>
      <button onclick="run('p0')"><b>P0 Lấy DS Mã</b><small>Cập nhật toàn bộ list mã thị trường</small></button>
      <button onclick="openPicker()"><b>📋 Chọn mã thủ công</b><small id="tickcount">Đang chọn: …</small></button>
    </div>

    <!-- TIER 2 & 3: DATA INGESTION -->
    <div class="sec">
      <h3 style="color:var(--text)">📥 TIER 2 & 3: CRAWL DỮ LIỆU</h3>
      <div class="row">Nhóm:
        <select id="p3group" onchange="updateGroupStatus()">
          <option value="VN30">VN30 (30 mã)</option>
          <option value="VN100">VN100 (100 mã)</option>
          <option value="HOSE">HOSE (~300)</option>
          <option value="HNX">HNX (~250)</option>
          <option value="UPCOM">UPCOM (~200)</option>
          <option value="ALL" selected>TẤT CẢ</option>
          <option value="CUSTOM">Mã đã chọn</option>
        </select>
      </div>
      <div class="row" style="gap:12px">
        <label style="flex:none"><input type="checkbox" id="p3recrawl"> TỪ ĐẦU</label>
        <div style="display:flex;align-items:center;gap:6px;flex:1;min-width:0">
          <span style="flex:none">Limit:</span> 
          <input id="p3limit" type="number" placeholder="∞" style="flex:1;min-width:0;width:100%">
        </div>
      </div>
      <button class="btn-primary" onclick="runP3Group()">
        <b>▶ TỰ ĐỘNG CRAWL (P3)</b><small>Chạy full tiến trình lấy dữ liệu</small></button>
      
      <details style="margin-top:12px;border-top:1px dashed var(--line);padding-top:12px">
        <summary style="cursor:pointer;font-size:12px;font-weight:600;color:var(--muted);outline:none;user-select:none">▾ Nâng cao (Chạy tay từng bước)</summary>
        <div style="margin-top:10px">
          <button onclick="run('p1')"><b>P1 BCTC & Giá</b><small>Crawl tài chính & dòng tiền mã mẫu</small></button>
          <button onclick="run('p2')"><b>P2 Tin tức & Sự kiện</b><small>Crawl hồ sơ & tin tức mã mẫu</small></button>
        </div>
      </details>
    </div>

    <!-- TIER 4: P4 AI FINANCIAL ANALYSIS -->
    <div class="sec highlight">
      <h3 style="color:var(--accent)">🧠 TIER 4: PHÂN TÍCH AI (P4)</h3>
      <div class="row">Mục tiêu:
        <select id="p4group" onchange="updateGroupStatus()">
          <option value="VN30">VN30 (30 mã)</option>
          <option value="VN100">VN100 (100 mã)</option>
          <option value="HOSE">HOSE (~300)</option>
          <option value="HNX">HNX (~250)</option>
          <option value="UPCOM">UPCOM (~200)</option>
          <option value="ALL">TẤT CẢ đã crawl</option>
          <option value="CUSTOM" selected>Mã thủ công</option>
        </select>
      </div>
      <div class="row">Limit: <input id="p4limit" type="number" placeholder="∞"></div>
      
      <div id="ai_status_badge" style="margin:12px 0;padding:8px 10px;background:var(--bg);border:1px solid var(--line);border-radius:6px;font-size:12px;color:var(--accent)">
        ⏳ Đang tải số liệu nhóm...
      </div>

      <button class="btn-primary" onclick="runP4Resume()">
        <b>▶ BẮT ĐẦU PHÂN TÍCH</b><small>Bỏ qua mã đã xong, chạy tiếp</small>
      </button>
      <button onclick="runP4Reanalyze()">
        <b>🔄 Chạy lại từ đầu</b><small>Phân tích đè lên dữ liệu cũ</small>
      </button>
    </div>

    <!-- TIER 5: P5 PUBLISHING & UI DASHBOARD LAUNCH -->
    <div class="sec">
      <h3 style="color:var(--text)">📊 TIER 5: XUẤT BẢN & MỞ UI (P5)</h3>
      <button onclick="run('p5')"><b>P5 Xuất file JSON</b><small>Cập nhật dữ liệu cho giao diện người dùng</small></button>
      <button onclick="window.open('/app/', '_blank')" style="border-color:var(--ok);background:rgba(34,197,94,0.1)">
        <b style="color:var(--ok-txt)">🚀 MỞ BẢNG ĐIỀU KHIỂN (UI)</b>
      </button>
    </div>

    <!-- TIER 6: UNIFIED AUTOMATED PIPELINE -->
    <div class="sec" style="border-color:var(--accent);background:linear-gradient(180deg, rgba(0,216,255,0.08), transparent), var(--panel)">
      <h3 style="color:var(--accent)">⚡ TIER 6: PIPELINE TỰ ĐỘNG TOÀN DIỆN</h3>
      <div class="row">Nhóm:
        <select id="pgroup">
          <option value="VN30" selected>VN30 (30 mã)</option>
          <option value="VN100">VN100 (100 mã)</option>
          <option value="HOSE">HOSE (~300)</option>
          <option value="HNX">HNX (~250)</option>
          <option value="UPCOM">UPCOM (~200)</option>
          <option value="ALL">TẤT CẢ</option>
        </select>
      </div>
      <div class="row">
        <label style="flex:none"><input type="checkbox" id="preanalyze"> Chạy lại từ đầu (Reanalyze)</label>
      </div>
      <button class="btn-primary" onclick="runPipeline()" style="background:linear-gradient(135deg, #00d8ff, #3b82f6);color:#0b1120">
        <b>⚡ RUN PIPELINE (1-CLICK)</b><small>Chạy tự động toàn bộ 1 mạch (P1 → P2 → P4 → P5)</small>
      </button>
    </div>
  </div>
  <div class="main">
    <header>
      <h1>⚙️ Crawl Data — Bảng điều khiển</h1>
      <span id="status" class="status s-idle">● Rảnh</span>
      <span id="now" style="color:var(--muted);font-size:13px"></span>
      <span id="elapsed" style="color:var(--muted);font-size:13px;font-family:Consolas,monospace"></span>
    </header>
    <div class="stats" id="stats"></div>
    <div class="prog">
      <div class="pmeta">
        <span>Tiến độ: <b id="pstage">—</b> <span id="pcur" class="cur"></span></span>
        <span><b id="pnum">0/0</b> · <span style="color:var(--ok)">✓ <b id="pdone">0</b></span>
          · <span style="color:var(--err)">✗ <b id="perr">0</b></span> · <b id="ppct">0%</b></span>
      </div>
      <div class="pbar"><div id="pfill" class="pfill"></div></div>
    </div>
    <div class="grid" id="grid"><span class="empty">Chưa có mã nào. Bấm một bước crawl (P1/P2/P3/P4) để xem chi tiết từng mã.</span></div>
    <details class="logwrap" open>
      <summary style="display:flex;align-items:center;gap:10px">
        <span style="flex:1">▾ Log chi tiết</span>
        <button class="logbtn" id="btnErr" onclick="toggleErr(event)">Chỉ lỗi</button>
        <button class="logbtn" onclick="downloadLog(event)">Tải log</button>
      </summary>
      <pre id="log" class="log">Sẵn sàng.</pre>
    </details>
    <div class="bar">
      <button class="stop" onclick="stop()">■ Dừng</button>
      <button class="open" onclick="window.open('/app/','_blank')">↗ Phân tích</button>
      <span style="flex:1"></span>
      <label style="font-size:12px;color:var(--muted)"><input type="checkbox" id="autoscroll" checked> auto-scroll</label>
    </div>
  </div>
</div>
<div id="modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:50">
  <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:640px;max-width:94vw;
    height:78vh;background:var(--panel);border:1px solid var(--line);border-radius:12px;display:flex;flex-direction:column;overflow:hidden">
    <div style="padding:14px 18px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px">
      <b style="font-size:15px">📋 Chọn mã để crawl</b>
      <span id="selcount" style="color:var(--muted);font-size:12.5px"></span>
      <span style="flex:1"></span>
      <button onclick="closePicker()" style="width:auto;margin:0">✕ Đóng</button>
    </div>
    <div style="padding:12px 18px;display:flex;gap:10px;align-items:center">
      <input id="psearch" placeholder="Tìm mã hoặc tên công ty..." style="flex:1" oninput="searchSyms()">
      <button onclick="addTyped()" style="width:auto;margin:0">+ Thêm mã gõ tay</button>
    </div>
    <div style="display:flex;gap:0;flex:1;min-height:0">
      <div id="results" style="flex:1;overflow:auto;padding:6px 18px;border-right:1px solid var(--line)"></div>
      <div style="width:230px;overflow:auto;padding:10px 14px">
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;margin-bottom:8px">Đang chọn (<span id="chcount">0</span>)</div>
        <div id="chosen" style="display:flex;flex-wrap:wrap;gap:5px"></div>
      </div>
    </div>
    <div style="padding:12px 18px;border-top:1px solid var(--line);display:flex;gap:10px;align-items:center">
      <button onclick="clearChosen()" class="stop" style="margin:0">Xóa hết</button>
      <span style="flex:1"></span>
      <button onclick="saveTickers()" class="open" style="margin:0;font-weight:700">💾 Lưu danh sách</button>
    </div>
  </div>
</div>

<script>
let since=0, timer=null, TASKS={}, CHOSEN=new Set();
let LOG_LINES=[], errOnly=false, startedAt=null, elapsedTimer=null;
const MAX_DOM_LINES=500;      // giữ tối đa 500 dòng trong DOM
const $=id=>document.getElementById(id);
fetch('/tasks').then(r=>r.json()).then(t=>TASKS=t);
refreshStats(); setInterval(refreshStats,4000);
loadTickerCount();
updateGroupStatus(); setInterval(updateGroupStatus, 4000);

// ------- Đếm số mã chưa phân tích theo nhóm cho UI -------
async function updateGroupStatus(){
  const g = $('p4group') ? $('p4group').value : 'VN30';
  const badge = $('ai_status_badge');
  if(!badge) return;
  try {
    const res = await (await fetch('/api/analysis_status?group=' + encodeURIComponent(g))).json();
    if(res.ok){
      badge.innerHTML = `📊 <b>Nhóm ${res.group}</b>: Tổng <b>${res.total}</b> mã<br>` +
                        `• Đã phân tích AI: <b style="color:var(--ok-txt)">${res.analyzed}</b> mã<br>` +
                        `• Còn trống (cần làm): <b style="color:var(--run-txt)">${res.remaining_ai}</b> mã`;
    }
  } catch(e){}
}

// ------- Trạng thái hệ thống (poll nhẹ /health + kiểm Gemini theo yêu cầu) -------
function _fd(s){ return s? String(s).replace('T',' ').slice(0,16) : '—'; }
async function pollHealth(){
  let h; try{ h=await (await fetch('/health')).json(); }catch(e){ return; }
  const be_id=h.backend||'local_api';
  // CDP chỉ còn là kênh dự phòng → chưa mở KHÔNG phải lỗi khi backend là local_api.
  const cdp=$('h_cdp'); if(cdp){ cdp.textContent=h.cdp_up?'✓ đang mở':'✗ chưa mở';
    cdp.style.color=h.cdp_up?'var(--ok)':(be_id==='gemini'?'var(--err)':'var(--muted)'); }
  const la=$('h_local'), L=h.local_api||{};
  if(la){
    const ok=L.up&&L.has_key;
    la.textContent = !L.has_key ? '⚠ thiếu API key' : (L.up?'✓ sẵn sàng':'✗ không phản hồi');
    la.style.color = ok?'var(--ok)':(be_id==='local_api'?'var(--err)':'var(--muted)');
    la.title = (L.url||'')+(L.model?(' · '+L.model):'');
  }
  const be=$('h_backend'); if(be) be.textContent=be_id+' · trễ '+(h.request_delay||0)+'s';
  const di=$('delayInput'); if(di && document.activeElement!==di && h.request_delay!=null) di.value=h.request_delay;
  const db=$('h_db'); if(db&&h.db) db.textContent=(h.db.companies||0)+'·'+(h.db.fin_symbols||0)+'·'+(h.db.analyzed||0);
  const fr=$('h_fresh'); if(fr&&h.fresh) fr.textContent='giá '+_fd(h.fresh.price)+' · PT '+_fd(h.fresh.analyzed);
}
async function setDelay(ev){
  if(ev)ev.preventDefault();
  const di=$('delayInput'); if(!di)return;
  const v=parseFloat(di.value);
  if(isNaN(v)||v<0){ toast('Nhập số giây hợp lệ (0-120)','err'); return; }
  try{
    const r=await (await fetch('/set_delay',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({delay:v})})).json();
    if(r.ok) toast('Đã đặt delay '+r.delay+'s — áp dụng NGAY từ lượt Gemini kế tiếp','ok');
    else toast(r.msg||'Lỗi đặt delay','err');
  }catch(e){ toast('Lỗi mạng khi đặt delay','err'); }
}
async function checkGemini(ev){
  if(ev)ev.preventDefault();
  const g=$('h_gemini'), btn=$('btnGem');
  if(g){ g.textContent='⏳ đang kiểm...'; g.style.color='var(--muted)'; }
  if(btn)btn.disabled=true;
  // Kiểm tra ĐÚNG kênh đang chọn trong ô "Nguồn AI" (local_api | gemini | claude).
  const be=$('backend') ? $('backend').value : '';
  let r; try{ r=await (await fetch('/gemini_check',{method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify({backend:be})})).json();
  }catch(e){ r={state:'error',msg:'lỗi mạng'}; }
  const map={ready:['✓ sẵn sàng','var(--ok)'], blocked:['⛔ bị chặn CAPTCHA (1095)','var(--err)'],
    login:['⚠ chưa đăng nhập','var(--run)'], nocdp:['✗ Chrome chưa mở','var(--err)'],
    nokey:['⚠ thiếu API key','var(--run)'], nolocal:['✗ server local tắt','var(--err)'],
    error:['✗ lỗi','var(--err)']};
  const m=map[r.state]||['?','var(--muted)'];
  if(g){ g.textContent=m[0]; g.style.color=m[1]; g.title=r.msg||''; }
  if(btn)btn.disabled=false;
  if(r.state==='blocked')toast('Gemini bị Google chặn CAPTCHA (lỗi 1095). Mở Chrome giải CAPTCHA rồi thử lại.','err');
  else if(r.state==='ready')toast('Kênh AI sẵn sàng ✓','ok');
  else if(r.msg)toast(String(r.msg).slice(0,120), (r.state==='login'||r.state==='nokey')?'warn':'err');
}
// Lưu LOCAL_API_KEY vào Crawl Data/.env → mọi service (:5000/:5555/:9999/:3000)
// dùng chung 1 key, không phải nhập lại từng nơi.
async function saveKey(ev){
  if(ev)ev.preventDefault();
  const el=$('apikey'); if(!el)return;
  const v=(el.value||'').trim();
  if(!v){ toast('Nhập API key trước khi lưu','warn'); return; }
  try{
    const r=await (await fetch('/set_local_api_key',{method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify({apikey:v})})).json();
    if(r.ok){ toast('Đã lưu API key vào .env — mọi service dùng chung','ok'); pollHealth(); }
    else toast(r.msg||'Lỗi lưu API key','err');
  }catch(e){ toast('Lỗi mạng khi lưu API key','err'); }
}
pollHealth(); setInterval(pollHealth, 5000);

// ------- toast: div nổi góc dưới phải, tự ẩn sau ~3s -------
function toast(msg,type){
  const box=$('toasts'); if(!box)return;
  const el=document.createElement('div');
  el.className='toast'+(type?(' '+type):'');
  el.textContent=msg; box.appendChild(el);
  setTimeout(()=>{el.style.transition='opacity .3s';el.style.opacity='0';
    setTimeout(()=>el.remove(),300);},3000);
}

// ------- hiển thị/append log -------
function isErrLine(ln){return ln.includes('✗')||ln.includes('[LỖI]')||ln.includes('Traceback')||ln.includes('Lỗi');}
function lineClass(ln){
  if(ln.startsWith('$ '))return 'cmd';
  if(ln.startsWith('---'))return 'end';
  if(isErrLine(ln))return 'err';
  return '';
}
// <details> KHÔNG truyền chiều cao xác định cho con → flex/grid không stretch #log,
// khiến log đầy tràn đè lên thanh nút. Ép chiều cao #log = logwrap − summary để nó
// luôn vừa khung và cuộn nội bộ (gọi khi render/resize/mở-đóng log).
function fitLog(){
  const lw=document.querySelector('.logwrap'), log=$('log');
  const sum=lw&&lw.querySelector('summary');
  if(!lw||!log||!sum)return;
  if(!lw.open){log.style.height='';return;}
  log.style.height=Math.max(60,(lw.clientHeight-sum.offsetHeight))+'px';
}
function renderLog(){
  fitLog();
  const log=$('log'); log.innerHTML='';
  let arr=errOnly?LOG_LINES.filter(isErrLine):LOG_LINES;
  if(arr.length>MAX_DOM_LINES)arr=arr.slice(-MAX_DOM_LINES);   // cắt bớt đầu
  const frag=document.createDocumentFragment();
  arr.forEach(ln=>{const d=document.createElement('span');
    const c=lineClass(ln); if(c)d.className=c;
    d.textContent=ln+'\n'; frag.appendChild(d);});
  log.appendChild(frag);
  if($('autoscroll').checked)log.scrollTop=log.scrollHeight;
}
function appendLogLines(lines){
  if(!lines||!lines.length)return;
  LOG_LINES.push(...lines);
  if(LOG_LINES.length>2000)LOG_LINES=LOG_LINES.slice(-2000);   // trần bộ nhớ client
  renderLog();
}
function toggleErr(ev){if(ev)ev.preventDefault();errOnly=!errOnly;
  $('btnErr').classList.toggle('active',errOnly);renderLog();}
function downloadLog(ev){
  if(ev)ev.preventDefault();
  const blob=new Blob([LOG_LINES.join('\n')],{type:'text/plain;charset=utf-8'});
  const url=URL.createObjectURL(blob), a=document.createElement('a');
  a.href=url; a.download='run-log-'+new Date().toISOString().slice(0,19).replace(/[:T]/g,'-')+'.txt';
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}
window.addEventListener('resize', fitLog);
document.addEventListener('DOMContentLoaded', ()=>{
  const lw=document.querySelector('.logwrap');
  if(lw) lw.addEventListener('toggle', fitLog);
  fitLog();
});

// ------- đồng hồ đếm thời gian chạy -------
function fmtElapsed(s){s=Math.max(0,Math.floor(s));
  const m=Math.floor(s/60), ss=s%60;
  return (m>0?(m+'p '):'')+ss+'s';}
function startElapsed(){
  if(elapsedTimer)clearInterval(elapsedTimer);
  elapsedTimer=setInterval(()=>{if(startedAt)$('elapsed').textContent='⏱ '+fmtElapsed((Date.now()-startedAt)/1000);},500);
}
function stopElapsed(){if(elapsedTimer){clearInterval(elapsedTimer);elapsedTimer=null;}}

async function loadTickerCount(){
  const j=await (await fetch('/tickers')).json();
  CHOSEN=new Set(j.tickers);
  $('tickcount').textContent='Đang chọn: '+CHOSEN.size+' mã';
}
function openPicker(){$('modal').style.display='block';searchSyms();renderChosen();}
function closePicker(){$('modal').style.display='none';}
async function searchSyms(){
  const q=$('psearch').value.trim();
  const j=await (await fetch('/symbols?limit=80&q='+encodeURIComponent(q))).json();
  $('results').innerHTML=j.items.map(s=>{
    const on=CHOSEN.has(s.symbol);
    return `<div onclick="toggle('${s.symbol}')" style="display:flex;gap:10px;padding:7px 6px;
      border-bottom:1px solid var(--line);cursor:pointer;align-items:center">
      <span style="width:18px">${on?'✅':'⬜'}</span>
      <b style="color:var(--accent);width:54px">${s.symbol}</b>
      <span style="color:var(--muted);font-size:12px">${(s.organ_name||'').slice(0,46)}</span></div>`;
  }).join('')||'<div class="empty">Không thấy mã. (Đã chạy P0 chưa?)</div>';
  $('selcount').textContent='Tìm thấy '+j.total+' mã';
}
function toggle(sym){CHOSEN.has(sym)?CHOSEN.delete(sym):CHOSEN.add(sym);searchSyms();renderChosen();}
function addTyped(){const v=$('psearch').value.trim().toUpperCase();if(v){CHOSEN.add(v);renderChosen();searchSyms();}}
function clearChosen(){CHOSEN.clear();renderChosen();searchSyms();}
function renderChosen(){
  $('chcount').textContent=CHOSEN.size;
  $('chosen').innerHTML=[...CHOSEN].map(s=>
    `<span class="chip c-ok" style="cursor:pointer" onclick="toggle('${s}')" title="bỏ chọn">${s} ✕</span>`).join('')
    ||'<span class="empty">chưa chọn mã nào</span>';
}
async function saveTickers(){
  const r=await fetch('/tickers',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({tickers:[...CHOSEN]})});
  const j=await r.json();
  $('tickcount').textContent='Đang chọn: '+j.count+' mã';
  closePicker();
  toast('Đã lưu '+j.count+' mã. Giờ bấm P1/P2/P4 để crawl các mã này.','ok');
}

function setBusy(b){document.querySelectorAll('.side button').forEach(x=>x.disabled=b);}
function statusBadge(s,txt){const e=$('status');e.className='status '+s;e.innerHTML=txt;}

async function refreshStats(){
  try{const s=await (await fetch('/stats')).json();
    $('stats').innerHTML=[
      ['Công ty',s.companies],['Mã có tài chính',s.fin_symbols],
      ['Bản tin',s.news],['Đã phân tích',s.analyzed],
      ['Crawl TC xong',s.fin_done],['Crawl TT xong',s.co_done],
    ].map(([k,v])=>`<div class="stat"><div class="v">${v.toLocaleString('vi-VN')}</div><div class="k">${k}</div></div>`).join('');
  }catch(e){}
}

async function run(task,opts={}){
  const r=await fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(Object.assign({task},opts))});
  const j=await r.json();
  if(!j.ok){toast(j.msg||'Không chạy được','err');return;}
  LOG_LINES=[]; since=0; setBusy(true); renderLog();
  $('grid').innerHTML=''; $('now').textContent='→ '+(TASKS[task]||task);
  startedAt=Date.now(); startElapsed();
  statusBadge('s-run','<span class="spin"></span> Đang chạy');
  if(timer)clearInterval(timer); timer=setInterval(pollLoop,700);
}

function runP3Group(){
  const group = $('p3group') ? $('p3group').value : 'ALL';
  const no_resume = $('p3recrawl') ? $('p3recrawl').checked : false;
  const limit = parseInt($('p3limit').value) || 0;
  run('p3', { group: group, no_resume: no_resume, limit: limit });
}

function runP4Resume(){
  const group = $('p4group') ? $('p4group').value : 'CUSTOM';
  const limit = parseInt($('p4limit').value) || 0;
  run('p4', {
    group: group,
    reanalyze: false,
    backend: $('backend').value,
    apikey: $('apikey') ? $('apikey').value : '',
    limit: limit
  });
}

function runP4Reanalyze(){
  if(!confirm("⚠️ Bạn có chắc chắn muốn chạy lại phân tích AI từ đầu? Tất cả dữ liệu phân tích cũ sẽ bị ghi đè!")) return;
  const group = $('p4group') ? $('p4group').value : 'CUSTOM';
  const limit = parseInt($('p4limit').value) || 0;
  run('p4', {
    group: group,
    reanalyze: true,
    backend: $('backend').value,
    apikey: $('apikey') ? $('apikey').value : '',
    limit: limit
  });
}

function runP3(){const l=parseInt($('p3limit').value)||0;run('p3',l?{limit:l}:{});}
function runP4(){runP4Resume();}
function runPipeline(){
  const g = $('pgroup') ? $('pgroup').value : 'VN30';
  const b = $('backend') ? $('backend').value : 'gemini';
  const k = $('apikey') ? $('apikey').value : '';
  const r = $('preanalyze') ? $('preanalyze').checked : false;
  run('pipeline', { group: g, backend: b, apikey: k, reanalyze: r });
}
async function stop(){
  try{const j=await (await fetch('/stop',{method:'POST'})).json();
    toast(j.ok?(j.msg||'Đã gửi lệnh dừng'):(j.msg||'Không có tiến trình'),j.ok?'warn':'err');
  }catch(e){toast('Lỗi khi dừng','err');}
}

const COLS=[['balance_sheet','BCĐKT'],['income_statement','KQKD'],['cash_flow','Dòng tiền'],
  ['ratio','Chỉ số'],['overview','Hồ sơ'],['lãnh đạo','Lãnh đạo'],['cổ đông','Cổ đông'],
  ['cty con','Cty con'],['liên kết','Liên kết'],['giá','Giá (phiên)'],
  ['news','Tin tức'],['events','Sự kiện'],['reasons','Lý do'],
  ['F-Score','F-Score'],['sức khỏe','Sức khỏe'],['rủi ro','Rủi ro']];

function renderProgress(p){
  $('pstage').textContent=p.stage||(p.total?'đang chạy':'—');
  $('pcur').textContent=p.cur_sym?('▶ '+p.cur_sym):'';
  $('pnum').textContent=p.current+'/'+p.total;
  $('pdone').textContent=p.done; $('perr').textContent=p.errors;
  const pct=p.total?Math.round(p.current/p.total*100):0;
  $('ppct').textContent=pct+'%'; $('pfill').style.width=pct+'%';

  const d=p.detail||{}, order=p.order||[];
  if(!order.length)return;
  const present=COLS.filter(([k])=>order.some(s=>d[s]&&d[s].steps[k]));
  let h='<table class="dtable"><thead><tr><th>Mã</th>'+
    present.map(([,l])=>`<th>${l}</th>`).join('')+'<th>Trạng thái</th></tr></thead><tbody>';
  order.slice(-200).forEach(s=>{
    const row=d[s]; if(!row)return;
    h+=`<tr class="${row.status==='run'?'r-run':''}"><td class="sym">${s}</td>`;
    present.forEach(([k])=>{
      const st=row.steps[k];
      if(!st)h+='<td class="muted">·</td>';
      else if(st.status==='ok')h+=`<td class="c-ok2">${st.n!==''?st.n:'✓'}</td>`;
      else if(st.status==='err')h+='<td class="c-err2">✗</td>';
      else h+=`<td>${st.status}</td>`;
    });
    const b=row.status==='ok'?'<span class="chip c-ok">XONG</span>':
      row.status==='err'?'<span class="chip c-error">LỖI</span>':
      '<span class="spin"></span> đang chạy';
    h+=`<td style="text-align:left">${b}</td></tr>`;
  });
  h+='</tbody></table>';
  $('grid').innerHTML=h;
  if($('autoscroll').checked){const g=$('grid');g.scrollTop=g.scrollHeight;}
}

async function pollLoop(){
  let j;
  try{ j=await (await fetch('/poll?since='+since)).json(); }
  catch(e){ return; }
  // /poll trả các dòng MỚI kể từ `since` → APPEND, cập nhật con trỏ theo tổng số dòng.
  if(typeof j.since==='number' && j.since<since){ LOG_LINES=[]; }  // log bị reset → dựng lại
  appendLogLines(j.lines);
  if(typeof j.total==='number') since=j.total;
  if(j.progress)renderProgress(j.progress);
  if(j.running){ $('now').textContent = (typeof j.eta==='number'&&j.eta>0)? ('· còn ~'+fmtElapsed(j.eta)) : ''; }
  if(!j.running){
    clearInterval(timer);timer=null;setBusy(false);$('now').textContent='';$('pcur').textContent='';
    stopElapsed();
    if(typeof j.elapsed==='number')$('elapsed').textContent='⏱ '+fmtElapsed(j.elapsed);
    statusBadge(j.rc===0?'s-ok':'s-err', j.rc===0?'● Hoàn tất':'● Lỗi (mã '+j.rc+')');
    refreshStats();
  }
}
</script></body></html>"""


def _kill_tree(pid: int) -> bool:
    """Kill một tiến trình và toàn bộ con cháu (chống zombie). True nếu có kill."""
    try:
        import psutil
        proc = psutil.Process(pid)
        for ch in proc.children(recursive=True):
            try: ch.terminate()
            except Exception: pass
        proc.terminate()
        return True
    except Exception:
        return False


def _cleanup_orphan_on_start():
    """Khi khởi động: nếu còn run.pid của lần chạy trước (Flask bị tắt đột ngột) → kill."""
    if RUN_PID.exists():
        try:
            pid = int(RUN_PID.read_text(encoding="utf-8").strip())
            if _kill_tree(pid):
                print(f"⚠️  Đã dọn orphan process từ lần chạy trước (PID {pid})")
        except Exception:
            pass
        RUN_PID.unlink(missing_ok=True)


def _on_exit():
    """Khi Flask thoát: kill tiến trình con đang chạy để không thành zombie."""
    if _proc is not None and _proc.poll() is None:
        _kill_tree(_proc.pid)
    if RUN_PID.exists():
        RUN_PID.unlink(missing_ok=True)


if __name__ == "__main__":
    import atexit
    import signal
    _cleanup_orphan_on_start()
    atexit.register(_on_exit)
    # Bắt SIGTERM/SIGINT để chạy _on_exit rồi thoát sạch.
    for _sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(_sig, lambda *_: (_on_exit(), sys.exit(0)))
        except Exception:
            pass
    PORT = int(os.getenv("PORT", "5000"))
    print(f"=> Bang dieu khien: http://localhost:{PORT}")
    app.run(host="127.0.0.1", port=PORT, threaded=True, debug=True, use_reloader=True)
