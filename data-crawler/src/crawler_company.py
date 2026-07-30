"""P2 — Crawler thông tin công ty qua vnstock Company:
overview (hồ sơ), news (tin tức), events (sự kiện/cổ tức).

Sinh thêm insights/reasons.jsonl: gom tiêu đề + tóm tắt tin tức/sự kiện
làm "nguyên nhân/lý do" để gửi AI phân tích (P4).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from datetime import date, timedelta

import pandas as pd
from vnstock import Company, Quote

from . import config, progress, storage
from .runner import _is_ratelimit

NEWS_LIMIT = 50    # số tin gần nhất giữ lại
EVENT_LIMIT = 30
PRICE_YEARS = 2    # số năm giá lịch sử OHLCV
ARTICLE_LIMIT = 20                        # bài báo Vietstock (có nội dung) giữ lại
VIETSTOCK_BASE = "https://vietstock.vn"   # KBS trả đường dẫn tương đối "/2026/07/....htm"


def _dump_df(cdir, sub, name, df, symbol, sym_step) -> int:
    """Lưu DataFrame ra JSON theo công ty + phát @STEP. Trả về số dòng."""
    rows = (df.to_dict("records")
            if df is not None and not df.empty else [])
    storage.write_json(cdir / sub / f"{name}.json",
                       {"symbol": symbol, "fetched_at": storage.now_iso(),
                        "count": len(rows), "items": rows})
    progress.step(symbol, sym_step, "ok", len(rows))
    return len(rows)


def _write_empty_insider(cdir, symbol: str, note: str) -> None:
    """Ghi ownership/insider_deals.json RỖNG kèm note.

    Phân biệt "nguồn không trả dữ liệu" (count=0 + note) với "chưa crawl" (file
    không tồn tại) → manifest đếm được 18/18 với chú thích thay vì trông như thiếu."""
    storage.write_json(cdir / "ownership" / "insider_deals.json",
                       {"symbol": symbol, "fetched_at": storage.now_iso(),
                        "count": 0, "items": [], "note": note})


def _cell(df: pd.DataFrame, col: str, default=None):
    if df is None or df.empty or col not in df.columns:
        return default
    v = df.iloc[0][col]
    return None if pd.isna(v) else v


def _num(v):
    try:
        return float(v) if v is not None and not pd.isna(v) else None
    except (TypeError, ValueError):
        return None


def crawl_one(conn, symbol: str) -> dict:
    symbol = symbol.upper()
    cdir = config.company_dir(symbol)
    progress.start(symbol)
    co = Company(symbol=symbol, source="VCI")
    summary: dict[str, int] = {}
    organ_name = ""

    # ---- overview / profile
    try:
        ov = co.overview()
        profile = ov.iloc[0].to_dict() if ov is not None and not ov.empty else {}
        organ_name = str(_cell(ov, "organ_name", "") or "")
        storage.write_json(cdir / "profile.json", {
            "symbol": symbol, "updated_at": storage.now_iso(), "overview": profile,
        })
        storage.upsert_company(
            conn, symbol,
            organ_name=str(_cell(ov, "organ_name", "")),
            sector=str(_cell(ov, "sector", "")),
            market_cap=_num(_cell(ov, "market_cap")),
            current_price=_num(_cell(ov, "current_price")),
        )
        summary["overview"] = 1
        progress.step(symbol, "overview", "ok", 1)
    except Exception as exc:
        if _is_ratelimit(exc):   # không nuốt rate-limit → để guard() cooldown
            raise
        summary["overview"] = -1
        progress.step(symbol, "overview", "err", 0)
        print(f"  [!] {symbol} overview: {exc}")

    # ---- news
    news_rows: list[dict] = []
    try:
        nf = co.news()
        if nf is not None and not nf.empty:
            nf = nf.head(NEWS_LIMIT)
            for r in nf.itertuples(index=False):
                d = r._asdict()
                news_rows.append({
                    "news_id": str(d.get("news_id") or d.get("id") or ""),
                    "title": str(d.get("news_title") or d.get("friendly_title") or "").strip(),
                    "short_content": str(d.get("news_short_content") or "").strip(),
                    "source_link": str(d.get("news_source_link") or "").strip(),
                    "public_date": str(d.get("public_date") or "").strip(),
                })
        storage.write_json(cdir / "news" / "news.json",
                           {"symbol": symbol, "fetched_at": storage.now_iso(),
                            "count": len(news_rows), "items": news_rows})
        storage.replace_news(conn, symbol, news_rows)
        summary["news"] = len(news_rows)
        progress.step(symbol, "news", "ok", len(news_rows))
    except Exception as exc:
        if _is_ratelimit(exc):   # không nuốt rate-limit → để guard() cooldown
            raise
        summary["news"] = -1
        progress.step(symbol, "news", "err", 0)
        print(f"  [!] {symbol} news: {exc}")

    # ---- events
    event_rows: list[dict] = []
    try:
        ef = co.events()
        if ef is not None and not ef.empty:
            ef = ef.head(EVENT_LIMIT)
            for r in ef.itertuples(index=False):
                d = r._asdict()
                event_rows.append({
                    "event_id": str(d.get("id") or ""),
                    "event_name": str(d.get("event_name_vi") or "").strip(),
                    "title": str(d.get("event_title_vi") or "").strip(),
                    "public_date": str(d.get("public_date") or "").strip(),
                    "value_per_share": _num(d.get("value_per_share")),
                })
        storage.write_json(cdir / "disclosures" / "events.json",
                           {"symbol": symbol, "fetched_at": storage.now_iso(),
                            "count": len(event_rows), "items": event_rows})
        storage.replace_events(conn, symbol, event_rows)
        summary["events"] = len(event_rows)
        progress.step(symbol, "events", "ok", len(event_rows))
    except Exception as exc:
        if _is_ratelimit(exc):   # không nuốt rate-limit → để guard() cooldown
            raise
        summary["events"] = -1
        progress.step(symbol, "events", "err", 0)
        print(f"  [!] {symbol} events: {exc}")

    # ---- hồ sơ sở hữu: lãnh đạo, cổ đông, cty con, cty liên kết
    for meth, sub, name, step_lbl in (
        ("officers", "ownership", "officers", "lãnh đạo"),
        ("shareholders", "ownership", "shareholders", "cổ đông"),
        ("subsidiaries", "ownership", "subsidiaries", "cty con"),
        ("affiliate", "ownership", "affiliate", "liên kết"),
    ):
        try:
            df = getattr(co, meth)()
            summary[name] = _dump_df(cdir, sub, name, df, symbol, step_lbl)
        except Exception as exc:
            if _is_ratelimit(exc):   # không nuốt rate-limit → để guard() cooldown
                raise
            summary[name] = -1
            progress.step(symbol, step_lbl, "err", 0)
            print(f"  [!] {symbol} {meth}: {str(exc)[:60]}")

    # ---- bài báo có NỘI DUNG (nguồn KBS → Vietstock)
    # `co.news()` của VCI (khối "news" phía trên) trả tin CÔNG BỐ THÔNG TIN: đo
    # thật trên FPT thì 0/50 bản ghi có `news_source_link`, 0/50 có
    # `news_short_content` — chỉ có mỗi tiêu đề pháp lý. Nhánh KBS trả BỘ KHÁC:
    # có `head` (tóm tắt nội dung thật) và `url` bài gốc. Đây là nguồn duy nhất
    # AI đọc được nội dung thay vì đoán từ tiêu đề.
    article_rows: list[dict] = []
    try:
        adf = Company(symbol=symbol, source="KBS").news(page_size=ARTICLE_LIMIT)
        if adf is not None and not adf.empty:
            for r in adf.itertuples(index=False):
                d = r._asdict()
                title = str(d.get("title") or "").strip()
                if not title:
                    continue
                url = str(d.get("url") or "").strip()
                article_rows.append({
                    "article_id": str(d.get("article_id") or ""),
                    "title": title,
                    "head": str(d.get("head") or "").strip(),
                    "link": (VIETSTOCK_BASE + url) if url.startswith("/") else url,
                    "public_date": str(d.get("publish_time") or "").strip(),
                    "source": "Vietstock",
                })
        storage.write_json(cdir / "news" / "articles.json",
                           {"symbol": symbol, "fetched_at": storage.now_iso(),
                            "count": len(article_rows), "items": article_rows})
        summary["articles"] = len(article_rows)
        progress.step(symbol, "bài báo", "ok", len(article_rows))
    except Exception as exc:
        if _is_ratelimit(exc):
            raise
        summary["articles"] = -1
        progress.step(symbol, "bài báo", "err", 0)
        print(f"  [!] {symbol} articles: {str(exc)[:60]}")

    # ---- lịch sử tăng vốn + giao dịch nội bộ (chỉ nguồn KBS hỗ trợ)
    # insider_deals: vnstock (KBS) thường trả RỖNG cho nhiều mã — đó là nguồn
    # không có dữ liệu, KHÔNG phải crawler lỗi. Luôn ghi file (kèm note khi rỗng)
    # để manifest phân biệt "nguồn không trả dữ liệu" với "chưa crawl".
    try:
        co_kbs = Company(symbol=symbol, source="KBS")
        for meth, name, step_lbl in (
            ("capital_history", "capital_history", "lịch sử vốn"),
            ("insider_trading", "insider_deals", "GD nội bộ"),
        ):
            try:
                df = getattr(co_kbs, meth)()
                summary[name] = _dump_df(cdir, "ownership", name, df, symbol, step_lbl)
                # Nguồn trả rỗng cho GD nội bộ → ghi kèm note để UI khỏi hiểu là thiếu.
                if name == "insider_deals" and summary[name] == 0:
                    _write_empty_insider(cdir, symbol, "nguồn không trả dữ liệu")
            except Exception as exc:
                if _is_ratelimit(exc):
                    raise
                summary[name] = -1
                progress.step(symbol, step_lbl, "err", 0)
                print(f"  [!] {symbol} {meth}: {str(exc)[:60]}")
                if name == "insider_deals":
                    _write_empty_insider(cdir, symbol, "nguồn báo lỗi khi lấy dữ liệu")
    except Exception as exc:
        if _is_ratelimit(exc):
            raise
        print(f"  [!] {symbol} KBS source: {str(exc)[:60]}")
        # Cả nguồn KBS lỗi → vẫn ghi file insider_deals rỗng có note.
        _write_empty_insider(cdir, symbol, "nguồn KBS không khả dụng")

    # ---- giá lịch sử OHLCV (nguồn VNDirect)
    try:
        start = (date.today() - timedelta(days=365 * PRICE_YEARS)).isoformat()
        from . import vndirect
        prows = vndirect.price_history(symbol, start, date.today().isoformat())
        prows.sort(key=lambda r: str(r.get("time")))   # đảm bảo tăng dần theo ngày
        storage.write_json(cdir / "market" / "price.json",
                           {"symbol": symbol, "fetched_at": storage.now_iso(),
                            "count": len(prows), "items": prows})
        storage.replace_price(conn, symbol, prows)
        summary["price"] = len(prows)
        progress.step(symbol, "giá", "ok", len(prows))
    except Exception as exc:
        if _is_ratelimit(exc):   # không nuốt rate-limit → để guard() cooldown
            raise
        summary["price"] = -1
        progress.step(symbol, "giá", "err", 0)
        print(f"  [!] {symbol} price: {str(exc)[:60]}")

    # ---- snapshot bảng giá (khối ngoại + độ sâu lệnh 3 bậc) từ vnstock Trading
    try:
        from vnstock import Trading
        from . import board as board_mod
        tdf = Trading(source="VCI").price_board([symbol])
        col = board_mod._flat(tdf)
        snap = {}
        if len(tdf):
            for f in ("match_price", "accumulated_volume",
                      "foreign_buy_volume", "foreign_sell_volume",
                      "bid_1_price", "bid_1_volume", "ask_1_price", "ask_1_volume"):
                s = col(f)
                snap[f] = board_mod._num(list(s)[0]) if s is not None and len(s) else None
        storage.write_json(cdir / "market" / "board_snapshot.json",
                           {"symbol": symbol, "fetched_at": storage.now_iso(), "snapshot": snap})
        # Tích lũy chuỗi khối ngoại theo ngày (1 dòng/phiên) để về sau tính
        # "mua/bán ròng N phiên liên tiếp" — snapshot chỉ có 1 phiên hiện tại.
        _append_foreign_history(cdir, snap)
        summary["board"] = 1 if snap else 0
        progress.step(symbol, "khối ngoại", "ok", 1 if snap else 0)
    except Exception as exc:
        if _is_ratelimit(exc):
            raise
        summary["board"] = -1
        progress.step(symbol, "khối ngoại", "err", 0)
        print(f"  [!] {symbol} board: {str(exc)[:60]}")

    # ---- tin báo chí thật (Google News RSS) — mạng ngoài, có cờ tắt
    press_rows: list[dict] = []
    if os.environ.get("CRAWL_PRESS", "1") != "0":
        try:
            from . import news_rss
            press_rows = news_rss.fetch(symbol, organ_name)
            storage.write_json(cdir / "news" / "press.json",
                               {"symbol": symbol, "fetched_at": storage.now_iso(),
                                "count": len(press_rows), "items": press_rows})
            summary["press"] = len(press_rows)
            progress.step(symbol, "báo chí", "ok", len(press_rows))
        except Exception as exc:
            summary["press"] = -1
            progress.step(symbol, "báo chí", "err", 0)
            print(f"  [!] {symbol} press: {str(exc)[:60]}")

    # ---- reasons.jsonl (nguyên liệu cho AI)
    _write_reasons(cdir, symbol, news_rows, event_rows, press_rows, article_rows)
    summary["reasons"] = (len(news_rows) + len(event_rows)
                          + len(press_rows) + len(article_rows))
    progress.step(symbol, "reasons", "ok", summary["reasons"])

    # ---- manifest: bảng kê minh bạch crawl được gì
    try:
        from . import manifest
        manifest.build(symbol)
    except Exception as exc:
        print(f"  [!] {symbol} manifest: {str(exc)[:60]}")

    conn.commit()
    progress.done(symbol, "err" if any(v == -1 for v in summary.values()) else "ok")
    return summary


def _append_foreign_history(cdir: Path, snap: dict) -> None:
    """Append 1 dòng khối ngoại của phiên hôm nay vào market/foreign_history.jsonl.

    Snapshot bảng giá là dữ liệu realtime trong phiên, không kèm ngày → dùng ngày
    hôm nay làm ngày phiên. Chống trùng: nếu dòng cuối cùng đã cùng "date" thì THAY
    dòng đó (số liệu mới hơn trong ngày), không append thêm → 1 dòng/ngày.

    Ghi chú backfill: đã thăm dò vnstock bản đang cài cho API lịch sử giao dịch
    khối ngoại theo ngày (Trading.foreign_trade) — trả NotImplementedError trên
    nguồn VCI, không dùng được để backfill. Vì vậy chuỗi khối ngoại CHỈ tích lũy
    dần từ snapshot mỗi lần crawl (sau vài tuần chạy định kỳ mới đủ chuỗi N phiên);
    không thêm dependency mới. Nếu về sau vnstock mở API này, bổ sung bước backfill
    riêng ghi vào cùng file (khóa theo date, không ghi đè dòng đã có)."""
    buy = snap.get("foreign_buy_volume")
    sell = snap.get("foreign_sell_volume")
    if buy is None and sell is None:
        return   # không có dữ liệu khối ngoại → khỏi ghi
    today = date.today().isoformat()
    net = (buy or 0) - (sell or 0)
    row = {"date": today, "foreign_buy_volume": buy, "foreign_sell_volume": sell,
           "foreign_net": net, "fetched_at": storage.now_iso()}

    path = cdir / "market" / "foreign_history.jsonl"
    lines: list[str] = []
    if path.exists():
        try:
            lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        except Exception:
            lines = []
    # Nếu dòng cuối cùng trùng ngày → thay bằng số liệu mới; ngược lại append.
    if lines:
        try:
            last = json.loads(lines[-1])
            if last.get("date") == today:
                lines[-1] = json.dumps(row, ensure_ascii=False)
            else:
                lines.append(json.dumps(row, ensure_ascii=False))
        except Exception:
            lines.append(json.dumps(row, ensure_ascii=False))
    else:
        lines.append(json.dumps(row, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_reasons(cdir: Path, symbol: str,
                   news_rows: list[dict], event_rows: list[dict],
                   press_rows: list[dict] | None = None,
                   article_rows: list[dict] | None = None) -> None:
    """Gom tin tức + sự kiện + báo chí thành các dòng JSONL mô tả nguyên nhân/lý do."""
    lines: list[str] = []
    for n in news_rows:
        text = n["title"]
        if n["short_content"]:
            text += " — " + n["short_content"]
        lines.append(json.dumps({
            "type": "news", "date": n["public_date"],
            "text": text, "source": n["source_link"],
        }, ensure_ascii=False))
    for e in event_rows:
        lines.append(json.dumps({
            "type": "event", "date": e["public_date"],
            "text": f"{e['event_name']}: {e['title']}",
            "value_per_share": e["value_per_share"],
        }, ensure_ascii=False))
    for p in (press_rows or []):
        lines.append(json.dumps({
            "type": "press", "date": p.get("public_date", ""),
            "text": p.get("title", ""), "source": p.get("source", ""),
            "link": p.get("link", ""),
        }, ensure_ascii=False))
    # Bài báo Vietstock là loại DUY NHẤT có `head` — đưa tóm tắt vào `text` để
    # AI đọc nội dung thay vì suy từ tiêu đề. Cắt 300 ký tự: đo trên FPT thì
    # `head` trung bình 180 ký tự, dài nhất 402.
    for a in (article_rows or []):
        text = a.get("title", "")
        if a.get("head"):
            text += " — " + str(a["head"])[:300]
        lines.append(json.dumps({
            "type": "article", "date": a.get("public_date", ""),
            "text": text, "source": a.get("source", "Vietstock"),
            "link": a.get("link", ""),
        }, ensure_ascii=False))
    (cdir / "insights" / "reasons.jsonl").write_text(
        "\n".join(lines), encoding="utf-8")
