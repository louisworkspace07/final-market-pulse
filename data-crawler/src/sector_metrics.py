"""Bộ chỉ tiêu ĐÚNG THEO NGÀNH + ngưỡng cờ đỏ.

Vì sao cần: chấm mọi doanh nghiệp bằng cùng một bộ chỉ tiêu (biên gộp, Z-score...)
là SAI phương pháp — ngân hàng phải nhìn NIM/CIR/LDR, không có "biên lãi gộp" hay
Altman Z. Module này:

1. Chọn bộ chỉ tiêu theo nhóm (bank / non_bank) — securities & insurance nằm ở
   non_bank nhưng gắn nhãn ngành để diễn giải.
2. ĐỌC giá trị CHUẨN từ statement='ratio' (nguồn KBS đã tính sẵn: NIM, CIR, LDR,
   DIO, DSO, interest_coverage, accrual...). Thiếu ở KBS → fallback raw_ratios
   (xấp xỉ từ báo cáo gốc). NPL/CAR không có nguồn → ghi rõ "n/a", KHÔNG bịa.
3. Gắn cờ good/warn/danger theo ngưỡng ngành + gom red_flags (mô tả dữ kiện,
   không dùng từ khuyến nghị — tuân thủ legal.py).

Trả về cấu trúc render-ready cho UI + text block gọn cho AI.
"""
from __future__ import annotations

from . import raw_ratios

# item_id trong statement='ratio' (nguồn KBS) — đã kiểm chứng qua scripts/diag_items.py
# Mỗi spec: (key, item_id_KBS, nhãn, đơn vị, chiều tốt, ngưỡng cờ)
# chiều: "high"=cao tốt, "low"=thấp tốt, "band"=trong khoảng tốt, "info"=không chấm
# ngưỡng: dict {danger, warn} hiểu theo chiều (vd low: value>warn→warn, >danger→danger)

_BANK_SPECS = [
    ("nim",  "net_interest_margin_nim",              "NIM (biên lãi thuần)",      "%", "high", {"warn": 2.5, "danger": 1.5}),
    ("cir",  "cost_income_ratio_cir",                "CIR (chi phí/thu nhập)",    "%", "low",  {"warn": 40, "danger": 50}),
    ("ldr",  "outstanding_loans_customer_deposits",  "LDR (cho vay/tiền gửi)",    "%", "band", {"lo": 70, "hi": 90, "danger_hi": 100}),
    ("yoea", "yield_on_earning_assets_yoea",         "Lợi suất TS sinh lãi",      "%", "info", {}),
    ("cof",  "cost_of_funding_earning_assets_cof",   "Chi phí vốn",               "%", "low",  {"warn": 5, "danger": 7}),
    ("llp",  "loan_loss_provision_ratio",            "Trích lập DP/cho vay",      "%", "info", {}),
    ("eta",  "equity_total_assets",                  "Vốn chủ/Tổng TS (đệm vốn)", "%", "high", {"warn": 7, "danger": 5}),
    ("roe",  "roe",                                  "ROE",                       "%", "high", {"warn": 12, "danger": 8}),
    ("roa",  "roa",                                  "ROA",                       "%", "high", {"warn": 1, "danger": 0.5}),
]

_NONBANK_SPECS = [
    ("gross_margin", "gross_margin",       "Biên lãi gộp",       "%", "high", {"warn": 12, "danger": 6}),
    ("net_margin",   "net_margin",         "Biên lãi ròng",      "%", "high", {"warn": 6, "danger": 2}),
    ("ebit_margin",  "ebit_margin",        "Biên EBIT",          "%", "info", {}),
    ("roe",          "roe",                "ROE",                "%", "high", {"warn": 12, "danger": 6}),
    ("roa",          "roa",                "ROA",                "%", "high", {"warn": 5, "danger": 2}),
    ("roce",         "return_on_capital_employed_roce", "ROCE",  "%", "info", {}),
    ("de",           "debt_to_equity",     "Nợ/Vốn chủ",         "%", "low",  {"warn": 100, "danger": 200}),
    ("icr",          "interest_coverage",  "Khả năng trả lãi",   "x", "high", {"warn": 3, "danger": 1.5}),
    ("dio",          "days_of_inventory_on_hand", "Số ngày tồn kho", "ngày", "info", {}),
    ("dso",          "days_of_sales_outstanding", "Số ngày phải thu", "ngày", "low", {"warn": 90, "danger": 150}),
    ("str",          "short_term_ratio",   "Thanh toán hiện hành", "x", "high", {"warn": 1.2, "danger": 1.0}),
]


def _latest_annual(rat: list[dict], item_id: str):
    """Giá trị KBS kỳ NĂM mới nhất; fallback quý mới nhất nếu không có năm."""
    ann = [(p, v) for p, v, in [(r["period"], r["value"]) for r in rat
            if r.get("item_id") == item_id and isinstance(r.get("value"), (int, float))]
           if "-Q" not in str(p)]
    if ann:
        ann.sort(key=lambda x: str(x[0]))
        return ann[-1][1]
    q = [(r["period"], r["value"]) for r in rat
         if r.get("item_id") == item_id and isinstance(r.get("value"), (int, float))]
    if q:
        q.sort(key=lambda x: str(x[0]))
        return q[-1][1]
    return None


def _flag(value, direction: str, th: dict) -> str:
    """Trả 'good' | 'warn' | 'danger' | 'na' theo chiều + ngưỡng."""
    if value is None:
        return "na"
    if direction == "info" or not th:
        return "info"
    if direction == "high":
        if value < th.get("danger", -1e9):
            return "danger"
        if value < th.get("warn", -1e9):
            return "warn"
        return "good"
    if direction == "low":
        if value > th.get("danger", 1e9):
            return "danger"
        if value > th.get("warn", 1e9):
            return "warn"
        return "good"
    if direction == "band":
        if value > th.get("danger_hi", 1e9):
            return "danger"
        if value < th.get("lo", -1e9) or value > th.get("hi", 1e9):
            return "warn"
        return "good"
    return "info"


def classify(sector: str | None, is_bank_flag: bool) -> tuple[str, str]:
    """(group, sub_label). group ∈ {'bank','non_bank'}."""
    s = (sector or "").lower()
    if is_bank_flag or "bank" in s:
        return "bank", "Ngân hàng"
    if "insurance" in s:
        return "non_bank", "Bảo hiểm"
    if "financial services" in s or "securities" in s:
        return "non_bank", "Dịch vụ tài chính / Chứng khoán"
    if "real estate" in s:
        return "non_bank", "Bất động sản"
    return "non_bank", sector or "Doanh nghiệp phi tài chính"


def compute(rat: list[dict], inc: list[dict], bs: list[dict], cf: list[dict],
            sector: str | None, raw: dict | None = None) -> dict:
    """Bộ chỉ tiêu theo ngành cho 1 mã.

    rat/inc/bs/cf: records từng statement (như _load trong fundamentals).
    raw: output raw_ratios.compute (nếu đã có) để fallback khi KBS thiếu.
    """
    raw = raw if raw is not None else raw_ratios.compute(inc, bs, cf)
    is_bank = raw.get("is_bank") or raw_ratios.is_bank(bs, inc)
    group, sub = classify(sector, is_bank)
    specs = _BANK_SPECS if group == "bank" else _NONBANK_SPECS

    # nguồn fallback từ raw_ratios (đã nhân 100 cho %)
    raw_map = {}
    if is_bank and raw.get("bank_metrics"):
        bm = raw["bank_metrics"]
        raw_map = {"nim": bm.get("nim"), "cir": bm.get("cir"),
                   "ldr": (bm.get("ldr") * 100 if bm.get("ldr") is not None else None)}
    else:
        raw_map = {"gross_margin": raw.get("margins", {}).get("gross"),
                   "net_margin": raw.get("margins", {}).get("net"),
                   "roe": raw.get("profitability", {}).get("roe"),
                   "roa": raw.get("profitability", {}).get("roa"),
                   "de": (raw.get("solvency", {}).get("debt_to_equity") * 100
                          if raw.get("solvency", {}).get("debt_to_equity") is not None else None),
                   "str": raw.get("solvency", {}).get("current_ratio")}

    metrics, red_flags = [], []
    for key, item_id, label, unit, direction, th in specs:
        val = _latest_annual(rat, item_id)
        src = "KBS"
        if val is None and raw_map.get(key) is not None:
            val, src = round(raw_map[key], 2), "raw"
        fl = _flag(val, direction, th)
        metrics.append({"key": key, "label": label,
                        "value": round(val, 2) if isinstance(val, (int, float)) else None,
                        "unit": unit, "flag": fl, "source": src if val is not None else None})
        if fl == "danger":
            red_flags.append(f"{label}: {round(val, 2)}{unit} (ngưỡng nguy hiểm)")
        elif fl == "warn":
            red_flags.append(f"{label}: {round(val, 2)}{unit} (cần lưu ý)")

    out = {"group": group, "sub_label": sub, "is_bank": is_bank,
           "metrics": metrics, "red_flags": red_flags}

    # Ngân hàng: NPL/CAR không có nguồn — ghi rõ thay vì để trống gây hiểu nhầm.
    if group == "bank":
        out["unavailable"] = {
            "npl": "cần thuyết minh nhóm nợ — không có trong BCTC chuẩn/nguồn KBS",
            "car": "cần RWA — ngân hàng công bố riêng, không có trong nguồn"}

    # Bất động sản: bổ sung người mua trả trước (nguồn doanh thu tương lai) từ BS gốc.
    if "real estate" in (sector or "").lower():
        adv = _latest_bs(bs, "advances_from_customers") or _latest_bs(bs, "short_term_advances_from_customers")
        inv = _latest_bs(bs, "inventories_net") or _latest_bs(bs, "inventories")
        ta = _latest_bs(bs, "total_assets")
        if adv is not None and ta:
            metrics.append({"key": "adv_ta", "label": "Người mua trả trước/Tổng TS",
                            "value": round(adv / ta * 100, 1), "unit": "%", "flag": "info", "source": "raw"})
        if inv is not None and ta:
            metrics.append({"key": "inv_ta", "label": "Hàng tồn kho/Tổng TS",
                            "value": round(inv / ta * 100, 1), "unit": "%", "flag": "info", "source": "raw"})

    return out


def _latest_bs(bs: list[dict], item_id: str):
    s = raw_ratios._pref_qy(bs, item_id)[0]
    return raw_ratios._last(s)


def text_block(sm: dict) -> str:
    """Chuỗi gọn cho prompt AI — nêu mô hình ngành + chỉ tiêu + cờ đỏ."""
    lines = [f"Mô hình chỉ tiêu: {sm['sub_label']} (nhóm {sm['group']})."]
    for m in sm["metrics"]:
        if m["value"] is None:
            continue
        tag = {"danger": " [NGUY HIỂM]", "warn": " [lưu ý]", "good": " [tốt]"}.get(m["flag"], "")
        lines.append(f"- {m['label']}: {m['value']}{m['unit']}{tag}")
    if sm.get("unavailable"):
        lines.append("Không có dữ liệu: " + "; ".join(sm["unavailable"].keys()).upper()
                     + " (nguồn không cấp — không suy diễn).")
    if sm["red_flags"]:
        lines.append("Cờ cảnh báo: " + "; ".join(sm["red_flags"]))
    return "\n".join(lines)
