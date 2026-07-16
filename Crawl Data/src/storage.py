"""Lưu trữ kép: JSON gốc theo công ty + SQLite tổng hợp.

JSON là nguồn sự thật (raw). SQLite được sinh ra từ JSON để truy vấn/so sánh nhanh.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from . import config

YEAR_RE = re.compile(r"^\d{4}$")          # cột kỳ dạng "2024"
PERIOD_RE = re.compile(r"^\d{4}")          # bắt cả "2024-Q1"

# Kỳ CHUẨN sau chuẩn hóa: "YYYY" hoặc "YYYY-QN". Dùng để validate trước khi ghi.
CLEAN_PERIOD_RE = re.compile(r"^\d{4}(-Q[1-4])?$")

# Nhãn cột kỳ của Finance.ratio() nguồn KBS: "2025-Năm" (năm), "2025-Q4" (quý),
# đôi khi "2025-Q4_1" (pandas dedup cột trùng). Nhận cả biến thể không dấu "Nam".
_RATIO_YEAR_COL_RE = re.compile(r"^(\d{4})-N[aă]m$")
_RATIO_Q_COL_RE = re.compile(r"^(\d{4})-Q([1-4])")

# Các hàng metadata trong ratio (không phải chỉ tiêu định giá) cần bỏ qua.
_RATIO_META_IDS = {"year", "quarter", "ratiottmid", "ratiotype", "ticker"}


# ---------------------------------------------------------------- JSON

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- Chuẩn hóa BCTC

def _dedup_columns(cols: list[str]) -> list[str]:
    """Khử trùng tên cột (thêm hậu tố .1, .2...) để truy cập không ra Series."""
    seen: dict[str, int] = {}
    out: list[str] = []
    for c in cols:
        if c in seen:
            seen[c] += 1
            out.append(f"{c}.{seen[c]}")
        else:
            seen[c] = 0
            out.append(c)
    return out


def statement_to_records(df: pd.DataFrame) -> list[dict]:
    """Chuyển DataFrame BCTC (dạng long: item/item_en/item_id + cột năm)
    thành danh sách bản ghi {item_id, item, item_en, period, value}.
    Tự nhận diện cột kỳ (năm) so với cột metadata; chịu được cột trùng tên.
    """
    if df is None or df.empty:
        return []

    df = df.copy()
    # Phẳng hóa MultiIndex cột nếu có.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join(str(c) for c in tup if str(c) != "") for tup in df.columns]
    df.columns = _dedup_columns([str(c) for c in df.columns])
    cols = list(df.columns)

    period_cols = [c for c in cols if PERIOD_RE.match(c.strip())]
    if not period_cols:
        return []

    id_col = next((c for c in ("item_id", "item") if c in cols), cols[0])
    name_col = "item" if "item" in cols else id_col
    en_col = "item_en" if "item_en" in cols else None

    records: list[dict] = []
    for r in df.itertuples(index=False):
        d = dict(zip(cols, r))
        item_id = str(d.get(id_col, "")).strip()
        item = str(d.get(name_col, "")).strip()
        item_en = str(d.get(en_col, "")).strip() if en_col else ""
        for p in period_cols:
            val = d.get(p)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                continue
            records.append({
                "item_id": item_id,
                "item": item,
                "item_en": item_en,
                "period": p.strip(),
                "value": float(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else str(val),
            })
    return records


def _clean_ratio_period(col: str) -> str | None:
    """Chuẩn hóa nhãn cột kỳ của Finance.ratio() (nguồn KBS) về "YYYY" / "YYYY-QN".

    KBS trả cột dạng "2025-Năm" (cả năm) và "2025-Q4" (quý), thi thoảng có hậu tố
    "_1" do pandas khử trùng cột. Trả None nếu không phải cột kỳ (vd item/item_id).
    """
    c = str(col).strip()
    m = _RATIO_YEAR_COL_RE.match(c)
    if m:
        return m.group(1)                     # "2025-Năm" -> "2025"
    m = _RATIO_Q_COL_RE.match(c)
    if m:
        return f"{m.group(1)}-Q{m.group(2)}"   # "2025-Q4_1" -> "2025-Q4"
    return None


def ratio_to_records(df: pd.DataFrame) -> list[dict]:
    """Chuyển DataFrame Finance.ratio() (nguồn KBS) → list record chuẩn.

    Cấu trúc thật (đã xác minh bằng scripts/diag_ratio.py): dạng LONG — mỗi hàng
    là một chỉ tiêu (cột item + item_id), các cột còn lại là kỳ dạng
    "YYYY-Năm"/"YYYY-QN". Khác hẳn 3 báo cáo kia nên KHÔNG dùng chung
    statement_to_records (nguồn VCI của ratio bị hỏng: cột toàn "2018").

    Trả về {item_id, item, item_en, period, value} với period CHUẨN "YYYY"/"YYYY-QN".
    """
    if df is None or df.empty:
        return []

    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join(str(c) for c in tup if str(c) != "") for tup in df.columns]
    df.columns = _dedup_columns([str(c) for c in df.columns])
    cols = list(df.columns)

    # Map cột kỳ thật -> period chuẩn (bỏ cột meta item/item_id/item_en).
    period_map = {c: _clean_ratio_period(c) for c in cols}
    period_cols = [c for c in cols if period_map[c]]
    if not period_cols:
        return []

    id_col = "item_id" if "item_id" in cols else next(
        (c for c in ("item", "name") if c in cols), cols[0])
    name_col = "item" if "item" in cols else id_col
    en_col = "item_en" if "item_en" in cols else None

    records: list[dict] = []
    for r in df.itertuples(index=False):
        d = dict(zip(cols, r))
        item_id = str(d.get(id_col, "")).strip()
        # Bỏ các hàng metadata (year/quarter/ratioType...) — không phải chỉ tiêu.
        if item_id.lower() in _RATIO_META_IDS or not item_id:
            continue
        item = str(d.get(name_col, "")).strip()
        item_en = str(d.get(en_col, "")).strip() if en_col else ""
        for c in period_cols:
            val = d.get(c)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                continue
            records.append({
                "item_id": item_id,
                "item": item,
                "item_en": item_en,
                "period": period_map[c],
                "value": float(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else str(val),
            })
    return records


# ---------------------------------------------------------------- SQLite

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    symbol        TEXT PRIMARY KEY,
    organ_name    TEXT,
    exchange      TEXT,
    sector        TEXT,
    market_cap    REAL,
    current_price REAL,
    updated_at    TEXT
);
CREATE TABLE IF NOT EXISTS financials (
    symbol     TEXT,
    statement  TEXT,
    item_id    TEXT,
    item       TEXT,
    item_en    TEXT,
    period     TEXT,
    value      REAL,
    PRIMARY KEY (symbol, statement, item_id, period)
);
CREATE INDEX IF NOT EXISTS idx_fin_symbol ON financials(symbol);
CREATE TABLE IF NOT EXISTS news (
    symbol       TEXT,
    news_id      TEXT,
    title        TEXT,
    short_content TEXT,
    source_link  TEXT,
    public_date  TEXT,
    PRIMARY KEY (symbol, news_id)
);
CREATE INDEX IF NOT EXISTS idx_news_symbol ON news(symbol);
CREATE TABLE IF NOT EXISTS events (
    symbol      TEXT,
    event_id    TEXT,
    event_name  TEXT,
    title       TEXT,
    public_date TEXT,
    value_per_share REAL,
    PRIMARY KEY (symbol, event_id)
);
CREATE TABLE IF NOT EXISTS price (
    symbol  TEXT,
    time    TEXT,
    open    REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (symbol, time)
);
CREATE INDEX IF NOT EXISTS idx_price_symbol ON price(symbol);
CREATE TABLE IF NOT EXISTS ai_analysis (
    symbol      TEXT PRIMARY KEY,
    analysis    TEXT,
    updated_at  TEXT
);
CREATE TABLE IF NOT EXISTS crawl_state (
    symbol      TEXT,
    stage       TEXT,
    status      TEXT,
    detail      TEXT,
    attempts    INTEGER DEFAULT 0,
    updated_at  TEXT,
    PRIMARY KEY (symbol, stage)
);
"""

# Số lần thử tối đa: sau ngần này lượt mà vẫn "partial" (thiếu statement bản
# chất, vd ngân hàng/chứng khoán không có cash_flow chuẩn) thì coi như đã ổn
# định → get_done tính là done, khỏi crawl lại đốt quota.
PARTIAL_STABLE_ATTEMPTS = 2

# Cột bổ sung thêm vào bảng companies cũ nếu thiếu (migration nhẹ).
_MIGRATE_COLS = {
    "sector": "TEXT", "market_cap": "REAL", "current_price": "REAL",
}


def _migrate(conn: sqlite3.Connection) -> None:
    existing = {r[1] for r in conn.execute("PRAGMA table_info(companies)")}
    for col, typ in _MIGRATE_COLS.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE companies ADD COLUMN {col} {typ}")
    # Thêm cột đếm số lần thử vào crawl_state cũ nếu thiếu (migration nhẹ).
    state_cols = {r[1] for r in conn.execute("PRAGMA table_info(crawl_state)")}
    if "attempts" not in state_cols:
        conn.execute("ALTER TABLE crawl_state ADD COLUMN attempts INTEGER DEFAULT 0")


def connect() -> sqlite3.Connection:
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def upsert_company(conn: sqlite3.Connection, symbol: str,
                   organ_name: str = "", exchange: str = "",
                   sector: str = "", market_cap=None, current_price=None) -> None:
    conn.execute(
        """INSERT INTO companies(symbol, organ_name, exchange, sector,
                                 market_cap, current_price, updated_at)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(symbol) DO UPDATE SET
             organ_name=COALESCE(NULLIF(excluded.organ_name,''), companies.organ_name),
             exchange=COALESCE(NULLIF(excluded.exchange,''), companies.exchange),
             sector=COALESCE(NULLIF(excluded.sector,''), companies.sector),
             market_cap=COALESCE(excluded.market_cap, companies.market_cap),
             current_price=COALESCE(excluded.current_price, companies.current_price),
             updated_at=excluded.updated_at""",
        (symbol.upper(), organ_name, exchange, sector,
         market_cap, current_price, now_iso()),
    )


def replace_news(conn, symbol, rows: list[dict]) -> None:
    conn.execute("DELETE FROM news WHERE symbol=?", (symbol.upper(),))
    conn.executemany(
        """INSERT OR REPLACE INTO news
           (symbol, news_id, title, short_content, source_link, public_date)
           VALUES (?,?,?,?,?,?)""",
        [(symbol.upper(), r["news_id"], r["title"], r["short_content"],
          r["source_link"], r["public_date"]) for r in rows],
    )


def replace_events(conn, symbol, rows: list[dict]) -> None:
    conn.execute("DELETE FROM events WHERE symbol=?", (symbol.upper(),))
    conn.executemany(
        """INSERT OR REPLACE INTO events
           (symbol, event_id, event_name, title, public_date, value_per_share)
           VALUES (?,?,?,?,?,?)""",
        [(symbol.upper(), r["event_id"], r["event_name"], r["title"],
          r["public_date"], r["value_per_share"]) for r in rows],
    )


def replace_price(conn, symbol, rows: list[dict]) -> None:
    conn.execute("DELETE FROM price WHERE symbol=?", (symbol.upper(),))
    conn.executemany(
        """INSERT OR REPLACE INTO price(symbol, time, open, high, low, close, volume)
           VALUES (?,?,?,?,?,?,?)""",
        [(symbol.upper(), str(r.get("time")), r.get("open"), r.get("high"),
          r.get("low"), r.get("close"), r.get("volume")) for r in rows],
    )


def set_state(conn, symbol, stage, status, detail="") -> None:
    # attempts tăng +1 mỗi lần ghi trạng thái để get_done biết mã đã được thử
    # bao nhiêu lượt (dùng cho việc chốt "partial ổn định" thành done).
    conn.execute(
        """INSERT INTO crawl_state(symbol, stage, status, detail, attempts, updated_at)
           VALUES (?,?,?,?,1,?)
           ON CONFLICT(symbol, stage) DO UPDATE SET
             status=excluded.status, detail=excluded.detail,
             attempts=crawl_state.attempts + 1,
             updated_at=excluded.updated_at""",
        (symbol.upper(), stage, status, str(detail)[:500], now_iso()),
    )


def get_done(conn, stage) -> set[str]:
    """Mã coi như đã xong = status 'ok', HOẶC 'partial' đã thử đủ số lần
    (PARTIAL_STABLE_ATTEMPTS) — tránh crawl lại vô hạn những DN đặc thù thiếu
    statement bản chất (ngân hàng/chứng khoán không có cash_flow chuẩn)."""
    return {r[0] for r in conn.execute(
        "SELECT symbol FROM crawl_state WHERE stage=? AND "
        "(status='ok' OR (status='partial' AND attempts >= ?))",
        (stage, PARTIAL_STABLE_ATTEMPTS))}


def replace_financials(conn: sqlite3.Connection, symbol: str,
                       statement: str, records: list[dict]) -> None:
    conn.execute(
        "DELETE FROM financials WHERE symbol=? AND statement=?",
        (symbol.upper(), statement),
    )
    conn.executemany(
        """INSERT OR REPLACE INTO financials
           (symbol, statement, item_id, item, item_en, period, value)
           VALUES (?,?,?,?,?,?,?)""",
        [(symbol.upper(), statement, r["item_id"], r["item"],
          r["item_en"], r["period"], r["value"]) for r in records],
    )


def merge_financials(conn: sqlite3.Connection, symbol: str,
                     statement: str, records: list[dict]) -> None:
    """Tích lũy BCTC qua các lần crawl (KHÔNG xóa kỳ cũ).

    vnstock community giới hạn 4 kỳ/lần gọi. replace_financials() xóa-ghi-đè nên
    mỗi lần crawl lại mất kỳ cũ. Hàm này chỉ INSERT OR REPLACE theo khóa chính
    (symbol, statement, item_id, period): kỳ mới ghi đè giá trị trùng khóa, kỳ cũ
    không có trong batch được GIỮ NGUYÊN → lịch sử tự dày lên vượt trần 4 kỳ.

    Khóa chính (symbol, statement, item_id, period) đã có sẵn trong SCHEMA; thêm
    UNIQUE INDEX idempotent để chắc chắn với DB cũ có thể thiếu ràng buộc.
    """
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_fin_key "
        "ON financials(symbol, statement, item_id, period)"
    )
    # Chốt chặn cuối: kỳ không chuẩn "YYYY"/"YYYY-QN" không bao giờ được vào DB
    # (di chứng bug ratio/VCI trả cột "2018.1"...).
    clean = [r for r in records if CLEAN_PERIOD_RE.match(str(r.get("period", "")))]
    if len(clean) < len(records):
        print(f"  [!] {symbol} {statement}: bỏ {len(records) - len(clean)} "
              f"record period không chuẩn khi ghi DB")
    conn.executemany(
        """INSERT OR REPLACE INTO financials
           (symbol, statement, item_id, item, item_en, period, value)
           VALUES (?,?,?,?,?,?,?)""",
        [(symbol.upper(), statement, r["item_id"], r["item"],
          r["item_en"], r["period"], r["value"]) for r in clean],
    )
