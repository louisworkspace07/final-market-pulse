# -*- coding: utf-8 -*-
"""Orchestrator — luồng "Tổng quan Thị trường" MỘT CỔNG DUY NHẤT.

Đúng yêu cầu thiết kế: người dùng cần overview thị trường → hệ thống TỰ chạy
tuần tự từ dữ liệu đến kết luận, chia nhỏ từng task AI để câu trả lời chuẩn,
sát, đầy đủ lý do và bằng chứng:

  BƯỚC 1. THU THẬP  — bảng giá realtime (Test tool) + fundamentals/news (Crawl Data)
  BƯỚC 2. KỸ THUẬT  — tính RSI/SMA/MACD/độ rộng thuần Python (không AI)
  BƯỚC 3. AI TASK 1 — "Phân tích thuần": chỉ đọc số, mô tả trạng thái, CẤM suy diễn
  BƯỚC 4. AI TASK 2 — "Phân tích reason": tìm nguyên nhân, BẮT BUỘC trích mã
                       bằng chứng [N1][E2]... từ tin CBTT/sự kiện thật
  BƯỚC 5. AI TASK 3 — "Tổng hợp": kết luận + điểm theo dõi từ 2 task trước
                       (KHÔNG dự phóng kịch bản xác suất / khuyến nghị mua-bán)

Mỗi task 1 prompt độc lập (phù hợp Gemini web qua CDP — không có system prompt,
JSON bắt buộc, không backticks). Task sau nhận output đã validate của task trước.
"""
import json
import re
import threading
import time
import uuid

from .technical import get_board, board_stats, technical_snapshot
from .collector import collect_flow_outputs
from . import context_builder as cb
from .market_technical import (market_snapshot, compute_regime,
                               sector_rotation, liquidity_concentration)
from .gemini_transport import open_session, parse_json_answer

_jobs: dict = {}

# 7 phần hội thoại (phần 0 thuần Python, 1-6 hỏi AI trong cùng 1 tab/phiên).
STEPS = [
    "Thu thập + kỹ thuật (Python thuần)",
    "Nạp ngữ cảnh vào phiên hội thoại",
    "Độ rộng & dòng tiền",
    "Kháng cự / hỗ trợ từng mã",
    "Nguyên nhân + bằng chứng",
    "Rủi ro & thiếu dữ liệu",
    "Tổng hợp + điểm theo dõi",
    # Ảnh 10: lượt cuối rút gọn TOÀN BỘ các phần trên cho người mới (mode Cơ bản).
    # Không sinh nhận định mới — chỉ tóm lược nội dung đã trả lời trong phiên.
    "Rút gọn cho người mới",
]

from modules.common.legal import DISCLAIMER, LEGAL_PROMPT_RULE, check_payload

JSON_RULE = ("\nQUY TẮC TRẢ LỜI (BẮT BUỘC):\n"
             "- Trả về DUY NHẤT một JSON hợp lệ, KHÔNG dùng backticks, "
             "không chữ nào ngoài JSON.\n"
             "- Viết tiếng Việt, giữ thuật ngữ tài chính tiếng Anh khi cần.\n"
             + LEGAL_PROMPT_RULE)

# Mã bằng chứng hợp lệ: [N1] [E2] [M3] [R-FPT] [TT-ACB] [CD-FPT]
_CITATION_RE = re.compile(r"\[((?:N|E|M|R-|TT-|CD-)[\w-]*)\]")


# ------------------------------------------------------------- prompt builders
def _fmt_board(b: dict) -> str:
    if not b.get("available"):
        return "Không có dữ liệu bảng giá."
    g = lambda rows: "; ".join(
        f"{r['symbol']} {r['chg_pct']:+.1f}% (KL {r['vol']:.0f}, NN ròng {r['foreign_net']:+.0f})"
        for r in rows)
    # tuổi cache: nếu là bản chụp cũ, nêu rõ thời điểm để AI biết độ tươi
    freshness = ("REALTIME" if b["live"]
                 else f"gần nhất (CACHE lúc {b.get('as_of') or '?'})")
    return (f"Phiên {freshness} — {b['n_symbols']} mã: "
            f"tăng {b['breadth']['up']} / giảm {b['breadth']['down']} / tham chiếu {b['breadth']['flat']}. "
            f"Khối ngoại ròng toàn bảng: {b['foreign_net_total']:+.0f}.\n"
            f"Top tăng: {g(b['top_gainers'])}.\nTop giảm: {g(b['top_losers'])}.")


def _shares_vn(v, signed: bool = False) -> str:
    """B9: khối lượng cổ phiếu → chuỗi dễ đọc (triệu/nghìn cp), rõ đơn vị."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "?"
    sign = "+" if (signed and v > 0) else ""
    a = abs(v)
    if a >= 1e6:
        return f"{sign}{v / 1e6:,.2f} triệu cp"
    if a >= 1e3:
        return f"{sign}{v / 1e3:,.1f} nghìn cp"
    return f"{sign}{v:,.0f} cp"


def _fmt_orderbook(b: dict, top_n: int = 15) -> str:
    """Sổ lệnh chi tiết: dư mua/bán 3 bậc + khối ngoại từng mã đáng chú ý."""
    if not b.get("available"):
        return "Không có dữ liệu sổ lệnh."
    rows = (b.get("top_gainers", []) + b.get("top_losers", []) +
            b.get("top_foreign_buy", []))
    seen, lines = set(), []
    for r in rows:
        if r["symbol"] in seen:
            continue
        seen.add(r["symbol"])
        br = r.get("book_ratio")
        # B9: KL & khối ngoại đưa vào prompt dưới dạng đã format (triệu cp), rõ đơn vị
        lines.append(
            f"{r['symbol']}: {r['chg_pct']:+.1f}%, KL {_shares_vn(r.get('vol') or 0)}, "
            f"NN ròng {_shares_vn(r['foreign_net'], signed=True)}, dư mua/bán ×{br if br is not None else '?'}")
        if len(lines) >= top_n:
            break
    return "\n".join(lines)


def _fmt_fund_detail(pack: dict, top_n: int = 20) -> str:
    """BCTC chi tiết từng mã + so ngành (từ context_builder.fundamentals_pack)."""
    lines = []
    peers = pack.get("peers", {})
    for d in pack.get("details", [])[:top_n]:
        s = d["symbol"]
        rev_q = "; ".join(f"{q['period']} {q['value_bn']}" for q in d["revenue_quarters"][:4])
        pos = peers.get(s, {}).get("position", {})
        pos_txt = ", ".join(f"{k} {v}" for k, v in pos.items()) if pos else "—"
        lines.append(
            f"{s}: DT quý [{rev_q or 'n/a'}]; DT YoY {d['revenue_yoy_year']}, "
            f"LNST YoY {d['profit_yoy_year']}; biên ròng {d['net_margin_pct']}, "
            f"ROE {d['roe_pct']}, Nợ/VCSH {d['debt_to_equity']}; "
            f"P/E {d['pe']}, P/B {d['pb']}, EV/EBITDA {d['ev_ebitda']}; so ngành: {pos_txt}")
    return "\n".join(lines) or "Không có BCTC chi tiết."


def _fmt_news_detailed(pack: dict) -> str:
    """Tin CBTT kèm tóm tắt nội dung (không chỉ tiêu đề)."""
    lines = []
    for n in pack.get("items", []):
        summ = f" — {n['summary']}" if n.get("summary") else ""
        lines.append(f"[{n['id']}] ({n['date']}) {n['symbol']}: {n['title']}{summ}")
    return "\n".join(lines) or "Không có tin."


def _fmt_rss(pack: dict) -> str:
    if not pack.get("available"):
        return f"(RSS không khả dụng: {pack.get('reason', '?')})"
    lines = [f"[{a['id']}] ({a['date']}) {a['symbol']} · {a['press']}: {a['title']}"
             for a in pack.get("items", [])]
    return "\n".join(lines) or "Không có tin báo chí."


def _fmt_dividends(pack: dict) -> str:
    def fmt(items):
        return "; ".join(
            f"[{e['id']}] {e['symbol']} {e['event']} ({e['date']}"
            + (f", cổ tức {e['value_per_share']}" if e.get("value_per_share") else "") + ")"
            for e in items) or "không"
    return (f"Sự kiện SẮP TỚI (lịch chốt quyền): {fmt(pack.get('upcoming', []))}\n"
            f"Gần đây: {fmt(pack.get('recent', []))}")


def _fmt_macro(pack: dict) -> str:
    if not pack.get("available"):
        return f"(Vĩ mô không khả dụng: {pack.get('reason', '?')})"
    idx = pack.get("indexes", {})
    parts = []
    for code, v in idx.items():
        if v.get("ok"):
            parts.append(f"{code} {v.get('latest')} ({v.get('pct_1d', 0):+.2f}% 1D, "
                         f"{v.get('pct_ytd', 0):+.2f}% YTD, thanh khoản {v.get('liquidity_value', 0)/1e9:,.0f} tỷ)")
    fx = pack.get("fx", {})
    ind = pack.get("indicators", {})
    return (f"Chỉ số THẬT: {'; '.join(parts) or '—'}.\n"
            f"Tỷ giá USD/VND bán {fx.get('usd_sell')} (nguồn {fx.get('source')}).\n"
            f"GDP {ind.get('gdp_growth_yoy', {}).get('value')}% · "
            f"CPI {ind.get('cpi_yoy', {}).get('value')}% "
            f"(nguồn {ind.get('source')} — cập nhật tay).")


def _fmt_market(mkt: dict) -> str:
    """Bức tranh TOÀN thị trường (~700 mã HOSE+HNX) — aggregates từ market_technical."""
    if not mkt.get("available"):
        return "(Chưa có dữ liệu toàn thị trường — chạy P6/P7 bên Crawl Data.)"
    b = mkt["breadth"]
    cov = mkt.get("coverage", {})
    lines = [
        f"PHẠM VI DỮ LIỆU: {cov.get('n_symbols')} mã {cov.get('exchanges')} "
        f"(cập nhật {cov.get('as_of')}). Đây là TOÀN thị trường, không chỉ nhóm dẫn dắt.",
        f"Độ rộng toàn thị trường: {b['pct_above_ma20']}% mã trên MA20, "
        f"{b['pct_above_ma50']}% trên MA50; phiên gần nhất {b['n_up_1d']} tăng / "
        f"{b['n_down_1d']} giảm; {b['new_high_52w']} mã sát đỉnh 52 tuần / "
        f"{b['new_low_52w']} mã sát đáy 52 tuần."]
    for code, v in (mkt.get("indexes") or {}).items():
        lines.append(
            f"{code}: {v['close']} ({v['pct_1d']:+.2f}% 1D, {v.get('pct_5d', 0):+.2f}% 5D, "
            f"{v.get('pct_ytd', 0):+.2f}% YTD); thanh khoản {v.get('liquidity_last_bn')} tỷ "
            f"(TB20 {v.get('liquidity_avg20_bn')} tỷ).")
    lines.append("Theo NGÀNH (n mã · %>MA20 · trung vị %1D · trung vị %20D · sát đỉnh/sát đáy 52W):")
    for s in (mkt.get("sectors") or [])[:19]:
        lines.append(
            f"- {s['sector']}: {s['n']} mã · {s['pct_above_ma20']}% · "
            f"{s['median_chg_1d']:+.2f}% · "
            f"{s['median_chg_20d'] if s['median_chg_20d'] is not None else '?'}% · "
            f"{s['n_near_high']}/{s['n_near_low']}")
    return "\n".join(lines)


def _fmt_regime(reg: dict, liq: dict) -> str:
    """Chế độ thị trường + bảng tín hiệu con (minh bạch) + tập trung thanh khoản."""
    if not reg.get("available"):
        return "(Chưa đủ dữ liệu xác định chế độ thị trường.)"
    lines = [
        f"CHẾ ĐỘ THỊ TRƯỜNG: {reg['label']} (điểm {reg['score']:+d}/{reg['max_score']} "
        f"tín hiệu). {reg['note']}",
        "Tín hiệu con (đạt/không — mỗi tín hiệu ±1 điểm):"]
    for s in reg["signals"]:
        mark = "✓" if s["dat"] else ("✗" if s["dat"] is False else "–")
        lines.append(f"  {mark} {s['ten']}: {s['chi_tiet']}")
    if liq.get("available"):
        lines.append(
            f"Tập trung thanh khoản: top-10 mã chiếm {liq['top10_pct']}% GTGD toàn "
            f"thị trường (HHI {liq['hhi']:.0f}). {liq['note']}")
    return "\n".join(lines)


def _fmt_market_news(items: list[dict]) -> str:
    return "\n".join(f"[{n['id']}] ({n['date']}) {n['press']}: {n['title']}"
                     for n in items) or "Không có tin thị trường."


def _fmt_tech(t: dict, top_n: int = 14) -> str:
    lines = [
        f"Tính đến {t['as_of']} ({t['n_symbols']} mã lớn). Vị trí so kháng cự/hỗ trợ: "
        f"SÁT KHÁNG CỰ: {', '.join(t['sr_at_resistance']) or 'không'}; "
        f"VỀ HỖ TRỢ: {', '.join(t['sr_at_support']) or 'không'}; "
        f"VƯỢT ĐỈNH: {', '.join(t['sr_breakout']) or 'không'}. "
        f"Độ rộng: {t['breadth_ma20_pct']}% trên MA20, "
        f"{t['breadth_up20d_pct']}% tăng 20 phiên. "
        f"RSI>70: {', '.join(t['overbought_rsi70']) or 'không'}; "
        f"RSI<30: {', '.join(t['oversold_rsi30']) or 'không'}."]
    for x in t["symbols"][:top_n]:
        vbp = ", ".join(f"vùng KL dày {n['price']} ({n['vol_share_pct']}%)"
                        for n in (x.get("vbp_nodes") or [])[:1])
        lines.append(
            f"{x['symbol']}: giá {x['close']:.2f} — {x['position']}; "
            f"hỗ trợ gần {x['nearest_support']} (-{x['dist_support_pct']}%), "
            f"kháng cự gần {x['nearest_resistance']} (+{x['dist_resistance_pct']}%); "
            f"{vbp}; RSI {x['rsi14']}, 20 phiên {x['chg_20d_pct']:+.1f}%, "
            f"KL 5/60 ngày ×{x['vol_5d_vs_60d']}")
    return "\n".join(lines)


def _fmt_fund(f: dict) -> str:
    parts = []
    if "macro" in f:
        m = f["macro"]
        parts.append(
            f"Vĩ mô: GDP {m['gdp_forecast']['year']} dự báo {m['gdp_forecast']['mean']}% "
            f"(KTC80 {m['gdp_forecast']['range80']}), CPI {m['cpi_forecast']['mean']}%. "
            f"GDP thực tế gần nhất: {m['gdp_last_actual']}.")
    if "market_range" in f:
        k = f["market_range"]
        b, rp = k["band"], k["return_pct"]
        parts.append(
            f"VNINDEX hiện {k['index_now']}. DẢI THỐNG KÊ 30 phiên (phân phối lịch sử "
            f"{k['n_samples']} mẫu, KHÔNG phải dự báo): P5 {b['p5']} / trung vị {b['p50']} "
            f"/ P95 {b['p95']} điểm (lợi suất {rp['p5']}%…+{rp['p95']}%).")
    if "health_by_sector" in f:
        top3 = f["health_by_sector"][:3]
        parts.append("Sức khỏe ngành (điểm TB /100): " + "; ".join(
            f"{s['sector']} {s['avg_health']} ({s['n']} DN, {s['n_danger']} nguy hiểm)"
            for s in top3))
        parts.append(f"Top khỏe: {f['health_top5']}. Yếu nhất: {f['health_bottom5']}.")
    return "\n".join(parts)


# ------------------------------------------------- prompt từng phần hội thoại
# Mỗi prompt CHỈ tập trung 1 chủ đề. Ngữ cảnh (bảng giá, S/R, cơ bản, tin...)
# đã nạp ở phần 1 nên Gemini web tự nhớ — các phần sau KHÔNG nhắc lại dữ liệu.
def _prompt_context(ctx_txt: str, id_catalog: str) -> str:
    return (
        "Đây là phiên phân tích TỔNG QUAN THỊ TRƯỜNG chứng khoán Việt Nam. "
        "Tôi sẽ nạp toàn bộ DỮ LIỆU NGỮ CẢNH một lần, rồi hỏi bạn từng phần nhỏ. "
        "Nhiệm vụ bây giờ: ĐỌC KỸ và GHI NHỚ dữ liệu dưới đây, chưa phân tích.\n\n"
        f"{ctx_txt}\n\n"
        f"[DANH MỤC MÃ BẰNG CHỨNG hợp lệ — chỉ được trích các id này]\n{id_catalog}\n"
        + JSON_RULE +
        'Chỉ xác nhận đã nhận: {"da_nhan": true, "thieu_gi": ["dữ liệu bạn thấy thiếu/mâu thuẫn, rỗng nếu đủ"]}')


def _prompt_flow(pillar: str, schema: str) -> str:
    # Ảnh 8: chèn bảng tên ngành VI để AI không trả "Banks / Food & Beverage".
    from modules.common.sector_vi import prompt_rule
    return (pillar + "\nDùng đúng dữ liệu ngữ cảnh đã nạp ở đầu phiên (không bịa số, "
            "không dùng thông tin ngoài). Mọi mã bằng chứng phải nằm trong danh mục id hợp lệ."
            + prompt_rule()
            + JSON_RULE + "Schema: " + schema)


_P2 = _prompt_flow(
    "PHẦN — ĐỘ RỘNG & DÒNG TIỀN TOÀN THỊ TRƯỜNG: phân tích ở TẦNG THỊ TRƯỜNG và "
    "TẦNG NGÀNH (dùng khối [TOÀN THỊ TRƯỜNG]): độ rộng (% trên MA20/50, mã tăng/giảm, "
    "sát đỉnh/sát đáy 52W), ngành mạnh/yếu nhất, thanh khoản chỉ số so TB20, dòng tiền "
    "khối ngoại. ĐỐI CHIẾU độ rộng với CHẾ ĐỘ THỊ TRƯỜNG (khối [CHẾ ĐỘ THỊ TRƯỜNG]): "
    "độ rộng có xác nhận nhãn chế độ không, hay phân kỳ. KHÔNG sa đà từng mã lẻ — mã "
    "chỉ nêu làm ví dụ đại diện ngành.",
    '{"cung_cau": ["2-4 quan sát tầng thị trường kèm số"], '
    '"do_rong_thi_truong": "nhận xét độ rộng TOÀN thị trường bằng con số", '
    '"nganh_manh_yeu": [{"nganh": "...", "nhan_xet": "kèm số %MA20, trung vị %"}], '
    '"dong_tien_khoi_ngoai": "nhận xét khối ngoại kèm số"}')

_P3 = _prompt_flow(
    "PHẦN — NHÓM DẪN DẮT (kháng cự/hỗ trợ): với các mã trong khối [NHÓM DẪN DẮT], nêu "
    "vị trí giá so vùng kháng cự/hỗ trợ, vùng khối lượng dày (VBP), khoảng cách %. "
    "Đây là các mã vốn hóa lớn ảnh hưởng chỉ số — nêu rõ hàm ý của chúng lên VN30/VNINDEX.",
    '{"khang_cu_ho_tro": ["3-8 quan sát, nêu đúng mức giá và khoảng cách %"], '
    '"tin_hieu_dang_chu_y": [{"symbol": "...", "tin_hieu": "vị trí S/R + tín hiệu + số"}], '
    '"ham_y_chi_so": "1-2 câu: nhóm dẫn dắt đang kéo hay ghìm chỉ số, kèm số"}')

_P4 = _prompt_flow(
    # Ảnh 13: bản cũ chỉ ra 5 gạch đầu dòng 1 câu — mỏng so với ngữ cảnh đã nạp.
    # Bản này ép: cơ chế tác động, ≥2 bằng chứng TỪ 2 LỚP KHÁC NHAU, và dữ kiện
    # NGƯỢC chiều (phản đề) — đúng tinh thần RAG: chỉ dữ kiện, không kết luận.
    "PHẦN — NGUYÊN NHÂN + BẰNG CHỨNG: lý giải nguyên nhân cho các quan sát ở 2 phần "
    "trước, ưu tiên nguyên nhân TẦNG THỊ TRƯỜNG (tin [M..] vĩ mô/khối ngoại/lãi suất) "
    "trước nguyên nhân mã lẻ. Nêu TỐI THIỂU 5 nguyên nhân, xếp theo tầm ảnh hưởng giảm dần.\n"
    "LUẬT BẮT BUỘC cho MỖI nguyên nhân:\n"
    "1) 'co_che': 2-3 câu nêu CHUỖI TÁC ĐỘNG — vì sao xảy ra → truyền dẫn qua kênh nào "
    "→ dẫn tới con số nào quan sát được. Phải có ít nhất 1 con số cụ thể.\n"
    "2) 'bang_chung': ÍT NHẤT 2 mã, và phải thuộc ÍT NHẤT 2 LỚP KHÁC NHAU trong 4 lớp: "
    "[M..] vĩ mô/thị trường · [N..][E..][R-..] tin & sự kiện · [TT-..] kỹ thuật bảng giá · "
    "[CD-..] báo cáo tài chính. Nếu thật sự chỉ có 1 lớp, ghi rõ ở 'do_tin_cay_vi_sao'.\n"
    "3) 'phan_de': dữ kiện NGƯỢC chiều nếu tồn tại (kèm mã bằng chứng); không có thì để null. "
    "Đây là phần chống thiên kiến — hãy thực sự tìm.\n"
    "4) 'do_tin_cay' + 'do_tin_cay_vi_sao': 1 câu vì sao ở mức đó.\n"
    "TRÌNH BÀY: 'quan_sat' và 'phan_de' ≤160 ký tự; 'co_che' 2-3 câu. Dòng đối chiếu "
    "MỞ ĐẦU bằng mã CK (VD 'FPT: ...') khi nói về 1 mã cụ thể. "
    "Chỉ MÔ TẢ dữ kiện — KHÔNG kết luận đúng/sai, KHÔNG quy kết thao túng.",
    '{"nguyen_nhan": [{"quan_sat": "≤160 ký tự", '
    '"co_che": "2-3 câu: vì sao → qua kênh nào → dẫn tới số nào", '
    '"bang_chung": ["M1","CD-ACB"], '
    '"phan_de": "dữ kiện ngược chiều kèm [mã] hoặc null", '
    '"do_tin_cay": "cao|trung bình|thấp", "do_tin_cay_vi_sao": "1 câu"}], '
    '"doi_chieu_luong_khac": [{"noi_dung": "MÃ: ≤160 ký tự", "bang_chung": ["TT-..","CD-.."]}]}')

_P5 = _prompt_flow(
    "PHẦN — RỦI RO & THIẾU DỮ LIỆU: rủi ro tiềm ẩn người dùng dễ bỏ qua (kèm bằng chứng "
    "và mức độ) + điều muốn kết luận nhưng chưa đủ bằng chứng.",
    '{"rui_ro_tiem_an": [{"rui_ro": "...", "bang_chung": ["..."], "muc_do": "cao|trung bình|thấp"}], '
    '"thieu_du_lieu": ["..."]}')

_P6 = _prompt_flow(
    "PHẦN — TỔNG HỢP: kết luận toàn cảnh cho nhà đầu tư cá nhân, dựa trên các phần đã "
    "phân tích. Mở đầu bằng CHẾ ĐỘ THỊ TRƯỜNG (nhãn + điểm tín hiệu, khối [CHẾ ĐỘ THỊ "
    "TRƯỜNG]) rồi tới phạm vi dữ liệu (số mã, sàn, ngày cập nhật — lấy từ khối "
    "[TOÀN THỊ TRƯỜNG]). Nêu rõ độ tươi dữ liệu (nếu bảng giá là cache thì nói). Giữ mã "
    "bằng chứng khi nhắc lại. KHÔNG dự phóng kịch bản xác suất / khuyến nghị mua-bán. "
    "TRÌNH BÀY: mỗi phần tử 'diem_nhan'/'theo_doi' là 1 Ý GỌN ≤160 ký tự (KHÔNG đoạn dài).",
    '{"tieu_de": "tiêu đề 1 dòng", "tong_quan": "4-6 câu tổng hợp, dẫn bằng chứng", '
    '"diem_nhan": ["3-5 điểm nhấn ≤160 ký tự, kèm số + bằng chứng"], '
    '"theo_doi": ["3-5 dữ kiện/sự kiện đáng theo dõi tuần tới, KHÔNG khuyến nghị mua/bán"], '
    f'"disclaimer": "{DISCLAIMER}"}}')

# Ảnh 10 · PHẦN 7 — RÚT GỌN CHO NGƯỜI MỚI.
# Chạy trong CÙNG phiên hội thoại nên AI đã có toàn bộ nội dung 6 phần trước;
# nhiệm vụ duy nhất là rút gọn, KHÔNG được thêm nhận định/số liệu mới.
_P7 = _prompt_flow(
    "PHẦN — RÚT GỌN CHO NGƯỜI MỚI: dựa trên CHÍNH các câu trả lời bạn đã đưa ra ở "
    "những phần trước trong phiên này, viết bản rút gọn cho người CHƯA có kiến thức "
    "đầu tư. Quy tắc: (1) TUYỆT ĐỐI không thêm nhận định mới, không thêm số liệu mới — "
    "chỉ rút gọn cái đã có; (2) dùng từ ngữ đời thường, hạn chế thuật ngữ, nếu buộc "
    "phải dùng thì giải thích ngắn trong ngoặc; (3) giữ nguyên mã bằng chứng dạng [..] "
    "nếu câu đó vốn có; (4) 'y_chinh' tối đa 2 câu, mỗi 'gach_dau_dong' ≤ 18 từ.",
    '{"cung_cau": {"y_chinh": "...", "gach_dau_dong": ["...", "..."]}, '
    '"khang_cu_ho_tro": {"y_chinh": "...", "gach_dau_dong": ["..."]}, '
    '"nguyen_nhan": {"y_chinh": "...", "gach_dau_dong": ["..."]}, '
    '"rui_ro": {"y_chinh": "...", "gach_dau_dong": ["..."]}, '
    '"summary": {"y_chinh": "...", "gach_dau_dong": ["..."]}}')


# ---------------------------------------------------------------- job engine
def _set_step(job, idx, status, detail=None):
    job["steps"][idx]["status"] = status
    if detail:
        job["steps"][idx]["detail"] = detail
    job["updated_at"] = time.time()


def _valid_id_set(news, flows, rss_items) -> set:
    ids = {n["id"] for n in news} | {f["id"] for f in flows}
    ids |= {a["id"] for a in rss_items}
    return ids


_BARE_ID_RE = re.compile(r"^(?:N|E|M|R-|TT-|CD-)[\w-]*$")


def _normalize_summary_lists(summary: dict) -> None:
    """B2: ép diem_nhan / theo_doi về list[str] — AI đôi khi trả object
    {y|text|noi_dung, bang_chung[]} thay vì string → '[object Object]' ở JS."""
    def _to_str(item) -> str:
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            text = item.get("y") or item.get("text") or item.get("noi_dung") or item.get("diem") or ""
            ev = item.get("bang_chung") or item.get("evidence") or []
            if ev:
                ids = ", ".join(str(e) for e in ev[:4])
                return f"{text} [{ids}]" if text else ids
            return str(text)
        return str(item)

    for field in ("diem_nhan", "theo_doi"):
        raw = summary.get(field)
        if isinstance(raw, list):
            summary[field] = [_to_str(x) for x in raw if x not in (None, "")]


def _clean_brief(b: dict) -> dict:
    """Ảnh 10: chuẩn hoá 1 khối rút gọn về đúng {y_chinh: str, gach_dau_dong: [str]}.

    AI có thể trả bullet dạng object hoặc trả quá dài/quá nhiều — ép về string và
    cắt còn tối đa 3 gạch đầu dòng để mode Cơ bản luôn ngắn đúng ý đồ (≤5 dòng).
    Pháp lý đã được _ask_part quét bằng check_payload trước khi tới đây.
    """
    def _s(v) -> str:
        if isinstance(v, str):
            return v.strip()
        if isinstance(v, dict):
            return str(v.get("y") or v.get("text") or v.get("noi_dung") or "").strip()
        return str(v or "").strip()

    bullets = b.get("gach_dau_dong")
    if not isinstance(bullets, list):
        bullets = []
    bullets = [x for x in (_s(x) for x in bullets) if x][:3]
    return {"y_chinh": _s(b.get("y_chinh")), "gach_dau_dong": bullets}


def _scan_citations(obj, valid: set) -> list[str]:
    """Tìm mọi mã bằng chứng trong 1 object AI mà KHÔNG nằm trong tập id hợp lệ.

    Hai dạng: (a) [N1] trong text tự do; (b) id TRẦN trong mảng "bang_chung"
    (schema AI trả ["N1","TT-ACB"] không có ngoặc)."""
    bad = set()

    def walk(o, in_bangchung=False):
        if isinstance(o, str):
            for m in _CITATION_RE.findall(o):        # dạng [N1] trong text
                if m not in valid:
                    bad.add(m)
            if in_bangchung and _BARE_ID_RE.match(o.strip()) and o.strip() not in valid:
                bad.add(o.strip())                    # id trần trong bang_chung
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(v, in_bangchung=(k == "bang_chung"))
        elif isinstance(o, list):
            for v in o:
                walk(v, in_bangchung=in_bangchung)
    walk(obj)
    return sorted(bad)


def _ask_part(session, prompt: str, valid_ids: set, retries: int = 1,
              lenient: bool = False) -> dict:
    """Hỏi 1 phần trong phiên: parse JSON → quét từ cấm pháp lý → kiểm tra id
    bằng chứng. Lỗi cú pháp/từ cấm → feedback vào CÙNG hội thoại (rẻ, không gửi
    lại ngữ cảnh). Trả dict kèm _meta {invalid_citations}.

    lenient=True (dùng cho phần NẠP NGỮ CẢNH — chỉ để mồi hội thoại): nếu Gemini
    trả lời văn xuôi thay vì JSON, KHÔNG coi là lỗi — dữ liệu vẫn đã vào ngữ cảnh."""
    feedback = ""
    last_err = None
    for _ in range(retries + 1):
        raw = session.ask(prompt + feedback)
        try:
            data = parse_json_answer(raw)
        except Exception as e:
            last_err = f"JSON lỗi cú pháp: {str(e)[:120]}"
            if lenient:
                return {"da_nhan": True, "raw": (raw or "")[:200], "_meta": {}}
            feedback = ("\n\nLƯU Ý: câu trước JSON sai cú pháp. Trả lại ĐÚNG JSON, "
                        "escape dấu nháy kép, không backticks, không chữ ngoài JSON.")
            continue
        banned = check_payload(data)
        if banned:
            last_err = f"dùng từ cấm pháp lý: {', '.join(banned)}"
            feedback = (f"\n\nLƯU Ý: câu trước dùng từ bị cấm ({', '.join(banned)}). "
                        "Chỉ MÔ TẢ dữ kiện và rủi ro, KHÔNG khuyến nghị mua/bán/nắm giữ.")
            continue
        bad_ids = _scan_citations(data, valid_ids)
        data["_meta"] = {"invalid_citations": bad_ids}
        return data
    if lenient:
        return {"da_nhan": True, "_meta": {}}
    raise RuntimeError(last_err or "phần này thất bại")


def _run_overview(job_id: str, db_path: str, prefer: str):
    job = _jobs[job_id]
    job["parts"] = {}
    session = None
    try:
        # ---- Phần 0: thu thập + kỹ thuật (thuần Python) ----
        _set_step(job, 0, "running")
        board = get_board()
        board_s = board_stats(board)
        tech = technical_snapshot(db_path)
        news_pack = cb.news_detailed(db_path, limit=30)
        news = news_pack["items"]
        flows, flow_meta = collect_flow_outputs(db_path)
        priced = [x["symbol"] for x in tech.get("symbols", [])]
        fund_pack = cb.fundamentals_pack(db_path)
        div_pack = cb.dividend_events(db_path, limit=15)
        # top movers cho RSS: 10 mã biến động mạnh nhất phiên
        movers = [r["symbol"] for r in (board_s.get("top_gainers", []) +
                                        board_s.get("top_losers", []))][:10]
        rss_pack = cb.rss_pack(db_path, movers, per_symbol=3) if movers else {"items": [], "available": False}
        macro_pack = cb.macro_pack()
        # bức tranh TOÀN thị trường (~700 mã HOSE+HNX, P6/P7 Crawl Data)
        mkt = market_snapshot(db_path)
        m_news = mkt.get("market_news", [])
        # chế độ thị trường + luân chuyển ngành + tập trung thanh khoản (thuần Python)
        regime = compute_regime(db_path)
        rotation = sector_rotation(db_path)
        liq_conc = liquidity_concentration(db_path, board.get("rows") or None)

        job["data"] = {"board": board_s, "technical": tech, "news": news,
                       "market": mkt, "market_news": m_news,
                       "regime": regime, "rotation": rotation,
                       "liquidity_concentration": liq_conc,
                       "flows": flows, "rss": rss_pack.get("items", []),
                       "dividends": div_pack, "macro": macro_pack,
                       "sources": {
                           "board": {"source": board_s.get("source"), "as_of": board.get("as_of"),
                                     "stale": not board_s.get("live")},
                           "news": news_pack.get("meta"),
                           "fundamentals": fund_pack.get("meta"),
                           "macro": macro_pack.get("meta"),
                           "rss": rss_pack.get("meta"),
                           # ĐÃ THÊM: trước đây flow_meta chỉ dùng nội bộ cho
                           # dòng log bước 0, không lọt tới job["data"] — UI
                           # đọc /api/overview/status không có cách nào biết
                           # nguồn TT- (S/R quét Gemini) phủ được bao nhiêu mã.
                           "flows": flow_meta,
                       }}
        cov = mkt.get("coverage", {})
        _set_step(job, 0, "done",
                  f"toàn thị trường {cov.get('n_symbols', 0)} mã HOSE+HNX · bảng giá "
                  f"{'LIVE' if board_s.get('live') else 'cache'} {board_s.get('n_symbols', 0)} mã · "
                  f"{len(news)} tin + {len(m_news)} tin thị trường · {len(flows)} luồng khác "
                  f"({flow_meta.get('skipped', 0)} bỏ) · {len(rss_pack.get('items', []))} RSS")

        valid_ids = _valid_id_set(news, flows, rss_pack.get("items", []))
        valid_ids |= {n["id"] for n in m_news}

        # ---- mở phiên hội thoại (CDP 1 tab, hoặc API stateful) ----
        _set_step(job, 1, "running")
        session = open_session(prefer)
        job["transport"] = session.transport

        # gom ngữ cảnh giàu, nạp 1 lần
        fl_txt = "\n".join(f"[{f['id']}] ({f['date']}) {f['symbol']} — {f['type']}: {f['title']}"
                           for f in flows)
        # ĐÃ THÊM: nói thẳng độ phủ/độ cũ của nguồn TT- (quét Gemini kỹ thuật ở
        # app Bảng giá) — nếu không, vài mã [TT-mã] lẻ tẻ nằm cạnh hàng loạt
        # [CD-mã]/[N..] khác dễ bị AI đọc nhầm thành "đã quét kỹ thuật đều
        # khắp thị trường". Con số lấy thẳng từ collect_flow_outputs(), không
        # tự đặt ngưỡng "cũ" — chỉ báo cáo trung thực ngày cũ nhất/mới nhất.
        n_universe = cov.get("n_symbols", 0)
        tt_n = flow_meta.get("tt_count", 0)
        tt_note = (
            f"[LƯU Ý ĐỘ PHỦ NGUỒN TT-] Phân tích kỹ thuật S/R quét bằng Gemini (app "
            f"Bảng giá) chỉ có cho {tt_n}/{n_universe or '?'} mã, bản ghi từ "
            f"{flow_meta.get('tt_oldest') or '—'} đến {flow_meta.get('tt_newest') or '—'}. "
            f"KHÔNG suy rộng vài mã này thành nhận định kỹ thuật cho toàn thị trường."
            if tt_n else
            "[LƯU Ý ĐỘ PHỦ NGUỒN TT-] Không có mã nào có phân tích kỹ thuật quét Gemini "
            "trong kỳ này — bỏ qua loại bằng chứng [TT-mã]."
        )
        ctx_txt = (
            f"[CHẾ ĐỘ THỊ TRƯỜNG]\n{_fmt_regime(regime, liq_conc)}\n\n"
            f"[TOÀN THỊ TRƯỜNG — độ rộng, ngành, chỉ số thật]\n{_fmt_market(mkt)}\n\n"
            f"[TIN CẤP THỊ TRƯỜNG]\n{_fmt_market_news(m_news)}\n\n"
            f"[BẢNG GIÁ + SỔ LỆNH]\n{_fmt_board(board_s)}\n{_fmt_orderbook(board_s)}\n\n"
            f"[NHÓM DẪN DẮT — KHÁNG CỰ/HỖ TRỢ/VBP chi tiết]\n{_fmt_tech(tech, top_n=len(priced) or 30)}\n\n"
            f"[BCTC CHI TIẾT + SO NGÀNH]\n{_fmt_fund_detail(fund_pack)}\n\n"
            f"[VĨ MÔ & CHỈ SỐ THẬT]\n{_fmt_macro(macro_pack)}\n\n"
            f"[TIN CBTT]\n{_fmt_news_detailed(news_pack)}\n\n"
            f"[TIN BÁO CHÍ RSS]\n{_fmt_rss(rss_pack)}\n\n"
            f"[CỔ TỨC & SỰ KIỆN]\n{_fmt_dividends(div_pack)}\n\n"
            f"[KẾT QUẢ LUỒNG KHÁC]\n{fl_txt or 'chưa có'}\n{tt_note}")
        id_catalog = ", ".join(sorted(valid_ids)) or "(chưa có mã bằng chứng)"
        ack = _ask_part(session, _prompt_context(ctx_txt, id_catalog), valid_ids,
                        lenient=True)
        job["parts"]["context"] = ack
        _set_step(job, 1, "done",
                  f"kênh {session.transport} · thiếu: {', '.join(ack.get('thieu_gi', [])) or 'không'}")

        # ---- các phần phân tích tuần tự; phần lỗi KHÔNG giết job ----
        # FAIL-FAST: mỗi phần chỉ gửi lại tối đa 1 lần (retries=1 trong _ask_part);
        # 2 phần LIÊN TIẾP lỗi → ngắt mạch (kênh AI không ổn định, gửi tiếp chỉ tốn
        # thời gian); tổng thời gian AI vượt ngân sách → dừng các phần còn lại.
        AI_BUDGET_S = 360
        ai_t0 = time.time()
        consec_fail = 0
        tripped = None   # lý do ngắt mạch (None = bình thường)
        plan = [(2, _P2, "cung_cau"), (3, _P3, "khang_cu_ho_tro"),
                (4, _P4, "nguyen_nhan"), (5, _P5, "rui_ro")]
        for idx, prompt, key in plan:
            if tripped:
                job["parts"][key] = {"error": f"bỏ qua — {tripped}"}
                _set_step(job, idx, "error", f"bỏ qua — {tripped}")
                continue
            if time.time() - ai_t0 > AI_BUDGET_S:
                tripped = f"quá ngân sách thời gian AI ({AI_BUDGET_S}s)"
                job["parts"][key] = {"error": f"bỏ qua — {tripped}"}
                _set_step(job, idx, "error", f"bỏ qua — {tripped}")
                continue
            _set_step(job, idx, "running")
            try:
                t0 = time.time()
                part = _ask_part(session, prompt, valid_ids)
                job["parts"][key] = part
                consec_fail = 0
                bad = part.get("_meta", {}).get("invalid_citations", [])
                _set_step(job, idx, "done",
                          f"{round(time.time() - t0)}s"
                          + (f" · ⚠ {len(bad)} trích dẫn không hợp lệ" if bad else ""))
            except Exception as e:
                job["parts"][key] = {"error": str(e)[:300]}
                _set_step(job, idx, "error", str(e)[:200])
                consec_fail += 1
                if consec_fail >= 2:
                    tripped = "kênh AI không ổn định (2 phần liên tiếp lỗi)"

        # ---- phần 6 tổng hợp: cần tối thiểu phần 2-4 chạy được ----
        _set_step(job, 6, "running")
        core_ok = sum(1 for k in ("cung_cau", "khang_cu_ho_tro", "nguyen_nhan")
                      if "error" not in job["parts"].get(k, {"error": 1}))
        if core_ok < 2:
            _set_step(job, 6, "error", "thiếu quá nhiều phần lõi để tổng hợp")
            job["status"] = "error"
            job["error"] = "Các phần lõi (độ rộng/S-R/nguyên nhân) đa số lỗi — không tổng hợp."
        else:
            try:
                summary = _ask_part(session, _P6, valid_ids)
                _normalize_summary_lists(summary)  # B2: ép diem_nhan/theo_doi về string
                job["parts"]["summary"] = summary
                _set_step(job, 6, "done")
                job["status"] = "done"
            except Exception as e:
                job["parts"]["summary"] = {"error": str(e)[:300]}
                _set_step(job, 6, "error", str(e)[:200])
                job["status"] = "error"
                job["error"] = f"Tổng hợp lỗi: {str(e)[:200]}"

        # ---- phần 7 (ảnh 10): rút gọn cho người mới ----
        # Chạy KHÔNG chặn kết quả: lỗi ở đây chỉ mất bản rút gọn, mode Cơ bản sẽ
        # rơi về bản đầy đủ. Không được biến job đang "done" thành "error".
        if job["status"] == "done":
            _set_step(job, 7, "running")
            try:
                brief = _ask_part(session, _P7, valid_ids)
                brief.pop("_meta", None)
                # gắn bản rút gọn vào ĐÚNG phần tương ứng để UI đọc cùng chỗ
                attached = 0
                for key in ("cung_cau", "khang_cu_ho_tro", "nguyen_nhan", "rui_ro", "summary"):
                    b = brief.get(key)
                    part = job["parts"].get(key)
                    if isinstance(b, dict) and isinstance(part, dict) and "error" not in part:
                        part["brief"] = _clean_brief(b)
                        attached += 1
                _set_step(job, 7, "done" if attached else "error",
                          None if attached else "AI không trả đúng schema rút gọn")
            except Exception as e:
                # thất bại êm: giữ job done, UI tự fallback bản đầy đủ
                _set_step(job, 7, "error", str(e)[:200])
        else:
            _set_step(job, 7, "error", "bỏ qua — phần tổng hợp chưa xong")

        # tổng hợp cờ trích dẫn sai toàn job (cho UI banner)
        all_bad = []
        for p in job["parts"].values():
            all_bad += (p.get("_meta", {}) or {}).get("invalid_citations", [])
        job["invalid_citations"] = sorted(set(all_bad))
    except Exception as e:
        for s in job["steps"]:
            if s["status"] == "running":
                s["status"] = "error"
                s["detail"] = str(e)[:300]
        job["status"] = "error"
        job["error"] = str(e)[:500]
    finally:
        if session is not None:
            session.close()   # luôn đóng tab dù thành công hay lỗi
        job["updated_at"] = time.time()


def start_overview(db_path: str, prefer: str = "auto") -> str:
    job_id = uuid.uuid4().hex[:10]
    _jobs[job_id] = {
        "id": job_id, "status": "running",
        "steps": [{"name": n, "status": "pending"} for n in STEPS],
        "created_at": time.time(), "updated_at": time.time(),
    }
    threading.Thread(target=_run_overview, args=(job_id, db_path, prefer),
                     daemon=True).start()
    return job_id


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)
