import sys, os

file_path = 'modules/market_overview/anomaly.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace _rss_backfill
old_rss = '''def _rss_backfill(signals: list[dict], names: dict) -> None:
    """Top-N mã price_run ngoài coverage đi lấy RSS báo chí (song song, có deadline).

    Có bài → cập nhật news_status='rss_found' + rss_count, đổi headline sang
    "có N bài báo chí (chưa phải CBTT)". Lỗi/không có → giữ nguyên 'uncrawled'.
    """
    cand = [s for s in signals
            if s["kind"] == "price_run_no_news"
            and s.get("metrics", {}).get("news_status") == "uncrawled"]
    if not cand:
        return
    cand.sort(key=lambda s: -s["_mag"])
    cand = cand[:CONFIG["rss_top_n"]]

    try:
        import sys
        crawl_src = os.path.join(_PROJECT_ROOT, "data-crawler", "src")
        if crawl_src not in sys.path:
            sys.path.insert(0, crawl_src)
        import news_rss  # module có sẵn bên data-crawler
    except Exception:
        return

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _one(sig):
        try:
            arts = news_rss.fetch(sig["symbol"], names.get(sig["symbol"], ""), limit=5)
            return sig, arts
        except Exception:
            return sig, []

    ex = ThreadPoolExecutor(max_workers=min(5, len(cand)))
    try:
        futs = [ex.submit(_one, s) for s in cand]
        for fut in as_completed(futs, timeout=CONFIG["rss_deadline_s"]):
            sig, arts = fut.result()
            if arts:
                n = len(arts)
                sig["metrics"]["news_status"] = "rss_found"
                sig["metrics"]["rss_count"] = n
                run = sig["metrics"].get("run_pct", 0)
                direction = "tăng" if run > 0 else "giảm"
                sig["headline"] = (
                    f"Giá {direction} {abs(round(run,1))}% trong "
                    f"{sig['metrics'].get('days')} phiên — có {n} bài báo chí "
                    f"(chưa phải CBTT)")
                sig["verify"] = ("Đã có bài báo chí (RSS) nhưng CHƯA có công bố "
                                 "thông tin chính thức — đọc để hiểu bối cảnh, "
                                 "chưa thay được CBTT.")
    except Exception:
        pass  # timeout tổng / lỗi mạng → bỏ qua, giữ trạng thái 'uncrawled'
    finally:
        ex.shutdown(wait=False)'''

new_rss = '''_crawl_src = os.path.join(_PROJECT_ROOT, "data-crawler", "src")
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
    t.start()'''

if old_rss in content:
    content = content.replace(old_rss, new_rss)
    print("Replaced _rss_backfill")
else:
    print("Could not find _rss_backfill!")

# 2. Cache SQLite df
old_db = '''def _load(con) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT symbol, time, open, high, low, close, volume "
        "FROM price ORDER BY symbol, time", con)'''

new_db = '''_DB_CACHE = {}
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
    return df'''

if old_db in content:
    content = content.replace(old_db, new_db)
    print("Replaced _load")
else:
    print("Could not find _load!")

# 3. Cache foreign history
old_fh = '''def _read_foreign_history() -> dict:
    """{symbol: [ {date, net, buy, sell}... ]} từ data-crawler/companies/*/market/."""
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
    return out'''

new_fh = '''_FH_CACHE = {}
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
    return out'''

if old_fh in content:
    content = content.replace(old_fh, new_fh)
    print("Replaced _read_foreign_history")
else:
    print("Could not find _read_foreign_history!")

# 4. Remove _anomalies_cache completely!
old_ac_top = '''def scan_anomalies(db_path: str, limit: int = 80, board_rows: list | None = None,
                   today: str | None = None) -> dict:
    """Quét toàn thị trường → danh sách tín hiệu bất thường (sắp theo mức độ).

    board_rows: rows bảng giá LIVE (:5555) để bù foreign snapshot + turnover — tuỳ chọn.
    today: 'YYYY-MM-DD' (mặc định hôm nay) — dùng để đánh dấu dữ liệu cũ (stale).
    """
    global _anomalies_cache
    now = time.time()
    today_str = today or datetime.now().strftime("%Y-%m-%d")
    
    # 1. Trả cache nếu có và còn hạn (15s)
    cached = _anomalies_cache.get(db_path)
    if cached and (now - cached["ts"] < 15):
        # Trả về bản sao + đính kèm board_rows nếu có
        res = dict(cached["data"])
        res["signals"] = res["signals"][:limit]
        res["foreign_flip"] = _detect_foreign_flip(cached["vol_by_sym"], board_rows or [], today_str)
        return res'''

new_ac_top = '''def scan_anomalies(db_path: str, limit: int = 80, board_rows: list | None = None,
                   today: str | None = None) -> dict:
    """Quét toàn thị trường → danh sách tín hiệu bất thường (sắp theo mức độ).

    board_rows: rows bảng giá LIVE (:5555) để bù foreign snapshot + turnover — tuỳ chọn.
    today: 'YYYY-MM-DD' (mặc định hôm nay) — dùng để đánh dấu dữ liệu cũ (stale).
    """
    today_str = today or datetime.now().strftime("%Y-%m-%d")'''

if old_ac_top in content:
    content = content.replace(old_ac_top, new_ac_top)
    print("Replaced _anomalies_cache top")
else:
    print("Could not find _anomalies_cache top!")

old_ac_bot = '''    base_res = {
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
    res["foreign_flip"] = _detect_foreign_flip(vol_by_sym, board_rows or [], today_str)
    return res'''

new_ac_bot = '''    base_res = {
        "available": True,
        "as_of": as_of,
        "stale": stale,
        "expected_session": expected,
        "n_signals": len(signals),
        "by_kind": by_kind,
        "signals": signals[:limit],
        "coverage": {"n_with_news": len(covered),
                     "n_symbols": int(df["symbol"].nunique())},
        "foreign_flip": _detect_foreign_flip(vol_by_sym, board_rows or [], today_str),
        "note": ("Radar chỉ nêu dữ kiện lệch chuẩn để soi kỹ hơn, KHÔNG kết luận "
                 "thao túng/làm giá và KHÔNG phải khuyến nghị giao dịch."),
    }
    return base_res'''

if old_ac_bot in content:
    content = content.replace(old_ac_bot, new_ac_bot)
    print("Replaced _anomalies_cache bottom")
else:
    print("Could not find _anomalies_cache bottom!")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
