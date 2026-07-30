# -*- coding: utf-8 -*-
"""Chặn lỗi SAI TÊN item_id — loại lỗi im lặng nguy hiểm nhất của dự án.

Ngày 2026-07-27 phát hiện BA lỗi cùng loại trong một buổi:
  fundamentals.py  hỏi "ev_to_ebitda"  → bảng lưu "ev_ebitda"                (9.891 bản ghi)
  fundamentals.py  hỏi "roic"          → bảng lưu "return_on_capital_employed_roce" (9.525)
  chart_data.py    hỏi "purchase_of_fixed_assets" → "purchases_of_fixed_assets_and_other_long_term_assets"

Không cái nào ném lỗi. Chúng chỉ trả None, prompt in "n/a", rồi AI viết
"không đủ dữ liệu về EV/EBITDA và ROIC" cho thứ đang nằm sẵn trong bảng — 7 mã
đã ghi câu đó vào kết quả lưu trong DB.

Test này quét chuỗi trong mã nguồn và đối chiếu với `SELECT DISTINCT item_id`.
Chỉ xét chuỗi TRÔNG GIỐNG item_id (snake_case dài) để không báo động giả.
"""
import io
import re
import sqlite3
import tokenize

import pytest

from src import config

# Các tệp thật sự hỏi item_id từ bảng `financials`.
_SOURCES = [
    config.ROOT / "src" / "fundamentals.py",
    config.ROOT / "src" / "raw_ratios.py",
    config.ROOT / "src" / "analyzer.py",
    config.ROOT.parent / "market-pulse" / "modules" / "stock_page" / "chart_data.py",
]

# Chuỗi snake_case đủ dài mới đáng ngờ là item_id (bỏ "a_b" kiểu tên biến ngắn).
_CAND = re.compile(r'["\']([a-z][a-z0-9]*(?:_[a-z0-9]+){2,})["\']')

# Chuỗi snake_case nhưng KHÔNG phải item_id — khoá nội bộ, đường dẫn, tên cột.
_NOT_ITEM = {
    "current_ratio", "debt_to_equity", "financial_leverage", "health_score",
    "valuation_verdict", "earnings_quality", "sector_model", "valuation_band",
    "fscore_max", "trend_periods", "yoy_q_source", "ttm_yoy", "pass_secs",
    "last_error", "last_attempt_at", "generated_at", "risk_level",
    "investment_rating", "fundamental_summary", "valuation_comment",
    "growth_comment", "peer_comment", "key_drivers", "cashflow_summary",
    "cfo_to_ni", "dso_trend", "cfo_vs_profit", "cfo_latest", "duration_s",
    "share_own_percent", "value_per_share", "public_date", "source_link",
    "short_content", "organ_name", "company_profile", "com_group_code",
    "updated_at", "market_cap", "current_price", "n_passes", "n_peers",
    "n_sector", "peer_values", "sample_sizes", "raw_derived_counts",
    "is_year", "chart_id", "read_this", "history_note", "highlight_periods",
    "max_zero_days", "min_gtgd", "zero_days", "total_secs", "prompt_chars",
    "raw_chars", "item_id", "period_type", "cfo_item_id",
    # khoá của market/board_snapshot.json, không phải bảng financials
    "foreign_buy_volume", "foreign_sell_volume",
}


def _code_strings(path):
    """Chuỗi trong PHẦN CODE, bỏ chú thích và docstring.

    Cần thiết vì chính các chú thích giải thích lỗi (vd: 'bảng lưu ev_ebitda,
    không phải ev_to_ebitda') lại chứa đúng cái tên sai — quét cả chú thích thì
    test tự báo động vì lời cảnh báo của chính nó."""
    out, prev = set(), tokenize.INDENT
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(
            path.read_text(encoding="utf-8")).readline))
    except (tokenize.TokenError, SyntaxError):
        return out
    for tok in toks:
        if tok.type == tokenize.STRING:
            # docstring = chuỗi đứng một mình ngay sau NEWLINE/INDENT/def
            if prev in (tokenize.NEWLINE, tokenize.NL, tokenize.INDENT,
                        tokenize.DEDENT, tokenize.ENCODING):
                prev = tok.type
                continue
            out.update(_CAND.findall(tok.string))
        if tok.type != tokenize.COMMENT:
            prev = tok.type
    return out


@pytest.fixture(scope="module")
def known_ids():
    db = config.DB_PATH
    if not db.exists():
        pytest.skip("chưa có market.db trên máy này")
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return {r[0] for r in conn.execute("SELECT DISTINCT item_id FROM financials")}
    finally:
        conn.close()


def test_moi_item_id_trong_ma_nguon_deu_ton_tai(known_ids):
    """Chuỗi trông như item_id mà DB không có → gần như chắc chắn gõ sai tên."""
    if len(known_ids) < 50:
        pytest.skip("market.db chưa đủ dữ liệu để đối chiếu")

    ban = []
    for path in _SOURCES:
        if not path.exists():
            continue
        for name in _code_strings(path):
            if name in _NOT_ITEM or name in known_ids:
                continue
            # Chỉ tính khi tiền tố của nó CÓ trong DB — dấu hiệu đang gọi đúng
            # họ chỉ tiêu nhưng gõ sai đuôi, thay vì một biến bình thường.
            stem = name.split("_")[0]
            if any(k.startswith(stem + "_") or k == stem for k in known_ids):
                ban.append(f"{path.name}: {name!r}")

    assert not ban, (
        "Các tên item_id sau KHÔNG có trong market.db — kiểm lại chính tả "
        "(đây là lỗi im lặng: hàm sẽ trả None và prompt in 'n/a'):\n  "
        + "\n  ".join(sorted(ban)))


@pytest.mark.parametrize("item_id", [
    "ev_ebitda", "ev_ebit", "return_on_capital_employed_roce",
    "purchases_of_fixed_assets_and_other_long_term_assets",
    "days_of_inventory_on_hand", "days_of_sales_outstanding",
    "number_of_days_of_payables", "interest_coverage", "quick_ratio",
])
def test_cac_item_id_vua_sua_deu_co_that(known_ids, item_id):
    """Chốt chặn cho đúng 3 lỗi đã sửa + các chỉ tiêu P1 sắp dùng."""
    assert item_id in known_ids, f"{item_id} không có trong market.db"
