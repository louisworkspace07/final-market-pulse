"""Cấu hình đường dẫn & hằng số dùng chung cho toàn hệ thống crawl."""
from __future__ import annotations

import sys
from pathlib import Path

# Bật UTF-8 cho stdout/stderr trên Windows (console mặc định cp1252).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Gốc dự án = thư mục cha của src/
ROOT = Path(__file__).resolve().parent.parent

# Nạp biến môi trường từ .env (nếu có) — không ghi đè biến đã đặt sẵn.
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except Exception:
    pass

CONFIG_DIR = ROOT / "config"
COMPANIES_DIR = ROOT / "companies"      # mỗi công ty 1 thư mục JSON
DATABASE_DIR = ROOT / "database"
DB_PATH = DATABASE_DIR / "market.db"    # SQLite tổng hợp
DATA_DIR = ROOT / "data"                # dữ liệu dùng chung (vĩ mô/thị trường)
MACRO_FILE = DATA_DIR / "macro" / "context.json"

COMPANIES_FILE = CONFIG_DIR / "companies.txt"
MACRO_SEED_FILE = CONFIG_DIR / "macro_seed.json"

# Nguồn dữ liệu tài chính của vnstock (VCI ổn định cho BCTC).
FINANCE_SOURCE = "VCI"

# 4 loại báo cáo tài chính sẽ crawl ở P1.
STATEMENTS = ("balance_sheet", "income_statement", "cash_flow", "ratio")

# Lịch sự với máy chủ: nghỉ giữa các mã (giây).
REQUEST_DELAY = 1.0


def ensure_dirs() -> None:
    """Tạo các thư mục cần thiết nếu chưa có."""
    for d in (COMPANIES_DIR, DATABASE_DIR, DATA_DIR / "macro"):
        d.mkdir(parents=True, exist_ok=True)


def load_tickers() -> list[str]:
    """Đọc danh sách mã từ config/companies.txt (bỏ qua dòng trống & dòng #)."""
    if not COMPANIES_FILE.exists():
        return []
    tickers: list[str] = []
    for line in COMPANIES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip().upper()
        if line and not line.startswith("#"):
            tickers.append(line)
    return tickers


def company_dir(symbol: str) -> Path:
    """Thư mục dữ liệu của một công ty, tạo sẵn cây con."""
    base = COMPANIES_DIR / symbol.upper()
    (base / "financials").mkdir(parents=True, exist_ok=True)
    (base / "reports").mkdir(parents=True, exist_ok=True)
    (base / "news").mkdir(parents=True, exist_ok=True)
    (base / "disclosures").mkdir(parents=True, exist_ok=True)
    (base / "insights").mkdir(parents=True, exist_ok=True)
    (base / "analysis").mkdir(parents=True, exist_ok=True)
    (base / "ownership").mkdir(parents=True, exist_ok=True)   # cổ đông, lãnh đạo, cty con/liên kết
    (base / "market").mkdir(parents=True, exist_ok=True)       # giá lịch sử OHLCV
    return base
