# -*- coding: utf-8 -*-
"""D-1 · Tầng dữ liệu biểu đồ — PLAN-F0-TRUC-QUAN Phụ lục D.

Hai nhóm test:
1. Hợp đồng dữ liệu chạy trên DB giả — luôn chạy được, không cần máy có market.db.
2. Kiểm tính đúng trên market.db thật — tự bỏ qua nếu máy chưa có dữ liệu.
"""
import os
import sqlite3

import pytest

from modules.stock_page import chart_data

DB_REAL = os.path.join(os.path.dirname(__file__), "..", "..",
                       "data-crawler", "database", "market.db")


# ------------------------------------------------------------------ DB giả
@pytest.fixture()
def fake_db(tmp_path):
    """DB tối thiểu: 4 năm KQKD + cân đối, đủ để dựng nhóm A/B/D."""
    p = tmp_path / "t.db"
    c = sqlite3.connect(p)
    c.executescript("""
        CREATE TABLE financials (symbol TEXT, statement TEXT, item_id TEXT, item TEXT,
            item_en TEXT, period TEXT, value REAL);
        CREATE TABLE price (symbol TEXT, time TEXT, open REAL, high REAL, low REAL,
            close REAL, volume REAL);
        CREATE TABLE index_ohlc (code TEXT, time TEXT, open REAL, high REAL, low REAL,
            close REAL, volume REAL);
        CREATE TABLE events (symbol TEXT, event_id TEXT, event_name TEXT, title TEXT,
            public_date TEXT, value_per_share REAL);
        CREATE TABLE companies (symbol TEXT PRIMARY KEY, organ_name TEXT, exchange TEXT,
            updated_at TEXT, sector TEXT, market_cap REAL, current_price REAL);
    """)
    rows = []
    for i, y in enumerate(("2022", "2023", "2024", "2025")):
        rev = 1000e9 * (1 + i / 10)
        rows += [("T", "income_statement", "net_sales", "", "", y, rev),
                 ("T", "income_statement", "gross_profit", "", "", y, rev * 0.3),
                 ("T", "income_statement", "cost_of_sales", "", "", y, -rev * 0.7),
                 ("T", "income_statement", "net_profit_loss_after_tax", "", "", y, rev * 0.1),
                 ("T", "income_statement", "attributable_to_parent_company", "", "", y, rev * 0.09),
                 ("T", "balance_sheet", "total_assets", "", "", y, rev * 2),
                 ("T", "balance_sheet", "owners_equity", "", "", y, rev),
                 ("T", "balance_sheet", "liabilities", "", "", y, rev)]
    c.executemany("INSERT INTO financials VALUES (?,?,?,?,?,?,?)", rows)
    c.commit(); c.close()
    return str(p)


def test_hop_dong_moi_bieu_do(fake_db):
    """Mọi biểu đồ phải có đủ khoá bắt buộc và độ dài chuỗi khớp trục x."""
    out = chart_data.build(fake_db, "T")
    assert out["count"] > 0
    assert not out["errors"], out["errors"]
    ids = set()
    for c in out["charts"]:
        for k in ("id", "group", "title", "kind", "unit", "x", "series", "source"):
            assert k in c, f"{c.get('id')} thiếu khoá {k}"
        assert c["id"] not in ids, f"trùng id {c['id']}"
        ids.add(c["id"])
        assert c["series"], f"{c['id']} không có chuỗi nào"
        for s in c["series"]:
            # timeline/scatter/heatmap mang dữ liệu dạng danh sách bản ghi, không
            # ăn theo trục hạng mục nên không áp ràng buộc độ dài.
            if c["kind"] in ("timeline", "scatter", "heatmap"):
                continue
            assert len(s["data"]) == len(c["x"]), (
                f"{c['id']} · {s['name']}: {len(s['data'])} điểm nhưng trục x có {len(c['x'])}")


def test_ma_khong_co_du_lieu_khong_lam_vo(fake_db):
    out = chart_data.build(fake_db, "KHONGCO")
    assert out["count"] == 0 and not out["errors"]


def test_thac_nuoc_chi_phi_luon_la_cot_am(fake_db):
    """vnstock lưu chi phí là số ÂM; đảo dấu nhầm sẽ ra cột chi phí DƯƠNG."""
    out = chart_data.build(fake_db, "T")
    wf = next((c for c in out["charts"] if c["id"] == "profit_waterfall"), None)
    assert wf is not None
    data = wf["series"][0]["data"]
    assert data[0] > 0, "doanh thu phải dương"
    assert data[1] < 0, "giá vốn phải là cột âm"


# ------------------------------------------------------------------ DB thật
def _real():
    if not os.path.exists(DB_REAL):
        pytest.skip("máy này chưa có market.db")
    return os.path.normpath(DB_REAL)


@pytest.mark.parametrize("sym", ["FPT", "ACB"])
def test_du_lieu_that_dung_it_nhat_20_bieu_do(sym):
    """ACB có mặt để chắc nhóm ngân hàng không rơi về rỗng (không có net_sales)."""
    out = chart_data.build(_real(), sym)
    assert out["count"] >= 20, f"{sym} chỉ dựng được {out['count']} biểu đồ"
    assert not out["errors"], out["errors"]


def test_nhom_khong_trung_va_dung_thu_tu():
    """`groups` phải liệt kê mỗi nhóm ĐÚNG MỘT LẦN, theo thứ tự A→I.

    Một hàm dựng có thể phát ra biểu đồ thuộc nhiều nhóm (vd nhóm so ngành trả
    cả D và E) nên chỗ này từng sinh nhóm trùng."""
    out = chart_data.build(_real(), "FPT")
    keys = [g["key"] for g in out["groups"]]
    assert len(keys) == len(set(keys)), f"nhóm bị trùng: {keys}"
    order = list(chart_data.GROUP_TITLES)
    assert keys == [k for k in order if k in keys], f"sai thứ tự: {keys}"
    for c in out["charts"]:
        assert c["group"] in chart_data.GROUP_TITLES, (
            f"{c['id']} thuộc nhóm lạ {c['group']!r}")


def test_chu_ky_tien_mat_dung_cong_thuc():
    """Chốt chặn: chu kỳ tiền mặt = tồn kho + thu tiền − trả tiền, theo từng năm."""
    out = chart_data.build(_real(), "FPT")
    ch = {c["id"]: c for c in out["charts"]}
    if "cash_cycle" not in ch:
        pytest.skip("FPT chưa có đủ chỉ tiêu số ngày")
    days = ch["working_capital_days"]
    dio, dso, dpo = (s["data"] for s in days["series"])
    ccc = dict(zip(ch["cash_cycle"]["x"], ch["cash_cycle"]["series"][0]["data"]))
    for i, p in enumerate(days["x"]):
        if None in (dio[i], dso[i], dpo[i]) or ccc.get(p) is None:
            continue
        assert ccc[p] == pytest.approx(dio[i] + dso[i] - dpo[i], abs=0.11), (
            f"kỳ {p}: {ccc[p]} ≠ {dio[i]}+{dso[i]}−{dpo[i]}")


def test_ttm_khop_voi_so_ca_nam():
    """Chốt chặn tính đúng: tổng 4 quý của 2025 phải bằng doanh thu năm 2025."""
    out = chart_data.build(_real(), "FPT")
    ch = {c["id"]: c for c in out["charts"]}
    q = ch["rev_quarter_ttm"]
    ttm = dict(zip(q["x"], q["series"][1]["data"]))["2025-Q4"]
    year = dict(zip(ch["rev_profit_year"]["x"],
                    ch["rev_profit_year"]["series"][0]["data"]))["2025"]
    assert ttm == pytest.approx(year, rel=1e-6), f"TTM {ttm} ≠ năm {year}"


def test_khong_co_chuoi_du_bao():
    """Legal: trục thời gian phải dừng ở kỳ đã có, không kéo dài ra tương lai."""
    out = chart_data.build(_real(), "FPT")
    for c in out["charts"]:
        joined = " ".join(str(v) for v in c["x"])
        assert "dự báo" not in (c.get("note") or "").lower()
        assert "2027" not in joined, f"{c['id']} có kỳ tương lai trên trục x"
