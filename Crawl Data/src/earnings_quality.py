"""Chất lượng lợi nhuận — lợi nhuận có được "đỡ" bằng tiền thật không?

Đây là nơi phát hiện "lãi trên giấy": doanh nghiệp báo lãi nhưng dòng tiền không
theo kịp (khoản phải thu phình to, hàng tồn ứ đọng) là dấu hiệu cảnh báo mà chỉ
nhìn P/E hay tăng trưởng LNST sẽ bỏ lỡ.

Chỉ tiêu (thuần Python từ dữ liệu đã crawl):
- cfo_to_ni : Σ CFO 4 quý / Σ LNST 4 quý — chuẩn ≥0.8 tốt; <0.5 cờ đỏ.
- dso_trend : xu hướng số ngày phải thu (KBS days_of_sales_outstanding) — tăng
  mạnh khi doanh thu đi ngang → cảnh báo chất lượng doanh thu.
- accrual   : accrual_ratio_cf (KBS) làm tín hiệu bổ trợ (accrual cao = ít tiền mặt).

Ngân hàng: CFO gồm biến động tiền gửi/cho vay nên tỷ lệ CFO/LNST vô nghĩa →
KHÔNG chấm accrual; nêu rõ đánh giá qua trích lập dự phòng & ổn định NIM.

Mô tả dữ kiện, không dùng từ khuyến nghị (tuân thủ legal.py).
"""
from __future__ import annotations

from . import raw_ratios


def _ttm(records, item_id):
    q = raw_ratios._series(records, item_id, "Q")
    if len(q) >= 4:
        return sum(v for _, v in q[-4:])
    y = raw_ratios._series(records, item_id, "Y")
    return y[-1][1] if y else None


def _annual_series(rat, item_id, n=4):
    s = [(p, v) for p, v in
         [(r["period"], r["value"]) for r in rat
          if r.get("item_id") == item_id and isinstance(r.get("value"), (int, float))]
         if "-Q" not in str(p)]
    s.sort(key=lambda x: str(x[0]))
    return s[-n:]


def compute(inc: list[dict], bs: list[dict], cf: list[dict],
            rat: list[dict], is_bank: bool | None = None) -> dict:
    if is_bank is None:
        is_bank = raw_ratios.is_bank(bs, inc)

    if is_bank:
        # Ngân hàng: đánh giá qua trích lập dự phòng + ổn định NIM (nếu có chuỗi).
        nim_s = _annual_series(rat, "net_interest_margin_nim", 4)
        prov_s = _annual_series(rat, "loan_loss_provision_ratio", 4)
        note = ("Mô hình ngân hàng: không dùng CFO/accrual (dòng tiền gồm biến động "
                "tiền gửi/cho vay). Chất lượng lợi nhuận nhìn qua trích lập dự phòng "
                "& ổn định NIM.")
        flags = []
        nim_trend = None
        if len(nim_s) >= 2:
            nim_trend = round(nim_s[-1][1] - nim_s[0][1], 2)
            if nim_trend < -0.5:
                flags.append(f"NIM giảm {abs(nim_trend)} điểm % qua {len(nim_s)-1} năm")
        return {"applicable": True, "model": "bank", "score": None,
                "cfo_to_ni": None, "dso_trend": None, "accrual": None,
                "nim_trend": nim_trend,
                "provision_latest": prov_s[-1][1] if prov_s else None,
                "flags": flags, "note": note}

    # --- Non-bank ---
    cfo = _ttm(cf, raw_ratios.cfo_item_id(False))
    ni = _ttm(inc, "net_profit_loss_after_tax")
    cfo_to_ni = round(cfo / ni, 2) if (cfo is not None and ni not in (None, 0)) else None

    dso = _annual_series(rat, "days_of_sales_outstanding", 3)
    dso_trend = None
    if len(dso) >= 2 and dso[0][1]:
        dso_trend = round((dso[-1][1] - dso[0][1]) / abs(dso[0][1]) * 100, 1)  # %

    acc = _annual_series(rat, "accrual_ratio_cf", 1)
    accrual = acc[-1][1] if acc else None

    # --- Điểm 0-100: khởi 70, cộng/trừ theo 3 tín hiệu ---
    score, flags = 70, []
    if cfo_to_ni is not None:
        if cfo_to_ni >= 1.0:
            score += 20
        elif cfo_to_ni >= 0.8:
            score += 10
        elif cfo_to_ni >= 0.5:
            score -= 5
        else:
            score -= 20
            flags.append(f"CFO/LNST chỉ {cfo_to_ni} — lợi nhuận ít được tiền mặt hỗ trợ")
    if dso_trend is not None and dso_trend > 30:
        score -= 12
        flags.append(f"Số ngày phải thu tăng {dso_trend}% — khoản phải thu phình nhanh")
    if accrual is not None and accrual > 30:
        score -= 8
        flags.append(f"Accrual cao ({accrual}%) — chênh lệch lãi kế toán vs tiền mặt lớn")
    score = max(0, min(100, score))

    return {"applicable": True, "model": "non_bank", "score": score,
            "cfo_to_ni": cfo_to_ni, "dso_trend": dso_trend, "accrual": accrual,
            "flags": flags,
            "note": "≥0.8 CFO/LNST là lành mạnh; phải thu tăng nhanh hoặc accrual "
                    "cao là dấu hiệu lợi nhuận kém chất lượng."}


def text_block(eq: dict) -> str:
    if eq.get("model") == "bank":
        parts = [eq["note"]]
        if eq.get("nim_trend") is not None:
            parts.append(f"Xu hướng NIM: {eq['nim_trend']:+} điểm %.")
        if eq.get("provision_latest") is not None:
            parts.append(f"Trích lập DP/cho vay gần nhất: {eq['provision_latest']}%.")
        if eq["flags"]:
            parts.append("Cảnh báo: " + "; ".join(eq["flags"]))
        return " ".join(parts)
    parts = [f"Điểm chất lượng lợi nhuận: {eq['score']}/100."]
    if eq["cfo_to_ni"] is not None:
        parts.append(f"CFO/LNST (4 quý): {eq['cfo_to_ni']}.")
    if eq["dso_trend"] is not None:
        parts.append(f"Xu hướng phải thu: {eq['dso_trend']:+}%.")
    if eq["accrual"] is not None:
        parts.append(f"Accrual: {eq['accrual']}%.")
    if eq["flags"]:
        parts.append("Cảnh báo: " + "; ".join(eq["flags"]))
    return " ".join(parts)
