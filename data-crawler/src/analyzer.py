"""P4 — Phân tích doanh nghiệp như một chuyên gia đầu tư.

Kết hợp:
- Số liệu cơ bản định lượng (fundamentals.py): doanh thu/LNST + YoY, biên lãi,
  ROE/ROA, định giá P/E P/B EV/EBITDA, đòn bẩy, F-Score, điểm sức khỏe 0-100.
- So sánh ngang ngành (peers.py): trung vị P/E, P/B, ROE, biên ròng, Nợ/VCSH.
- Tin tức có TRỌNG SỐ (giảm nhiễu): tin lớn (bắt/trúng thầu/tỷ USD) nặng hơn
  tin nhỏ (bổ nhiệm/lịch họp).
- AI tổng hợp thành nhận định đầu tư. Chỉ dùng AI thật; nếu AI lỗi thì giữ
  nguyên số liệu định lượng và báo rõ "AI lỗi" — KHÔNG bịa nhận định.

Backend AI: `local_api` (MẶC ĐỊNH — server local tự phát triển, xem local_api.py),
`gemini` (CDP trực tiếp, giữ lại để dự phòng), `claude` (Anthropic API).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from pathlib import Path

from . import config, fundamentals, local_api, macro, peers, progress, storage

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
# B5 #6: 18 → 30 tin/sự kiện mỗi mã (FPT có 105 mục, đo thật). Trần độ dài prompt
# vẫn được `_fit` bảo vệ ở lượt `risk` — lượt duy nhất nhận danh sách tin.
MAX_REASONS = 30

# Đa lượt (multi-pass): mặc định BẬT. Đặt AI_MULTIPASS=0 để quay lại 1 lượt.
def _multipass_on() -> bool:
    return (os.environ.get("AI_MULTIPASS") or "1").strip().lower() not in ("0", "false", "off", "no")


BACKENDS = ("local_api", "gemini", "claude")


def resolve_backend() -> str:
    """Backend AI hiệu lực. MẶC ĐỊNH `local_api` — mọi luồng phân tích đi qua
    server AI local tự phát triển thay vì tự lái Chrome/CDP.

    AI_BACKEND=mock (hoặc giá trị lạ) → coi như không khai báo: dùng local_api,
    chỉ rơi về claude khi có ANTHROPIC_API_KEY mà server local không có key."""
    b = (os.environ.get("AI_BACKEND") or "").strip().lower()
    if b in BACKENDS:
        return b
    if local_api.api_key():
        return "local_api"
    return "claude" if os.environ.get("ANTHROPIC_API_KEY") else "local_api"


# Schema đầu ra giàu hơn — phục vụ ra quyết định đầu tư.
SCHEMA_HINT = {
    "ticker": "str",
    "fundamental_summary": "tóm tắt sức khỏe tài chính 2-3 câu (doanh thu, lợi nhuận, biên, đòn bẩy)",
    "valuation_comment": ("vị trí định giá theo PERCENTILE lịch sử của chính mã + so trung vị "
                          "ngành (vùng thấp/giữa/cao); KHÔNG kết luận rẻ/đắt tuyệt đối"),
    "growth_comment": "đánh giá tăng trưởng doanh thu & lợi nhuận YoY",
    "peer_comment": "so sánh với trung bình ngành",
    "key_drivers": ["động lực chính (dữ kiện)"],
    "causes": [{"factor": "str", "impact": "positive|negative|neutral",
                "weight": "1-5 (mức độ tác động)", "confidence": "0.0-1.0"}],
    "risk_level": "low|medium|high",
    "investment_rating": "tích cực|khả quan|trung lập|thận trọng|tiêu cực",
    "verdict": ("2-3 câu kết luận MÔ TẢ tình trạng & rủi ro doanh nghiệp dựa trên dữ kiện — "
                "KHÔNG khuyến nghị hành động"),
}

# Luật pháp lý chèn vào MỌI prompt (Điều 71) — đưa ranh giới vào GỐC prompt thay vì lọc sau.
LEGAL_RULE = (
    "\n\nLUẬT PHÁP LÝ (BẮT BUỘC — Điều 71 Luật Chứng khoán 2019, vi phạm = câu trả lời bị từ "
    "chối): Trong các phần văn xuôi (verdict, causes...), CHỈ mô tả dữ kiện, số liệu và rủi ro. "
    "TUYỆT ĐỐI KHÔNG khuyến nghị, KHÔNG bảo nhà đầu tư phải làm gì. Cấm: 'nên mua/bán/giữ', 'khuyến nghị', "
    "'vào lệnh', 'giải ngân', 'chờ… trước khi', 'mở/xem xét vị thế', giá mục tiêu, và KHÔNG kết luận 'rẻ/đắt' tuyệt đối "
    "(dùng ngôn ngữ percentile: vùng thấp/giữa/cao so với lịch sử). Việc chọn `investment_rating` chỉ dùng để phân loại trạng thái."
)

# Từ khóa → trọng số tác động tin tức (giảm nhiễu).
_WEIGHT_KW = [
    (5, ("bị bắt", "khởi tố", "vỡ nợ", "hủy niêm yết", "phá sản", "thâu tóm",
         "sáp nhập", "tỷ usd", "kỷ lục", "đột biến", "trúng thầu", "thao túng")),
    (4, ("m&a", "phát hành riêng lẻ", "tăng vốn", "thoái vốn", "chia tách",
         "lợi nhuận", "thua lỗ", "doanh thu", "trái phiếu", "mua lại")),
    (3, ("cổ tức", "hợp đồng", "dự án", "mở rộng", "nhà máy", "kết quả kinh doanh",
         "ký kết", "đầu tư")),
    (1, ("bổ nhiệm", "miễn nhiệm", "thay đổi nhân sự", "lịch họp", "nghị quyết",
         "ngày đăng ký", "chốt quyền", "thông báo", "điều lệ")),
]


def _weight(text: str) -> int:
    t = (text or "").lower()
    for w, kws in _WEIGHT_KW:
        if any(k in t for k in kws):
            return w
    return 2


# ---------------------------------------------------------------- dữ liệu

def _iso_day(v) -> str:
    """Về 'YYYY-MM-DD' từ ISO, RFC-2822 (RSS) hoặc chuỗi lạ (→ rỗng)."""
    s = str(v or "").strip()
    if not s:
        return ""
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).date().isoformat()
    except Exception:                                        # noqa: BLE001
        return ""


def _load_reasons(cdir: Path) -> list[dict]:
    p = cdir / "insights" / "reasons.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            r["weight"] = _weight(r.get("text", ""))
            # Chuẩn hoá ngày TRƯỚC khi sắp xếp: reasons.jsonl cũ còn giữ ngày RSS
            # dạng RFC-2822, sắp theo chuỗi đó là sắp theo tên thứ trong tuần.
            r["date"] = _iso_day(r.get("date"))
            out.append(r)
        except Exception:
            pass
    # ưu tiên tin tác động lớn, rồi mới tới gần đây
    out.sort(key=lambda r: (r.get("weight", 2), r.get("date", "")), reverse=True)
    return out[:MAX_REASONS]


def _fmt(v, pct=False, money=False):
    if v is None:
        return "n/a"
    if money:
        return f"{v/1e9:,.0f} tỷ" if abs(v) >= 1e9 else f"{v:,.0f}"
    if pct:
        return f"{v:+.1f}%"
    return f"{v:,.2f}" if abs(v) < 1000 else f"{v:,.0f}"


# C1: câu cảnh báo mùa vụ — đo thật trên 1.525 mã (2026-07-27). QoQ Q1-so-Q4 âm ở
# 67,4% thị trường (trung vị −10,6%) chỉ vì Q4 là quý cao điểm, trong khi YoY cùng
# quý chỉ âm ở 33,1% mã (trung vị +12,0%). Không có câu này, AI đọc QoQ âm thành
# "suy giảm" — sai với 2/3 thị trường.
_SEASONAL_NOTE = ("- LƯU Ý MÙA VỤ: QoQ (quý này so quý liền trước) KHÔNG phải thước đo tăng trưởng — "
                  "Q4 là quý cao điểm nên Q1 gần như luôn thấp hơn. Đo thật toàn thị trường: trung vị "
                  "QoQ −10,6% nhưng YoY cùng quý +12,0%; 67,4% mã âm theo QoQ trong khi chỉ 33,1% âm "
                  "theo YoY. Hãy kết luận tăng/giảm theo YoY cùng quý, coi QoQ là dữ kiện mùa vụ.")

# Nhãn dòng doanh thu theo mô hình ngành — ngân hàng KHÔNG có `net_sales`.
_REV_LABEL = {
    "total_operating_income": "Tổng thu nhập hoạt động",
    "net_sales": "Doanh thu thuần",
}


def _growth_str(d: dict) -> str:
    """Cụm tăng trưởng của 1 khoản mục: YoY cùng quý TRƯỚC, QoQ sau (C1).

    `yoy_q_source == "derived"` phải ghi rõ là số SUY RA — AI không được coi là
    số công bố."""
    parts = []
    if d.get("yoy_q") is not None:
        src = " (suy ra từ báo cáo tài chính năm)" if d.get("yoy_q_source") == "derived" else ""
        parts.append(f"YoY cùng quý: {_fmt(d['yoy_q'], pct=True)}{src}")
    if d.get("qoq") is not None:
        parts.append(f"QoQ (mùa vụ): {_fmt(d['qoq'], pct=True)}")
    if d.get("yoy_y") is not None:
        parts.append(f"YoY năm: {_fmt(d['yoy_y'], pct=True)}")
    return " | ".join(parts) if parts else "không đủ dữ liệu tăng trưởng"


def _ttm_lines(m: dict) -> list[str]:
    """C3 — TTM (4 quý liên tiếp gần nhất) + EPS TTM + P/E TTM.

    `ttm_yoy` cần 8 quý liên tiếp nên gần như luôn None → thiếu thì BỎ dòng,
    không in None."""
    rv, np_ = m.get("revenue") or {}, m.get("net_profit") or {}
    L = []
    ttm_parts = []
    if rv.get("ttm") is not None:
        s = f"doanh thu {_fmt(rv['ttm'], money=True)}"
        if rv.get("ttm_yoy") is not None:
            s += f" (so TTM cùng kỳ {_fmt(rv['ttm_yoy'], pct=True)})"
        ttm_parts.append(s)
    if np_.get("ttm") is not None:
        s = f"LNST {_fmt(np_['ttm'], money=True)}"
        if np_.get("ttm_yoy") is not None:
            s += f" (so TTM cùng kỳ {_fmt(np_['ttm_yoy'], pct=True)})"
        ttm_parts.append(s)
    if ttm_parts:
        L.append("- TTM (tổng 4 quý gần nhất): " + " | ".join(ttm_parts))
    eps_parts = []
    if m.get("eps_ttm") is not None:
        eps_parts.append(f"EPS TTM {_fmt(m['eps_ttm'])} đ/CP")
    if m.get("pe_ttm") is not None:
        eps_parts.append(f"P/E TTM {_fmt(m['pe_ttm'])}")
    if eps_parts:
        L.append("- " + " | ".join(eps_parts) + " (P/E ở dòng Định giá tính theo kỳ NĂM — lệch là bình thường)")
    return L


def _capital_cycle_block(m: dict) -> str:
    """P1 · Vòng quay vốn & an toàn nợ — 12 chỉ tiêu lấy từ bảng `ratio`.

    Bỏ QUA hoàn toàn với ngân hàng: "vòng quay hàng tồn kho" hay "chu kỳ tiền
    mặt" không có nghĩa với mô hình huy động–cho vay, đưa vào chỉ khiến AI so
    sánh sai. Chỉ tiêu ngân hàng đã có ở khối `sector_model` (NIM/CIR/LDR)."""
    if m.get("is_bank"):
        return ""
    e = m.get("efficiency") or {}
    if not any(v is not None for v in e.values()):
        return ""
    L = []
    if e.get("cash_cycle") is not None:
        L.append(f"- Chu kỳ tiền mặt: {_fmt(e['cash_cycle'])} ngày "
                 f"(tồn kho {_fmt(e['days_inventory'])} + thu tiền {_fmt(e['days_receivable'])} "
                 f"− trả tiền {_fmt(e['days_payable'])}) — số ngày vốn bị chôn trong 1 vòng bán hàng")
    turns = [(lb, e.get(k)) for lb, k in (("tổng tài sản", "turnover_asset"),
                                          ("tồn kho", "turnover_inventory"),
                                          ("phải thu", "turnover_receivable"))]
    turns = [f"{lb} {_fmt(v)}" for lb, v in turns if v is not None]
    if turns:
        L.append("- Vòng quay: " + " | ".join(turns) + " (lần)")
    safety = [(lb, e.get(k)) for lb, k in (("Trả lãi vay", "interest_coverage"),
                                           ("Trả nợ từ dòng tiền HĐKD", "debt_coverage"))]
    safety = [f"{lb} {_fmt(v)} lần" for lb, v in safety if v is not None]
    if safety:
        L.append("- Đệm an toàn nợ: " + " | ".join(safety))
    liq = [(lb, e.get(k)) for lb, k in (("nhanh", "quick_ratio"), ("bằng tiền mặt", "cash_ratio"))]
    liq = [f"{lb} {_fmt(v)}" for lb, v in liq if v is not None]
    if liq:
        L.append("- Thanh toán: " + " | ".join(liq))
    cash_ret = [(lb, e.get(k)) for lb, k in (("VCSH", "cash_roe"), ("tổng tài sản", "cash_roa"))]
    cash_ret = [f"{lb} {_fmt(v)}%" for lb, v in cash_ret if v is not None]
    if cash_ret:
        L.append("- Dòng tiền HĐKD trên: " + " | ".join(cash_ret))
    return "\n".join(L)


def _metrics_block(m: dict) -> str:
    rv, np_ = m["revenue"], m["net_profit"]
    mg, pr, val, sv = m["margins"], m["profitability"], m["valuation"], m["solvency"]
    rev_lbl = _REV_LABEL.get(rv.get("item_id"), "Doanh thu")
    L = [
        f"- {rev_lbl} (kỳ {rv['period']}): {_fmt(rv['latest'], money=True)} | {_growth_str(rv)}",
        f"- LNST (kỳ {np_['period']}): {_fmt(np_['latest'], money=True)} | {_growth_str(np_)}",
    ]
    L += _ttm_lines(m)
    L += [
        f"- Biên lãi: gộp {_fmt(mg['gross'])}% | ròng {_fmt(mg['net'])}% | EBIT {_fmt(mg['ebit'])}%",
        f"- Hiệu quả: ROE {_fmt(pr['roe'])}% | ROA {_fmt(pr['roa'])}% | "
        f"ROCE {_fmt(pr.get('roce'))}% (chỉ tiêu NĂM; ROCE tính trên vốn dài hạn bình quân)",
        f"- Định giá: P/E {_fmt(val['pe'])} | P/B {_fmt(val['pb'])} | EV/EBITDA {_fmt(val['ev_ebitda'])} "
        f"| Tỷ suất cổ tức {_fmt(val['dividend_yield'])}%",
        f"- Đòn bẩy: Nợ/VCSH {_fmt(sv['debt_to_equity'])} | Thanh toán hiện hành {_fmt(sv['current_ratio'])}",
        f"- ĐIỂM SỨC KHỎE: {m['health_score']}/100 | Piotroski F-Score: {m['fscore']}/{m['fscore_max']} "
        f"| Định giá sơ bộ: {m['valuation_verdict']}",
    ]
    if (sv.get("npl") or 0) > 0 or (sv.get("car") or 0) > 0:
        L.append(f"- Ngân hàng: NPL {_fmt(sv['npl'])}% | CAR {_fmt(sv['car'])}%")
    if rv.get("qoq") is not None or np_.get("qoq") is not None:
        L.append(_SEASONAL_NOTE)
    return "\n".join(L)



def _peer_rank_block(p: dict) -> str:
    """C7 — xếp hạng percentile trong ngành, không chỉ trung vị.

    Xếp theo GIÁ TRỊ GIẢM DẦN cho mọi chỉ tiêu (mô tả vị trí, không phán tốt/xấu):
    #1 = giá trị cao nhất. Percentile = tỉ lệ công ty có giá trị thấp hơn.
    Thiếu mẫu (<5 cty) hoặc thiếu giá trị của chính mã → bỏ chỉ tiêu."""
    pv = p.get("peer_values") or {}
    me = p.get("self") or {}
    label = {"pe": "P/E", "pb": "P/B", "roe": "ROE", "net_margin": "Biên ròng",
             "debt_to_equity": "Nợ/VCSH"}
    parts = []
    for k in ("roe", "net_margin", "pe", "pb", "debt_to_equity"):
        mine = me.get(k)
        rows = pv.get(k) or []
        if not isinstance(mine, (int, float)):
            continue
        vals = [r["value"] for r in rows
                if isinstance(r, dict) and isinstance(r.get("value"), (int, float))
                and r.get("sym") != p.get("symbol")]
        vals.append(float(mine))
        n = len(vals)
        if n < 5:
            continue
        rank = sum(1 for v in vals if v > mine) + 1
        pct = sum(1 for v in vals if v < mine) / (n - 1) * 100
        parts.append(f"{label[k]} #{rank}/{n} (P{pct:.0f})")
    if not parts:
        return ""
    return (f"- Xếp hạng trong ngành {p.get('sector')} (xếp theo giá trị GIẢM DẦN, #1 = cao nhất; "
            f"P = percentile, chỉ mô tả vị trí): " + " | ".join(parts))


def _peer_block(p: dict) -> str:
    if not p.get("sector"):
        return "(không có dữ liệu ngành)"
    b, pos = p.get("benchmark", {}), p.get("position", {})
    parts = [f"Ngành: {p['sector']} ({p['n_peers']}/{p['n_sector']} cty có dữ liệu)"]
    label = {"pe": "P/E", "pb": "P/B", "roe": "ROE", "net_margin": "Biên ròng",
             "debt_to_equity": "Nợ/VCSH"}
    for k in ("pe", "pb", "roe", "net_margin", "debt_to_equity"):
        if k in b:
            parts.append(f"{label[k]} ngành≈{b[k]} (cty: {pos.get(k,'?')})")
    out = " | ".join(parts)
    rank = _peer_rank_block(p)
    return out + ("\n" + rank if rank else "")



def _valband_block(vb: dict | None) -> str:
    """Dải định giá theo lịch sử chính mã — ngôn ngữ percentile (không rẻ/đắt)."""
    if not vb:
        return "(không có dữ liệu dải định giá lịch sử)"
    label = {"pe": "P/E", "pb": "P/B"}
    lines = []
    for k in ("pe", "pb"):
        d = vb.get(k)
        if not d or not d.get("available"):
            continue
        peer = f", trung vị ngành {d['peer_median']}" if d.get("peer_median") is not None else ""
        lines.append(
            f"- {label[k]}: hiện {d['current']} → {d['label']} (percentile {d['percentile']:.0f}%, "
            f"dải {d['n']} kỳ: min {d['min']} / P20 {d['p20']} / trung vị {d['p50']} / "
            f"P80 {d['p80']} / max {d['max']}{peer})")
    if not lines:
        return "(không đủ lịch sử định giá để tính percentile)"
    return "\n".join(lines) + f"\n{vb.get('note', '')}"


def _reasons_block(reasons: list[dict]) -> str:
    if not reasons:
        return "(không có tin tức)"
    label = {"news": "công bố", "event": "sự kiện", "press": "báo chí",
             "article": "bài báo"}
    # B5 #6: nâng 18 → 30 mục. Để 30 tiêu đề vừa trần 10.000 ký tự của lượt `risk`,
    # cắt tiêu đề ở 110 ký tự (đo thật: tiêu đề dài nhất 123 ký tự, phần đuôi bị cắt
    # là hậu tố lặp lại kiểu "... - Sở Giao dịch Chứng khoán TP.HCM").
    # Loại `article` mang thêm tóm tắt nội dung nên nới lên 260 ký tự — đó là dòng
    # DUY NHẤT trong khối này có nội dung thật thay vì mỗi tiêu đề.
    def one(r: dict) -> str:
        kind = r.get("type")
        text = re.sub(r"\s+", " ", str(r.get("text", ""))).strip()
        text = text[:260] if kind == "article" else text[:110]
        # Tên toà soạn là dữ kiện đánh giá độ tin cậy: "theo Vietstock" khác hẳn
        # "theo một trang tổng hợp". Trước đây bị bỏ khỏi prompt hoàn toàn.
        src = str(r.get("source") or "").strip()
        via = f" [nguồn: {src[:34]}]" if src and kind in ("press", "article") else ""
        return (f"- [trọng số {r.get('weight', 2)}/5] "
                f"({label.get(kind, kind)}, {r.get('date', '')[:10]}) {text}{via}")

    return "\n".join(one(r) for r in reasons)


# ---------------------------------------------------------------- C2: chuỗi nhiều kỳ
# `fundamentals` đã tính trend_q/trend_periods nhưng khối chỉ số chỉ in 1 lát cắt.
# Ở đây dựng BẢNG: 4 năm gần nhất + 3 quý gần nhất, để AI đọc XU HƯỚNG (biên bào
# mòn dần, biên gộp thấp nhất chuỗi trong khi biên ròng cao nhất...) thay vì 1 kỳ.
# KHÔNG in ROE ở dòng quý: ROE là chỉ tiêu NĂM, ROE quý chưa niên hóa nên đặt cạnh
# nhau sẽ bị đọc sai thành "ROE sụt".

def _period_map(recs: list[dict], item_id: str, ptype: str) -> dict[str, float]:
    return {str(r["period"]): float(r["value"]) for r in recs
            if r.get("item_id") == item_id and r.get("period_type", "Y") == ptype
            and isinstance(r.get("value"), (int, float)) and r.get("period")}


def _trend_block(cdir: Path, m: dict) -> str:
    """Bảng 4 năm + 3 quý gần nhất (tỷ đồng). Thiếu ô nào để trống, không bịa."""
    inc = _load_json(cdir, "financials/income_statement.json").get("records", [])
    bal = _load_json(cdir, "financials/balance_sheet.json").get("records", [])
    if not inc:
        return ""
    rev_item = (m.get("revenue") or {}).get("item_id") or "net_sales"
    is_bank = rev_item == "total_operating_income"

    series = {}
    for ptype in ("Y", "Q"):
        series[ptype] = {
            "rev": _period_map(inc, rev_item, ptype),
            "np": _period_map(inc, "net_profit_loss_after_tax", ptype),
            "gross": _period_map(inc, "gross_profit", ptype),
            "eq": _period_map(bal, "owners_equity", ptype),
            "liab": _period_map(bal, "liabilities" if not is_bank else "total_liabilities", ptype),
        }
    years = sorted(series["Y"]["rev"])[-4:]
    quarters = sorted(series["Q"]["rev"])[-3:]
    if not years and not quarters:
        return ""

    show_gross = not is_bank and (series["Y"]["gross"] or series["Q"]["gross"])
    rev_label = "TOI" if is_bank else "DT"
    head = f"{'Kỳ':<9}{rev_label:>10}{'LNST':>10}"
    if show_gross:
        head += f"{'BiênGộp':>9}"
    head += f"{'BiênRòng':>9}{'Nợ/VCSH':>9}"
    lines = [head]

    def row(ptype: str, p: str) -> str:
        s = series[ptype]
        rev, npf = s["rev"].get(p), s["np"].get(p)
        gr, eq, li = s["gross"].get(p), s["eq"].get(p), s["liab"].get(p)
        cells = f"{p:<9}{(rev/1e9 if rev else 0):>10,.0f}" if rev is not None else f"{p:<9}{'':>10}"
        cells += f"{(npf/1e9):>10,.0f}" if npf is not None else f"{'':>10}"
        if show_gross:
            g = f"{gr/rev*100:.1f}%" if (gr is not None and rev) else ""
            cells += f"{g:>9}"
        n = f"{npf/rev*100:.1f}%" if (npf is not None and rev) else ""
        cells += f"{n:>9}"
        de = f"{li/eq:.2f}" if (li is not None and eq) else ""
        cells += f"{de:>9}"
        return cells

    for p in years:
        lines.append(row("Y", p))
    for p in quarters:
        lines.append(row("Q", p))
    note = ("(đơn vị tỷ đồng; dòng có 'Q' là quý — KHÔNG so trực tiếp quý với năm. "
            "ROE cố ý không đưa vào dòng quý vì ROE là chỉ tiêu năm, quý chưa niên hóa.)")
    return "\n".join(lines) + "\n" + note



# ---------------------------------------------------------------- block dữ liệu mới

def _load_json(cdir: Path, rel: str) -> dict:
    p = cdir / rel
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _macro_block(macro_ctx: dict) -> str:
    if not macro_ctx:
        return "(không có dữ liệu vĩ mô — đừng suy diễn số liệu)"
    L = []
    for code, st in (macro_ctx.get("indexes") or {}).items():
        if st.get("ok") and st.get("latest") is not None:
            L.append(f"- {code}: {_fmt(st['latest'])} | 1M {_fmt(st.get('pct_1m'), pct=True)} "
                     f"| YTD {_fmt(st.get('pct_ytd'), pct=True)}")
    fx = macro_ctx.get("fx") or {}
    if fx.get("usd_sell"):
        L.append(f"- USD/VND: {_fmt(fx.get('usd_sell'))} (bán)")
    ind = macro_ctx.get("indicators") or {}
    seed = [(k, ind.get(k)) for k in ("gdp_growth_yoy", "cpi_yoy", "policy_rate", "credit_growth_ytd")]
    lbl = {"gdp_growth_yoy": "GDP", "cpi_yoy": "CPI", "policy_rate": "Lãi suất ĐH",
           "credit_growth_ytd": "Tăng trưởng tín dụng"}
    seed_parts = [f"{lbl[k]} {v.get('value')}{v.get('unit','')} ({v.get('period','')})"
                  for k, v in seed if isinstance(v, dict) and v.get("value") is not None]
    if seed_parts:
        L.append(f"- Vĩ mô (cập nhật tay, as_of {ind.get('as_of','?')}): " + " | ".join(seed_parts))
    return "\n".join(L) if L else "(không có dữ liệu vĩ mô)"


def _price_stats(cdir: Path) -> dict:
    """Tính momentum/biến động từ market/price.json (chuỗi close tăng dần)."""
    items = _load_json(cdir, "market/price.json").get("items", [])
    closes = [(str(r.get("time")), r.get("close")) for r in items
              if isinstance(r.get("close"), (int, float))]
    closes.sort(key=lambda x: x[0])
    if len(closes) < 2:
        return {}
    vals = [c for _, c in closes]
    last = vals[-1]

    def pct_ago(n):
        return (last - vals[-1 - n]) / vals[-1 - n] * 100 if len(vals) > n and vals[-1 - n] else None

    window = vals[-252:] if len(vals) >= 252 else vals
    hi, lo = max(window), min(window)
    # biến động: độ lệch chuẩn lợi suất ngày (~60 phiên), annualize thô
    rets = [(vals[i] - vals[i - 1]) / vals[i - 1] for i in range(max(1, len(vals) - 60), len(vals))
            if vals[i - 1]]
    vol = None
    if len(rets) >= 5:
        mean = sum(rets) / len(rets)
        var = sum((x - mean) ** 2 for x in rets) / len(rets)
        vol = (var ** 0.5) * (252 ** 0.5) * 100
    return {
        "last": last, "date": closes[-1][0],
        "pct_1m": pct_ago(21), "pct_3m": pct_ago(63),
        "pct_6m": pct_ago(126), "pct_1y": pct_ago(252),
        "high_52w": hi, "low_52w": lo,
        "from_high": (last - hi) / hi * 100 if hi else None,
        "volatility_ann": vol,
    }


def _price_block(cdir: Path, symbol: str | None = None) -> str:
    s = _price_stats(cdir)
    if not s:
        return "(không có dữ liệu giá)"
    out = (f"- Giá mới nhất ({s['date']}): {_fmt(s['last'])}\n"
           f"- Momentum: 1M {_fmt(s['pct_1m'], pct=True)} | 3M {_fmt(s['pct_3m'], pct=True)} "
           f"| 6M {_fmt(s['pct_6m'], pct=True)} | 1Y {_fmt(s['pct_1y'], pct=True)}\n"
           f"- Đỉnh/đáy 52T: {_fmt(s['high_52w'])} / {_fmt(s['low_52w'])} "
           f"(cách đỉnh {_fmt(s['from_high'], pct=True)})\n"
           f"- Biến động năm hóa (~60 phiên): {_fmt(s['volatility_ann'])}%")
    rel = _market_rel_block(cdir)
    return out + ("\n" + rel if rel else "")


# ---------------------------------------------------------------- C4: so với VNINDEX
# `index_ohlc` (VNINDEX 3.014 phiên từ 2014) trước đây KHÔNG được dùng lần nào.
# Ba dữ kiện thêm vào, đều là MÔ TẢ (không khuyến nghị):
#   - RS: chênh lệch điểm % giữa mã và VNINDEX cùng cửa sổ. "+8% khi VNINDEX +15%"
#     là THUA thị trường 7 điểm — prompt cũ chỉ thấy "+8%" nên rất dễ khen sai.
#   - Beta ~250 phiên: cov(r_mã, r_index)/var(r_index) trên ngày GIAO NHAU.
#   - Sụt sâu nhất (max drawdown) 1 năm của mã, kèm của VNINDEX để có mốc so.
# Đọc DB chỉ-đọc (mode=ro): tuyệt đối không ghi vào market.db từ luồng phân tích.

_INDEX_CODE = "VNINDEX"


def _index_closes() -> dict[str, float]:
    """{ngày: close} của VNINDEX, đọc chỉ-đọc. Lỗi/không có DB ⇒ {} (bỏ khối)."""
    import sqlite3
    p = config.DB_PATH
    if not p.exists():
        return {}
    try:
        conn = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    except Exception:
        return {}
    try:
        rows = conn.execute(
            "SELECT time, close FROM index_ohlc WHERE code=? AND close IS NOT NULL",
            (_INDEX_CODE,)).fetchall()
    except Exception:
        return {}
    finally:
        conn.close()
    return {str(t)[:10]: float(c) for t, c in rows if isinstance(c, (int, float))}


def _max_drawdown(vals: list[float]) -> float | None:
    """Sụt sâu nhất (%) từ đỉnh liền trước — số âm. Trả None nếu chuỗi quá ngắn."""
    if len(vals) < 2:
        return None
    peak, worst = vals[0], 0.0
    for v in vals:
        peak = max(peak, v)
        if peak:
            worst = min(worst, (v - peak) / peak * 100)
    return worst


def _market_rel_block(cdir: Path) -> str:
    items = _load_json(cdir, "market/price.json").get("items", [])
    stock = {str(r.get("time"))[:10]: float(r["close"]) for r in items
             if isinstance(r.get("close"), (int, float))}
    idx = _index_closes()
    if not stock or not idx:
        return ""
    days = sorted(set(stock) & set(idx))
    if len(days) < 30:
        return ""
    sv = [stock[d] for d in days]
    iv = [idx[d] for d in days]

    def rs(n: int) -> float | None:
        """Chênh lệch điểm % mã − VNINDEX qua n phiên giao nhau."""
        if len(days) <= n or not sv[-1 - n] or not iv[-1 - n]:
            return None
        return ((sv[-1] - sv[-1 - n]) / sv[-1 - n] - (iv[-1] - iv[-1 - n]) / iv[-1 - n]) * 100

    parts = []
    for lbl, n in (("1M", 21), ("3M", 63), ("1Y", 252)):
        v = rs(n)
        if v is not None:
            parts.append(f"{lbl} {v:+.1f} điểm")
    L = []
    if parts:
        L.append(f"- So VNINDEX (sức mạnh tương đối, {len(days)} phiên khớp ngày): "
                 + " | ".join(parts))

    rs_, ri = [], []
    for i in range(1, len(days)):
        if sv[i - 1] and iv[i - 1]:
            rs_.append((sv[i] - sv[i - 1]) / sv[i - 1])
            ri.append((iv[i] - iv[i - 1]) / iv[i - 1])
    beta = None
    if len(ri) >= 60:
        rs_, ri = rs_[-250:], ri[-250:]
        n = len(ri)
        ms, mi = sum(rs_) / n, sum(ri) / n
        var = sum((x - mi) ** 2 for x in ri)
        if var:
            beta = sum((rs_[i] - ms) * (ri[i] - mi) for i in range(n)) / var

    dd_s = _max_drawdown(sv[-252:])
    dd_i = _max_drawdown(iv[-252:])
    tail = []
    if beta is not None:
        tail.append(f"Beta ~250 phiên: {beta:.2f}")
    if dd_s is not None:
        t = f"Sụt sâu nhất 1 năm: {dd_s:.1f}%"
        if dd_i is not None:
            t += f" (VNINDEX {dd_i:.1f}%)"
        tail.append(t)
    if tail:
        L.append("- " + " | ".join(tail))
    return "\n".join(L)


def _ownership_block(cdir: Path) -> str:
    L = []
    sh = _load_json(cdir, "ownership/shareholders.json").get("items", [])
    if sh:
        top = sorted((r for r in sh if isinstance(r.get("share_own_percent"), (int, float))),
                     key=lambda r: r["share_own_percent"], reverse=True)[:5]
        parts = [f"{(r.get('share_holder') or '?')[:40]} {r['share_own_percent']*100:.1f}%"
                 if r["share_own_percent"] < 1.5 else
                 f"{(r.get('share_holder') or '?')[:40]} {r['share_own_percent']:.1f}%" for r in top]
        if parts:
            L.append("- Cổ đông lớn: " + " | ".join(parts))
    snap = _load_json(cdir, "market/board_snapshot.json").get("snapshot", {})
    fb, fs = snap.get("foreign_buy_volume"), snap.get("foreign_sell_volume")
    if fb is not None or fs is not None:
        net = (fb or 0) - (fs or 0)
        L.append(f"- Khối ngoại (phiên gần nhất): mua {_fmt(fb)} / bán {_fmt(fs)} "
                 f"→ ròng {_fmt(net)} CP")
    ins = _load_json(cdir, "ownership/insider_deals.json").get("items", [])
    if ins:
        L.append(f"- Giao dịch nội bộ: {len(ins)} giao dịch gần đây")
    cap = _latest_charter_capital(cdir)
    if cap:
        L.append(f"- Vốn điều lệ (kỳ {cap['date']}): {_fmt(cap['value'], money=True)}")
    fh = _foreign_streak(cdir)
    if fh:
        L.append(fh)
    return "\n".join(L) if L else "(không có dữ liệu sở hữu)"


# CHƯA TỪNG ĐƯỢC GỬI AI: `market/foreign_history.jsonl` tích luỹ khối ngoại theo
# NGÀY, nhưng prompt chỉ có `board_snapshot` — đúng một phiên. Một phiên bán ròng
# không nói lên gì; sáu phiên liên tiếp thì có. Đây là dữ liệu đã cào sẵn, đọc
# thêm không tốn request nào.
def _foreign_streak(cdir: Path) -> str:
    p = cdir / "market" / "foreign_history.jsonl"
    if not p.exists():
        return ""
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r.get("foreign_net"), (int, float)) and r.get("date"):
            rows.append(r)
    if len(rows) < 2:
        return ""
    rows.sort(key=lambda r: str(r["date"]))
    rows = rows[-10:]
    total = sum(r["foreign_net"] for r in rows)
    # Chuỗi liên tiếp tính NGƯỢC từ phiên gần nhất, cùng dấu.
    sign = 1 if rows[-1]["foreign_net"] > 0 else -1 if rows[-1]["foreign_net"] < 0 else 0
    streak = 0
    if sign:
        for r in reversed(rows):
            if (r["foreign_net"] > 0) == (sign > 0) and r["foreign_net"] != 0:
                streak += 1
            else:
                break
    word = "mua ròng" if sign > 0 else "bán ròng"
    tail = f"; {streak} phiên {word} liên tiếp" if streak >= 2 else ""
    return (f"- Khối ngoại {len(rows)} phiên gần nhất (từ {rows[0]['date']}): "
            f"ròng {_fmt(total)} CP{tail}. Lưu ý: chuỗi này chỉ gồm các phiên hệ "
            f"thống đã ghi nhận, KHÔNG phải mọi phiên giao dịch.")


# CHƯA TỪNG ĐƯỢC GỬI AI: officers/subsidiaries/affiliate. Ba tệp này đã cào từ
# đầu (FPT: 9 lãnh đạo, 14 công ty con, 5 công ty liên kết) nhưng 0 tham chiếu
# trong analyzer.py — AI phân tích doanh nghiệp mà không biết ai điều hành và
# tập đoàn gồm những gì. Tỷ lệ sở hữu của ban lãnh đạo còn là dữ kiện quản trị
# thật: người điều hành có "tiền trong cuộc chơi" hay không.
def _governance_block(cdir: Path) -> str:
    L = []
    off = _load_json(cdir, "ownership/officers.json").get("items", [])
    if off:
        rows = sorted(
            off, key=lambda r: (r.get("officer_own_percent") or 0), reverse=True)[:6]
        parts = []
        for r in rows:
            name = str(r.get("officer_name") or "?")[:28]
            pos = str(r.get("officer_position") or "")[:34]
            own = r.get("officer_own_percent")
            # `officer_own_percent` lưu dạng tỷ lệ (0.0689 = 6,89%), giống
            # `share_own_percent` ở khối cổ đông — nhân 100 chứ không in thẳng.
            share = f" — nắm {own * 100:.2f}%" if isinstance(own, (int, float)) and own else ""
            parts.append(f"{name} ({pos}){share}")
        total = sum(r.get("officer_own_percent") or 0 for r in off)
        L.append("- Ban lãnh đạo: " + " | ".join(parts))
        if total:
            L.append(f"- Tổng sở hữu của ban lãnh đạo: {total * 100:.2f}% vốn")
    def named(name, pct) -> str:
        s = str(name or "?")[:38]
        return f"{s} {pct * 100:.0f}%" if isinstance(pct, (int, float)) and pct else s

    sub = _load_json(cdir, "ownership/subsidiaries.json").get("items", [])
    if sub:
        top = sorted(sub, key=lambda r: (r.get("ownership_percent") or 0),
                     reverse=True)[:8]
        L.append(f"- Công ty con ({len(sub)}): "
                 + " | ".join(named(r.get("organ_name"), r.get("ownership_percent"))
                              for r in top))
    aff = _load_json(cdir, "ownership/affiliate.json").get("items", [])
    if aff:
        L.append(f"- Công ty liên kết ({len(aff)}): "
                 + " | ".join(named(r.get("right_organ_name_vi") or r.get("right_organ_code"),
                                    r.get("owned_percentage")) for r in aff[:6]))
    return "\n".join(L) if L else ""


# ---------------------------------------------------------------- B4: vốn điều lệ
# LỖI ĐÃ SỬA: `capital_history[-1]` từng được coi là "mới nhất" → FPT bị bơm vào
# prompt "vốn điều lệ 20 tỷ" trong khi số thật ~17.413 tỷ (sai 857 lần). Nguyên
# nhân: 21/26 bản ghi có `date="NaT"` nên danh sách KHÔNG sắp theo thời gian, phần
# tử cuối chính là vốn điều lệ thuở mới thành lập (20 tỷ, 1988).
# Nguyên tắc: chỉ nhận bản ghi có ngày ĐỌC ĐƯỢC, lấy ngày lớn nhất. Không còn bản
# ghi hợp lệ ⇒ trả None ⇒ BỎ HẲN dòng khỏi prompt (không in số sai, không bịa).

def _bad_date(v) -> bool:
    """True nếu ngày không dùng được: None / rỗng / 'NaT' / 'nan' / 'None'."""
    s = str(v or "").strip()
    return (not s) or s.lower() in ("nat", "nan", "none", "null", "-")


def _latest_charter_capital(cdir: Path) -> dict | None:
    """Vốn điều lệ của kỳ GẦN NHẤT XÁC ĐỊNH ĐƯỢC, hoặc None nếu không kỳ nào hợp lệ."""
    items = _load_json(cdir, "ownership/capital_history.json").get("items", [])
    ok = [r for r in items
          if not _bad_date(r.get("date"))
          and isinstance(r.get("charter_capital"), (int, float))
          and r["charter_capital"] > 0]
    if not ok:
        return None
    best = max(ok, key=lambda r: str(r["date"]))
    return {"date": str(best["date"])[:10], "value": float(best["charter_capital"])}


# ---------------------------------------------------------------- C5/C6: bảng `events`
# `events` có 41.000+ bản ghi/15 loại, trước đây chỉ lẫn vài mục trong danh sách tin.
# Tách làm 2 khối có mục đích rõ ràng:
#   C5 lịch sử cổ tức tiền mặt (6.414 bản ghi/1.047 mã, cột `value_per_share`)
#   C6 sự kiện PHA LOÃNG & QUẢN TRỊ — phát hành thêm/niêm yết bổ sung/ĐHĐCĐ bất
#      thường/chuyển sàn. Đây là dữ kiện pha loãng EPS, đi vào lượt `risk`, KHÔNG
#      trộn vào 18 tin thường (ở đó chúng bị tin báo chí đè theo trọng số).
# `public_date` trong DB có 2 dạng: '2026-05-22' và '2026-07-14T00:00:00' → cắt [:10].

_DILUTION_EVENTS = ("Phát hành cổ phiếu", "Niêm yết thêm", "Đại hội Cổ đông Bất thường",
                    "Chuyển Sàn", "Tạm dừng Niêm yết", "Mua Bán và Sát Nhập")


def _day(v) -> str:
    return str(v or "")[:10]


def _events_rows(symbol: str, cdir: Path) -> list[dict]:
    """Sự kiện của 1 mã: ưu tiên market.db (đầy đủ nhất, mở CHỈ-ĐỌC), fallback
    disclosures/events.json khi không có DB."""
    rows: list[dict] = []
    try:
        if config.DB_PATH.exists():
            with _ro_conn() as conn:
                for name, title, pd_, vps in conn.execute(
                        "SELECT event_name, title, public_date, value_per_share "
                        "FROM events WHERE symbol = ?", (symbol,)):
                    rows.append({"event_name": name, "title": title,
                                 "public_date": pd_, "value_per_share": vps})
    except Exception:
        rows = []
    if not rows:
        rows = _load_json(cdir, "disclosures/events.json").get("items", []) or []
    return rows


def _dividend_block(symbol: str, cdir: Path, m: dict) -> str:
    """C5 — lịch sử cổ tức tiền mặt: ≥2 kỳ gần nhất + tổng 12 tháng + tỷ suất."""
    rows = [r for r in _events_rows(symbol, cdir)
            if "cổ tức bằng tiền" in str(r.get("event_name") or "").lower()
            and isinstance(r.get("value_per_share"), (int, float))
            and r["value_per_share"] > 0 and not _bad_date(r.get("public_date"))]
    if not rows:
        return ""
    rows.sort(key=lambda r: _day(r["public_date"]), reverse=True)
    shown = rows[:4]
    parts = [f"{_day(r['public_date'])}: {r['value_per_share']:,.0f}đ/CP" for r in shown]
    L = ["- Cổ tức tiền mặt (kỳ gần nhất): " + " | ".join(parts)]
    # Tổng 12 tháng gần nhất, mốc là kỳ chi trả mới nhất (KHÔNG dùng ngày hôm nay:
    # dữ liệu có thể cũ, sẽ ra 0đ và bị đọc thành "ngừng trả cổ tức").
    newest = _day(rows[0]["public_date"])
    y, mo, d = newest[:4], newest[5:7], newest[8:10]
    if y.isdigit():
        floor = f"{int(y) - 1}-{mo}-{d}"
        last12 = sum(r["value_per_share"] for r in rows if _day(r["public_date"]) > floor)
        # Dùng lại hàm của fundamentals: price.json để giá theo NGHÌN đồng (62.9)
        # còn cổ tức theo ĐỒNG (1.000đ/CP) — tự chia sẽ ra tỷ suất sai 1.000 lần.
        price = fundamentals._latest_close_vnd(cdir)
        tail = f"- Cổ tức 12 tháng tới {newest}: {last12:,.0f}đ/CP"
        if price and last12:
            tail += f" | tỷ suất ~{last12 / price * 100:.1f}% theo giá {price:,.0f}đ"
        L.append(tail)
    yrs = sorted({_day(r["public_date"])[:4] for r in rows})
    if len(yrs) >= 2:
        L.append(f"- Số năm có chi trả tiền mặt trong dữ liệu: {len(yrs)} ({yrs[0]}–{yrs[-1]})")
    return "\n".join(L)


def _corp_action_block(symbol: str, cdir: Path) -> str:
    """C6 — sự kiện pha loãng & quản trị, khối RIÊNG cho lượt rủi ro."""
    rows = [r for r in _events_rows(symbol, cdir)
            if str(r.get("event_name") or "") in _DILUTION_EVENTS
            and not _bad_date(r.get("public_date"))]
    if not rows:
        return ""
    rows.sort(key=lambda r: _day(r["public_date"]), reverse=True)
    L = []
    for r in rows[:6]:
        title = re.sub(r"\s+", " ", str(r.get("title") or "")).strip()[:70]
        L.append(f"- {_day(r['public_date'])} · {r['event_name']}"
                 + (f": {title}" if title else ""))
    return "\n".join(L)


# ---------------------------------------------------------------- B5: mô tả doanh nghiệp
# Trước đây AI phân tích FPT mà KHÔNG biết FPT bán gì — đoạn `company_profile`
# không có mặt trong bất kỳ prompt nào. Đây là khối rẻ nhất/tác động lớn nhất.
#
# ⚠ PHÁP LÝ: `profile.json.overview` của nguồn có sẵn `rating: "BUY"`,
# `target_price`, `upside_to_target_percent`, `analyst`, `projected_tsr_percentage`
# — đó là KHUYẾN NGHỊ CỦA BÊN THỨ BA. Tuyệt đối không được lọt vào prompt: AI sẽ
# nhắc lại và ta thành nơi phát hành khuyến nghị (Điều 71). Vì vậy khối này CHỈ
# đọc danh sách khoá cho phép dưới đây, không bao giờ dump cả `overview`.
_PROFILE_ALLOW = ("organ_name", "sector", "com_group_code", "issue_share",
                  "company_profile", "foreigner_percentage",
                  "maximum_foreign_percentage", "state_percentage")


def _profile_block(cdir: Path, max_desc: int = 700) -> str:
    ov = _load_json(cdir, "profile.json").get("overview") or {}
    if not ov:
        return ""
    ov = {k: v for k, v in ov.items() if k in _PROFILE_ALLOW}
    L = []
    head = [x for x in (ov.get("organ_name"), ov.get("sector"),
                        ov.get("com_group_code")) if x]
    if head:
        L.append("- " + " | ".join(str(x) for x in head))
    if isinstance(ov.get("issue_share"), (int, float)):
        L.append(f"- Số cổ phiếu đang lưu hành: {ov['issue_share']:,.0f}")
    fo, fmax, st = (ov.get("foreigner_percentage"), ov.get("maximum_foreign_percentage"),
                    ov.get("state_percentage"))
    own = []
    if isinstance(fo, (int, float)):
        own.append(f"sở hữu nước ngoài {fo * 100:.1f}%"
                   + (f"/room {fmax * 100:.0f}%" if isinstance(fmax, (int, float)) else ""))
    if isinstance(st, (int, float)) and st > 0:
        own.append(f"nhà nước {st * 100:.1f}%")
    if own:
        L.append("- Cơ cấu: " + ", ".join(own))
    desc = re.sub(r"\s+", " ", str(ov.get("company_profile") or "")).strip()
    if desc:
        if len(desc) > max_desc:
            desc = desc[:max_desc].rsplit(". ", 1)[0] + "."
        L.append("- Hoạt động: " + desc)
    return "\n".join(L)


# Chỉ tiêu BCĐKT chính đưa vào AI (item_id → nhãn).
# B5 #4: mở rộng 8 → ~22 dòng. Ngân hàng có bộ item_id KHÁC hoàn toàn (không có
# `liabilities`/`inventories_net`; có `deposits_from_customers`,
# `loans_and_advances_to_customers`...) nên tách 2 danh sách, chọn theo is_bank.
_BALANCE_ITEMS = [
    ("total_assets", "Tổng tài sản"),
    ("owners_equity", "Vốn chủ sở hữu"),
    ("liabilities", "Nợ phải trả"),
    ("current_liabilities", "Nợ ngắn hạn"),
    ("long_term_liabilities", "Nợ dài hạn"),
    ("cash_and_cash_equivalents", "Tiền & tương đương"),
    ("inventories_net", "Hàng tồn kho ròng"),
    ("current_assets", "Tài sản ngắn hạn"),
    # ── B5 #4 bổ sung: vốn lưu động, cấu trúc vay, chất lượng phải thu.
    ("short_term_investments", "Đầu tư ngắn hạn"),
    ("accounts_receivable", "Phải thu ngắn hạn"),
    ("trade_accounts_receivable", "Phải thu khách hàng"),
    ("provision_for_doubtful_debts", "Dự phòng phải thu khó đòi"),
    ("prepayments_to_suppliers", "Trả trước cho người bán"),
    ("short_term_borrowings", "Vay ngắn hạn"),
    ("long_term_borrowings", "Vay dài hạn"),
    ("trade_accounts_payable", "Phải trả người bán"),
    ("advances_from_customers", "Người mua trả tiền trước"),
    ("long_term_assets", "Tài sản dài hạn"),
    ("fixed_assets", "Tài sản cố định"),
    ("construction_in_progress", "Xây dựng cơ bản dở dang"),
    ("long_term_investments", "Đầu tư dài hạn"),
    ("goodwill", "Lợi thế thương mại"),
    ("undistributed_earnings", "LN sau thuế chưa phân phối"),
    ("minority_interests", "Lợi ích cổ đông thiểu số"),
    ("deferred_revenue", "Doanh thu chưa thực hiện"),
]

# Ngân hàng: bộ chỉ tiêu riêng (BCĐKT nhà băng không có tồn kho/nợ ngắn-dài hạn).
_BALANCE_ITEMS_BANK = [
    ("total_assets", "Tổng tài sản"),
    ("owners_equity", "Vốn chủ sở hữu"),
    ("total_liabilities", "Tổng nợ phải trả"),
    ("charter_capital", "Vốn điều lệ"),
    ("cash_and_precious_metals", "Tiền & kim loại quý"),
    ("balances_with_the_sbv", "Tiền gửi tại NHNN"),
    ("placements_with_and_loans_to_other_credit_institutions", "Tiền gửi & cho vay TCTD khác"),
    ("loans_and_advances_to_customers", "Cho vay khách hàng (gộp)"),
    ("loans_and_advances_to_customers_net", "Cho vay khách hàng (ròng)"),
    ("less_provision_for_losses_on_loans_and_advances_to_customers", "Dự phòng rủi ro cho vay"),
    ("trading_securities_net", "Chứng khoán kinh doanh (ròng)"),
    ("investment_securities", "Chứng khoán đầu tư"),
    ("held_to_maturity_securities", "CK giữ đến ngày đáo hạn"),
    ("available_for_sales_securities", "CK sẵn sàng để bán"),
    ("deposits_from_customers", "Tiền gửi của khách hàng"),
    ("deposits_and_loans_from_other_credit_institutions", "Tiền gửi & vay TCTD khác"),
    ("due_to_gov_and_loans_from_sbv", "Nợ Chính phủ & NHNN"),
    ("convertible_bonds_cds_and_other_valuable_papers_issued", "Giấy tờ có giá đã phát hành"),
    ("retained_earnings", "LN để lại"),
    ("reserves", "Các quỹ"),
    ("fixed_assets", "Tài sản cố định"),
    ("irrevocable_loan_commitments", "Cam kết cho vay không hủy ngang"),
]


def _balance_block(cdir: Path, m: dict | None = None) -> str:
    recs = _load_json(cdir, "financials/balance_sheet.json").get("records", [])
    if not recs:
        return "(không có bảng cân đối kế toán)"
    # Bank hay không: dựa vào revenue.item_id do fundamentals trả về (bank =
    # total_operating_income vì nhà băng KHÔNG có net_sales). Không có `m` thì
    # nhận diện bằng sự hiện diện của chỉ tiêu đặc thù ngân hàng.
    rev_item = ((m or {}).get("revenue") or {}).get("item_id")
    if rev_item:
        is_bank = rev_item == "total_operating_income"
    else:
        is_bank = any(r.get("item_id") == "deposits_from_customers" for r in recs)
    items = _BALANCE_ITEMS_BANK if is_bank else _BALANCE_ITEMS

    # với mỗi item, lấy giá trị kỳ mới nhất (ưu tiên quý, fallback năm)
    def latest(item_id):
        cands = [(str(r.get("period", "")), r.get("value")) for r in recs
                 if r.get("item_id") == item_id and isinstance(r.get("value"), (int, float))]
        cands.sort(key=lambda x: x[0])
        return cands[-1] if cands else (None, None)
    L, period = [], None
    for item_id, lbl in items:
        p, v = latest(item_id)
        if v is not None:
            period = period or p
            L.append(f"- {lbl}: {_fmt(v, money=True)}")
    if not L:
        return "(không có bảng cân đối kế toán)"
    head = f"(số dư cuối kỳ {period})" if period else ""
    return (head + "\n" if head else "") + "\n".join(L)


# ---------------------------------------------------------------- prompt

def _build_prompt(symbol: str, m: dict, peer: dict, reasons: list[dict]) -> str:
    return (
        f"Bạn là chuyên gia phân tích dữ liệu chứng khoán Việt Nam. Hãy phân tích mã {symbol} "
        f"theo phương pháp top-down (vĩ mô → ngành → doanh nghiệp), MÔ TẢ tình trạng & rủi ro.\n\n"
        f"### CHỈ SỐ TÀI CHÍNH ĐỊNH LƯỢNG (đã tính sẵn)\n{_metrics_block(m)}\n\n"
        f"### SO SÁNH NGÀNH\n{_peer_block(peer)}\n\n"
        f"### TIN TỨC THEO TRỌNG SỐ TÁC ĐỘNG (1=nhỏ, 5=lớn)\n{_reasons_block(reasons)}\n\n"
        f"Yêu cầu phân tích:\n"
        f"1. Đánh giá sức khỏe tài chính dựa trên doanh thu/LNST, tăng trưởng YoY, biên lãi, đòn bẩy.\n"
        f"2. Định giá: vị trí theo percentile lịch sử + so P/E, P/B với ngành (KHÔNG kết luận rẻ/đắt tuyệt đối).\n"
        f"3. Phân biệt độ lớn tác động của từng tin theo trọng số (đừng coi tin nhỏ ngang tin lớn).\n\n"
        f"Trả về DUY NHẤT một object JSON hợp lệ (không markdown) theo schema:\n"
        f"{json.dumps(SCHEMA_HINT, ensure_ascii=False)}\n"
        f"causes: 3-6 yếu tố kèm weight 1-5; toàn bộ tiếng Việt."
        + LEGAL_RULE
    )


# ---------------------------------------------------------------- multi-pass (đa lượt)
# Mỗi công ty phân tích NHIỀU LƯỢT theo từng khía cạnh → bức tranh overall rõ ràng.

_ASPECT_SCHEMA = {
    "aspect": "str (khía cạnh)",
    "summary": "2-4 câu nhận định chuyên sâu về khía cạnh này",
    "score": "0-100 (điểm khía cạnh)",
    "signals": [{"label": "tín hiệu", "impact": "positive|negative|neutral",
                 "detail": "giải trình ngắn có dẫn số liệu"}],
    "verdict": "1-2 câu kết luận cho riêng khía cạnh này",
}


def _aspect_prompt(symbol: str, title: str, focus: str, data_blocks: str) -> str:
    return (
        f"Bạn là chuyên gia phân tích đầu tư chứng khoán Việt Nam. Đây là MỘT LƯỢT phân tích "
        f"CHUYÊN SÂU cho mã {symbol}, chỉ tập trung khía cạnh: **{title}**.\n\n"
        f"{data_blocks}\n\n"
        f"Yêu cầu: {focus}\n"
        f"Phân tích có giải trình, dẫn số liệu cụ thể, KHÔNG mơ hồ. Nếu thiếu dữ liệu thì nói rõ "
        f"'không đủ dữ liệu' thay vì suy diễn.\n\n"
        f"Trả về DUY NHẤT object JSON (không markdown) theo schema:\n"
        f"{json.dumps(_ASPECT_SCHEMA, ensure_ascii=False)}\nsignals: 2-5 mục; toàn bộ tiếng Việt."
        + LEGAL_RULE
    )


def _sec(title: str, body: str) -> str:
    """Một mục dữ liệu. Body rỗng ⇒ trả "" ⇒ mục BỊ BỎ HẲN (không in tiêu đề trống)."""
    body = (body or "").strip()
    return f"### {title}\n{body}\n\n" if body else ""


# Trần CỨNG của server Local API (`Task.js: maxlength: 10000`). Vượt = HTTP 400.
# Client `local_api.py` phát lại lịch sử hội thoại nên lượt sau nặng hơn lượt trước
# → phải chừa khoảng an toàn cho phần lịch sử, không được ăn hết 10.000 ở lượt 1.
PROMPT_HARD_LIMIT = 10000
PROMPT_BUDGET = 9200


def _fit(prompt: str, limit: int = PROMPT_BUDGET) -> str:
    """Chốt chặn cuối: nếu prompt vượt trần thì CẮT BỚT DỮ LIỆU (giữ nguyên phần
    yêu cầu + schema + luật pháp lý ở cuối) và ghi rõ đã cắt. Thà thiếu dữ liệu
    còn hơn để server trả 400 rồi mã đó mất luôn phân tích."""
    if len(prompt) <= limit:
        return prompt
    # Phần đuôi (từ "Yêu cầu:" trở đi) là bắt buộc — không bao giờ cắt.
    tail_at = prompt.rfind("\n\nYêu cầu:")
    if tail_at < 0:
        return prompt[:limit]
    head, tail = prompt[:tail_at], prompt[tail_at:]
    note = "\n[đã lược một phần dữ liệu để vừa giới hạn độ dài prompt]"
    keep = limit - len(tail) - len(note)
    if keep <= 0:
        return prompt[:limit]
    return head[:keep].rsplit("\n", 1)[0] + note + tail


def _build_aspect_prompts(symbol: str, m: dict, peer: dict, reasons: list[dict],
                          cdir: Path, macro_ctx: dict) -> dict:
    """Sinh prompt cho 4 lượt khía cạnh, mỗi lượt kèm khối dữ liệu phù hợp.

    Phân bổ khối theo lượt (không lặp lại khối nặng ở mọi lượt vì trần 10.000
    ký tự/lượt): bảng chuỗi nhiều kỳ + BCĐKT mở rộng chỉ ở `financial`; chuỗi
    ngắn + vĩ mô ở `growth`; cổ tức ở `valuation`; sự kiện pha loãng ở `risk`."""
    metrics = _metrics_block(m)
    trend = _trend_block(cdir, m)
    profile = _profile_block(cdir)
    # Bộ chỉ tiêu đúng theo ngành + chất lượng lợi nhuận (nếu fundamentals đã tính).
    from . import sector_metrics, earnings_quality
    sm = m.get("sector_model")
    eq = m.get("earnings_quality")
    sector_txt = (_sec("CHỈ TIÊU THEO MÔ HÌNH NGÀNH (đánh giá đúng đặc thù)",
                       sector_metrics.text_block(sm)) if sm else "")
    quality_txt = (_sec("CHẤT LƯỢNG LỢI NHUẬN (lãi có được đỡ bằng tiền thật?)",
                        earnings_quality.text_block(eq)) if eq else "")
    prof_sec = _sec("DOANH NGHIỆP NÀY LÀM GÌ", profile)
    trend_sec = _sec("CHUỖI NHIỀU KỲ (đọc XU HƯỚNG, không chỉ 1 lát cắt)", trend)
    red_flags = ("; ".join(sm.get("red_flags", [])) if sm and sm.get("red_flags") else "")

    out = {
        "financial": _aspect_prompt(
            symbol, "Tài chính & dòng tiền",
            "Đánh giá sức khỏe BCTC theo ĐÚNG mô hình ngành (ngân hàng nhìn NIM/CIR/LDR/đệm vốn, "
            "KHÔNG dùng biên gộp; doanh nghiệp thường nhìn biên lãi/tồn kho/phải thu), chất lượng "
            "lợi nhuận (CFO vs LNST, accrual), cơ cấu nợ. Đọc bảng chuỗi nhiều kỳ để nói rõ chỉ "
            "tiêu nào đang cải thiện/bào mòn qua thời gian. Nêu rõ các cờ cảnh báo.",
            _sec("DOANH NGHIỆP NÀY LÀM GÌ", _profile_block(cdir, max_desc=420))
            + _sec("CHỈ SỐ ĐỊNH LƯỢNG", metrics) + sector_txt + quality_txt
            + _sec("VÒNG QUAY VỐN & AN TOÀN NỢ", _capital_cycle_block(m))
            + trend_sec
            + _sec("BẢNG CÂN ĐỐI KẾ TOÁN (kỳ mới nhất)", _balance_block(cdir, m))),
        "valuation": _aspect_prompt(
            symbol, "Định giá & so sánh ngành",
            "Định giá hiện tại đang ở vùng nào SO VỚI LỊCH SỬ 3 NĂM CỦA CHÍNH MÃ (percentile) "
            "và so trung vị ngành? Dùng ngôn ngữ percentile (vùng thấp/giữa/cao), KHÔNG kết luận "
            "rẻ/đắt tuyệt đối. Nêu biên an toàn dựa trên dải lịch sử. Đối chiếu P/E theo kỳ năm "
            "với P/E TTM và nói rõ vì sao lệch nếu có.",
            _sec("ĐỊNH GIÁ & CHỈ SỐ", metrics)
            + _sec("DẢI ĐỊNH GIÁ THEO LỊCH SỬ CHÍNH MÃ (percentile 3 năm)",
                   _valband_block(m.get("valuation_band")))
            + _sec("SO SÁNH NGÀNH & XẾP HẠNG", _peer_block(peer))
            + _sec("LỊCH SỬ CỔ TỨC TIỀN MẶT", _dividend_block(symbol, cdir, m))),
        "growth": _aspect_prompt(
            symbol, "Tăng trưởng & triển vọng",
            "Phân tích xu hướng doanh thu/LNST nhiều kỳ, động lực tăng trưởng, và tác động của "
            "bối cảnh vĩ mô/ngành tới triển vọng doanh nghiệp (phân tích top-down). Ưu tiên đọc "
            "YoY cùng kỳ và TTM; KHÔNG kết luận suy giảm chỉ vì QoQ âm do mùa vụ.",
            prof_sec + _sec("TĂNG TRƯỞNG & CHỈ SỐ", metrics) + trend_sec
            + _sec("BỐI CẢNH VĨ MÔ & THỊ TRƯỜNG", _macro_block(macro_ctx))),
        "risk": _aspect_prompt(
            symbol, "Rủi ro & kỹ thuật giá",
            "Nhận diện rủi ro (pháp lý, đòn bẩy, cổ đông, thanh khoản, PHA LOÃNG cổ phiếu) có giải "
            "trình. Đọc tín hiệu momentum/biến động giá, sức mạnh tương đối so VNINDEX, beta và "
            "mức sụt sâu nhất. Phân biệt độ lớn tác động theo trọng số tin.",
            _sec(f"TIN TỨC & BÁO CHÍ THEO TRỌNG SỐ (1=nhỏ,5=lớn; {len(reasons)} mục)",
                 _reasons_block(reasons))
            + _sec("CỜ CẢNH BÁO CƠ BẢN (chất lượng lợi nhuận + chỉ tiêu ngành)",
                   (earnings_quality.text_block(eq) if eq else "") + "\n" + red_flags)
            + _sec("KỸ THUẬT GIÁ & SO VỚI VNINDEX", _price_block(cdir))
            + _sec("SỰ KIỆN PHA LOÃNG & QUẢN TRỊ (tách riêng khỏi tin thường)",
                   _corp_action_block(symbol, cdir))
            + _sec("SỞ HỮU & DÒNG TIỀN KHỐI NGOẠI", _ownership_block(cdir))
            + _sec("BAN LÃNH ĐẠO & CƠ CẤU TẬP ĐOÀN", _governance_block(cdir))),
    }
    return {k: _fit(v) for k, v in out.items()}


def _overall_prompt(symbol: str, aspects: dict, m: dict) -> str:
    """Lượt tổng hợp: nhận 4 kết quả khía cạnh → verdict cuối theo SCHEMA_HINT."""
    parts = []
    titles = {"financial": "Tài chính & dòng tiền", "valuation": "Định giá & so ngành",
              "growth": "Tăng trưởng & triển vọng", "risk": "Rủi ro & kỹ thuật giá"}
    for key, res in aspects.items():
        if not isinstance(res, dict):
            continue
        parts.append(f"### {titles.get(key, key).upper()} (điểm {res.get('score','?')})\n"
                     f"{res.get('summary','')}\nKết luận: {res.get('verdict','')}")
    return (
        f"Bạn là chuyên gia phân tích đầu tư. Dưới đây là 4 lượt phân tích chuyên sâu đã thực hiện "
        f"cho mã {symbol}. Hãy TỔNG HỢP thành bức tranh MÔ TẢ cuối cùng, nhất quán và có giải trình "
        f"(mô tả tình trạng & rủi ro, KHÔNG khuyến nghị).\n\n"
        + "\n\n".join(parts)
        + f"\n\nĐiểm sức khỏe định lượng: {m['health_score']}/100, F-Score {m['fscore']}/{m['fscore_max']}, "
        f"vị trí định giá sơ bộ: {m['valuation_verdict']}.\n\n"
        f"Trả về DUY NHẤT object JSON (không markdown) theo schema:\n"
        f"{json.dumps(SCHEMA_HINT, ensure_ascii=False)}\n"
        f"causes: 3-6 yếu tố hợp nhất từ 4 lượt kèm weight 1-5; toàn bộ tiếng Việt."
        + LEGAL_RULE
    )


def _first_json_block(text: str) -> str | None:
    """Tìm khối {...} CÂN BẰNG ngoặc đầu tiên (bỏ qua ngoặc trong chuỗi).

    Ổn định hơn cách '{' đầu tới '}' cuối khi có văn xuôi kèm dấu ngoặc."""
    start = text.find("{")
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _parse_json(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        for part in text.split("```"):
            # Bỏ nhãn ngôn ngữ "json" ở đầu fenced block (không bào mòn ký tự j/s/o/n).
            part = re.sub(r"^\s*json\s*", "", part, flags=re.IGNORECASE).strip()
            if part.startswith("{"):
                text = part
                break
    # Ưu tiên khối JSON cân bằng ngoặc đầu tiên; fallback về cách cũ.
    block = _first_json_block(text)
    if block is not None:
        try:
            return json.loads(block)
        except Exception:
            pass
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def _call_claude(prompt: str) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL, max_tokens=4000,
        messages=[{"role": "user", "content": prompt}])
    return _parse_json(msg.content[0].text)


# ---------------------------------------------------------------- Gemini web (CDP)
# Playwright sync bị ràng buộc theo thread → mỗi thread giữ 1 GeminiCDP RIÊNG.
# Mỗi phân tích tự mở 1 tab mới rồi đóng (analyze_with_new_tab) → chạy song song
# an toàn khi phía gọi dùng ThreadPoolExecutor để giới hạn số luồng.
import threading as _threading

_tls = _threading.local()


def _thread_gemini():
    g = getattr(_tls, "gemini", None)
    if g is None:
        from .gemini_cdp import GeminiCDP
        g = GeminiCDP().__enter__()
        _tls.gemini = g
    return g


def close_gemini_threadlocal():
    g = getattr(_tls, "gemini", None)
    if g is not None:
        try:
            g.__exit__(None, None, None)
        finally:
            _tls.gemini = None


# Tương thích ngược: một số call site cũ vẫn gọi close_gemini().
def close_gemini():
    close_gemini_threadlocal()


def _call_gemini(prompt: str) -> dict:
    return _parse_json(_thread_gemini().analyze_with_new_tab(prompt, timeout=180))


# ---------------------------------------------------------------- AI lỗi → chỉ số liệu

def _quant_only(symbol: str, m: dict, peer: dict, reasons: list[dict], error: str) -> dict:
    """AI lỗi/timeout/JSON hỏng → giữ NGUYÊN số liệu định lượng, KHÔNG bịa nhận định.

    Không suy diễn rating/risk/causes bằng luật (đó là việc của AI). Chỉ đóng gói
    các con số đã tính (nguồn sự thật) + thông điệp lỗi trung thực để UI báo rõ."""
    hs = m["health_score"]
    rv, np_ = m["revenue"], m["net_profit"]
    return {
        "ticker": symbol,
        "fundamental_summary": (f"Điểm sức khỏe {hs}/100, F-Score {m['fscore']}/{m['fscore_max']}. "
                                f"ROE {_fmt(m['profitability']['roe'])}%, biên ròng {_fmt(m['margins']['net'])}%, "
                                f"Nợ/VCSH {_fmt(m['solvency']['debt_to_equity'])}."),
        "valuation_comment": f"P/E {_fmt(m['valuation']['pe'])}, P/B {_fmt(m['valuation']['pb'])} → {m['valuation_verdict']}.",
        "growth_comment": (f"DT: QoQ {_fmt(rv['qoq'], pct=True)}, YoY năm {_fmt(rv['yoy_y'], pct=True)}. "
                           f"LNST: QoQ {_fmt(np_['qoq'], pct=True)}, YoY năm {_fmt(np_['yoy_y'], pct=True)}."),
        "peer_comment": _peer_block(peer),
        "key_drivers": [],
        "causes": [],
        "risk_level": None,
        "investment_rating": None,
        "verdict": (f"AI chưa phân tích được (lỗi: {error[:120]}). "
                    f"Chỉ hiển thị số liệu định lượng — chưa có nhận định của chuyên gia AI."),
    }


# ---------------------------------------------------------------- entry

COMPARE_SCHEMA = {
    "pair": ["A", "B"],
    "winner": "mã tốt hơn cho đầu tư (hoặc 'tùy mục tiêu')",
    "summary": "2-3 câu so sánh tổng quan",
    "dimensions": [{"name": "Tăng trưởng|Định giá|Sinh lời|An toàn tài chính|Vị thế",
                    "better": "A|B|ngang", "comment": "giải thích ngắn"}],
    "verdict": "kết luận của chuyên gia: nên chọn mã nào và vì sao",
}


def _compare_brief(symbol: str, conn) -> str:
    m = fundamentals.compute(symbol)
    a = {}
    row = conn.execute("SELECT analysis FROM ai_analysis WHERE symbol=?", (symbol,)).fetchone()
    if row:
        try:
            a = json.loads(row[0])
        except Exception:
            a = {}
    return (f"[{symbol}] sức khỏe {m['health_score']}/100, F-Score {m['fscore']}/{m['fscore_max']}, "
            f"định giá {m['valuation_verdict']} (P/E {_fmt(m['valuation']['pe'])}, P/B {_fmt(m['valuation']['pb'])}), "
            f"ROE {_fmt(m['profitability']['roe'])}%, biên ròng {_fmt(m['margins']['net'])}%, "
            f"Nợ/VCSH {_fmt(m['solvency']['debt_to_equity'])}, "
            f"DT YoY năm {_fmt(m['revenue']['yoy_y'], pct=True)}, LNST YoY năm {_fmt(m['net_profit']['yoy_y'], pct=True)}. "
            f"Khuyến nghị hiện tại: {a.get('investment_rating','?')}.")


def compare_two(conn, a: str, b: str, backend: str | None = None) -> dict:
    a, b = a.upper(), b.upper()
    backend = (backend or "").strip().lower() or resolve_backend()
    prompt = (
        f"Bạn là chuyên gia phân tích đầu tư. So sánh 2 cổ phiếu sau và tư vấn nên chọn mã nào.\n\n"
        f"{_compare_brief(a, conn)}\n\n{_compare_brief(b, conn)}\n\n"
        f"So sánh theo 5 chiều: Tăng trưởng, Định giá (rẻ/đắt), Sinh lời, An toàn tài chính, Vị thế.\n"
        f"Trả về DUY NHẤT object JSON (không markdown) theo schema:\n"
        f"{json.dumps(COMPARE_SCHEMA, ensure_ascii=False)}\ntiếng Việt; pair=['{a}','{b}']."
    )
    if backend == "gemini":
        res = _parse_json(_thread_gemini().analyze_with_new_tab(prompt, timeout=180)); mode = "gemini"
    elif backend == "local_api":
        res = _parse_json(_raw_local_api(prompt)); mode = "local_api"
    elif backend == "claude":
        res = _call_claude(prompt); mode = "ai"
    else:
        # Không có backend AI hợp lệ → KHÔNG bịa winner; báo lỗi trung thực.
        res = {
            "winner": None,
            "summary": ("Chưa so sánh được: cần bật AI (server local :4000 + LOCAL_API_KEY, "
                        "hoặc Gemini CDP đã login, hoặc ANTHROPIC_API_KEY)."),
            "dimensions": [],
            "verdict": "Không có backend AI hợp lệ để so sánh 2 mã.",
        }
        mode = "ai_error"
    res["pair"] = [a, b]
    res["mode"] = mode
    res["generated_at"] = storage.now_iso()
    return res


# ---------------------------------------------------------------- gọi backend (kèm debug)
# Mỗi lượt gọi trả về (dict đã parse, raw_text) để LƯU DEBUG minh bạch.

def _raw_gemini(prompt: str) -> str:
    return _thread_gemini().analyze_with_new_tab(prompt, timeout=180)


def _raw_local_api(prompt: str) -> str:
    """Gọi server AI local (mặc định). Client dùng chung ở src/local_api.py."""
    return local_api.ask(prompt)


# GHI CHÚ — vì sao kênh local_api KHÔNG dùng phiên hội thoại nhiều lượt:
# server gộp toàn bộ messages thành MỘT chuỗi prompt, nên phát lại lịch sử làm
# payload phình theo cấp số cộng qua từng lượt. Đo thật trên FPT: lượt 3 đã
# 10.992 ký tự, lượt 4 là 13.156 — vượt giới hạn cũ của server và hỏng từ lượt 3
# trở đi. Mỗi lượt gọi độc lập là hành vi đã chạy đúng cho 429 mã, và lượt tổng
# hợp vốn đã được truyền tóm tắt 4 khía cạnh nên không mất ngữ cảnh đáng kể.


def _raw_claude(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL, max_tokens=4000,
        messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text


# Câu nhắc nối vào prompt khi thử lại vì JSON hỏng — ép Gemini trả JSON sạch.
_RETRY_FEEDBACK = (
    "\n\nLƯU Ý: lần trả lời trước rỗng hoặc JSON lỗi cú pháp. Trả về DUY NHẤT một "
    "object JSON hợp lệ đúng schema, không markdown, không văn bản ngoài JSON.")


def _call_backend(backend: str, prompt: str, retries: int = 2,
                  page=None) -> tuple[dict, str, int]:
    """Gọi 1 lượt theo backend, trả (parsed_dict, raw_text, attempts).

    `page`: nếu có (backend gemini) → hỏi trên CÙNG tab/phiên (RAG chung 1 session,
    Gemini nhớ ngữ cảnh các lượt trước) thay vì mở tab mới mỗi lượt. Kênh
    local_api gọi độc lập từng lượt (xem ghi chú ở trên `_raw_local_api`).
    Retry khi _parse_json ném JSONDecodeError. `attempts` = số lần đã thực gọi."""
    if backend not in BACKENDS:
        raise RuntimeError(f"backend không hỗ trợ multipass: {backend}")
    attempts_max = max(1, retries + 1)
    last_exc: Exception | None = None
    for i in range(attempts_max):
        # Lần thử lại: nối feedback để backend biết lần trước hỏng JSON.
        p = prompt if i == 0 else (prompt + _RETRY_FEEDBACK)
        if backend == "gemini":
            raw = _thread_gemini().ask_on_tab(page, p) if page is not None else _raw_gemini(p)
        elif backend == "local_api":
            raw = _raw_local_api(p)
        else:
            raw = _raw_claude(p)
        try:
            return _parse_json(raw), raw, i + 1
        except json.JSONDecodeError as exc:
            # Chỉ retry lỗi parse JSON; lỗi backend (rỗng/timeout) đã được
            # gemini_cdp retry ở tầng dưới và ném lên nếu hết lượt.
            last_exc = exc
            if i < attempts_max - 1:
                print(f"  [retry] JSON hỏng (lượt {i + 1}/{attempts_max}): "
                      f"{str(exc)[:80]} — thử lại với feedback.")
                continue
            raise
    # Không tới đây (vòng lặp luôn return hoặc raise).
    raise last_exc if last_exc else RuntimeError("Không parse được JSON từ backend.")


def _save_debug(cdir: Path, symbol: str, backend: str, passes: list[dict]) -> None:
    """Lưu prompt + raw của TỪNG lượt vào analysis/debug/<key>.json để soi trên UI."""
    dbg_dir = cdir / "analysis" / "debug"
    index = {"symbol": symbol, "backend": backend, "generated_at": storage.now_iso(),
             "passes": []}
    for p in passes:
        key = p["key"]
        storage.write_json(dbg_dir / f"{key}.json", {
            "symbol": symbol, "key": key, "title": p.get("title", key),
            "backend": backend, "ok": p.get("ok", False),
            "error": p.get("error"),
            "attempts": p.get("attempts", 1),
            "retried": p.get("retried", False),
            "prompt": p.get("prompt", ""),
            "raw": p.get("raw", ""),
            "parsed": p.get("parsed"),
            "generated_at": storage.now_iso(),
        })
        index["passes"].append({"key": key, "title": p.get("title", key),
                                "ok": p.get("ok", False), "error": p.get("error"),
                                "attempts": p.get("attempts", 1),
                                "retried": p.get("retried", False),
                                "secs": p.get("secs"),
                                "prompt_chars": len(p.get("prompt", "")),
                                "raw_chars": len(p.get("raw", "") or "")})
    index["total_secs"] = round(sum(p.get("secs") or 0 for p in passes), 1)
    storage.write_json(dbg_dir / "index.json", index)


# ---------------------------------------------------------------- điều phối đa lượt

_ASPECT_TITLES = {
    "financial": "Tài chính & dòng tiền",
    "valuation": "Định giá & so ngành",
    "growth": "Tăng trưởng & triển vọng",
    "risk": "Rủi ro & kỹ thuật giá",
}


def _close_page(page):
    """Đóng tab phiên RAG an toàn (bọc mọi lỗi)."""
    try:
        if page is not None:
            page.close()
    except Exception:
        pass


def _analyze_multipass(symbol: str, backend: str, metrics: dict, peer: dict,
                       reasons: list[dict], cdir: Path) -> tuple[dict, list[dict]]:
    """Chạy 4 lượt khía cạnh TUẦN TỰ + 1 lượt tổng hợp trên CÙNG tab (thread-local).

    Trả (result, passes) — passes để lưu debug. Ném lỗi nếu lượt tổng hợp hỏng
    (phía gọi sẽ fallback mock)."""
    macro_ctx = macro.load_context()
    prompts = _build_aspect_prompts(symbol, metrics, peer, reasons, cdir, macro_ctx)
    passes: list[dict] = []
    aspects: dict = {}
    # RAG CHUNG 1 PHIÊN: mở 1 tab dùng cho CẢ 5 lượt (Gemini nhớ ngữ cảnh giữa các
    # lượt) → ít churn tab hơn (đỡ bị Google chặn) + đúng tinh thần hội thoại. Mở
    # phiên lỗi → page=None → tự fallback về tab-mới-mỗi-lượt (an toàn).
    page = None
    if backend == "gemini":
        try:
            page = _thread_gemini().open_session_tab()
        except Exception as exc:
            print(f"  [phiên] {symbol}: không mở được phiên chung ({str(exc)[:60]}) "
                  f"→ dùng tab-mới mỗi lượt.", flush=True)
            page = None
    for key, prompt in prompts.items():
        title = _ASPECT_TITLES.get(key, key)
        rec = {"key": key, "title": title, "prompt": prompt, "attempts": 0, "retried": False}
        _t0 = time.time()
        try:
            parsed, raw, attempts = _call_backend(backend, prompt, page=page)
            rec.update(ok=True, raw=raw, parsed=parsed, attempts=attempts,
                       retried=attempts > 1)
            aspects[key] = parsed
            progress.step(symbol, title, "ok", parsed.get("score", ""))
            # In LOG THẤY ĐƯỢC từng lượt (để không cảm giác treo khi mỗi mã mất vài phút).
            print(f"       · {symbol} · {title}: ✓ điểm {parsed.get('score','?')}"
                  + f" ({time.time() - _t0:.0f}s)"
                  + (f" (thử lại {attempts})" if attempts > 1 else ""), flush=True)
        except (Exception, SystemExit) as exc:
            rec.update(ok=False, raw="", parsed=None, error=str(exc)[:160], attempts=1)
            progress.step(symbol, title, "lỗi", "")
            print(f"       · {symbol} · {title}: ✗ {str(exc)[:60]}", flush=True)
        rec["secs"] = round(time.time() - _t0, 1)
        passes.append(rec)

    # ---- vòng VÁ: gom các lượt khía cạnh lỗi chạy lại đúng 1 vòng nữa.
    # Sleep 10s trước mỗi lượt vá để tránh rate-limit sau khi vừa dồn nhiều lượt.
    failed = [p for p in passes if not p.get("ok")]
    if failed:
        print(f"  [vá] {symbol}: {len(failed)} lượt khía cạnh lỗi → chạy lại 1 vòng.")
        for rec in failed:
            time.sleep(10)
            key, title = rec["key"], rec["title"]
            _t0 = time.time()
            try:
                parsed, raw, attempts = _call_backend(backend, rec["prompt"], page=page)
                # attempts nội bộ _call_backend + 1 (đây đã là lượt thứ 2 ở tầng này).
                rec.update(ok=True, raw=raw, parsed=parsed, error=None,
                           attempts=rec.get("attempts", 1) + attempts, retried=True)
                aspects[key] = parsed
                progress.step(symbol, title, "ok (vá)", parsed.get("score", ""))
            except (Exception, SystemExit) as exc:
                rec.update(ok=False, error=str(exc)[:160],
                           attempts=rec.get("attempts", 1) + 1, retried=True)
                progress.step(symbol, title, "lỗi (vá)", "")
            # cộng dồn: thời gian lượt đầu + lượt vá
            rec["secs"] = round((rec.get("secs") or 0) + time.time() - _t0, 1)

    # Lượt tổng hợp: cần ít nhất 1 khía cạnh có kết quả.
    if not aspects:
        _close_page(page)
        raise RuntimeError("Tất cả lượt khía cạnh đều lỗi")
    op = _overall_prompt(symbol, aspects, metrics)
    rec = {"key": "overall", "title": "Tổng hợp cuối", "prompt": op,
           "attempts": 0, "retried": False}
    _t0 = time.time()
    try:
        parsed, raw, attempts = _call_backend(backend, op, page=page)
    finally:
        _close_page(page)   # đóng tab phiên dù lượt tổng hợp thành công hay lỗi
        rec["secs"] = round(time.time() - _t0, 1)
    rec.update(ok=True, raw=raw, parsed=parsed, attempts=attempts, retried=attempts > 1)
    passes.append(rec)

    result = dict(parsed)
    # Gắn kèm 4 khía cạnh để UI hiển thị chi tiết.
    result["aspects"] = {k: {"title": _ASPECT_TITLES.get(k, k), **v}
                         for k, v in aspects.items() if isinstance(v, dict)}
    result["multipass"] = True
    result["n_passes"] = len(passes)
    # Còn lượt khía cạnh lỗi sau vòng vá → đánh dấu partial để pipeline nhặt lại.
    result["partial"] = any(not p.get("ok") for p in passes if p["key"] != "overall")
    return result, passes


def _keep_previous(conn, symbol: str, metrics: dict, peer: dict, error: str) -> dict | None:
    """Bản phân tích AI cũ (nếu có và còn dùng được) đã làm mới phần số liệu.

    Trả None khi chưa từng có bản tốt — lúc đó gọi `_quant_only` như cũ.
    "Còn dùng được" = có ít nhất 1 lượt khía cạnh, tức thực sự do AI sinh ra chứ
    không phải một bản báo lỗi trước đó."""
    try:
        row = conn.execute(
            "SELECT analysis FROM ai_analysis WHERE symbol=?", (symbol,)).fetchone()
        old = json.loads(row[0]) if row and row[0] else None
    except (sqlite3.Error, TypeError, ValueError):
        return None
    if not isinstance(old, dict):
        return None
    if old.get("mode") == "ai_error" or not (old.get("aspects") or old.get("causes")):
        return None

    # Giữ nguyên phần chữ của AI, nhưng số liệu định lượng thì luôn tính lại —
    # chúng rẻ và không phụ thuộc AI, để trang không hiện chỉ số cũ.
    kept = dict(old)
    kept["metrics"] = metrics
    kept["peer"] = peer
    kept["stale"] = True                 # UI dùng cờ này để nói "nhận định từ lần trước"
    kept["last_error"] = error[:200]
    kept["last_attempt_at"] = storage.now_iso()
    print(f"  [giữ] {symbol}: giữ lại bản phân tích cũ "
          f"({kept.get('n_passes') or '?'} lượt, {kept.get('generated_at', '')[:10]}) "
          f"— chỉ cập nhật số liệu.")
    return kept


def _finish(symbol: str, result: dict, stale: bool = False) -> None:
    """Đóng tiến trình cho 1 mã (dùng chung cho đường thành công và đường giữ-bản-cũ)."""
    progress.step(symbol, "rủi ro", result.get("risk_level", "?"), "")
    progress.done(symbol, "cũ" if stale else
                  ("partial" if result.get("partial") else "ok"))


def analyze_one(conn, symbol: str, backend: str | None = None) -> dict:
    symbol = symbol.upper()
    cdir = config.company_dir(symbol)
    _t_start = time.time()
    progress.start(symbol)

    # Sector từ bảng companies → fundamentals chọn ĐÚNG mô hình ngành.
    srow = conn.execute("SELECT sector FROM companies WHERE symbol=?", (symbol,)).fetchone()
    sector = srow[0] if srow else None
    metrics = fundamentals.compute(symbol, sector=sector)
    peer = peers.compute(conn, symbol)
    reasons = _load_reasons(cdir)
    progress.step(symbol, "F-Score", "ok", metrics["fscore"])
    progress.step(symbol, "sức khỏe", "ok", metrics["health_score"])

    # Chỉ AI thật. Backend lạ (vd "mock" ép bằng tay) → chuẩn hóa về AI hợp lệ.
    backend = (backend or "").strip().lower()
    if backend not in BACKENDS:
        backend = resolve_backend()
    multipass = _multipass_on()
    passes: list[dict] = []
    # AI lỗi/timeout/JSON hỏng → giữ NGUYÊN số liệu định lượng, KHÔNG bịa nhận định.
    try:
        _model = {"gemini": "gemini-web-cdp",
                  "local_api": f"local-api:{local_api.model()}"}.get(backend, MODEL)
        if multipass:
            result, passes = _analyze_multipass(symbol, backend, metrics, peer, reasons, cdir)
            result["mode"] = backend
            result["model"] = _model
        else:
            prompt = _build_prompt(symbol, metrics, peer, reasons)
            parsed, raw, attempts = _call_backend(backend, prompt)
            passes = [{"key": "single", "title": "Phân tích 1 lượt", "prompt": prompt,
                       "ok": True, "raw": raw, "parsed": parsed,
                       "attempts": attempts, "retried": attempts > 1}]
            result = parsed
            result["mode"] = backend
            result["model"] = _model
    except (Exception, SystemExit) as exc:
        print(f"  [!] {symbol} AI ({backend}) lỗi → chỉ giữ số liệu định lượng: {str(exc)[:80]}")
        # KHÔNG để một sự cố tạm thời xoá mất bản phân tích tốt đã có.
        # Đo thật 2026-07-27: Local API tắt vài giây giữa chừng → nhánh này chạy
        # và ghi đè bản 5 lượt đầy đủ của ACB bằng bản báo lỗi. Dữ liệu đã mất thì
        # phải chạy lại 2 phút/mã mới có lại, mà nguyên nhân chỉ là mạng chớp.
        kept = _keep_previous(conn, symbol, metrics, peer, str(exc))
        if kept is not None:
            storage.write_json(cdir / "analysis" / "ai_analysis.json", kept)
            conn.execute(
                "INSERT OR REPLACE INTO ai_analysis(symbol, analysis, updated_at) "
                "VALUES (?,?,?)",
                (symbol, json.dumps(kept, ensure_ascii=False), storage.now_iso()))
            conn.commit()
            _finish(symbol, kept, stale=True)
            return kept
        result = _quant_only(symbol, metrics, peer, reasons, str(exc))
        result["mode"] = "ai_error"; result["model"] = "quant-only"

    result.setdefault("ticker", symbol)
    # gắn số liệu định lượng (nguồn sự thật) vào kết quả
    result["metrics"] = metrics
    result["peer"] = peer
    # tương thích ngược với web cũ
    result.setdefault("cashflow_summary", result.get("fundamental_summary", ""))
    result["generated_at"] = storage.now_iso()
    # Thời gian phân tích — để UI nói được "phân tích mất bao lâu" thay vì
    # người dùng phải đoán xem trang đang treo hay đang chạy.
    result["duration_s"] = round(time.time() - _t_start, 1)
    result["pass_secs"] = {p.get("key"): p.get("secs") for p in passes if p.get("secs")}
    # PHÁP LÝ (Điều 71): KHÔNG lưu/khoe khuyến nghị mua/bán. Bỏ trường investment_rating
    # (giữ lại đánh giá rủi ro + số liệu). Hiển thị log/lưới dùng risk_level, không dùng từ bán/mua.
    result["investment_rating"] = None

    storage.write_json(cdir / "analysis" / "ai_analysis.json", result)
    # Lưu debug từng lượt (nếu có gọi AI) để soi minh bạch trên UI.
    if passes:
        try:
            _save_debug(cdir, symbol, backend, passes)
        except Exception as exc:
            print(f"  [!] {symbol} lưu debug lỗi (bỏ qua): {str(exc)[:80]}")
    conn.execute(
        "INSERT OR REPLACE INTO ai_analysis(symbol, analysis, updated_at) VALUES (?,?,?)",
        (symbol, json.dumps(result, ensure_ascii=False), storage.now_iso()))
    conn.commit()
    # (Bỏ @STEP "khuyến nghị" — không hiển thị mua/bán trên lưới; chỉ báo rủi ro.)
    # Còn lượt lỗi sau mọi retry → "partial" để lần chạy pipeline sau nhặt lại.
    _finish(symbol, result)
    return result
