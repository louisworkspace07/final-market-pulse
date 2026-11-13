# -*- coding: utf-8 -*-
"""Radar bất thường (P2) — quét tín hiệu lệch chuẩn từ giá/khối lượng + tin/sự kiện.

Thuần Python (pandas), đọc trực tiếp market.db. KHÔNG quy kết thao túng/đội lái —
chỉ nêu DỮ KIỆN lệch chuẩn để nhà đầu tư tự soi kỹ hơn. Mỗi tín hiệu kèm số đo
cụ thể + gợi ý "cần kiểm chứng gì".

Bộ phát hiện:
- vol_spike        : khối lượng phiên gần nhất ≫ TB20 (đã lọc mã chết thanh khoản).
- price_run_no_news: giá chạy mạnh nhiều phiên — PHÂN BIỆT 3 trạng thái tin:
                     0 tin CBTT (mã CÓ trong coverage) / chưa crawl (mã NGOÀI
                     coverage — không kết luận được) / có N bài báo chí (RSS bù).
- limit_streak     : chuỗi phiên tăng/giảm sát biên độ trần-sàn của sàn niêm yết.
- divergence       : giá và khối lượng phân kỳ (giá lên KL cạn / giá xuống KL tăng).
- foreign_flip     : dòng vốn ngoại đảo chiều — đọc foreign_history.jsonl (Crawl
                     Data) + fallback snapshot board LIVE tích lũy theo ngày.

CHỐNG FALSE-POSITIVE: chỉ 40/728 mã có tin CBTT trong DB → nếu cứ thấy "không có
tin" là báo "0 tin" thì đa số là do CHƯA CRAWL, không phải thật sự không có tin.
Vì vậy price_run_no_news tách coverage (khẳng định được) vs ngoài coverage (không).
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta

import pandas as pd

# ── Cấu hình ngưỡng phát hiện ────────────────────────────────────────────────
# Đặt tập trung ở đây để dễ hiệu chỉnh và giải trình. Ngưỡng "cao" (hard) chỉ dùng
# làm fallback khi nhóm quá nhỏ để tính percentile; bình thường severity CAO là
# top 25% ĐỘ MẠNH trong chính nhóm đó (nhất quán giữa các mã cùng loại).
CONFIG = {
    # vol_spike
    "vol_spike_ratio": 3.0,        # KL phiên cuối / TB20 ≥ 3 lần mới xét
    "vol_spike_hard_cao": 5.0,     # fallback: ≥5× là CAO khi nhóm < 4 mã
    "vol_ratio_suspect": 20.0,     # >20× → nghi GD thỏa thuận/sự kiện vốn, gắn cờ
    "liq_min_avg_vol": 30_000,     # TB20 KL ≥ 30.000 cp/phiên (lọc mã chết thanh khoản)
    "liq_min_turnover": 500_000_000,  # giá trị GD phiên ≥ 500 triệu đồng
    # price_run_no_news
    "price_run_pct": 15.0,         # |biến động 5 phiên| ≥ 15% coi là "chạy mạnh"
    "price_run_days": 5,
    "price_run_hard_cao": 25.0,    # fallback: ≥25% là CAO khi nhóm < 4 mã
    "news_window_days": 30,        # cửa sổ soi tin CBTT (ngày lịch)
    # limit_streak
    "limit_near": 0.9,             # |%1D| ≥ 90% biên độ = "sát trần/sàn"
    "limit_min_streak": 2,
    "limit_hard_cao": 3,
    # divergence
    "div_chg": 5.0,                # |biến động 5 phiên| ngưỡng
    "div_vol_drop": -30.0,         # KL cạn ≥ 30% (giá tăng)
    "div_vol_rise": 40.0,          # KL tăng ≥ 40% (giá giảm)
    # severity percentile
    "sev_top_pct": 0.75,           # từ phân vị 75 trở lên trong nhóm = CAO
    "sev_min_group": 4,            # nhóm ≥ 4 mã mới dùng percentile, nhỏ hơn dùng hard
    # foreign_flip
    "fx_min_sessions": 5,          # cần ≥5 phiên khối ngoại để kết luận đảo chiều
    "fx_streak": 3,                # ≥3 phiên cùng chiều trước khi đảo
    "fx_net_share": 0.20,          # |ròng| ≥ 20% KLGD phiên mới coi là "mạnh"
    # RSS bù
    "rss_top_n": 5,                # số mã ngoài coverage (severity cao) đi lấy RSS
    "rss_deadline_s": 10,          # tổng thời gian chờ RSS (chạy song song)
}

# Biên độ trần-sàn theo sàn (%/phiên). UPCOM 15%, HNX 10%, HOSE 7%.
_LIMIT_BY_EXCHANGE = {"HOSE": 7.0, "HNX": 10.0, "UPCOM": 15.0}
_DEFAULT_LIMIT = 7.0

# rank severity (nhỏ = nặng hơn) — thêm 'thap' cho tín hiệu bị hạ bậc (ngoài coverage).
_SEVERITY_RANK = {"cao": 0, "vua": 1, "thap": 2}
_SEV_DOWN = {"cao": "vua", "vua": "thap", "thap": "thap"}

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_ECONO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_FOREIGN_SNAPSHOT = os.path.join(_ECONO_ROOT, "gateway", "static", "data",
                                 "foreign_snapshot.jsonl")


# ── Nạp dữ liệu nền ──────────────────────────────────────────────────────────
_DB_CACHE = {}
_DB_CACHE_DATE = ""

def _load(con) -> pd.DataFrame:
    global _DB_CACHE, _DB_CACHE_DATE
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    if _DB_CACHE and _DB_CACHE_DATE == today: return _DB_CACHE["df"]
    df = pd.read_sql_query(
        "SELECT symbol, time, open, high, low, close, volume "
        "FROM price ORDER BY symbol, time", con)
    _DB_CACHE["df"] = df
    _DB_CACHE_DATE = today
    return df


def _news_coverage(con) -> tuple[set, dict]:
    """(news_covered, news_days).

    news_covered = tập mã CÓ ÍT NHẤT 1 tin/sự kiện trong DB (dù cũ) → mới đủ tư
    cách khẳng định "0 tin". news_days = {symbol: set(ngày có tin)} để soi 30 ngày.
    """
    covered: set = set()
    days: dict[str, set] = {}
    for tbl in ("news", "events"):
        try:
            for sym, d in con.execute(
                    f"SELECT symbol, substr(public_date,1,10) FROM {tbl}"):
                if sym:
                    covered.add(sym)
                    if d:
                        days.setdefault(sym, set()).add(d)
        except sqlite3.Error:
            pass
    return covered, days


def _exchanges(con) -> dict:
    try:
        return {s: (e or "").upper()
                for s, e in con.execute("SELECT symbol, exchange FROM companies")}
    except sqlite3.Error:
        return {}


def _company_names(con) -> dict:
    try:
        return {s: (n or "") for s, n in
                con.execute("SELECT symbol, organ_name FROM companies")}
    except sqlite3.Error:
        return {}


def _recent_news(news_days: set, ref_date: str, days: int) -> bool:
    """Có tin CBTT nào trong `days` ngày lịch tính từ ref_date không?"""
    if not news_days:
        return False
    try:
        ref = datetime.strptime(str(ref_date)[:10], "%Y-%m-%d")
    except ValueError:
        return bool(news_days)
    cutoff = ref - timedelta(days=days)
    for d in news_days:
        try:
            if datetime.strptime(d, "%Y-%m-%d") >= cutoff:
                return True
        except ValueError:
            pass
    return False


# ── Phát hiện tín hiệu cho 1 mã ──────────────────────────────────────────────
def _sig(kind, symbol, headline, metrics, verify, mag, note=None):
    """Tín hiệu thô — severity gán sau (theo percentile trong nhóm)."""
    s = {"kind": kind, "symbol": symbol, "headline": headline,
         "metrics": metrics, "verify": verify, "_mag": mag}
    if note:
        s["note"] = note
    return s


def _detect_symbol(sym, g_or_c, *args, **kwargs) -> list[dict]:
    if isinstance(g_or_c, pd.DataFrame):
        g = g_or_c
        c = g["close"]
        v = g["volume"]
        t = g["time"]
        news_days = args[0] if len(args) > 0 else kwargs.get("news_days", set())
        in_coverage = args[1] if len(args) > 1 else kwargs.get("in_coverage", True)
        limit_pct = args[2] if len(args) > 2 else kwargs.get("limit_pct", 7.0)
    elif len(args) >= 4:
        c = g_or_c
        v = args[0]
        t = args[1]
        news_days = args[2]
        in_coverage = args[3]
        limit_pct = args[4] if len(args) > 4 else kwargs.get("limit_pct", 7.0)
    else:
        c = g_or_c
        news_days = args[0] if len(args) > 0 else kwargs.get("news_days", set())
        in_coverage = args[1] if len(args) > 1 else kwargs.get("in_coverage", True)
        limit_pct = args[2] if len(args) > 2 else kwargs.get("limit_pct", 7.0)
        v = kwargs.get("v", c)
        t = kwargs.get("t", c)
    n = len(c)
    if n < 21 or not c.iloc[-1]:
        return []
    out = []
    last, prev = float(c.iloc[-1]), float(c.iloc[-2])
    chg_1d = (last / prev - 1) * 100 if prev else 0.0
    vol_last = float(v.iloc[-1])
    vol20 = float(v.iloc[-21:-1].mean()) if v.iloc[-21:-1].mean() else 0.0
    as_of = t.iloc[-1]

    # 1) vol_spike — CHỈ xét mã đủ thanh khoản (lọc mã chết thanh khoản ×5 vô nghĩa)
    turnover_last = vol_last * last * 1000  # close đơn vị nghìn đồng → ×1000 ra đồng
    liquid = (vol20 >= CONFIG["liq_min_avg_vol"]
              and turnover_last >= CONFIG["liq_min_turnover"])
    if vol20 and liquid and vol_last / vol20 >= CONFIG["vol_spike_ratio"]:
        ratio = round(vol_last / vol20, 1)
        note = None
        if ratio > CONFIG["vol_ratio_suspect"]:
            note = ("KL gấp >20× TB20 — có thể do giao dịch thỏa thuận/sự kiện vốn "
                    "(chia tách, phát hành), kiểm tra trước khi diễn giải.")
        out.append(_sig(
            "vol_spike", sym,
            f"Khối lượng phiên {as_of} gấp {ratio}× trung bình 20 phiên",
            {"vol_ratio": ratio, "chg_1d": round(chg_1d, 2), "as_of": as_of,
             "avg_vol20": int(vol20), "turnover": int(turnover_last)},
            "Kiểm tra có tin CBTT/giao dịch thỏa thuận/khối ngoại giải thích đột biến không.",
            mag=ratio, note=note))

    # 2) price_run_no_news — tách 3 trạng thái tin (coverage-aware)
    days_win = CONFIG["price_run_days"]
    if n >= days_win + 1:
        base = float(c.iloc[-days_win - 1])
        run = (last / base - 1) * 100 if base else 0.0
        if abs(run) >= CONFIG["price_run_pct"]:
            has_recent = _recent_news(news_days, as_of, CONFIG["news_window_days"])
            direction = "tăng" if run > 0 else "giảm"
            if in_coverage and has_recent:
                pass  # biến động ĐÃ có tin nền giải thích → không phải bất thường
            elif in_coverage:
                # Khẳng định được: mã có crawl tin nhưng 30 ngày qua KHÔNG có CBTT.
                out.append(_sig(
                    "price_run_no_news", sym,
                    f"Giá {direction} {abs(round(run,1))}% trong {days_win} phiên "
                    f"nhưng không có tin công bố 30 ngày",
                    {"run_pct": round(run, 2), "days": days_win, "as_of": as_of,
                     "news_status": "none_confirmed"},
                    "Biến động mạnh không tin nền → soi kỹ nguồn tin đồn, tránh FOMO theo giá.",
                    mag=abs(run)))
            else:
                # NGOÀI coverage: chưa crawl tin → KHÔNG kết luận "0 tin". Hạ 1 bậc.
                out.append(_sig(
                    "price_run_no_news", sym,
                    f"Giá {direction} {abs(round(run,1))}% trong {days_win} phiên "
                    f"— CHƯA có dữ liệu tin để đối chiếu",
                    {"run_pct": round(run, 2), "days": days_win, "as_of": as_of,
                     "news_status": "uncrawled"},
                    "Chưa crawl tin cho mã này → chưa thể khẳng định có/không tin nền. "
                    "Cần crawl CBTT hoặc đối chiếu báo chí.",
                    mag=abs(run)))

    # 3) limit_streak
    near = limit_pct * CONFIG["limit_near"]
    streak, sdir = 0, 0
    for i in range(n - 1, 0, -1):
        p0, p1 = float(c.iloc[i]), float(c.iloc[i - 1])
        if not p1:
            break
        d = (p0 / p1 - 1) * 100
        this_dir = 1 if d > 0 else -1
        if abs(d) >= near and (sdir == 0 or sdir == this_dir):
            streak += 1
            sdir = this_dir
        else:
            break
    if streak >= CONFIG["limit_min_streak"]:
        out.append(_sig(
            "limit_streak", sym,
            f"{streak} phiên liên tiếp {'tăng' if sdir > 0 else 'giảm'} "
            f"sát biên độ (±{limit_pct:g}%)",
            {"streak": streak, "direction": "tăng" if sdir > 0 else "giảm",
             "limit_pct": limit_pct, "as_of": as_of},
            "Chuỗi trần/sàn liên tiếp thường đi kèm tin hoặc dòng tiền lớn — xác minh nguyên nhân.",
            mag=streak * 10))

    # 4) divergence
    if n >= 11:
        chg_5d = (last / float(c.iloc[-6]) - 1) * 100 if c.iloc[-6] else 0.0
        vol5 = float(v.iloc[-5:].mean())
        vol_prev5 = float(v.iloc[-10:-5].mean())
        if vol_prev5:
            vol_trend = (vol5 / vol_prev5 - 1) * 100
            if chg_5d >= CONFIG["div_chg"] and vol_trend <= CONFIG["div_vol_drop"]:
                out.append(_sig(
                    "divergence", sym,
                    f"Giá tăng {round(chg_5d,1)}% nhưng khối lượng cạn {abs(round(vol_trend))}% — phân kỳ",
                    {"chg_5d": round(chg_5d, 2), "vol_trend": round(vol_trend, 1), "as_of": as_of},
                    "Giá tăng trên thanh khoản thấp → đà tăng dễ đuối, cần theo dõi lực cầu.",
                    mag=abs(chg_5d) + abs(vol_trend)))
            elif chg_5d <= -CONFIG["div_chg"] and vol_trend >= CONFIG["div_vol_rise"]:
                out.append(_sig(
                    "divergence", sym,
                    f"Giá giảm {abs(round(chg_5d,1))}% kèm khối lượng tăng {round(vol_trend)}% — áp lực bán",
                    {"chg_5d": round(chg_5d, 2), "vol_trend": round(vol_trend, 1), "as_of": as_of},
                    "Giá giảm trên thanh khoản tăng → áp lực bán mạnh, kiểm tra tin xấu tiềm ẩn.",
                    mag=abs(chg_5d) + abs(vol_trend)))
    return out


# ── Gán severity theo percentile trong nhóm ─────────────────────────────────
def _hard_cao(kind, mag) -> bool:
    if kind == "vol_spike":
        return mag >= CONFIG["vol_spike_hard_cao"]
    if kind == "price_run_no_news":
        return mag >= CONFIG["price_run_hard_cao"]
    if kind == "limit_streak":
        return mag >= CONFIG["limit_hard_cao"] * 10
    return False


def _assign_severity(signals: list[dict]) -> None:
    """Gán 'cao'/'vua' theo percentile ĐỘ MẠNH trong từng nhóm kind.

    Nhóm ≥ sev_min_group mã: từ phân vị 75 trở lên = CAO (nhất quán BVS/SFN…).
    Nhóm nhỏ hơn: dùng ngưỡng cứng per-kind (percentile trên n<4 vô nghĩa).
    Sau đó tín hiệu ngoài coverage (news_status='uncrawled') bị HẠ 1 bậc.
    """
    from collections import defaultdict
    groups = defaultdict(list)
    for s in signals:
        groups[s["kind"]].append(s)
    for kind, arr in groups.items():
        if len(arr) >= CONFIG["sev_min_group"]:
            mags = sorted(s["_mag"] for s in arr)
            idx = min(int(len(mags) * CONFIG["sev_top_pct"]), len(mags) - 1)
            thr = mags[idx]
            for s in arr:
                s["severity"] = "cao" if s["_mag"] >= thr else "vua"
        else:
            for s in arr:
                s["severity"] = "cao" if _hard_cao(kind, s["_mag"]) else "vua"
    # Hạ bậc tín hiệu ngoài coverage — không đủ căn cứ để xếp mức cao.
    for s in signals:
        if s.get("metrics", {}).get("news_status") == "uncrawled":
            s["severity"] = _SEV_DOWN.get(s["severity"], "vua")


# ── RSS bù cho mã ngoài coverage (severity cao) ─────────────────────────────
import sys
_crawl_src = os.path.join(_PROJECT_ROOT, "data-crawler", "src")
if _crawl_src not in sys.path:
    sys.path.insert(0, _crawl_src)
try:
    import news_rss
except ImportError:
    news_rss = None

_RSS_CACHE = {}

def _rss_backfill(signals: list[dict], names: dict) -> None:
    import threading
    for sig in signals:
        sym = sig["symbol"]
        if sym in _RSS_CACHE:
            sig["metrics"]["news_status"] = _RSS_CACHE[sym].get("status", "none_confirmed")
            if _RSS_CACHE[sym].get("count"):
                sig["metrics"]["rss_count"] = _RSS_CACHE[sym]["count"]
                sig["rationale"] = (sig.get("rationale", "") +
                                    f" (Có {_RSS_CACHE[sym]['count']} tin RSS, click để xem).")

    cand = [s for s in signals
            if s["metrics"].get("news_status") == "uncrawled"
            and _SEVERITY_RANK.get(s["severity"], 9) <= 2]
    cand = cand[:CONFIG["rss_top_n"]]
    if not cand or news_rss is None:
        return

    def _worker(cand_list):
        for sig in cand_list:
            sym = sig["symbol"]
            if sym in _RSS_CACHE: continue
            name = names.get(sym, sym)
            try:
                arts = news_rss.fetch(sym, name, limit=5)
                if arts:
                    _RSS_CACHE[sym] = {"status": "rss_found", "count": len(arts)}
                else:
                    _RSS_CACHE[sym] = {"status": "none_confirmed", "count": 0}
            except Exception:
                pass
    t = threading.Thread(target=_worker, args=(cand,))
    t.daemon = True
    t.start()


# ── foreign_flip: đọc foreign_history.jsonl + fallback snapshot board ────────
_FH_CACHE = {}
_FH_CACHE_DATE = ""

def _read_foreign_history() -> dict:
    """{symbol: [ {date, net, buy, sell}... ]} từ data-crawler/companies/*/market/."""
    global _FH_CACHE, _FH_CACHE_DATE
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    if _FH_CACHE and _FH_CACHE_DATE == today: return _FH_CACHE
    import glob
    out: dict[str, list] = {}
    pattern = os.path.join(_PROJECT_ROOT, "data-crawler", "companies", "*",
                           "market", "foreign_history.jsonl")
    for path in glob.glob(pattern):
        sym = os.path.basename(os.path.dirname(os.path.dirname(path)))
        rows = []
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)
                    rows.append({
                        "date": str(r.get("date", ""))[:10],
                        "net": r.get("foreign_net"),
                        "buy": r.get("foreign_buy_volume"),
                        "sell": r.get("foreign_sell_volume"),
                    })
        except Exception:
            continue
        rows = [r for r in rows if r["date"] and isinstance(r["net"], (int, float))]
        rows.sort(key=lambda r: r["date"])
        if rows:
            out[sym] = rows
    _FH_CACHE = out
    _FH_CACHE_DATE = today
    return out


def _append_foreign_snapshot(board_rows: list[dict], today: str) -> None:
    """Lưu 1 dòng/ngày snapshot khối ngoại từ board LIVE (tự tích lũy chuỗi)."""
    if not board_rows:
        return
    data = {}
    for r in board_rows:
        sym = r.get("symbol")
        fb, fs = r.get("foreignBuyVol") or r.get("foreignBuy"), \
            r.get("foreignSellVol") or r.get("foreignSell")
        if sym and (fb is not None or fs is not None):
            fb = float(fb or 0)
            fs = float(fs or 0)
            data[sym] = {"buy": fb, "sell": fs, "net": fb - fs}
    if not data:
        return
    # Không ghi trùng ngày (idempotent trong phiên).
    try:
        if os.path.exists(_FOREIGN_SNAPSHOT):
            with open(_FOREIGN_SNAPSHOT, encoding="utf-8") as f:
                for line in f:
                    try:
                        if json.loads(line).get("date") == today:
                            return
                    except Exception:
                        pass
        os.makedirs(os.path.dirname(_FOREIGN_SNAPSHOT), exist_ok=True)
        with open(_FOREIGN_SNAPSHOT, "a", encoding="utf-8") as f:
            f.write(json.dumps({"date": today, "data": data}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _read_foreign_snapshots() -> list[dict]:
    if not os.path.exists(_FOREIGN_SNAPSHOT):
        return []
    out = []
    try:
        with open(_FOREIGN_SNAPSHOT, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except Exception:
        return []
    out.sort(key=lambda r: r.get("date", ""))
    return out


def _detect_foreign_flip(vol_by_sym: dict, board_rows: list[dict], today: str) -> dict:
    """Phát hiện đảo chiều dòng vốn ngoại. Ưu tiên foreign_history (đủ phiên),
    fallback chuỗi snapshot board. Thiếu dữ liệu → message tích lũy CHÍNH XÁC."""
    _append_foreign_snapshot(board_rows, today)
    hist = _read_foreign_history()

    signals = []
    max_sessions = 0
    for sym, rows in hist.items():
        max_sessions = max(max_sessions, len(rows))
        if len(rows) < CONFIG["fx_min_sessions"]:
            continue
        nets = [r["net"] for r in rows]
        last_net = nets[-1]
        prior = nets[-1 - CONFIG["fx_streak"]:-1]
        if not prior:
            continue
        # đảo chiều: trước đó cùng chiều ≥ streak phiên, phiên cuối ngược hẳn
        prev_all_buy = all(x > 0 for x in prior)
        prev_all_sell = all(x < 0 for x in prior)
        klgd = vol_by_sym.get((sym, rows[-1]["date"]))
        strong = klgd and abs(last_net) >= CONFIG["fx_net_share"] * klgd
        if strong and prev_all_buy and last_net < 0:
            signals.append({"symbol": sym, "flip": "mua→bán",
                            "net": last_net, "date": rows[-1]["date"]})
        elif strong and prev_all_sell and last_net > 0:
            signals.append({"symbol": sym, "flip": "bán→mua",
                            "net": last_net, "date": rows[-1]["date"]})

    snaps = _read_foreign_snapshots()
    if signals:
        return {"available": True, "signals": signals,
                "reason": f"Phát hiện {len(signals)} mã đảo chiều dòng vốn ngoại."}
    # Chưa đủ dữ liệu — message chính xác thay vì "chưa tích hợp".
    n = max(max_sessions, len(snaps))
    return {
        "available": False,
        "signals": [],
        "n_sessions": n,
        "reason": (f"Đang tích lũy chuỗi khối ngoại ({n}/{CONFIG['fx_min_sessions']} "
                   f"phiên) — cần chạy pipeline vài ngày để đủ dữ liệu đối chiếu đảo chiều."),
    }


# ── Lịch giao dịch: as_of có phải phiên gần nhất không ───────────────────────
def _last_trading_day(ref: datetime) -> str:
    """Phiên giao dịch gần nhất tính đến ref (bỏ T7/CN). Không tính nghỉ lễ —
    xấp xỉ đủ dùng để cảnh báo dữ liệu cũ."""
    d = ref
    while d.weekday() >= 5:  # 5=T7, 6=CN
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


# ── API chính ────────────────────────────────────────────────────────────────
_anomalies_cache = {}

def scan_anomalies(db_path: str, limit: int = 80, board_rows: list | None = None,
                   today: str | None = None) -> dict:
    """Quét toàn thị trường → danh sách tín hiệu bất thường (sắp theo mức độ).

    board_rows: rows bảng giá LIVE (:5555) để bù foreign snapshot + turnover — tuỳ chọn.
    today: 'YYYY-MM-DD' (mặc định hôm nay) — dùng để đánh dấu dữ liệu cũ (stale).
    """
    global _anomalies_cache
    import time
    now = time.time()
    today_str = today or datetime.now().strftime("%Y-%m-%d")
    
    # 1. Trả cache nếu có và còn hạn (15s)
    cached = _anomalies_cache.get(db_path)
    if cached and (now - cached["ts"] < 15):
        # Trả về bản sao + đính kèm board_rows nếu có
        res = dict(cached["data"])
        res["signals"] = res["signals"][:limit]
        res["foreign_flip"] = _detect_foreign_flip(cached["vol_by_sym"], board_rows or [], today_str)
        return res
    if not os.path.exists(db_path):
        return {"available": False, "reason": "Chưa có market.db.", "signals": [],
                "foreign_flip": {"available": False,
                                 "reason": "Chưa có dữ liệu giao dịch khối ngoại."}}
    try:
        from modules.common.db import connect_readonly
        con = connect_readonly(db_path)
    except Exception:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        df = _load(con)
        covered, news_days = _news_coverage(con)
        exch = _exchanges(con)
        names = _company_names(con)
    finally:
        con.close()

    vol_by_sym = {}
    signals: list[dict] = []
    as_of = None
    
    from collections import defaultdict
    c_dict = defaultdict(list)
    v_dict = defaultdict(list)
    t_dict = defaultdict(list)
    
    symbols = df["symbol"].values
    closes = df["close"].values
    volumes = df["volume"].values
    times = df["time"].values
    
    for i in range(len(symbols)):
        sym = symbols[i]
        c_dict[sym].append(closes[i])
        v_dict[sym].append(volumes[i])
        t_dict[sym].append(times[i])
        
    for sym in c_dict:
        c = pd.Series(c_dict[sym])
        v = pd.Series(v_dict[sym])
        t = pd.Series(t_dict[sym])
        limit_pct = _LIMIT_BY_EXCHANGE.get(exch.get(sym, ""), _DEFAULT_LIMIT)
        sigs = _detect_symbol(sym, c, v, t, news_days.get(sym, set()),
                              sym in covered, limit_pct)
        last_time = str(t.iloc[-1])
        vol_by_sym[(sym, last_time[:10])] = float(v.iloc[-1])
        if sigs:
            signals.extend(sigs)
            as_of = max(as_of or "", last_time)

    _assign_severity(signals)
    _rss_backfill(signals, names)

    signals.sort(key=lambda s: (_SEVERITY_RANK.get(s["severity"], 9), -s["_mag"]))
    for s in signals:                       # _mag chỉ dùng nội bộ để xếp hạng
        s.pop("_mag", None)

    by_kind: dict[str, int] = {}
    for s in signals:
        by_kind[s["kind"]] = by_kind.get(s["kind"], 0) + 1

    today = today or datetime.now().strftime("%Y-%m-%d")
    expected = _last_trading_day(datetime.strptime(today, "%Y-%m-%d"))
    stale = bool(as_of) and str(as_of)[:10] < expected

    fx = _detect_foreign_flip(vol_by_sym, board_rows or [], today)

    base_res = {
        "available": True,
        "as_of": as_of,
        "stale": stale,
        "expected_session": expected,
        "n_signals": len(signals),
        "by_kind": by_kind,
        "signals": signals,
        "coverage": {"n_with_news": len(covered),
                     "n_symbols": int(df["symbol"].nunique())},
        "note": ("Radar chỉ nêu dữ kiện lệch chuẩn để soi kỹ hơn, KHÔNG kết luận "
                 "thao túng/làm giá và KHÔNG phải khuyến nghị giao dịch."),
    }
    
    _anomalies_cache[db_path] = {
        "ts": now,
        "data": base_res,
        "vol_by_sym": vol_by_sym
    }

    res = dict(base_res)
    res["signals"] = res["signals"][:limit]
    res["foreign_flip"] = fx
    return res


if __name__ == "__main__":
    root = _PROJECT_ROOT
    db = os.path.join(root, "data-crawler", "database", "market.db")
    r = scan_anomalies(db)
    print("available:", r["available"], "| n_signals:", r.get("n_signals"),
          "| stale:", r.get("stale"), "| by_kind:", r.get("by_kind"))
    print("coverage:", r.get("coverage"), "| foreign:", r["foreign_flip"]["reason"])
    for s in r["signals"][:10]:
        ns = s.get("metrics", {}).get("news_status", "")
        print(f"  [{s['severity']:4}] {s['kind']:18} {s['symbol']:6} {ns:14} {s['headline']}")
