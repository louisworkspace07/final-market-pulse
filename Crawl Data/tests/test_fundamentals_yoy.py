"""Test C1 (YoY cùng quý suy ra) + C3 (TTM) + fix dòng doanh thu ngân hàng.

Toàn bộ dùng dữ liệu giả dựng trong test — KHÔNG đọc market.db, KHÔNG gọi mạng.
`compute()` được test qua monkeypatch `config.company_dir` trỏ vào thư mục tmp,
và chặn `vndirect.valuation` (nhánh mạng duy nhất trong compute).
"""
from __future__ import annotations

import json

import pytest

from src import fundamentals as F


# ----------------------------------------------------------------- helpers dựng dữ liệu
def rec(item_id: str, period: str, value: float, ptype: str) -> dict:
    return {"item_id": item_id, "period": period, "value": value, "period_type": ptype}


def quarters(item_id: str, pairs) -> list[dict]:
    return [rec(item_id, p, v, "Q") for p, v in pairs]


def years(item_id: str, pairs) -> list[dict]:
    return [rec(item_id, str(y), v, "Y") for y, v in pairs]


# Mẫu kỳ phổ biến nhất đo thật (1.032/1.525 mã): có Q2..Q4 của y-1 và Q1 của y,
# THIẾU đúng Q1(y-1) → đây chính là ca mà C1 phải suy ra được.
def signature_income(rev_item: str = "net_sales") -> list[dict]:
    q = quarters(rev_item, [("2025-Q2", 200.0), ("2025-Q3", 200.0),
                            ("2025-Q4", 300.0), ("2026-Q1", 132.0)])
    # FY2025 = 800 ⇒ Q1(2025) suy ra = 800 − (200+200+300) = 100
    y = years(rev_item, [(2022, 600.0), (2023, 700.0), (2024, 750.0), (2025, 800.0)])
    return q + y


# ----------------------------------------------------------------- C1: reported
def test_yoy_q_reported_uu_tien_hon_derived():
    """Có sẵn quý cùng kỳ ⇒ source="reported" và dùng đúng số công bố, không suy ra."""
    recs = quarters("net_sales", [
        ("2025-Q1", 100.0), ("2025-Q2", 200.0), ("2025-Q3", 200.0),
        ("2025-Q4", 300.0), ("2026-Q1", 150.0),
    ]) + years("net_sales", [(2025, 800.0)])
    val, src = F._yoy_same_quarter(recs, "net_sales")
    assert src == "reported"
    assert val == pytest.approx(50.0)   # 150 vs 100


def test_yoy_q_reported_khong_bi_guard_additive_chan():
    """Nhánh reported KHÔNG cần giả định cộng dồn: FY lệch xa vẫn dùng được số công bố."""
    recs = quarters("net_sales", [
        ("2025-Q1", 100.0), ("2025-Q2", 200.0), ("2025-Q3", 200.0),
        ("2025-Q4", 300.0), ("2026-Q1", 120.0),
    ]) + years("net_sales", [(2025, 5000.0)])   # FY vô lý so với Σ quý
    val, src = F._yoy_same_quarter(recs, "net_sales")
    assert src == "reported"
    assert val == pytest.approx(20.0)


# ----------------------------------------------------------------- C1: derived
def test_yoy_q_derived_tu_fy_tru_3_quy():
    """Thiếu Q1(y-1) ⇒ suy ra = FY − 3 quý còn lại, source="derived"."""
    val, src = F._yoy_same_quarter(signature_income(), "net_sales")
    assert src == "derived"
    # Q1(2025) = 800 − 700 = 100 ; Q1(2026) = 132 ⇒ +32%
    assert val == pytest.approx(32.0)


def test_yoy_q_derived_am_van_tra_dung_dau():
    """Quý mới nhất thấp hơn cùng kỳ ⇒ trả số âm, không kẹp về 0."""
    recs = quarters("net_sales", [("2025-Q2", 200.0), ("2025-Q3", 200.0),
                                  ("2025-Q4", 300.0), ("2026-Q1", 80.0)]) \
        + years("net_sales", [(2025, 800.0)])
    val, src = F._yoy_same_quarter(recs, "net_sales")
    assert src == "derived"
    assert val == pytest.approx(-20.0)   # 80 vs 100


# ----------------------------------------------------------------- C1: guards
def test_guard_lech_hon_2_phan_tram_thi_bo_han():
    """|FY − Σ4 quý| / |FY| > 2% ⇒ số quý không rời rạc ⇒ None, KHÔNG trả 0."""
    # 2024 đủ 4 quý: Σ = 400+400+400+400 = 1600 nhưng FY2024 = 1000 (lệch 60%).
    recs = quarters("net_sales", [
        ("2024-Q1", 400.0), ("2024-Q2", 400.0), ("2024-Q3", 400.0), ("2024-Q4", 400.0),
        ("2025-Q2", 200.0), ("2025-Q3", 200.0), ("2025-Q4", 300.0), ("2026-Q1", 132.0),
    ]) + years("net_sales", [(2024, 1000.0), (2025, 800.0)])
    val, src = F._yoy_same_quarter(recs, "net_sales")
    assert val is None
    assert src is None


def test_guard_lech_duoi_2_phan_tram_thi_van_dung():
    """Lệch 1% (làm tròn/đơn vị nhỏ) vẫn trong ngưỡng ⇒ tiếp tục suy ra."""
    recs = quarters("net_sales", [
        ("2024-Q1", 250.0), ("2024-Q2", 250.0), ("2024-Q3", 250.0), ("2024-Q4", 250.0),
        ("2025-Q2", 200.0), ("2025-Q3", 200.0), ("2025-Q4", 300.0), ("2026-Q1", 132.0),
    ]) + years("net_sales", [(2024, 1010.0), (2025, 800.0)])   # lệch 0,99%
    val, src = F._yoy_same_quarter(recs, "net_sales")
    assert src == "derived"
    assert val == pytest.approx(32.0)


def test_guard_quy_dong_bang_2018_khi_fy_da_2025():
    """5 mã đo thật có chuỗi quý đóng băng ở 2018 trong khi FY đã tới 2025.
    Quý và FY lệch năm ⇒ TUYỆT ĐỐI không ghép ⇒ None."""
    recs = quarters("net_sales", [("2018-Q2", 50.0), ("2018-Q3", 50.0),
                                  ("2018-Q4", 60.0), ("2018-Q1", 40.0)]) \
        + years("net_sales", [(2024, 750.0), (2025, 800.0)])
    val, src = F._yoy_same_quarter(recs, "net_sales")
    assert val is None
    assert src is None


def test_guard_thieu_mot_quy_thi_bo():
    """Thiếu Q3(y-1) ⇒ không đủ 3 quý để trừ ⇒ None (không coi quý thiếu là 0)."""
    recs = quarters("net_sales", [("2025-Q2", 200.0), ("2025-Q4", 300.0),
                                  ("2026-Q1", 132.0)]) \
        + years("net_sales", [(2025, 800.0)])
    assert F._yoy_same_quarter(recs, "net_sales") == (None, None)


def test_guard_thieu_fy_thi_bo():
    recs = quarters("net_sales", [("2025-Q2", 200.0), ("2025-Q3", 200.0),
                                  ("2025-Q4", 300.0), ("2026-Q1", 132.0)])
    assert F._yoy_same_quarter(recs, "net_sales") == (None, None)


def test_guard_cung_ky_suy_ra_bang_0_thi_bo():
    """FY − 3 quý = 0 ⇒ mẫu số 0 ⇒ None, không chia cho 0, không trả 0%."""
    recs = quarters("net_sales", [("2025-Q2", 200.0), ("2025-Q3", 200.0),
                                  ("2025-Q4", 300.0), ("2026-Q1", 132.0)]) \
        + years("net_sales", [(2025, 700.0)])   # 700 − 700 = 0
    assert F._yoy_same_quarter(recs, "net_sales") == (None, None)


def test_khong_co_du_lieu_quy_thi_bo():
    recs = years("net_sales", [(2024, 750.0), (2025, 800.0)])
    assert F._yoy_same_quarter(recs, "net_sales") == (None, None)


# ----------------------------------------------------------------- C3: TTM
def test_ttm_du_4_quy_lien_tiep():
    s = F._series(signature_income(), "net_sales", "Q")
    assert F._ttm_sum(s) == pytest.approx(200 + 200 + 300 + 132)


def test_ttm_thieu_quy_giua_chuoi_thi_none():
    """Hụt Q3 ⇒ 4 phần tử cuối không liên tục ⇒ None (không cộng bừa)."""
    recs = quarters("net_sales", [("2025-Q1", 100.0), ("2025-Q2", 200.0),
                                  ("2025-Q4", 300.0), ("2026-Q1", 132.0)])
    s = F._series(recs, "net_sales", "Q")
    assert F._ttm_sum(s) is None


def test_ttm_duoi_4_quy_thi_none():
    recs = quarters("net_sales", [("2025-Q4", 300.0), ("2026-Q1", 132.0)])
    assert F._ttm_sum(F._series(recs, "net_sales", "Q")) is None


def test_ttm_bat_qua_nam_dung_lien_tiep():
    """Q2/2025→Q1/2026 vắt qua năm nhưng vẫn liên tiếp ⇒ tính được."""
    s = F._series(signature_income(), "net_sales", "Q")
    assert F._ttm_sum(s) is not None


def test_ttm_yoy_can_8_quy_nen_thuong_none():
    """Chỉ 4 quý ⇒ cửa sổ TTM cùng kỳ (back=4) không có ⇒ None. Đo thật chỉ 1/1.525
    mã đủ 8 quý, nên ttm_yoy là khoá giữ chỗ cho tương lai."""
    s = F._series(signature_income(), "net_sales", "Q")
    assert F._ttm_sum(s, back=4) is None


def test_ttm_yoy_tinh_duoc_khi_du_8_quy():
    pairs = [(f"{y}-Q{q}", 100.0) for y in (2024, 2025) for q in (1, 2, 3, 4)]
    pairs += [("2026-Q1", 100.0), ("2026-Q2", 100.0),
              ("2026-Q3", 100.0), ("2026-Q4", 100.0)]
    s = F._series(quarters("net_sales", pairs), "net_sales", "Q")
    assert F._ttm_sum(s) == pytest.approx(400.0)
    assert F._ttm_sum(s, back=4) == pytest.approx(400.0)
    assert F._growth(F._ttm_sum(s), F._ttm_sum(s, back=4)) == pytest.approx(0.0)


# ----------------------------------------------------------------- compute(): hợp đồng output
def _write_company(tmp_path, symbol: str, income: list[dict],
                   balance: list[dict] | None = None,
                   close: float | None = None):
    cdir = tmp_path / symbol
    (cdir / "financials").mkdir(parents=True, exist_ok=True)
    for name, recs in (("income_statement", income),
                       ("balance_sheet", balance or []),
                       ("cash_flow", []), ("ratio", [])):
        (cdir / "financials" / f"{name}.json").write_text(
            json.dumps({"records": recs}), encoding="utf-8")
    if close is not None:
        (cdir / "market").mkdir(parents=True, exist_ok=True)
        (cdir / "market" / "price.json").write_text(
            json.dumps({"items": [{"time": "2026-07-24", "close": close}]}),
            encoding="utf-8")
    return cdir


@pytest.fixture
def offline(monkeypatch, tmp_path):
    """Trỏ company_dir vào tmp + chặn nhánh mạng duy nhất (vndirect.valuation)."""
    monkeypatch.setattr(F.config, "company_dir", lambda s: tmp_path / s.upper())
    from src import vndirect
    monkeypatch.setattr(vndirect, "valuation",
                        lambda s: (_ for _ in ()).throw(RuntimeError("offline")))
    return tmp_path


def test_compute_them_khoa_moi_khong_xoa_khoa_cu(offline):
    inc = signature_income() + quarters("net_profit_loss_after_tax", [
        ("2025-Q2", 20.0), ("2025-Q3", 20.0), ("2025-Q4", 30.0), ("2026-Q1", 13.2)])
    inc += years("net_profit_loss_after_tax", [(2024, 75.0), (2025, 80.0)])
    _write_company(offline, "AAA", inc)
    m = F.compute("AAA")

    rv = m["revenue"]
    # Khoá MỚI (hợp đồng chốt với WS-3/WS-4)
    assert rv["yoy_q"] == pytest.approx(32.0)
    assert rv["yoy_q_source"] == "derived"
    assert rv["ttm"] == pytest.approx(832.0)
    assert rv["ttm_yoy"] is None          # cần 8 quý
    assert rv["item_id"] == "net_sales"
    assert "eps_ttm" in m and "pe_ttm" in m
    for k in ("yoy_q", "yoy_q_source", "ttm", "ttm_yoy"):
        assert k in m["net_profit"]
    # Khoá CŨ phải còn nguyên tên + ý nghĩa (stock_page/api.py đọc valuation_band)
    for k in ("latest", "period", "qoq", "yoy_y", "trend_q", "trend_periods"):
        assert k in rv
    assert "valuation_band" in m
    # qoq giữ nguyên ý nghĩa Q1-so-Q4: 132 vs 300 = −56%
    assert rv["qoq"] == pytest.approx((132 - 300) / 300 * 100)


def test_compute_ngan_hang_dung_total_operating_income(offline):
    """Ngân hàng KHÔNG có net_sales ⇒ trước fix revenue.latest = None cho MỌI bank.
    Sau fix phải đọc total_operating_income và báo đúng item_id."""
    inc = signature_income("total_operating_income")
    inc += quarters("net_interest_income", [("2026-Q1", 90.0)])
    inc += quarters("net_profit_loss_after_tax", [("2026-Q1", 40.0)])
    bal = [rec("loans_and_advances_to_customers_net", "2026-Q1", 5000.0, "Q"),
           rec("deposits_from_customers", "2026-Q1", 6000.0, "Q"),
           rec("total_assets", "2026-Q1", 9000.0, "Q"),
           rec("owners_equity", "2026-Q1", 800.0, "Q")]
    _write_company(offline, "VCB", inc, balance=bal)
    m = F.compute("VCB")

    assert m["is_bank"] is True
    assert m["revenue"]["item_id"] == "total_operating_income"
    assert m["revenue"]["latest"] == pytest.approx(132.0)     # KHÔNG còn None
    assert m["revenue"]["yoy_q"] == pytest.approx(32.0)
    assert m["revenue"]["yoy_q_source"] == "derived"


def test_compute_phi_ngan_hang_khong_doc_total_operating_income(offline):
    inc = signature_income("net_sales")
    _write_company(offline, "BBB", inc)
    m = F.compute("BBB")
    assert m["is_bank"] is False
    assert m["revenue"]["item_id"] == "net_sales"


def test_compute_pe_ttm_tu_eps_ttm_va_gia(offline):
    """EPS TTM = Σ4 quý eps_basic_vnd; giá theo nghìn đồng được quy về đồng."""
    inc = signature_income() + quarters("eps_basic_vnd", [
        ("2025-Q2", 1000.0), ("2025-Q3", 1000.0),
        ("2025-Q4", 1000.0), ("2026-Q1", 1000.0)])
    _write_company(offline, "CCC", inc, close=62.9)   # 62,9 nghìn đ = 62.900 đ
    m = F.compute("CCC")
    assert m["eps_ttm"] == pytest.approx(4000.0)
    assert m["pe_ttm"] == pytest.approx(62900.0 / 4000.0)


def test_compute_eps_ttm_am_thi_pe_ttm_none(offline):
    inc = signature_income() + quarters("eps_basic_vnd", [
        ("2025-Q2", -500.0), ("2025-Q3", -500.0),
        ("2025-Q4", -500.0), ("2026-Q1", -500.0)])
    _write_company(offline, "DDD", inc, close=10.0)
    m = F.compute("DDD")
    assert m["eps_ttm"] == pytest.approx(-2000.0)
    assert m["pe_ttm"] is None


def test_compute_khong_co_gia_thi_pe_ttm_none(offline):
    inc = signature_income() + quarters("eps_basic_vnd", [
        ("2025-Q2", 1000.0), ("2025-Q3", 1000.0),
        ("2025-Q4", 1000.0), ("2026-Q1", 1000.0)])
    _write_company(offline, "EEE", inc)   # không ghi price.json
    m = F.compute("EEE")
    assert m["eps_ttm"] == pytest.approx(4000.0)
    assert m["pe_ttm"] is None


def test_compute_quy_dong_bang_2018_khong_bia_yoy_q(offline):
    inc = quarters("net_sales", [("2018-Q1", 40.0), ("2018-Q2", 50.0),
                                 ("2018-Q3", 50.0), ("2018-Q4", 60.0)]) \
        + years("net_sales", [(2024, 750.0), (2025, 800.0)])
    _write_company(offline, "FFF", inc)
    m = F.compute("FFF")
    assert m["revenue"]["yoy_q"] is None
    assert m["revenue"]["yoy_q_source"] is None


def test_quarter_key_bo_nhan_ky_la():
    assert F._quarter_key("2025-Q3") == (2025, 3)
    assert F._quarter_key("2025") is None
    assert F._quarter_key("2025-Q9") is None
    assert F._quarter_key("") is None
    assert F._quarter_key(None) is None
