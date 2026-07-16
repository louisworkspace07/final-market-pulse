# -*- coding: utf-8 -*-
"""D-3 · Lời dẫn AI cho biểu đồ.

Trọng tâm test là VALIDATOR, không phải chất lượng câu chữ: ràng buộc D0 nói AI
không được sinh số, nên điều duy nhất phải chứng minh là mọi tham chiếu sai đều
bị LOẠI — không được sửa hộ, không được lọt lên giao diện.
"""
import json

from modules.stock_page import chart_notes

CHARTS = [
    {"id": "margin_trend", "group": "A", "title": "Biên lãi qua các kỳ", "kind": "line",
     "unit": "%", "x": ["2022", "2023", "2024"],
     "series": [{"name": "Biên gộp", "data": [39.0, 38.6, 36.9]}]},
    {"id": "price_volume", "group": "F", "title": "Giá & khối lượng", "kind": "price",
     "unit": "nghìn đồng", "x": ["2026-07-01", "2026-07-02"],
     "series": [{"name": "Giá", "data": [62.9, 63.1]}]},
]


def _raw(items):
    return json.dumps(items, ensure_ascii=False)


def test_giu_muc_hop_le():
    notes, bad = chart_notes.validate(_raw([{
        "chart_id": "margin_trend",
        "title": "Biên lãi gộp bào mòn ba năm liên tiếp",
        "read_this": "Đường đi xuống nghĩa là mỗi đồng doanh thu giữ lại được ít lãi hơn.",
        "history_note": "Mức 36,9% năm 2024 là thấp nhất trong chuỗi.",
        "annotations": [{"period": "2024", "note": "thấp nhất chuỗi"}],
    }]), CHARTS)
    assert not bad
    n = notes["margin_trend"]
    assert n["history_note"].startswith("Mức 36,9%")
    assert n["annotations"] == [{"period": "2024", "note": "thấp nhất chuỗi"}]


def test_loai_chart_id_khong_co_that():
    notes, bad = chart_notes.validate(_raw([
        {"chart_id": "khong_ton_tai", "title": "x", "read_this": "y"},
    ]), CHARTS)
    assert notes == {}
    assert any("không có thật" in b for b in bad)


def test_loai_ky_khong_co_that_nhung_giu_lai_loi_dan():
    """Chú thích trỏ sai kỳ bị bỏ, phần chữ đúng vẫn được giữ."""
    notes, bad = chart_notes.validate(_raw([{
        "chart_id": "margin_trend", "title": "t", "read_this": "r",
        "annotations": [{"period": "2019", "note": "kỳ không có trong biểu đồ"},
                        {"period": "2023", "note": "kỳ có thật"}],
    }]), CHARTS)
    assert notes["margin_trend"]["annotations"] == [{"period": "2023", "note": "kỳ có thật"}]
    assert any("2019" in b for b in bad)


def test_loai_noi_dung_vi_pham_phap_ly():
    """Lời dẫn mang hàm ý mua/bán bị chặn bởi legal.check_payload."""
    notes, bad = chart_notes.validate(_raw([{
        "chart_id": "margin_trend", "title": "Nên mua khi giá về vùng này",
        "read_this": "r",
    }]), CHARTS)
    assert notes == {}
    assert any("pháp lý" in b for b in bad)


def test_phan_hoi_khong_phai_json():
    notes, bad = chart_notes.validate("xin lỗi tôi không hiểu", CHARTS)
    assert notes == {} and bad


def test_json_lan_trong_van_xuoi_va_rao_code():
    """AI hay kèm lời dẫn hoặc bọc ```json — vẫn phải lấy được mảng."""
    raw = ("Đây là kết quả:\n```json\n"
           + _raw([{"chart_id": "price_volume", "title": "t", "read_this": "r"}])
           + "\n```\nHy vọng giúp được bạn.")
    notes, _ = chart_notes.validate(raw, CHARTS)
    assert "price_volume" in notes


def test_merge_gan_loi_dan_va_giu_ten_goc():
    payload = {"charts": [dict(c) for c in CHARTS], "groups": []}
    out = chart_notes.merge(payload, {"margin_trend": {
        "title": "Tiêu đề mới", "read_this": "r", "history_note": "h", "annotations": []}})
    c = next(x for x in out["charts"] if x["id"] == "margin_trend")
    assert c["title"] == "Tiêu đề mới"
    assert c["title_data"] == "Biên lãi qua các kỳ"     # tên kỹ thuật vẫn còn để đối chiếu
    assert c["narrated"] is True
    assert out["narrated_count"] == 1


def test_merge_khong_co_loi_dan_thi_giu_nguyen():
    payload = {"charts": [dict(c) for c in CHARTS]}
    assert chart_notes.merge(payload, {}) is payload


def test_mot_nhom_hong_khong_lam_hong_nhom_khac():
    payload = {"charts": CHARTS,
               "groups": [{"key": "A", "title": "Kết quả"}, {"key": "F", "title": "Giá"}]}
    calls = {"n": 0}

    def ask(_prompt):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("Local API sập")
        return _raw([{"chart_id": "price_volume", "title": "t", "read_this": "r"}])

    data = chart_notes.generate(payload, ask, "TST")
    assert "price_volume" in data["notes"]           # nhóm sau vẫn chạy
    assert data["report"][0]["ok"] == 0
    assert any("gọi AI lỗi" in r for r in data["report"][0]["rejected"])


def test_prompt_co_rao_phap_ly_va_khong_gui_toan_bo_chuoi():
    p = chart_notes.build_prompt("FPT", "Kết quả kinh doanh", CHARTS)
    assert "margin_trend" in p and "KHÔNG" in p
    assert "khuyến nghị" in p.lower() or "mua" in p.lower()   # rào legal có mặt
    assert "38.6" not in p        # điểm giữa không được gửi, chỉ đầu/cuối/min/max
