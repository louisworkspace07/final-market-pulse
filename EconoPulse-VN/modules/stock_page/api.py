# -*- coding: utf-8 -*-
"""Trang phân tích đơn doanh nghiệp (PILLAR-A · A1+A2) — /api/stock/<sym>.

Gom MỌI dữ liệu về 1 mã từ nguồn ĐÃ CÓ (không gọi AI, không crawl mới):
- companies / financials / news / events / ai_analysis / price  ← market.db
- health_scores.json                                            ← gateway data
- peers.compute (trung vị ngành)                                ← Crawl Data/src/peers.py
- fund_detail (BCTC 4 quý + ratio KBS)                          ← context_builder

Audit trail: mỗi khối có "source" + ngày; citation id giữ chuẩn [N..][E..][CD-mã].
Legal: chỉ dữ kiện + thống kê mô tả; KHÔNG sinh khuyến nghị.
"""
import datetime as _dt
import json
import os
import sqlite3

from modules.market_overview.context_builder import (
    fund_detail, _iso_date, _peers, _is_quarter, _period_key, _norm_pct,
)
from modules.common import legal as _legal

# A6 · 3 engine đã có trong "Crawl Data/src" nhưng trước đây KHÔNG được nối ra API
# (chỉ chạy trong pipeline P4 rồi nằm im trong ai_analysis.metrics). context_builder
# đã chèn "Crawl Data" vào sys.path khi import ở trên → import chéo an toàn.
# Thiếu module (checkout lẻ) → None, các khối A6 vắng mặt chứ KHÔNG làm chết endpoint.
try:
    from src import sector_metrics as _sector_metrics      # type: ignore
except Exception:
    _sector_metrics = None
try:
    from src import earnings_quality as _earnings_quality  # type: ignore
except Exception:
    _earnings_quality = None
try:
    from src import fundamentals as _fundamentals          # type: ignore
except Exception:
    _fundamentals = None
try:
    from src import raw_ratios as _raw_ratios              # type: ignore
except Exception:
    _raw_ratios = None


# ---------------------------------------------------------------- báo chí có nguồn
# Tin trong market.db là CÔNG BỐ THÔNG TIN của vnstock/VCI: đo thật trên FPT thì
# 0/50 bản ghi có `source_link`, 0/50 có `short_content` — nghĩa là tab Tin trên
# :9999 xưa nay chỉ có tiêu đề pháp lý trần, không nguồn, không nội dung để đọc.
# Hai tệp DUY NHẤT có nguồn kiểm chứng được lại nằm NGOÀI market.db và trước đây
# chỉ xem được ở tab "Dữ liệu gốc":
#   news/press.json     — Google News RSS: tên toà soạn + link
#   news/articles.json  — Vietstock (KBS): `head` là nội dung tóm tắt thật
# Đọc thẳng từ thư mục companies/ theo đúng cách raw_sources.py đang làm.

def _press_date(v) -> str:
    """RSS trả 'Mon, 27 Jul 2026 10:21:19 GMT', Vietstock trả ISO. Về YYYY-MM-DD."""
    s = str(v or "").strip()
    if not s:
        return ""
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).date().isoformat()
    except Exception:                                        # noqa: BLE001
        return ""


def _press_rows(db_path: str, symbol: str, limit: int = 12) -> list[dict]:
    """Báo chí + bài báo, gộp và xếp theo ngày giảm dần. Lỗi đọc tệp → []."""
    from . import raw_sources

    base = os.path.join(raw_sources._companies_dir(db_path), symbol.upper())
    out: list[dict] = []
    for rel, kind in (("news/press.json", "press"), ("news/articles.json", "article")):
        p = os.path.join(base, rel.replace("/", os.sep))
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                items = json.load(f).get("items") or []
        except (OSError, ValueError):
            continue
        for it in items:
            title = str(it.get("title") or "").strip()
            if not title:
                continue
            out.append({
                "kind": kind,
                "title": title,
                "publisher": str(it.get("source") or "").strip(),
                "publisher_url": str(it.get("source_url") or "").strip(),
                "link": str(it.get("link") or "").strip(),
                "summary": str(it.get("head") or "").strip(),
                "date": _press_date(it.get("public_date")),
            })
    out.sort(key=lambda r: r["date"] or "", reverse=True)
    rows = out[:limit]
    for i, r in enumerate(rows):
        r["id"] = f"P{i + 1}"                    # citation [P..] — tách khỏi [N..]/[E..]
    return rows


def _ro(db_path: str) -> sqlite3.Connection:
    """Kết nối chỉ-đọc — an toàn tuyệt đối với crawler đang ghi (WAL)."""
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)


def _health_list(data_dir: str) -> list:
    path = os.path.join(data_dir, "health_scores.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("companies", [])


def _health_map(data_dir: str) -> dict:
    return {c["symbol"]: c for c in _health_list(data_dir)}


def _median(xs):
    xs = sorted(v for v in xs if v is not None)
    n = len(xs)
    if n == 0:
        return None
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _sector_radar_medians(conn, data_dir, sector):
    """Trung vị ngành cho 2 TRỤC RADAR có dữ liệu ngành TRUNG THỰC (không bịa):
    - Sức khỏe: trung vị health_score các mã cùng ngành
    - Hiệu quả: trung vị ROE ngành, quy về thang eff (roe/25*100)
    3 trục còn lại (Định giá/Cổ tức/Tăng trưởng) không có trung vị ngành honest
    → trả None để frontend KHÔNG vẽ overlay ở đó. sector lấy từ market.db.companies."""
    if not sector:
        return {}
    # map symbol→sector từ market.db (health_scores.json không có cột sector)
    try:
        rows = conn.execute(
            "SELECT symbol, sector FROM companies WHERE sector=?", (sector,)).fetchall()
    except sqlite3.Error:
        return {}
    syms = {r[0] for r in rows}
    if len(syms) < 3:                       # ngành quá ít mã → không đại diện
        return {}
    hs, roes = [], []
    for c in _health_list(data_dir):
        if c.get("symbol") in syms:
            if c.get("health_score") is not None:
                hs.append(c["health_score"])
            if c.get("roe") is not None:
                roes.append(c["roe"])
    med_h = _median(hs)
    med_roe = _median(roes)
    out = {"n": len(syms)}
    if med_h is not None:
        out["health"] = round(med_h)
    if med_roe is not None:
        out["eff"] = round(_clamp(med_roe / 25 * 100))
    return out


# Trường trong bản phân tích P4 mang tính KHUYẾN NGHỊ → không bao giờ ra API.
# Giữ đúng ranh giới của legal.py: hệ thống mô tả dữ kiện, không khuyên mua/bán.
_AI_DROP_FIELDS = ("investment_rating", "verdict", "target_price", "recommendation")


# CODE CHẾT ĐÃ GỠ: từng có 2 định nghĩa `_event_type` liền nhau + bảng tiền tố
# `_EVENT_TYPES`. Bản thứ hai (bên dưới) đè bản thứ nhất ở thời điểm import, nên
# bảng tiền tố và nhãn của nó (`cash_dividend`, `share_issue`, `insider`…) chưa
# bao giờ chạy — trong khi frontend lại lọc theo nhãn của bản đang chạy
# (`cash`, `issue`, `insider`…). Giữ lại đúng một bản để không còn hai bộ nhãn.

# events.event_name là cột PHÂN LOẠI sạch (15 giá trị trên toàn DB) → phân loại ở
# server thay vì để mỗi client regex lại chuỗi tiếng Việt (WS-5 đang làm ở JS).
# Nhóm: cash (cổ tức tiền) · issue (phát hành/niêm yết thêm) · insider (giao dịch
# nội bộ) · meeting (ĐHCĐ) · listing (niêm yết/chuyển sàn) · other.
def _event_type(event_name: str, value_per_share=None) -> str:
    n = (event_name or "").lower()
    if "cổ tức" in n or value_per_share is not None:
        return "cash"
    if "giao dịch nội bộ" in n:
        return "insider"
    if "phát hành" in n or "niêm yết thêm" in n:
        return "issue"
    if "đại hội" in n or "nghị quyết" in n:
        return "meeting"
    if "niêm yết" in n or "chuyển sàn" in n:
        return "listing"
    return "other"


def stock_detail(db_path: str, data_dir: str, symbol: str) -> dict:
    symbol = symbol.upper().strip()
    conn = _ro(db_path)
    try:
        row = conn.execute(
            "SELECT symbol, organ_name, exchange, sector, market_cap, current_price "
            "FROM companies WHERE symbol=?", (symbol,)).fetchone()
        if row is None:
            return {"error": f"không có mã {symbol} trong market.db"}
        info = {"symbol": row[0], "name": row[1] or "", "exchange": row[2] or "",
                "sector": row[3] or "", "market_cap": row[4], "current_price": row[5]}

        # Ảnh 17 · Thông tin cơ bản doanh nghiệp (SLCP lưu hành, room ngoại, sở hữu
        # nhà nước, GTGD bình quân) nằm trong companies/<mã>/profile.json từ P2 —
        # trước đây không được nối ra API nên trang So sánh toàn "—".
        # CHỦ Ý LOẠI BỎ rating / target_price / upside (khuyến nghị của CTCK) —
        # tuân thủ legal.py, hệ thống KHÔNG hiển thị giá mục tiêu.
        # §3.1: F0 phải biết DOANH NGHIỆP NÀY LÀM GÌ trước khi xem chỉ số →
        # company_profile (mô tả ngành nghề) + organ_name (tên pháp lý đầy đủ)
        # là dữ kiện thuần mô tả, KHÔNG phải khuyến nghị → được phép ra API.
        _SAFE_PROFILE_KEYS = (
            "issue_share", "foreigner_percentage", "maximum_foreign_percentage",
            "state_percentage", "average_match_value1_month",
            "average_match_volume1_month", "highest_price1_year", "lowest_price1_year",
            "organ_short_name", "com_type_code",
            "company_profile", "organ_name",
        )
        try:
            _p = os.path.join(os.path.dirname(db_path), "..", "companies",
                              symbol, "profile.json")
            _p = os.path.normpath(_p)
            if os.path.exists(_p):
                with open(_p, encoding="utf-8") as f:
                    _ov = (json.load(f) or {}).get("overview") or {}
                for k in _SAFE_PROFILE_KEYS:
                    if _ov.get(k) not in (None, ""):
                        info[k] = _ov[k]
        except Exception:
            pass          # thiếu hồ sơ → các trường này vắng, UI hiện "—"

        # ---- giá 120 phiên gần nhất (nếu mã nằm trong nhóm có giá)
        prows = conn.execute(
            "SELECT time, close, volume FROM price WHERE symbol=? "
            "ORDER BY time DESC LIMIT 120", (symbol,)).fetchall()
        prows.reverse()
        price = None
        if prows:
            closes = [r[1] for r in prows]
            chg = ((closes[-1] - closes[-2]) / closes[-2] * 100) if len(closes) >= 2 else None
            price = {"series": [[_iso_date(r[0]), r[1]] for r in prows],
                     "last": closes[-1], "change_pct": chg,
                     "as_of": _iso_date(prows[-1][0]),
                     "volume": [[_iso_date(r[0]), r[2]] for r in prows],
                     "source": "market.db · price (P6)"}
            # OHLCV cho nến (D1) + range thấp–cao (C7) + volume profile (D10)
            ocols = conn.execute(
                "SELECT time, open, high, low, close, volume FROM price WHERE symbol=? "
                "ORDER BY time DESC LIMIT 120", (symbol,)).fetchall()
            ocols.reverse()
            price["ohlc"] = [
                {"time": _iso_date(r[0]), "open": r[1], "high": r[2],
                 "low": r[3], "close": r[4], "volume": r[5]}
                for r in ocols if None not in (r[1], r[2], r[3], r[4])]

        # ---- BCTC 4 quý + ratio (KBS — VCI year-ratio hỏng)
        try:
            fund = fund_detail(conn, symbol)
        except Exception as e:
            fund = {"error": str(e)[:120]}

        # ---- peer trung vị ngành (A2)
        peers = None
        if _peers is not None:
            try:
                peers = _peers.compute(conn, symbol)
            except Exception as e:
                peers = {"error": str(e)[:120]}

        # ---- bảng peer cùng ngành: mã đã chấm điểm SK, xếp theo vốn hóa
        health_all = _health_map(data_dir)
        peer_rows = []
        if info["sector"]:
            sec_rows = conn.execute(
                "SELECT symbol, organ_name, market_cap FROM companies "
                "WHERE sector=? AND symbol!=? ORDER BY market_cap DESC LIMIT 40",
                (info["sector"], symbol)).fetchall()
            # ưu tiên mã ĐÃ chấm điểm SK; thiếu thì bù bằng mã vốn hóa lớn (điểm "—")
            scored = [(s, n, m) for s, n, m in sec_rows if s in health_all]
            unscored = [(s, n, m) for s, n, m in sec_rows if s not in health_all]
            for s, name, mcap in (scored + unscored)[:8]:
                h = health_all.get(s, {})
                peer_rows.append({
                    "symbol": s, "name": name or "", "market_cap": mcap,
                    "health": h.get("health_score"), "z_score": h.get("z_score"),
                    "z_zone": h.get("z_zone"), "f_score": h.get("f_score"),
                    "f_max": h.get("f_max"), "roa": h.get("roa"), "roe": h.get("roe"),
                })

        # ---- sức khỏe chính mã này
        health = health_all.get(symbol)

        # ---- tin CBTT [N..] + sự kiện [E..] của riêng mã
        nrows = conn.execute(
            "SELECT title, short_content, source_link, public_date FROM news "
            "WHERE symbol=? ORDER BY public_date DESC LIMIT 8", (symbol,)).fetchall()
        news = [{"id": f"N{i+1}", "title": r[0],
                 "summary": (r[1] or "")[:180], "content": (r[1] or ""),
                 "link": r[2] or "", "date": _iso_date(r[3])}
                for i, r in enumerate(nrows)]

        # LIMIT 8 cũ quá chặt: FPT có 9 sự kiện cùng ngày 2026-06-29 (nội bộ +
        # phát hành) nên 8 dòng đầu KHÔNG chứa cổ tức nào, dù mã có 2 kỳ trả tiền
        # (1.000 đ/cp 2026-05-22 và 2025-11-19) → card cổ tức luôn rỗng. Nâng 40 để
        # timeline đủ bề dày, KÈM khoá `dividends` riêng bên dưới để card tiền mặt
        # không phụ thuộc vào việc cổ tức có rơi vào cửa sổ 40 dòng hay không.
        erows = conn.execute(
            "SELECT event_name, title, public_date, value_per_share FROM events "
            "WHERE symbol=? ORDER BY public_date DESC LIMIT 40", (symbol,)).fetchall()
        today = _dt.date.today().isoformat()
        events = [{"id": f"E{i+1}", "event": r[0], "title": r[1],
                   "date": _iso_date(r[2]), "value_per_share": r[3],
                   "event_type": _event_type(r[0], r[3]),
                   "upcoming": _iso_date(r[2]) >= today}
                  for i, r in enumerate(erows)]

        # CHỒNG CHÉO ĐÃ TÁCH: "Giao dịch nội bộ" tồn tại ở HAI chỗ mang cùng một
        # tên. `ownership/insider_deals.json` là nguồn KBS riêng và gần như luôn
        # rỗng (đo thật: FPT count=0, note="nguồn không trả dữ liệu"), trong khi
        # dữ liệu THẬT nằm lẫn trong `events` — FPT có 21/30 sự kiện là giao dịch
        # nội bộ, chúng chiếm hết dòng thời gian và đẩy cổ tức/phát hành ra khỏi
        # tầm nhìn. Tách thành danh sách riêng, và `corp_events` là phần sự kiện
        # doanh nghiệp còn lại để timeline không bị một loại lấn át.
        insider = [e for e in events if e["event_type"] == "insider"]
        corp_events = [e for e in events if e["event_type"] != "insider"]

        # Cổ tức TIỀN MẶT tách riêng — cùng truy vấn đã dùng ở stock_analysis (P19)
        # để 2 endpoint không bao giờ lệch nhau.
        drows = conn.execute(
            "SELECT event_name, public_date, value_per_share FROM events "
            "WHERE symbol=? AND value_per_share IS NOT NULL "
            "ORDER BY public_date DESC LIMIT 12", (symbol,)).fetchall()
        dividends = {"history": [{"event": r[0], "date": _iso_date(r[1]),
                                  "value_per_share": r[2]} for r in drows],
                     "source": "market.db · events (value_per_share)"}

        # ---- phân tích AI đã lưu (P4) — citation [CD-<sym>]
        arow = conn.execute(
            "SELECT analysis, updated_at FROM ai_analysis WHERE symbol=?",
            (symbol,)).fetchone()
        ai = None
        if arow:
            try:
                _data = json.loads(arow[0])
                # PHÁP LÝ (legal.py · Luật CK 2019 Điều 71): schema P4 có trường
                # `investment_rating` / `verdict` mang nội dung KHUYẾN NGHỊ
                # ("giảm tỷ trọng", "tăng tỷ trọng"…). Giao diện không vẽ chúng,
                # nhưng để trong payload API là đã phát tán — client nào cũng đọc
                # được, và AI hạ nguồn có thể trích lại. Dùng legal.scrub() thay vì
                # .pop() thủ công 4 khoá cấp 1: scrub() đệ quy MỌI độ sâu, nên nếu
                # 1 khoá cấm (vd investment_rating) từng lọt vào bên trong aspects/
                # causes ở lượt AI sau này thì vẫn bị chặn, không phải sửa lại đây.
                _data = _legal.scrub(_data, extra_keys=_AI_DROP_FIELDS)
                ai = {"data": _data, "updated_at": _iso_date(arow[1]),
                      "citation": f"CD-{symbol}", "source": "market.db · ai_analysis (P4)"}
            except Exception:
                ai = None

        # ---- sở hữu & quản trị (P2, companies/<mã>/ownership/*.json) — dữ
        # kiện mô tả thuần (ai giữ chức gì, sở hữu bao nhiêu, công ty con nào,
        # lịch sử vốn điều lệ) — KHÔNG có rating/target nên không vướng
        # legal.py, chỉ đơn giản là chưa từng được nối ra API trước đây.
        ownership = {}
        try:
            _own_dir = os.path.normpath(os.path.join(
                os.path.dirname(db_path), "..", "companies", symbol, "ownership"))

            def _own_items(name):
                fp = os.path.join(_own_dir, f"{name}.json")
                if not os.path.exists(fp):
                    return []
                with open(fp, encoding="utf-8") as f:
                    return (json.load(f) or {}).get("items") or []

            officers = [o for o in _own_items("officers") if o.get("officer_name")]
            if officers:
                ownership["officers"] = [
                    {"name": o.get("officer_name"), "position": o.get("officer_position"),
                     "own_percent": o.get("officer_own_percent")} for o in officers]

            subs = [s for s in _own_items("subsidiaries") if s.get("organ_name")]
            if subs:
                ownership["subsidiaries"] = [
                    {"name": s.get("organ_name"), "code": s.get("sub_organ_code"),
                     "own_percent": s.get("ownership_percent")} for s in subs]

            shs = sorted((s for s in _own_items("shareholders") if s.get("share_holder")),
                         key=lambda s: s.get("share_own_percent") or 0, reverse=True)
            if shs:
                ownership["shareholders"] = [
                    {"name": s.get("share_holder"), "quantity": s.get("quantity"),
                     "own_percent": s.get("share_own_percent")} for s in shs[:10]]
                ownership["shareholders_total"] = len(shs)

            caph = sorted(
                (c for c in _own_items("capital_history") if c.get("date") not in (None, "", "NaT")),
                key=lambda c: c["date"], reverse=True)
            if caph:
                ownership["capital_history"] = [
                    {"date": _iso_date(c.get("date")), "charter_capital": c.get("charter_capital"),
                     "currency": c.get("currency")} for c in caph[:12]]
        except Exception:
            pass          # thiếu hồ sơ sở hữu → UI hiện trống, không lỗi endpoint

        # ---- xu hướng khối ngoại nhiều ngày (P6, companies/<mã>/market/
        # foreign_history.jsonl) — trang mã trước đây chỉ có snapshot bảng giá
        # 1 ngày (drawForeign trong stock.js); file này tích lũy mỗi ngày 1
        # dòng nên càng chạy lâu càng có xu hướng dài, dùng chung công thức đọc
        # với anomaly.py::_read_foreign_history() (foreign_flip cấp thị trường).
        foreign_history = []
        try:
            _fh_path = os.path.normpath(os.path.join(
                os.path.dirname(db_path), "..", "companies", symbol,
                "market", "foreign_history.jsonl"))
            if os.path.exists(_fh_path):
                with open(_fh_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        r = json.loads(line)
                        d_ = str(r.get("date", ""))[:10]
                        net = r.get("foreign_net")
                        if d_ and isinstance(net, (int, float)):
                            foreign_history.append({
                                "date": d_, "net": net,
                                "buy": r.get("foreign_buy_volume"),
                                "sell": r.get("foreign_sell_volume")})
                foreign_history.sort(key=lambda r: r["date"])
                foreign_history = foreign_history[-60:]
        except Exception:
            foreign_history = []
    finally:
        conn.close()

    return {
        "info": info, "price": price, "fund": fund, "peers": peers,
        "peer_rows": peer_rows, "health": health, "news": news, "events": events,
        "corp_events": corp_events, "insider": insider,
        "press": _press_rows(db_path, symbol),
        "dividends": dividends, "ai": ai, "ownership": ownership,
        "foreign_history": foreign_history,
        "meta": {"generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
                 "sources": ["market.db (companies/financials/news/events/price/ai_analysis)",
                             "companies/<mã>/news/press.json (Google News RSS)",
                             "companies/<mã>/news/articles.json (Vietstock qua KBS)",
                             "health_scores.json", "peers.py trung vị ngành"]},
    }


# ======================================================================
#  TAB "PHÂN TÍCH 360" — /api/stock/<sym>/analysis  (plan §5.2b, P1–P19)
#  Gom chuỗi BCTC NHIỀU NĂM từ market.db cho radar + các widget định lượng.
#  Chỉ dữ kiện thống kê mô tả — KHÔNG khuyến nghị / giá mục tiêu (legal.py).
# ======================================================================

def _year_series(conn, symbol, statement, item_id, n=6):
    """Chuỗi (year:int, value) theo NĂM (bỏ quý), cũ→mới, tối đa n năm gần nhất."""
    rows = conn.execute(
        "SELECT period, value FROM financials WHERE symbol=? AND statement=? "
        "AND item_id=? AND value IS NOT NULL", (symbol, statement, item_id)).fetchall()
    ys = [(int(p[:4]), v) for p, v in rows if not _is_quarter(p) and p[:4].isdigit()]
    ys.sort(key=lambda x: x[0])
    return ys[-n:]


def _quarter_series(conn, symbol, statement, item_id, n=8):
    """Chuỗi (period, value) theo QUÝ, cũ→mới, tối đa n quý gần nhất."""
    rows = conn.execute(
        "SELECT period, value FROM financials WHERE symbol=? AND statement=? "
        "AND item_id=? AND value IS NOT NULL", (symbol, statement, item_id)).fetchall()
    qs = [(p, v) for p, v in rows if _is_quarter(p)]
    qs.sort(key=lambda x: _period_key(x[0]))
    return qs[-n:]


def _cagr(series):
    """CAGR % từ chuỗi [(year,value)] (đầu→cuối); None nếu không tính được."""
    if len(series) < 2:
        return None
    v0, v1 = series[0][1], series[-1][1]
    yrs = series[-1][0] - series[0][0]
    if v0 is None or v1 is None or v0 <= 0 or v1 <= 0 or yrs <= 0:
        return None
    return ((v1 / v0) ** (1 / yrs) - 1) * 100


def _clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def _bn(v):
    """VND → tỷ đồng (float, làm tròn), None-safe."""
    return round(v / 1e9, 1) if v is not None else None


# ======================================================================
#  A6 · nối sector_model / earnings_quality / valuation_band ra API
# ======================================================================

def _records(conn, symbol: str, statement: str) -> list[dict]:
    """Nạp 1 báo cáo về dạng records mà sector_metrics/earnings_quality/fundamentals
    mong đợi.

    Bảng `financials` KHÔNG có cột `period_type` (đã kiểm: cột thật là symbol/
    statement/item_id/item/item_en/period/value), nhưng các engine lọc kỳ bằng
    `r["period_type"] in ("Y","Q")` → phải suy ra từ định dạng chuỗi period
    ("2026-Q1" = quý, "2025" = năm), đúng quy ước peers.py::_period_kind.
    Không suy được → bỏ hẳn dòng, KHÔNG mặc định "Y" (một dòng quý bị dán nhãn
    năm sẽ làm lệch mọi chuỗi TTM/CAGR ở hạ nguồn)."""
    rows = conn.execute(
        "SELECT item_id, item, period, value FROM financials "
        "WHERE symbol=? AND statement=? AND value IS NOT NULL",
        (symbol, statement)).fetchall()
    out = []
    for item_id, item, period, value in rows:
        p = str(period)
        if _is_quarter(p):
            ptype = "Q"
        elif p.strip()[:4].isdigit() and len(p.strip()) == 4:
            ptype = "Y"
        else:
            continue
        out.append({"item_id": item_id, "item": item, "period": p,
                    "value": value, "period_type": ptype})
    return out


def _build_a6(conn, symbol: str, sector: str, peers, aband) -> dict:
    """Tính 3 khối A6 TRỰC TIẾP từ market.db thay vì đọc lại ai_analysis.

    Vì sao không dùng ai_analysis: bảng đó chỉ có 400/1.5k mã và ảnh chụp có thể
    cũ nhiều tháng; 3 engine này thuần hàm số trên BCTC nên tính lại tại chỗ vừa
    tươi vừa phủ mọi mã có BCTC. Mỗi khối lỗi riêng → None, không kéo sập endpoint.

    valuation_band: TRUYỀN `peer` (trước đây gọi thiếu → nhánh trung vị ngành ở
    fundamentals.py là code chết, `peer_median` luôn None)."""
    out = {"sector_model": None, "earnings_quality": None, "valuation_band": aband}
    inc = _records(conn, symbol, "income_statement")
    bal = _records(conn, symbol, "balance_sheet")
    cf = _records(conn, symbol, "cash_flow")
    rat = _records(conn, symbol, "ratio")
    if not (inc or bal):
        return out

    is_bank = False
    if _raw_ratios is not None:
        try:
            is_bank = bool(_raw_ratios.is_bank(inc, bal))
        except Exception:
            is_bank = False

    if _sector_metrics is not None:
        try:
            raw = _raw_ratios.compute(inc, bal, cf) if _raw_ratios is not None else None
            out["sector_model"] = _sector_metrics.compute(
                rat, inc, bal, cf, sector or None, raw=raw)
        except Exception as e:
            out["sector_model"] = {"error": str(e)[:120]}

    if _earnings_quality is not None:
        try:
            out["earnings_quality"] = _earnings_quality.compute(
                inc, bal, cf, rat, is_bank=is_bank)
        except Exception as e:
            out["earnings_quality"] = {"error": str(e)[:120]}

    # Dải định giá: tự tính (kèm peer) — chỉ lấy bản của AI làm dự phòng.
    #
    # CHỦ Ý DÙNG P/E CƠ SỞ `ratio` (không phải P/E TTM) làm `current` ở đây: chuỗi
    # lịch sử mà valuation_band so percentile CHÍNH LÀ ratio.pe_ratio theo kỳ. Nhét
    # P/E TTM (giá hôm nay / EPS 4 quý) vào so với dải FY là trộn 2 cơ sở khác nhau
    # — đúng loại lỗi A3 đang sửa. Đo thật trên FPT: TTM 13,09 nằm dưới cả min dải
    # (15,53) → percentile bị ép về 0 và nhãn thành "vùng thấp" một cách giả tạo;
    # cùng cơ sở ratio (15,92) cho percentile 33 = "vùng giữa". P/E TTM vẫn được
    # công bố riêng ở khối `pe` bên dưới, kèm nhãn kỳ của nó.
    if _fundamentals is not None:
        try:
            pe_basis = None
            p_ratio = _latest_ratio_period(rat, "pe_ratio")
            if p_ratio is not None:
                pe_basis = next(
                    (r["value"] for r in rat
                     if r.get("item_id") == "pe_ratio" and r.get("period") == p_ratio
                     and isinstance(r.get("value"), (int, float))), None)
            pb_basis = None
            p_pb = _latest_ratio_period(rat, "pb_ratio")
            if p_pb is not None:
                pb_basis = next(
                    (r["value"] for r in rat
                     if r.get("item_id") == "pb_ratio" and r.get("period") == p_pb
                     and isinstance(r.get("value"), (int, float))), None)
            # fundamentals.valuation_band đọc trung vị ngành ở `peer["pe_median"]`
            # hoặc `peer["median"]["pe"]`, còn peers.compute trả `benchmark` →
            # KHÔNG khớp key nào, nên nhánh trung vị ngành (fundamentals.py:395-399)
            # là code chết và `peer_median` luôn None. Chuyển shape ở đây.
            _bm = ((peers.get("benchmark") or {})
                   if isinstance(peers, dict) and not peers.get("error") else {})
            band = _fundamentals.valuation_band(
                rat, {"pe": pe_basis, "pb": pb_basis},
                peer={"median": {"pe": _bm.get("pe"), "pb": _bm.get("pb")}})
            if isinstance(band, dict):
                # A3: mỗi con số đi kèm KỲ của nó để UI ghi "theo BCTC <kỳ>".
                band["basis"] = "ratio.pe_ratio / pb_ratio theo kỳ (cùng cơ sở với dải lịch sử)"
                band["period"] = p_ratio
                band["pb_period"] = p_pb
                out["valuation_band"] = band
        except Exception:
            pass          # giữ aband làm dự phòng
    return out


def _latest_close_vnd(conn, symbol: str) -> tuple[float | None, str | None]:
    """(giá đóng cửa mới nhất quy về ĐỒNG, ngày). Bảng price lưu theo nghìn đồng
    (FPT = 62.9); >1000 coi như đã là đồng — cùng quy ước fundamentals._latest_close_vnd."""
    row = conn.execute(
        "SELECT time, close FROM price WHERE symbol=? AND close IS NOT NULL "
        "ORDER BY time DESC LIMIT 1", (symbol,)).fetchone()
    if not row or not isinstance(row[1], (int, float)):
        return None, None
    c = float(row[1])
    return (c * 1000.0 if 0 < c < 1000 else c), _iso_date(row[0])


def _latest_ratio_period(rat: list[dict], item_id: str) -> str | None:
    """Kỳ MỚI NHẤT của 1 item trong statement='ratio'. Ưu tiên năm rồi mới quý —
    giữ đúng quy ước peers._latest_ratio để P/E của 2 tầng không lệch kỳ."""
    rows = [(r["period"], r["value"]) for r in rat
            if r.get("item_id") == item_id and isinstance(r.get("value"), (int, float))]
    if not rows:
        return None
    years = [pv for pv in rows if not _is_quarter(pv[0])]
    quarters = [pv for pv in rows if _is_quarter(pv[0])]
    chosen = years or quarters
    if not chosen:
        return None
    chosen.sort(key=lambda pv: _period_key(pv[0]))
    return chosen[-1][0]


# ======================================================================
#  A3 · MỘT nguồn chân lý cho P/E
# ======================================================================

def _pe_truth(conn, symbol: str, rat: list[dict], peers) -> tuple[float | None, str | None]:
    """P/E dùng CHUNG cho mọi tab + nhãn kỳ dữ liệu của nó.

    Vì sao cần: cùng mã FPT, trang đang hiện 15,91 ở tab này và 11,06 ở tab khác
    (lệch 44%) — không phải lỗi làm tròn mà là HAI KỲ khác nhau: 15,91 là
    `ratio.pe_ratio` kỳ FY2025, còn 11,06 là ảnh chụp trong ai_analysis tính từ
    giá lúc crawl. Lệch dấu này đảo ngược kết luận đắt/rẻ nên phải chốt 1 nguồn.

    Thứ tự ưu tiên:
      1. P/E TTM = giá mới nhất / EPS 4 quý liên tiếp → tươi nhất, sạch mùa vụ,
         và là thứ khớp với giá đang hiện trên trang. Kỳ = "TTM tới <quý>".
      2. `ratio.pe_ratio` kỳ mới nhất → khi thiếu EPS quý. Kỳ = period thật.
      3. peers.self.pe → chốt hạ, cùng nguồn với strip so ngành.
    EPS TTM ≤ 0 → bỏ nhánh 1 (P/E âm không mang nghĩa)."""
    eps_q = [(r["period"], r["value"]) for r in rat
             if r.get("item_id") == "eps_basic_vnd" and r.get("period_type") == "Q"
             and isinstance(r.get("value"), (int, float))]
    if not eps_q:
        eps_q = [(p, v) for p, v in _quarter_series(
            conn, symbol, "income_statement", "eps_basic_vnd", n=8)]
    eps_q.sort(key=lambda x: _period_key(x[0]))
    if len(eps_q) >= 4:
        eps_ttm = sum(v for _, v in eps_q[-4:])
        close_vnd, _d = _latest_close_vnd(conn, symbol)
        if eps_ttm > 0 and close_vnd:
            return round(close_vnd / eps_ttm, 2), f"TTM tới {eps_q[-1][0]}"

    p = _latest_ratio_period(rat, "pe_ratio")
    if p is not None:
        vals = [r["value"] for r in rat
                if r.get("item_id") == "pe_ratio" and r.get("period") == p
                and isinstance(r.get("value"), (int, float))]
        if vals:
            return round(vals[-1], 2), p

    if isinstance(peers, dict) and not peers.get("error"):
        v = (peers.get("self") or {}).get("pe")
        if isinstance(v, (int, float)):
            return round(v, 2), None
    return None, None


def stock_analysis(db_path: str, data_dir: str, symbol: str) -> dict:
    """Dữ liệu cho tab 'Phân tích 360'. Đọc market.db, tính chuỗi nhiều năm +
    5 điểm radar. Không AI, không crawl. Legal-safe: chỉ dữ kiện + thống kê."""
    symbol = symbol.upper().strip()
    conn = _ro(db_path)
    try:
        row = conn.execute(
            "SELECT symbol, organ_name, exchange, sector FROM companies WHERE symbol=?",
            (symbol,)).fetchone()
        if row is None:
            return {"error": f"không có mã {symbol} trong market.db"}
        info = {"symbol": row[0], "name": row[1] or "", "exchange": row[2] or "",
                "sector": row[3] or ""}

        health = _health_map(data_dir).get(symbol) or {}

        # ---- peer trung vị ngành (dùng cho strip P7/P13/P15/P17)
        peers = None
        if _peers is not None:
            try:
                peers = _peers.compute(conn, symbol)
            except Exception as e:
                peers = {"error": str(e)[:120]}

        # ---- AI đã lưu (lấy valuation_band + metrics — nếu có) cho định giá
        aband = None
        arow = conn.execute(
            "SELECT analysis FROM ai_analysis WHERE symbol=?", (symbol,)).fetchone()
        if arow:
            try:
                aband = (json.loads(arow[0]).get("metrics") or {}).get("valuation_band")
            except Exception:
                aband = None

        # ---- chuỗi năm cốt lõi ----
        IS, CF, BS, RT = "income_statement", "cash_flow", "balance_sheet", "ratio"
        rev_y = _year_series(conn, symbol, IS, "net_sales")
        npat_y = _year_series(conn, symbol, IS, "net_profit_loss_after_tax")
        gross_y = _year_series(conn, symbol, IS, "gross_profit")
        eps_y = _year_series(conn, symbol, IS, "eps_basic_vnd")
        roe_y = _year_series(conn, symbol, RT, "roe")
        roa_y = _year_series(conn, symbol, RT, "roa")
        nmargin_y = _year_series(conn, symbol, RT, "net_margin")
        gmargin_y = _year_series(conn, symbol, RT, "gross_margin")
        d2e_y = _year_series(conn, symbol, RT, "debt_to_equity")
        asset_turn_y = _year_series(conn, symbol, RT, "total_asset_turnover")
        lev_y = _year_series(conn, symbol, RT, "liabilities_to_equity")
        equity_y = _year_series(conn, symbol, BS, "owners_equity")
        liab_y = _year_series(conn, symbol, BS, "liabilities")
        assets_y = _year_series(conn, symbol, BS, "total_assets")
        cfo_y = _year_series(conn, symbol, CF, "net_cash_inflows_outflows_from_operating_activities")
        cfi_y = _year_series(conn, symbol, CF, "net_cash_inflows_outflows_from_investing_activities")
        cff_y = _year_series(conn, symbol, CF, "net_cash_inflows_outflows_from_financing_activities")
        cash_begin_y = _year_series(conn, symbol, CF, "cash_and_cash_equivalents_at_the_beginning_of_period")
        div_paid_y = _year_series(conn, symbol, CF, "dividends_paid")

        rev_q = _quarter_series(conn, symbol, IS, "net_sales")
        npat_q = _quarter_series(conn, symbol, IS, "net_profit_loss_after_tax")

        def _pct_series(ys):
            return [{"year": y, "value": _norm_pct(v)} for y, v in ys]

        def _bn_series(ys):
            return [{"year": y, "value": _bn(v)} for y, v in ys]

        # ---- P12: DT & LN quá khứ (bn) + biên ròng
        combo = {
            "years": [y for y, _ in rev_y],
            "revenue": _bn_series(rev_y),
            "profit": _bn_series(npat_y),
            "net_margin": _pct_series(nmargin_y),
            "revenue_quarters": [{"period": p, "value": _bn(v)} for p, v in rev_q],
            "profit_quarters": [{"period": p, "value": _bn(v)} for p, v in npat_q],
            "revenue_cagr": _cagr(rev_y),
            "profit_cagr": _cagr(npat_y),
        }

        # ---- P13: biên ròng/gộp so ngành
        margins = {
            "net": _pct_series(nmargin_y),
            "gross": _pct_series(gmargin_y),
            "net_latest": _norm_pct(nmargin_y[-1][1]) if nmargin_y else None,
            "gross_latest": _norm_pct(gmargin_y[-1][1]) if gmargin_y else None,
            "sector_net": (peers.get("benchmark", {}).get("net_margin")
                           if peers and not peers.get("error") else None),
        }

        # ---- P15: ROE/ROA lịch sử
        roe_roa = {
            "roe": _pct_series(roe_y), "roa": _pct_series(roa_y),
            "roe_latest": _norm_pct(roe_y[-1][1]) if roe_y else None,
            "roa_latest": _norm_pct(roa_y[-1][1]) if roa_y else None,
            "sector_roe": (peers.get("benchmark", {}).get("roe")
                           if peers and not peers.get("error") else None),
        }

        # ---- P16: DuPont ROE = biên ròng × vòng quay TS × đòn bẩy
        dupont = []
        by_year = {}
        for y, v in nmargin_y:
            by_year.setdefault(y, {})["nm"] = _norm_pct(v)
        for y, v in asset_turn_y:
            by_year.setdefault(y, {})["at"] = v
        for y, v in lev_y:
            by_year.setdefault(y, {})["lev"] = v
        for y, v in roe_y:
            by_year.setdefault(y, {})["roe"] = _norm_pct(v)
        for y in sorted(by_year):
            d = by_year[y]
            # LỖI CŨ: cột "đòn bẩy" lấy thẳng `liabilities_to_equity` (Nợ/VCSH tính
            # bằng %, vd 49,32) trong khi đẳng thức DuPont cần HỆ SỐ NHÂN VỐN
            # (Tổng tài sản / VCSH). Hậu quả: bảng ghi "ROE = biên × vòng quay ×
            # đòn bẩy" nhưng 20,51 × 0,85 × 49,32 = 859 ≠ ROE 27,63 — người đọc
            # nhân thử là thấy sai. Hệ số nhân vốn = 1 + (Nợ/VCSH)/100; đã đối
            # chiếu với bảng cân đối: 1 + 49,32/100 = 1,493 = 33.516/22.445 ✓.
            _de = d.get("lev")
            _em = (1 + _de / 100.0) if isinstance(_de, (int, float)) else None
            dupont.append({"year": y, "net_margin": d.get("nm"),
                           "asset_turnover": d.get("at"), "leverage": _em,
                           "debt_to_equity_pct": _de, "roe": d.get("roe")})

        # ---- P17: nợ vay & VCSH + đòn bẩy so ngành
        leverage = {
            "equity": _bn_series(equity_y),
            "liabilities": _bn_series(liab_y),
            "assets": _bn_series(assets_y),
            "d2e": _pct_series(d2e_y),
            "d2e_latest": _norm_pct(d2e_y[-1][1]) if d2e_y else None,
            "sector_d2e": (peers.get("benchmark", {}).get("debt_to_equity")
                           if peers and not peers.get("error") else None),
        }

        # ---- P18: waterfall dòng tiền (năm gần nhất)
        cashflow = None
        if cfo_y:
            ly = cfo_y[-1][0]
            get = lambda ser: next((v for yy, v in ser if yy == ly), None)
            begin = get(cash_begin_y)
            cfo, cfi, cff = get(cfo_y), get(cfi_y), get(cff_y)
            cashflow = {
                "year": ly, "begin": _bn(begin), "cfo": _bn(cfo),
                "cfi": _bn(cfi), "cff": _bn(cff),
                "cfo_series": _bn_series(cfo_y),
            }
            if None not in (begin, cfo, cfi, cff):
                cashflow["end"] = _bn(begin + cfo + cfi + cff)

        # ---- P19: cổ tức (events tiền mặt + dividends_paid CF + payout)
        drows = conn.execute(
            "SELECT event_name, public_date, value_per_share FROM events "
            "WHERE symbol=? AND value_per_share IS NOT NULL "
            "ORDER BY public_date DESC LIMIT 12", (symbol,)).fetchall()
        div_history = [{"event": r[0], "date": _iso_date(r[1]),
                        "value_per_share": r[2]} for r in drows]
        # payout ratio = |cổ tức tiền đã trả| / LNST (theo năm)
        npat_map = {y: v for y, v in npat_y}
        payout = []
        for y, v in div_paid_y:
            ni = npat_map.get(y)
            if ni and ni > 0 and v is not None:
                payout.append({"year": y, "value": round(abs(v) / ni * 100, 1)})
        dividends = {
            "history": div_history,
            "dividend_yield": (aband and None) or None,
            "paid_bn": [{"year": y, "value": _bn(abs(v))} for y, v in div_paid_y],
            "payout": payout,
        }
        # tỷ suất cổ tức từ ai metrics nếu có
        if arow:
            try:
                m = json.loads(arow[0]).get("metrics") or {}
                dividends["dividend_yield"] = (m.get("valuation") or {}).get("dividend_yield")
            except Exception:
                pass

        # ---- A6: 3 engine đã tính trong pipeline nhưng trước đây KHÔNG ra API
        # (sector_model / earnings_quality / valuation_band). Tính lại tại chỗ từ
        # market.db để phủ mọi mã có BCTC, không chỉ ~400 mã có ai_analysis.
        a6 = _build_a6(conn, symbol, info.get("sector") or "", peers, aband)

        # ---- A3: P/E MỘT nguồn chân lý + nhãn kỳ, dùng chung cho mọi tab
        _rat_records = _records(conn, symbol, "ratio")
        _pe_val, _pe_period = _pe_truth(conn, symbol, _rat_records, peers)
        pe = {"value": _pe_val, "period": _pe_period,
              "basis": ("ttm" if (_pe_period or "").startswith("TTM")
                        else ("ratio" if _pe_period else "peers")),
              "note": "P/E dùng chung cho mọi tab; kỳ dữ liệu ghi ở `period`."}

        # ---- P7: định giá strip vs peers (P/E, P/B) — dùng peers.py self/benchmark
        # `band` ưu tiên bản tự tính (đã truyền peer → có peer_median); aband chỉ
        # là dự phòng khi engine không chạy được.
        valuation = {"band": a6.get("valuation_band") or aband, "pe": pe}
        if peers and not peers.get("error"):
            valuation["self"] = peers.get("self", {})
            valuation["benchmark"] = peers.get("benchmark", {})
            valuation["position"] = peers.get("position", {})
            valuation["sector"] = peers.get("sector")
            valuation["n_peers"] = peers.get("n_peers")
            valuation["peer_values"] = peers.get("peer_values", {})  # B7: chấm peer trên strip

        # =========== RADAR 5 TRỤC (P1 · radar360) — điểm 0–100 ===========
        # Công thức công khai (methodology): mỗi trục chuẩn hóa dữ kiện đã có.
        sector_med = _sector_radar_medians(conn, data_dir, info.get("sector"))
        # Radar phải dùng ĐÚNG dải mà card định giá đang hiện (a6), không phải ảnh
        # chụp cũ trong ai_analysis — nếu không, trục "Định giá" và card ngay bên
        # trên nó nói hai điều khác nhau về cùng một mã (FPT: percentile 0 vs 33).
        radar = _radar360(health, valuation.get("band"), roe_roa, margins, combo,
                          dividends, leverage, sector_med)

        # =========== §12 · ONE BAR (tổng + per-KPI, chuẩn hóa chiều) ===========
        onebar = _build_onebar(radar, peers)

        return {
            "info": info,
            "radar": radar,
            "onebar": onebar,             # §12
            "health": {"health_score": health.get("health_score"),
                       "z_score": health.get("z_score"), "z_zone": health.get("z_zone"),
                       "f_score": health.get("f_score"), "f_max": health.get("f_max"),
                       "roe": health.get("roe"), "roa": health.get("roa"),
                       "debt_ratio": health.get("debt_ratio"),
                       "watch_flags": health.get("watch_flags", []),
                       "f_checks": health.get("f_checks", []), "year": health.get("year")},
            "valuation": valuation,          # P7
            # A6 · 3 engine đã tính từ lâu nhưng chưa bao giờ ra tới API
            "sector_model": a6.get("sector_model"),
            "earnings_quality": a6.get("earnings_quality"),
            "valuation_band": a6.get("valuation_band"),
            "combo": combo,                  # P12
            "margins": margins,              # P13
            "roe_roa": roe_roa,              # P15
            "dupont": dupont,                # P16
            "leverage": leverage,            # P17
            "cashflow": cashflow,            # P18
            "dividends": dividends,          # P19
            "peers": peers,
            "meta": {"generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
                     "source": "market.db · financials (BCTC vnstock, ratio KBS) + "
                               "health_scores.json + peers.py",
                     "legal": "Chỉ dữ kiện & thống kê mô tả — không phải khuyến nghị "
                              "đầu tư hay giá mục tiêu."},
        }
    finally:
        conn.close()


def _radar360(health, band, roe_roa, margins, combo, dividends, leverage, sector_med=None):
    """5 điểm radar 0–100 từ dữ liệu đã có (công thức công khai ở methodology).
    Trục: Định giá · Cổ tức · Tăng trưởng · Sức khỏe · Hiệu quả.
    Điểm chỉ mô tả vị thế thống kê, KHÔNG hàm ý mua/bán.

    - `anchor`: id section frontend cuộn tới khi click trục.
    - `formula`: công thức chuẩn hóa (hiện khi hover trục).
    - `weight`: trọng số công bố ở methodology dùng cho điểm tổng có trọng số.
    - `sector`: trung vị ngành CÙNG THANG (chỉ 2 trục có dữ liệu honest; None = không vẽ overlay).
    - score=None khi thiếu dữ liệu → frontend vẽ trục XÁM 'thiếu dữ liệu' (không cho 0 giả)."""
    sm = sector_med or {}
    axes = []

    # 1) Định giá — dựa percentile định giá lịch sử (thấp percentile = rẻ so với
    #    chính mã trong quá khứ → điểm cao). Trung tính: "rẻ/đắt so lịch sử CHÍNH MÃ".
    val_score = None
    if band and band.get("pe", {}).get("available") and band["pe"].get("percentile") is not None:
        val_score = _clamp(100 - band["pe"]["percentile"])
    elif band and band.get("pb", {}).get("available") and band["pb"].get("percentile") is not None:
        val_score = _clamp(100 - band["pb"]["percentile"])
    axes.append({"axis": "Định giá", "score": round(val_score) if val_score is not None else None,
                 "note": "percentile định giá lịch sử của chính mã (thấp = rẻ hơn quá khứ)",
                 "formula": "100 − percentile(P/E hoặc P/B trong lịch sử chính mã)",
                 "anchor": "valuation", "weight": 0.20, "sector": None})

    # 2) Cổ tức — tỷ suất cổ tức (cap 8% = 100đ) + có lịch sử chi trả đều
    dy = dividends.get("dividend_yield")
    div_score = None
    if dy is not None:
        div_score = _clamp(dy / 8 * 100)
        if dividends.get("payout"):
            div_score = _clamp(div_score + 8)  # thưởng nhẹ nếu có payout ổn định
    axes.append({"axis": "Cổ tức", "score": round(div_score) if div_score is not None else None,
                 "note": "tỷ suất cổ tức tiền mặt (0–8%+ → 0–100)",
                 "formula": "min(tỷ suất cổ tức / 8% × 100, 100) + 8 nếu có payout đều",
                 "anchor": "dividends", "weight": 0.15, "sector": None})

    # 3) Tăng trưởng — trung bình CAGR doanh thu & LNST (0%→50, 20%+→100)
    gr = [g for g in (combo.get("revenue_cagr"), combo.get("profit_cagr")) if g is not None]
    grow_score = None
    if gr:
        avg = sum(gr) / len(gr)
        grow_score = _clamp(50 + avg * 2.5)
    axes.append({"axis": "Tăng trưởng", "score": round(grow_score) if grow_score is not None else None,
                 "note": "CAGR doanh thu & LNST nhiều năm",
                 "formula": "50 + trung bình(CAGR doanh thu, CAGR LNST) × 2.5",
                 "anchor": "combo", "weight": 0.20, "sector": None})

    # 4) Sức khỏe — health_score có sẵn (Z''+F+flow) · CÓ trung vị ngành honest
    hs = health.get("health_score")
    axes.append({"axis": "Sức khỏe", "score": round(hs) if hs is not None else None,
                 "note": "điểm sức khỏe (Z''+Piotroski+dòng tiền)",
                 "formula": "trung bình(Altman Z''↦0–100, Piotroski F/F_max, ROA↦0–100)",
                 "anchor": "health", "weight": 0.25, "sector": sm.get("health")})

    # 5) Hiệu quả — ROE (mốc học thuật: 15%→75, 25%+→100) + biên ròng · CÓ trung vị ngành
    eff_score = None
    roe = roe_roa.get("roe_latest")
    if roe is not None:
        eff_score = _clamp(roe / 25 * 100)
        nm = margins.get("net_latest")
        if nm is not None:  # trộn nhẹ biên ròng (cap 20%)
            eff_score = _clamp(eff_score * 0.7 + _clamp(nm / 20 * 100) * 0.3)
    axes.append({"axis": "Hiệu quả", "score": round(eff_score) if eff_score is not None else None,
                 "note": "ROE + biên lợi nhuận ròng",
                 "formula": "ROE/25×100 (×0.7) + biên ròng/20×100 (×0.3)",
                 "anchor": "roe_roa", "weight": 0.20, "sector": sm.get("eff")})

    # điểm tổng CÓ TRỌNG SỐ trên các trục đủ dữ liệu (chuẩn hóa lại theo tổng trọng số hiện diện)
    present = [a for a in axes if a["score"] is not None]
    wsum = sum(a["weight"] for a in present)
    overall = round(sum(a["score"] * a["weight"] for a in present) / wsum) if wsum > 0 else None
    # nhãn TRUNG TÍNH (không mua/bán) mô tả nền tảng
    if overall is None:
        label = "chưa đủ dữ liệu"
    elif overall >= 70:
        label = "nền tảng vững theo mô hình"
    elif overall >= 50:
        label = "nền tảng khá"
    elif overall >= 35:
        label = "nền tảng trung bình"
    else:
        label = "cần chú ý"
    return {"axes": axes, "overall": overall, "label": label,
            "n_scored": len(present), "n_axes": len(axes),
            "sector_n": sm.get("n"), "sector": sm.get("_name") if sm else None}


def _build_onebar(radar: dict, peers) -> dict:
    """§12 · dữ liệu One Bar cho trang cổ phiếu:
    - `total`: thanh tổng "Nền tảng theo mô hình" (= radar overall) + 3 reasons
      lấy từ trục radar mạnh nhất / yếu nhất (mô tả, KHÔNG mua/bán).
    - `kpis`: percentile ngành đã chuẩn hóa chiều cho micro-bar dưới từng KPI.
    value=None → frontend vẽ thanh xám 'chưa đủ dữ liệu'."""
    present = [a for a in radar.get("axes", []) if a.get("score") is not None]
    reasons = []
    if present:
        best = max(present, key=lambda a: a["score"])
        worst = min(present, key=lambda a: a["score"])
        reasons.append({"t": f"{best['axis']} {best['score']}/100", "kind": "ok"})
        if worst["axis"] != best["axis"]:
            reasons.append({"t": f"{worst['axis']} {worst['score']}/100",
                            "kind": "bad" if worst["score"] < 40 else "neu"})
        # trục thứ 3: gần trung vị nhất để cân bằng góc nhìn
        mid = sorted(present, key=lambda a: abs(a["score"] - 50))
        for a in mid:
            if a["axis"] not in (best["axis"], worst["axis"]):
                reasons.append({"t": f"{a['axis']} {a['score']}/100", "kind": "neu"})
                break

    total = {
        "value": radar.get("overall"),
        "label_left": "cần chú ý",
        "label_right": "nền tảng vững",
        "verdict": radar.get("label"),
        "reasons": reasons,
        "n_scored": radar.get("n_scored"), "n_axes": radar.get("n_axes"),
    }

    # per-KPI: percentile ngành (đã chuẩn hóa chiều trong peers.py)
    kpis = {}
    if peers and isinstance(peers, dict) and not peers.get("error"):
        pct = peers.get("pct", {}) or {}
        LABELS = {"pe": "P/E", "pb": "P/B", "roe": "ROE",
                  "net_margin": "Biên ròng", "debt_to_equity": "Nợ/VCSH"}
        for k, label in LABELS.items():
            if k in pct:
                kpis[k] = {"value": pct[k], "label": label,
                           "self": (peers.get("self") or {}).get(k),
                           "median": (peers.get("benchmark") or {}).get(k)}
    return {"total": total, "kpis": kpis, "sector": (peers or {}).get("sector") if isinstance(peers, dict) else None}
