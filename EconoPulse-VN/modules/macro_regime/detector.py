# -*- coding: utf-8 -*-
"""Bộ nhận diện chế độ tiền tệ (PILLAR-M · M1) — "đèn 3 màu" LEGAL-SAFE.

Học ý tưởng Traffic Light của VNSignal NHƯNG chỉ giữ phần THÔNG TIN:
trạng thái + 3 chỉ báo thành phần + ngưỡng công khai. TUYỆT ĐỐI KHÔNG có
"tài sản thuận lợi / nên ưu tiên" (phần đó user đã đánh dấu dính pháp lý
trong PDF triage p32-33 và bị blacklist bởi legal.py).

3 trụ dữ liệu (đều đã có trong macro_plus.json — không crawl mới):
1. Lãi suất tái cấp vốn SBV (seed, cập nhật tay theo SBV)
2. Tăng trưởng tín dụng YTD (seed, SBV)
3. Áp lực tỷ giá: USD/VND bán ra (VCB, live) so với bình quân năm gần nhất
   của tỷ giá chính thức (World Bank fx_official)

Mỗi trụ bỏ phiếu +1 (nới lỏng) / 0 (trung tính) / −1 (thắt chặt) theo ngưỡng
CÔNG KHAI bên dưới. Tổng ≥2 → NỚI LỎNG · ≤−2 → THẮT CHẶT · còn lại TRUNG TÍNH.
Độ tin cậy = tỷ lệ trụ có dữ liệu × mức đồng thuận.
"""
import json
import os

DISCLAIMER = ("Trạng thái chỉ mô tả MÔI TRƯỜNG tiền tệ theo ngưỡng thống kê "
              "công khai — KHÔNG phải nhận định thị trường hay khuyến nghị "
              "phân bổ tài sản.")

# Ngưỡng công khai (đồng bộ với /methodology#regime)
TH_POLICY_EASE, TH_POLICY_TIGHT = 4.5, 6.0      # % lãi suất tái cấp vốn
TH_CREDIT_EASE, TH_CREDIT_TIGHT = 7.0, 4.0      # % tín dụng YTD (giữa năm)
TH_FX_EASE, TH_FX_TIGHT = 2.0, 3.0              # % thay đổi tỷ giá vs BQ năm trước


def _vote(value, ease_th, tight_th, higher_is_tight: bool):
    """+1 nới / 0 trung / −1 thắt theo 2 ngưỡng, chiều tùy chỉ báo."""
    if value is None:
        return None
    if higher_is_tight:
        if value <= ease_th:
            return 1
        if value >= tight_th:
            return -1
        return 0
    # giá trị cao = nới (vd tín dụng chạy nhanh)
    if value >= ease_th:
        return 1
    if value <= tight_th:
        return -1
    return 0


def detect(data_dir: str) -> dict:
    path = os.path.join(data_dir, "macro_plus.json")
    if not os.path.exists(path):
        return {"available": False,
                "reason": "chưa có macro_plus.json — chạy run_pipeline.py"}
    with open(path, encoding="utf-8") as f:
        mp = json.load(f)

    seed = (mp.get("seed") or {}).get("data") or {}
    comps = []

    # ---- 1. lãi suất chính sách
    pr = (seed.get("policy_rate") or {})
    v = pr.get("value")
    vote = _vote(v, TH_POLICY_EASE, TH_POLICY_TIGHT, higher_is_tight=True)
    comps.append({
        "id": "policy_rate", "label": "Lãi suất tái cấp vốn",
        "value": v, "unit": "%", "vote": vote,
        "threshold": f"≤{TH_POLICY_EASE}% nới · ≥{TH_POLICY_TIGHT}% thắt",
        "source": pr.get("source") or "SBV", "as_of": pr.get("as_of"),
    })

    # ---- 2. tăng trưởng tín dụng YTD
    cg = (seed.get("credit_growth_ytd") or {})
    v = cg.get("value")
    vote = _vote(v, TH_CREDIT_EASE, TH_CREDIT_TIGHT, higher_is_tight=False)
    comps.append({
        "id": "credit_growth", "label": f"Tín dụng YTD ({cg.get('period', '?')})",
        "value": v, "unit": "%", "vote": vote,
        "threshold": f"≥{TH_CREDIT_EASE}% nới · ≤{TH_CREDIT_TIGHT}% thắt",
        "source": cg.get("source") or "SBV", "as_of": cg.get("as_of"),
    })

    # ---- 3. áp lực tỷ giá: VCB bán ra vs bình quân năm gần nhất (fx_official)
    fx_now = (mp.get("fx") or {}).get("usd_sell")
    series = ((mp.get("indicators") or {}).get("fx_official") or {}).get("series") or []
    fx_base = series[-1]["value"] if series else None
    chg = None
    if fx_now and fx_base:
        chg = round((fx_now - fx_base) / fx_base * 100, 2)
    vote = _vote(chg, TH_FX_EASE, TH_FX_TIGHT, higher_is_tight=True)
    comps.append({
        "id": "fx_pressure", "label": "Biến động tỷ giá vs BQ năm gần nhất",
        "value": chg, "unit": "%", "vote": vote,
        "threshold": f"<{TH_FX_EASE}% ổn định · >{TH_FX_TIGHT}% áp lực",
        "source": "VCB (live) / World Bank fx_official",
        "as_of": (mp.get("fx") or {}).get("as_of"),
    })

    votes = [c["vote"] for c in comps if c["vote"] is not None]
    score = sum(votes)
    n_ok = len(votes)
    state = ("NỚI LỎNG" if score >= 2 else
             "THẮT CHẶT" if score <= -2 else "TRUNG TÍNH")
    # đồng thuận: cả 3 cùng chiều = 100%, lệch dần giảm
    agree = (abs(score) / n_ok) if n_ok else 0
    confidence = int(round((n_ok / 3) * (0.5 + 0.5 * agree) * 100))

    return {
        "available": True,
        "state": state, "score": score,
        "confidence_pct": confidence,
        "components": comps,
        "method": "3 trụ ±1, ngưỡng công khai — xem /methodology.html#regime",
        "disclaimer": DISCLAIMER,
        "updated_at": mp.get("updated_at"),
        "citation": "M-REG",
    }
