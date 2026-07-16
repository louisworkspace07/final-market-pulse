# -*- coding: utf-8 -*-
"""Market Pulse — Gateway hợp nhất.

Phục vụ dashboard tổng (static/) + API đọc kết quả pipeline + điều hướng
sang 4 ứng dụng thành phần (EconoLens, Crawl Data, FinPulse, Bảng giá realtime).

Chạy:  python gateway/app.py   → http://localhost:9999
"""
import json
import os
import subprocess
import sys
import time

from flask import Flask, Response, abort, jsonify, render_template, request

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
DATA = os.path.join(BASE, "static", "data")
DB_PATH = os.path.normpath(os.path.join(ROOT, "..", "Crawl Data", "database", "market.db"))

sys.path.insert(0, ROOT)

# static_folder TUYỆT ĐỐI (theo __file__), không phụ thuộc thư mục chạy — nếu để
# "static" tương đối, chạy từ cwd khác (preview/CI) sẽ 404 mọi file tĩnh.
# static_url_path="/static" (không phải "") để route trang /<page>.html không
# đụng route static catch-all; mọi asset trong template trỏ /static/...
app = Flask(__name__,
            static_folder=os.path.join(BASE, "static"),
            static_url_path="/static",
            template_folder=os.path.join(BASE, "templates"))
# debug=False nhưng vẫn muốn sửa template thấy ngay không phải restart gateway
app.config["TEMPLATES_AUTO_RELOAD"] = True

# 4 ứng dụng thành phần — vai trò THẬT trong kiến trúc hợp nhất hiện tại
SERVICES = [
    {"id": "crawl",
     "name": "Crawl Data — Tầng dữ liệu nền",
     "role": "Nạp market.db: BCTC 145k dòng, giá 33 mã, 1.963 tin CBTT, 1.147 sự "
             "kiện, phân tích cơ bản từng mã (P4). Mọi module của cổng :9999 đọc "
             "trực tiếp từ đây.",
     "provides": ["market.db", "tin CBTT [N..]", "sự kiện [E..]",
                  "phân tích cơ bản [CD-mã]"],
     "url": "http://localhost:5000", "dir": "Crawl Data", "cmd": "python app.py"},
    {"id": "banggia",
     "name": "Bảng giá realtime — Tầng thị trường sống",
     "role": "Bảng giá HOSE/HNX/UPCOM realtime (:5555/api/stocks — luồng Tổng quan "
             "tự nhận LIVE/cache), luồng quét Gemini sinh phân tích kháng cự/hỗ trợ "
             "từng mã, và cấp profile gemini_profile cho kênh AI CDP.",
     "provides": ["bảng giá LIVE", "phân tích S/R [TT-mã]", "profile Gemini CDP"],
     "url": "http://localhost:5555", "dir": "Test tool dự án", "cmd": "python server.py"},
    {"id": "econolens",
     "name": "EconoLens — Tầng AI hội thoại",
     "role": "AI chat kinh tế 4 nhóm người dùng (học sinh/phân tích/đầu tư/chính "
             "sách). Cấp GEMINI_API_KEY (kênh AI dự phòng khi CDP tắt) và mẫu "
             "schema JSON blocks cho giao diện động.",
     "provides": ["Gemini API key (fallback)", "schema blocks", "4 persona"],
     "url": "http://localhost:3333", "dir": "AI Analyze Economic", "cmd": "npm start"},
    {"id": "finpulse",
     "name": "FinPulse — Tầng tin tức quốc tế",
     "role": "Desktop app (Electron): dashboard RSS tài chính toàn cầu (CNBC, "
             "MarketWatch, CoinDesk...) + cây phân tích chủ đề AI. Danh sách feed "
             "là nguồn ngữ cảnh quốc tế cho các bước phân tích sau.",
     "provides": ["RSS feeds quốc tế", "cây phân tích chủ đề"],
     "url": None, "dir": "FinPulse-AI", "cmd": "npm start (Electron)"},
]


# --- Trang giao diện: render từ templates/ (shell dùng chung, hết copy-paste) ---
# Mỗi trang chỉ khai báo metadata; markup riêng nằm ở templates/pages/<id>.html.
PAGES = {
    "index": {
        "active": "index", "title": "Tổng quan Thị trường",
        "eyebrow": "Nền tảng AI-Quantum phân tích & dự báo kinh tế vĩ mô Việt Nam · ALL IN ONE :9999",
        "meta_desc": ("Market Pulse — nền tảng AI phân tích thị trường chứng khoán Việt Nam: "
                      "tổng quan VN-Index, sức khỏe doanh nghiệp, dự báo vĩ mô và dữ liệu "
                      "minh bạch có nguồn."),
    },
    "copilot": {
        "active": "copilot", "title": "Decision Copilot",
        "eyebrow": "Hỏi đáp đầu tư có phản biện — mọi con số đều có nguồn",
        "meta_desc": ("Decision Copilot — hỏi đáp đầu tư có phản biện, mọi câu trả lời đều "
                      "trích dẫn nguồn dữ liệu thật từ BCTC, tin CBTT và giá thị trường."),
    },
    "soitin": {
        "active": "soitin", "title": "Soi Tin",
        "eyebrow": "Dán tin đồn — đối chiếu với công bố chính thức, mỗi nhận định có nguồn",
        "meta_desc": ("Soi Tin — công cụ đối chiếu tin đồn chứng khoán với công bố chính "
                      "thức (CBTT), giúp bạn tự kiểm chứng thông tin trước khi ra quyết định."),
        "footer_legal": ("Soi Tin đối chiếu tin đồn với dữ liệu công bố, KHÔNG kết luận "
                         "tin thật/giả tuyệt đối và KHÔNG phải khuyến nghị đầu tư. Hãy tự "
                         "xác minh tại nguồn chính thức (HOSE/HNX/website doanh nghiệp) "
                         "trước khi quyết định."),
    },
    "banggia": {
        "active": "banggia", "title": "Bảng giá realtime",
        "embed": True, "body_class": "full-bleed",
        "meta_desc": ("Bảng giá realtime HOSE/HNX/UPCOM — theo dõi biến động giá cổ phiếu "
                      "Việt Nam theo thời gian thực, cập nhật liên tục trong phiên giao dịch."),
    },
    "data": {
        "active": "data", "title": "Dữ liệu Crawl",
        "embed": True, "body_class": "full-bleed",
        "meta_desc": ("Dữ liệu Crawl — kho dữ liệu BCTC, tin công bố thông tin và sự kiện "
                      "doanh nghiệp niêm yết được thu thập và chuẩn hóa tự động."),
    },
    "portfolio": {
        "active": "portfolio", "title": "Danh mục của bạn",
        "eyebrow": "Phân tích danh mục cá nhân & tối ưu hoá lượng tử",
        "features": [
            ("🔬", "QUBO / QAOA",
             "Bài toán chọn K trong N mã (Markowitz) chuyển thành QUBO, giải bằng "
             "QAOA mô phỏng lượng tử + Simulated Annealing, đối chứng brute-force."),
            ("📊", "Phân tích tương quan",
             "Ma trận tương quan giá giữa các mã trong danh mục — phát hiện "
             "tập trung rủi ro vào 1 nhóm ngành."),
            ("⚖️", "Đóng góp rủi ro",
             "Phân rã volatility danh mục theo từng mã để thấy mã nào "
             "chi phối rủi ro tổng."),
        ],
        "faqs": [
            ("Kết quả tối ưu có phải khuyến nghị mua bán không?",
             "Không. Đây là kết quả MÔ HÌNH trên dữ liệu lịch sử, mang tính tham khảo "
             "học thuật. Quyết định và trách nhiệm thuộc về nhà đầu tư."),
            ("QAOA có tốt hơn solver thường không?",
             "Ở quy mô nhỏ thì chưa — chúng tôi công bố optimality gap đo được thay vì "
             "quảng cáo. Giá trị nằm ở pipeline QUBO-hóa chuẩn bị cho quy mô lớn."),
        ],
        "meta_desc": ("Phân tích danh mục đầu tư cá nhân với tối ưu hóa lượng tử QUBO/QAOA, "
                      "ma trận tương quan và phân rã rủi ro theo từng mã cổ phiếu."),
    },
    "market": {
        "active": "market", "title": "Thị trường Chứng khoán",
        "eyebrow": "VNINDEX, dải thống kê 30 phiên (không phải dự báo) & sức khỏe doanh nghiệp niêm yết",
        "features": [
            ("📐", "Dải thống kê 30 phiên",
             "Percentile P5–P95 từ phân phối lịch sử VNINDEX (rolling 30 phiên). "
             "Mô tả biến động BÌNH THƯỜNG của quá khứ — không phải dự báo giá."),
            ("🏥", "Altman Z''-score",
             "Mô hình 4 hệ số cho thị trường mới nổi, phân vùng An toàn / Xám / "
             "Nguy hiểm theo ngưỡng học thuật (2.6 / 1.1)."),
            ("✅", "Piotroski F-score",
             "9 tiêu chí chấm sức khỏe tài chính từ BCTC 4 kỳ gần nhất "
             "(sinh lời, đòn bẩy, hiệu quả vận hành)."),
        ],
        "faqs": [
            ("Dải thống kê 30 phiên có phải dự báo giá không?",
             "Không. Đây là phân phối THỐNG KÊ của các đoạn 30 phiên trong quá khứ "
             "— cho biết biên độ dao động từng xảy ra, không dự đoán tương lai."),
            ("Vì sao ngân hàng/chứng khoán không có Z''-score?",
             "Altman Z'' thiết kế cho doanh nghiệp phi tài chính. Tổ chức tài chính "
             "có cấu trúc bảng cân đối khác hẳn nên hệ thống chấm bằng bộ chỉ tiêu riêng."),
            ("Điểm sức khỏe 0–100 tính thế nào?",
             "Tổng hợp từ Z''-score, F-score và ROA theo trọng số cố định, công khai "
             "— cùng một công thức cho mọi mã, không can thiệp tay."),
        ],
        "meta_desc": ("Thị trường chứng khoán Việt Nam — VN-Index, dải thống kê biến động "
                      "30 phiên và điểm sức khỏe doanh nghiệp niêm yết theo Altman Z và "
                      "Piotroski F-score."),
    },
    "macro": {
        "active": "macro", "title": "Kinh tế Vĩ mô",
        "eyebrow": "Dự báo GDP & lạm phát Việt Nam — SARIMAX trên dữ liệu World Bank",
        "meta_desc": ("Kinh tế vĩ mô Việt Nam — dự báo GDP và lạm phát bằng mô hình SARIMAX "
                      "trên dữ liệu World Bank, kèm khoảng tin cậy minh bạch."),
    },
    "apps": {
        "active": "apps", "title": "Hệ sinh thái",
        "eyebrow": "4 dự án thành phần — mỗi dự án đóng 1 vai trò trong luồng dữ liệu hợp nhất",
        "meta_desc": ("Hệ sinh thái Market Pulse — 4 ứng dụng thành phần thu thập, phân tích "
                      "và hiển thị dữ liệu thị trường chứng khoán Việt Nam hợp nhất."),
    },
    "methodology": {
        "active": "methodology", "title": "Phương pháp",
        "eyebrow": "Công khai công thức, nguồn dữ liệu và giới hạn — audit trail là điểm khác biệt",
        "crumbs": [("Trang chủ", "/"), ("Phương pháp", None)],
        "meta_desc": ("Phương pháp Market Pulse — công khai toàn bộ công thức tính điểm sức "
                      "khỏe doanh nghiệp, dự báo vĩ mô và mô hình tối ưu hóa lượng tử."),
    },
    "watchlist": {
        "active": "watchlist", "title": "Danh sách theo dõi",
        "eyebrow": "Neo mã cần soi thêm — bấm ☆ ở trang cổ phiếu để thêm/bỏ",
        "crumbs": [("Trang chủ", "/"), ("Danh sách theo dõi", None)],
        "meta_desc": ("Danh sách theo dõi — lưu lại các mã cổ phiếu cần quan sát thêm, đồng "
                      "bộ ngay trên trình duyệt của bạn."),
    },
    "compare": {
        "active": "compare", "title": "So sánh cổ phiếu",
        "eyebrow": "Đối chiếu 2 mã: hiệu suất giá chuẩn hóa + chỉ số cơ bản song song — dữ kiện, không xếp hạng",
        "crumbs": [("Trang chủ", "/"), ("So sánh", None)],
        "meta_desc": ("So sánh cổ phiếu — đối chiếu hiệu suất giá và chỉ số cơ bản giữa 2 mã "
                      "chứng khoán Việt Nam, trình bày dữ kiện khách quan."),
    },
    "screener": {
        "active": "screener", "title": "Bộ lọc dữ liệu",
        "eyebrow": "Lọc toàn thị trường theo tiêu chí sức khỏe/định lượng — mỗi mã hiện % khớp bộ lọc",
        "crumbs": [("Trang chủ", "/"), ("Bộ lọc dữ liệu", None)],
        "meta_desc": ("Bộ lọc dữ liệu — sàng lọc toàn thị trường chứng khoán Việt Nam theo "
                      "tiêu chí sức khỏe tài chính và chỉ số định lượng."),
    },
    "batdau": {
        "active": "batdau", "title": "Bắt đầu",
        "eyebrow": "3 bước làm quen Market Pulse — dành cho người mới bắt đầu tìm hiểu chứng khoán",
        "crumbs": [("Trang chủ", "/"), ("Bắt đầu", None)],
        "meta_desc": ("Bắt đầu với Market Pulse — hướng dẫn 3 bước cho người mới: nhìn thị "
                      "trường hôm nay, tra một mã cổ phiếu, hiểu điểm sức khỏe doanh nghiệp."),
    },
    "glossary": {
        "active": "glossary", "title": "Thuật ngữ",
        "eyebrow": "Giải thích ngắn các thuật ngữ xuất hiện trong hệ thống — từ Z''-score đến QAOA",
        "crumbs": [("Trang chủ", "/"), ("Thuật ngữ", None)],
        "meta_desc": ("Thuật ngữ chứng khoán và tài chính — giải thích ngắn gọn, dễ hiểu các "
                      "khái niệm từ EPS, ROE đến Altman Z-score và QAOA."),
    },
}


@app.route("/")
def index():
    return render_template("pages/index.html", **PAGES["index"])


@app.route("/<page>.html")
def render_page(page):
    """URL cũ /market.html, /macro.html... giữ nguyên — giờ render qua template."""
    meta = PAGES.get(page)
    if meta is None:
        abort(404)
    return render_template(f"pages/{page}.html", **meta)


# --- PILLAR-A · A1: trang phân tích đơn doanh nghiệp ---
@app.route("/co-phieu/<sym>")
def stock_page(sym):
    sym = sym.upper().strip()
    if not (2 <= len(sym) <= 8 and sym.isalnum()):
        abort(404)
    return render_template(
        "pages/stock.html", active=None, symbol=sym,
        title=f"Cổ phiếu {sym}",
        eyebrow="Phân tích đơn doanh nghiệp — mọi con số truy ngược được nguồn (audit trail)",
        crumbs=[("Trang chủ", "/"), ("Thị trường", "/market.html"), (sym, None)])


@app.route("/api/stock/<sym>")
def api_stock(sym):
    """Gom toàn bộ dữ liệu 1 mã: BCTC, peer, sức khỏe, tin, sự kiện, AI đã lưu."""
    from modules.stock_page.api import stock_detail
    out = stock_detail(DB_PATH, DATA, sym)
    return jsonify(_sanitize_json(out)), (404 if "error" in out else 200)


@app.route("/api/stock/<sym>/analysis")
def api_stock_analysis(sym):
    """Tab 'Phân tích 360': chuỗi BCTC nhiều năm + radar 5 trục (P1–P19).
    Chỉ dữ kiện & thống kê mô tả — không khuyến nghị (legal.py)."""
    from modules.stock_page.api import stock_analysis
    out = stock_analysis(DB_PATH, DATA, sym)
    return jsonify(_sanitize_json(out)), (404 if "error" in out else 200)


@app.route("/api/stock/<sym>/charts")
def api_stock_charts(sym):
    """Phụ lục D · D-1 + D-3: biểu đồ của 1 mã, kèm lời dẫn AI nếu đã sinh.

    Số liệu lấy thẳng từ market.db bằng SQL — KHÔNG gọi AI, nên endpoint này vẫn
    trả về được kể cả khi Local API tắt; lúc đó biểu đồ chỉ thiếu lời dẫn."""
    from modules.stock_page import chart_notes
    from modules.stock_page.chart_data import build
    out = build(DB_PATH, sym)
    out = chart_notes.merge(out, chart_notes.load(DB_PATH, sym))
    return jsonify(_sanitize_json(out)), (200 if out.get("count") else 404)


@app.route("/api/stock/<sym>/news_ai", methods=["POST"])
def api_stock_news_ai(sym):
    """Giải thích MỘT bản tin/sự kiện cho người mới — bấm mới chạy, tốn 1 lượt AI.

    Tiêu đề công bố viết theo văn phong pháp lý ("Nghị quyết HĐQT số 01.07-2026",
    "Giấy chứng nhận ĐKDN thay đổi lần thứ 61") — người mới đọc xong vẫn không
    biết chuyện gì xảy ra. Đây là chỗ AI có ích nhất mà rẻ nhất."""
    from modules.common import legal, local_api

    sym = (sym or "").strip().upper()
    body = request.get_json(silent=True) or {}
    title = str(body.get("title") or "").strip()[:300]
    if not title:
        return jsonify(ok=False, msg="Thiếu tiêu đề tin"), 400
    when = str(body.get("date") or "").strip()[:30]
    text = str(body.get("content") or "").strip()[:1200]
    publisher = str(body.get("publisher") or "").strip()[:80]

    # ĐỌC BÀI GỐC: tin CBTT trong market.db không có nội dung (0/50 bản ghi của
    # FPT có `short_content`), nên nếu chỉ gửi tiêu đề thì AI đang đoán chứ không
    # đọc. Có link bài báo thật thì tải nội dung về ngay tại đây rồi mới hỏi AI.
    # Tải khi BẤM, không tải lúc crawl — 1 request cho 1 lần người dùng hỏi.
    fetched_from = ""
    fetch_note = ""
    link = str(body.get("link") or "").strip()
    if link and not text:
        from modules.stock_page import article_text
        try:
            text = article_text.fetch(link)
            fetched_from = link
        except article_text.ArticleError as exc:
            fetch_note = str(exc)
        except Exception as exc:                   # noqa: BLE001
            fetch_note = f"Không đọc được bài gốc: {str(exc)[:120]}"

    src_line = f"Nguồn: {publisher}\n" if publisher else ""
    prompt = (
        f"Giải thích bản tin sau về doanh nghiệp niêm yết {sym} cho người "
        f"CHƯA BIẾT GÌ về chứng khoán.\n\n"
        f"Tiêu đề: {title}\n" + (f"Ngày: {when}\n" if when else "") + src_line
        + (f"\nNỘI DUNG BÀI:\n{text}\n" if text else "")
        + "\nTrả lời đúng 3 phần, mỗi phần 1–2 câu ngắn, tiếng Việt thường ngày:\n"
        "1. CHUYỆN GÌ: bản tin này nói doanh nghiệp làm gì.\n"
        "2. NGHĨA LÀ SAO: giải thích từ chuyên môn trong tiêu đề bằng lời thường.\n"
        "3. LIÊN QUAN GÌ ĐẾN CỔ ĐÔNG: ảnh hưởng tới người đang giữ cổ phiếu ở "
        "khía cạnh nào (số lượng cổ phiếu, quyền lợi, minh bạch…).\n\n"
        "Chỉ dựa vào thông tin nêu trên, không bổ sung dữ kiện từ trí nhớ. "
        "TUYỆT ĐỐI không suy đoán giá sẽ tăng hay giảm, không khuyên mua/bán/nắm "
        "giữ. Không chắc thì nói thẳng là bản tin không đủ thông tin."
        + legal.LEGAL_PROMPT_RULE)

    try:
        answer = (local_api.ask(prompt) or "").strip()
    except Exception as exc:                       # noqa: BLE001
        return jsonify(ok=False, msg=f"Không gọi được AI: {str(exc)[:160]}"), 502
    if not answer:
        return jsonify(ok=False, msg="AI trả về nội dung rỗng"), 502
    hits = legal.check_text(answer)
    if hits:
        return jsonify(ok=False, msg=f"Nội dung bị chặn theo quy tắc pháp lý: {hits}"), 422
    # `read_source`/`note` để giao diện nói thật AI đã đọc được gì: đọc nguyên bài,
    # hay chỉ có mỗi tiêu đề. Người đọc phải phân biệt được hai trường hợp đó.
    return jsonify(ok=True, symbol=sym, answer=answer,
                   read_source=fetched_from, chars=len(text), note=fetch_note)


@app.route("/api/stock/<sym>/sources")
def api_stock_sources(sym):
    """Liệt kê MỌI nguồn Crawl Data có thật cho 1 mã (lãnh đạo, công ty con,
    lịch sử tăng vốn, báo chí, BCTC thô…) — phần trước đây chỉ xem được ở :5000."""
    from modules.stock_page import raw_sources
    return jsonify(symbol=sym.upper(),
                   groups=raw_sources.groups(),
                   sources=raw_sources.available(DB_PATH, sym))


@app.route("/api/stock/<sym>/source/<key>")
def api_stock_source(sym, key):
    """Nội dung một nguồn. Đọc thẳng từ thư mục companies/ nên KHÔNG cần dịch vụ
    crawl (:5000) đang chạy. Đã lọc khoá khuyến nghị theo legal.py."""
    from modules.stock_page import raw_sources
    out = raw_sources.fetch(DB_PATH, sym, key,
                            limit=request.args.get("limit", type=int) or raw_sources.MAX_ROWS)
    if not out:
        return jsonify(ok=False, msg="Không có nguồn này cho mã đã chọn"), 404
    return jsonify(_sanitize_json(out))


@app.route("/api/stock/<sym>/charts/narrate", methods=["POST"])
def api_stock_charts_narrate(sym):
    """D-3: sinh lời dẫn cho biểu đồ của 1 mã — 1 lượt AI cho mỗi NHÓM.

    Đây là bước DUY NHẤT trong tầng biểu đồ có gọi AI. Lời dẫn chỉ tham chiếu
    `chart_id` và nhãn kỳ; mục nào trỏ vào thứ không có thật thì bị loại chứ
    không được sửa hộ (xem chart_notes.validate)."""
    from modules.common import local_api
    from modules.stock_page import chart_notes
    from modules.stock_page.chart_data import build

    sym = (sym or "").strip().upper()
    payload = build(DB_PATH, sym)
    if not payload.get("count"):
        return jsonify(ok=False, msg="Mã chưa có biểu đồ nào"), 404
    try:
        data = chart_notes.generate(payload, local_api.ask, sym)
    except Exception as exc:                       # noqa: BLE001
        return jsonify(ok=False, msg=str(exc)[:200]), 502
    chart_notes.save(DB_PATH, sym, data)
    return jsonify(ok=True, symbol=sym, narrated=len(data["notes"]),
                   total=payload["count"], report=data["report"])


@app.route("/api/stock/<sym>/chart_ai", methods=["POST"])
def api_stock_chart_ai(sym):
    """§18 · "AI đọc chart": gửi SỐ LIỆU kỹ thuật (không gửi ảnh) cho AI mô tả
    thành lời cho người mới. Chỉ mô tả trạng thái — không dự báo, không khuyến nghị."""
    from modules.market_overview import tech_full as _tf
    from modules.chart_ai import read_chart
    symbol = sym.upper().strip()
    tech = _tf.one(DB_PATH, symbol)
    if tech is None:
        return jsonify({"error": f"Không có dữ liệu giá cho {symbol}."}), 404
    out = read_chart(symbol, tech,
                     prefer=(request.get_json(silent=True) or {}).get("prefer") or "auto")
    return jsonify(_sanitize_json(out)), (200 if "error" not in out else 502)


@app.route("/api/stock/<sym>/request_analysis", methods=["POST"])
def api_request_analysis(sym):
    """§18 · Mã chưa chạy P4 → đưa vào hàng đợi cho worker phân tích."""
    from modules import analysis_queue as _q
    out = _q.enqueue(sym)
    return jsonify(out), (200 if "error" not in out else 429)


@app.route("/api/stock/<sym>/analysis_status")
def api_analysis_status(sym):
    from modules import analysis_queue as _q
    return jsonify(_q.status(sym))


# ---------------------------------------------------------------------------
# Ảnh 16 · Pulse Chat — proxy sang EconoLens (:3333)
# ---------------------------------------------------------------------------
# Vì sao proxy chứ không port sang Python: EconoLens đã có sẵn 4 provider
# (Claude/Gemini/Grok/Gemini CDP), schema blocks[], LEGAL_GUARDRAIL và JWT. Proxy
# giữ nguyên bộ não đó, chỉ đổi lớp vỏ giao diện — không nhân đôi logic pháp lý.
# Whitelist đúng 4 route: không proxy mù để tránh mở cửa hậu sang service khác.
_PCHAT_ROUTES = {"chat", "login", "register", "meta"}
ECONOLENS_BASE = os.environ.get("MP_ECONOLENS_URL", "http://127.0.0.1:3333")


@app.route("/api/pchat/<path:sub>", methods=["POST", "GET"])
def pchat_proxy(sub):
    """Chuyển tiếp yêu cầu chat sang EconoLens, giữ nguyên header Authorization."""
    root = sub.split("/")[0]
    if root not in _PCHAT_ROUTES:
        return jsonify({"error": f"Route không được phép: {root}"}), 404
    import requests as _rq
    url = f"{ECONOLENS_BASE}/api/{sub}"
    headers = {"Content-Type": "application/json"}
    if request.headers.get("Authorization"):
        headers["Authorization"] = request.headers["Authorization"]
    try:
        if request.method == "GET":
            r = _rq.get(url, headers=headers, timeout=120)
        else:
            r = _rq.post(url, json=request.get_json(silent=True) or {},
                         headers=headers, timeout=120)
    except _rq.exceptions.ConnectionError:
        return jsonify({"error": "AI chat tạm nghỉ — dịch vụ EconoLens (:3333) chưa chạy. "
                                 "Khởi động bằng: npm start trong thư mục AI Analyze Economic."}), 503
    except Exception as e:
        return jsonify({"error": f"Không gọi được AI chat: {str(e)[:160]}"}), 502
    return (r.content, r.status_code, {"Content-Type": "application/json"})


@app.route("/api/compare_ai", methods=["POST"])
def api_compare_ai():
    """Ảnh 17 · AI diễn giải khác biệt giữa 2 mã (chạy khi người dùng bấm nút).

    Nạp lại đúng payload mà trang So sánh đang dùng (stock_detail) rồi đưa AI —
    không thêm nguồn dữ liệu mới, nên số liệu AI nói luôn khớp bảng trên màn hình.
    """
    body = request.get_json(force=True, silent=True) or {}
    a = (body.get("a") or "").strip().upper()
    b = (body.get("b") or "").strip().upper()
    if not a or not b:
        return jsonify({"error": "Thiếu mã để so sánh."}), 400
    if a == b:
        return jsonify({"error": "Hai mã trùng nhau."}), 400

    from modules.stock_page.api import stock_detail
    da = stock_detail(DB_PATH, DATA, a)
    db_ = stock_detail(DB_PATH, DATA, b)
    for sym, d in ((a, da), (b, db_)):
        if "error" in d:
            return jsonify({"error": f"Không có dữ liệu cho {sym}: {d['error']}"}), 404

    from modules.compare_ai import compare_ai
    out = compare_ai(a, b, da, db_, prefer=body.get("prefer") or "auto")
    return jsonify(_sanitize_json(out)), (200 if "error" not in out else 502)


# --- Trang mới (A3 so sánh / A5 bộ lọc / P5 thuật ngữ) — template do agent dựng ---
@app.route("/so-sanh")
def compare_page():
    return render_template("pages/compare.html", **PAGES["compare"])


@app.route("/bo-loc")
def screener_page():
    return render_template("pages/screener.html", **PAGES["screener"])


@app.route("/kien-thuc")
def glossary_page():
    return render_template("pages/glossary.html", **PAGES["glossary"])


@app.route("/bat-dau")
def batdau_page():
    return render_template("pages/batdau.html", **PAGES["batdau"])


@app.route("/design-v3")
def design_v3_page():
    """Trang thử R0: render đủ helper chart-v3 + component v3 bằng dữ liệu mẫu."""
    return render_template("pages/design_v3.html", active=None,
                           title="Design v3 — trang thử",
                           eyebrow="Kiểm thử foundation R0: tokens + component + chart helpers")


@app.route("/sitemap.xml")
def sitemap_xml():
    """Sitemap động: trang tĩnh + mọi mã cổ phiếu trong market.db (bảng companies)."""
    import sqlite3
    base_url = request.url_root.rstrip("/")
    static_paths = [
        "/", "/market.html", "/macro.html", "/portfolio.html", "/copilot.html",
        "/soitin.html", "/banggia.html", "/data.html", "/apps.html",
        "/watchlist.html", "/methodology.html", "/so-sanh", "/bo-loc",
        "/kien-thuc", "/quantum-lab",
    ]
    urls = [f"{base_url}{p}" for p in static_paths]
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        rows = conn.execute("SELECT symbol FROM companies ORDER BY symbol").fetchall()
        conn.close()
        urls += [f"{base_url}/co-phieu/{row[0]}" for row in rows]
    except Exception:
        pass
    body = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>')
    return Response(xml, mimetype="application/xml")


@app.route("/robots.txt")
def robots_txt():
    base_url = request.url_root.rstrip("/")
    body = f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml"
    return Response(body, mimetype="text/plain")


@app.route("/api/market/board")
def market_board():
    """Bảng giá hiện tại (LIVE từ :5555 hoặc cache P6) — cho dashboard Tổng quan.

    Mỗi dòng được gắn thêm `tradable` (mã có giao dịch đủ đều để người mới mua
    bán được hay không) + `gtgd20`/`zero_days` làm bằng chứng. Gắn ở SERVER để
    trang chủ và trang Tổng quan dùng CHUNG một tiêu chí, khỏi lệch nhau."""
    from modules.market_overview.technical import get_board
    from modules.market_overview import liquidity
    data = dict(get_board())
    rows = [dict(r) for r in (data.get("rows") or [])]   # copy: đừng sửa cache 4s
    data["liquidity"] = liquidity.annotate_rows(rows, DB_PATH)
    data["rows"] = rows
    return jsonify(_sanitize_json(data))


def _row_pct(r):
    """%thay đổi phiên của 1 dòng bảng giá; thiếu matchChange thì suy từ giá vs ref."""
    try:
        ref = float(r.get("ref") or 0)
        px = float(r.get("matchPrice") or 0)
    except (TypeError, ValueError):
        return None
    if ref <= 0 or px <= 0:
        return None
    chg = r.get("matchChange")
    try:
        chg = float(chg) if chg is not None else (px - ref)
    except (TypeError, ValueError):
        chg = px - ref
    return chg / ref * 100.0


def _breadth_from_board(rows):
    """Độ rộng thị trường — port đúng cách đếm của renderPulse() bên JS sang Python
    để mọi client (trang chủ, ticker, trang mã) dùng CHUNG một con số."""
    up = down = flat = ceil_ = floor_ = 0
    tot_vol = 0.0
    n = 0
    for r in rows or []:
        if not r or not r.get("symbol"):
            continue
        pct = _row_pct(r)
        if pct is None:
            continue
        n += 1
        try:
            tot_vol += float(r.get("totalVol") or 0)
        except (TypeError, ValueError):
            pass
        try:
            px = float(r.get("matchPrice") or 0)
            if r.get("ceiling") is not None and px >= float(r["ceiling"]):
                ceil_ += 1
            elif r.get("floor") is not None and px <= float(r["floor"]):
                floor_ += 1
        except (TypeError, ValueError):
            pass
        if pct > 0:
            up += 1
        elif pct < 0:
            down += 1
        else:
            flat += 1
    return {"n": n, "up": up, "down": down, "flat": flat,
            "ceil": ceil_, "floor": floor_, "total_vol": tot_vol}


@app.route("/api/live")
def api_live():
    """R1 · Nhịp dữ liệu sống, GỘP 1 REQUEST cho cả trang (thay vì mỗi section tự
    gọi bảng giá). Trả: độ tươi, độ rộng, ticker top thanh khoản, và báo giá của
    riêng các mã client hỏi (?symbols=FPT,VNM).

    Nguồn duy nhất là get_board() (đã cache 4s) nên gọi 15s/lần rất rẻ.
    """
    from modules.market_overview.technical import get_board
    board = get_board()
    rows = board.get("rows") or []

    # ticker: top 22 theo giá trị giao dịch xấp xỉ
    def _liq(r):
        try:
            return float(r.get("matchPrice") or 0) * float(r.get("totalVol") or r.get("matchVol") or 0)
        except (TypeError, ValueError):
            return 0.0
    ranked = sorted((r for r in rows if r and r.get("symbol")), key=_liq, reverse=True)
    ticker = [{"symbol": r["symbol"], "price": r.get("matchPrice"), "chg_pct": _row_pct(r)}
              for r in ranked[:22]]

    want = {s.strip().upper() for s in (request.args.get("symbols") or "").split(",") if s.strip()}
    quotes = {r["symbol"]: {"price": r.get("matchPrice"), "chg_pct": _row_pct(r),
                            "vol": r.get("totalVol"), "ref": r.get("ref")}
              for r in rows if r and r.get("symbol", "").upper() in want}

    return jsonify(_sanitize_json({
        "as_of": board.get("as_of"),
        "live": board.get("live", False),
        "source": board.get("source"),
        "breadth": _breadth_from_board(rows),
        "ticker": ticker,
        "quotes": quotes,
    }))


# --- PILLAR-Q: Quantum Lab (wizard QUBO 3 bước) ---
@app.route("/quantum-lab")
def quantum_lab_page():
    return render_template(
        "pages/quantumlab.html", active="quantumlab",
        title="Quantum Lab", symbol=None,
        eyebrow="Tối ưu danh mục QUBO/QAOA — mô phỏng học thuật có đối chứng, không phải khuyến nghị",
        crumbs=[("Trang chủ", "/"), ("Danh mục", "/portfolio.html"), ("Quantum Lab", None)])


@app.route("/api/quantum/universe")
def quantum_universe():
    from modules.quantum_lab.api import universe
    return jsonify(universe(DB_PATH))


@app.route("/api/quantum/run", methods=["POST"])
def quantum_run():
    body = request.get_json(force=True, silent=True) or {}
    from modules.quantum_lab.api import start_lab
    try:
        job_id = start_lab(DB_PATH, body.get("symbols") or [],
                           body.get("k", 5), body.get("risk_aversion", 2.0))
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 400
    return jsonify({"job_id": job_id})


@app.route("/api/quantum/status/<job_id>")
def quantum_status(job_id):
    from modules.quantum_lab.api import job_status
    job = job_status(job_id)
    if job is None:
        return jsonify({"error": "không tìm thấy job"}), 404
    return jsonify(_sanitize_json({k: job[k] for k in ("status", "steps", "result", "error")}))


@app.route("/api/services")
def services():
    return jsonify(SERVICES)


@app.route("/api/services/status")
def services_status():
    """Ping nhanh từng app thành phần → đèn trạng thái trên trang Hệ sinh thái."""
    import requests as rq
    out = {}
    for s in SERVICES:
        if not s["url"]:
            out[s["id"]] = None  # desktop app — không ping được
            continue
        try:
            rq.get(s["url"], timeout=1.2)
            out[s["id"]] = True
        except Exception:
            out[s["id"]] = False
    return jsonify(out)


@app.route("/api/data/<name>")
def data(name):
    safe = "".join(c for c in name if c.isalnum() or c in "_-") + ".json"
    path = os.path.join(DATA, safe)
    if not os.path.exists(path):
        return jsonify({"error": f"chưa có {safe} — chạy python run_pipeline.py"}), 404
    with open(path, encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.route("/api/overview/start", methods=["POST"])
def overview_start():
    """Khởi động luồng Tổng quan Thị trường (5 bước, chạy nền)."""
    body = request.get_json(force=True, silent=True) or {}
    prefer = body.get("prefer", "auto")  # auto | cdp | api
    from modules.market_overview.orchestrator import start_overview
    return jsonify({"job_id": start_overview(DB_PATH, prefer)})


def _sanitize_json(o):
    """Khử NaN/Inf (không hợp lệ trong JSON chuẩn — trình duyệt parse lỗi)."""
    import math
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {k: _sanitize_json(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_sanitize_json(v) for v in o]
    return o


@app.route("/api/overview/status/<job_id>")
def overview_status(job_id):
    from modules.market_overview.orchestrator import get_job
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "không tìm thấy job"}), 404
    return jsonify(_sanitize_json(job))


# --- Nhận định bối cảnh vĩ mô (Phần C): chạy nền, cache macro_ai.json ---
_macro_ai_job = {"status": "idle", "steps": [], "error": None, "started_at": None}
_macro_ai_lock = None


@app.route("/api/macro/analyze", methods=["POST"])
def macro_analyze():
    """Chạy AI nhận định vĩ mô nền (2 lượt). Khóa chống chạy trùng; cache macro_ai.json."""
    import threading
    global _macro_ai_lock
    if _macro_ai_lock is None:
        _macro_ai_lock = threading.Lock()
    if _macro_ai_job["status"] == "running":
        return jsonify({"status": "running", "steps": _macro_ai_job["steps"]})

    body = request.get_json(force=True, silent=True) or {}
    prefer = body.get("prefer", "auto")
    data_dir = os.path.join(BASE, "static", "data")

    def _progress(step, status, detail=""):
        for s in _macro_ai_job["steps"]:
            if s["name"] == step:
                s["status"], s["detail"] = status, detail
                return
        _macro_ai_job["steps"].append({"name": step, "status": status, "detail": detail})

    def _worker():
        with _macro_ai_lock:
            _macro_ai_job.update({"status": "running", "error": None, "steps": [],
                                  "started_at": time.time()})
            try:
                from modules.macro_ai import engine
                result = engine.analyze(DB_PATH, data_dir, prefer, progress=_progress)
                engine.save_result(data_dir, result)
                _macro_ai_job["status"] = "done"
            except Exception as e:
                _macro_ai_job["status"] = "error"
                _macro_ai_job["error"] = str(e)[:400]

    threading.Thread(target=_worker, daemon=True).start()
    return jsonify({"status": "running", "msg": "Đã bắt đầu phân tích vĩ mô."})


@app.route("/api/macro/analyze/status")
def macro_analyze_status():
    return jsonify(_sanitize_json({k: _macro_ai_job[k]
                                   for k in ("status", "steps", "error")}))


@app.route("/api/data/macro_ai")
def macro_ai_data():
    """Trả bản cache macro_ai.json gần nhất (empty-state nếu chưa chạy lần nào)."""
    path = os.path.join(BASE, "static", "data", "macro_ai.json")
    if not os.path.exists(path):
        return jsonify({"available": False, "reason": "Chưa chạy phân tích lần nào."})
    try:
        with open(path, encoding="utf-8") as f:
            return jsonify(_sanitize_json({**json.load(f), "available": True}))
    except Exception as e:
        return jsonify({"available": False, "reason": f"Lỗi đọc cache: {str(e)[:100]}"})


@app.route("/api/tech_full")
def api_tech_full():
    """Ảnh 11 · Bộ chỉ báo kỹ thuật đầy đủ cho MỌI mã (S/R, VBP, RSI14, MA20/50,
    %KL so TB20, 52 tuần) — tính từ market.db, không phụ thuộc Test tool :5555.

    ?symbols=FPT,VCB để lấy riêng vài mã (trang cổ phiếu); không truyền = toàn bộ.
    """
    from modules.market_overview import tech_full as _tf
    full = _tf.build(DB_PATH)
    want = [s.strip().upper() for s in (request.args.get("symbols") or "").split(",") if s.strip()]
    if not want:
        return jsonify(full)
    return jsonify({
        "as_of": full["as_of"], "source": full["source"], "min_bars": full["min_bars"],
        "items": {s: full["items"][s] for s in want if s in full["items"]},
        "skipped": {s: full["skipped"][s] for s in want if s in full["skipped"]},
    })


def _warm_tech_full():
    """Tính sẵn tech_full lúc khởi động (mất ~13s cho 1.541 mã) để request đầu
    tiên của người dùng không phải chờ. Lỗi ở đây không được làm chết gateway."""
    try:
        from modules.market_overview import tech_full as _tf
        _tf.build(DB_PATH)
    except Exception:
        pass


if os.environ.get("MP_NO_WARM") != "1":
    import threading as _th
    _th.Thread(target=_warm_tech_full, daemon=True).start()


@app.route("/api/index_history")
def api_index_history():
    """Ảnh 1 · Lịch sử OHLC chỉ số cho biểu đồ NẾN (bảng index_ohlc do P9 crawl).

    Trước đây hero chỉ có `close` từ market_range (~275 phiên) nên phải vẽ area và
    tab "Tất cả" thực chất chỉ ~1 năm. Nay trả đủ O/H/L/C nhiều năm.

    TRUNG THỰC: nếu bảng chưa có dữ liệu, KHÔNG bịa nến từ close — trả candles
    rỗng + fallback để frontend giữ area như cũ.
    """
    import sqlite3
    code = (request.args.get("code") or "VNINDEX").upper()
    try:
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT time, open, high, low, close, volume FROM index_ohlc "
                "WHERE code=? ORDER BY time", (code,)).fetchall()
        finally:
            con.close()
    except sqlite3.OperationalError:
        return jsonify({"code": code, "candles": [], "fallback": "market_range",
                        "reason": "chưa có bảng index_ohlc — chạy: py -3.12 -m scripts.p9_index_ohlc"})
    if not rows:
        return jsonify({"code": code, "candles": [], "fallback": "market_range",
                        "reason": f"chưa có dữ liệu cho {code}"})
    return jsonify({
        "code": code,
        "source": "index_ohlc (vnstock VCI) — P9",
        "candles": [{"time": t, "open": o, "high": h, "low": l,
                     "close": c, "volume": v} for t, o, h, l, c, v in rows],
    })


@app.route("/api/market/heatmap")
def market_heatmap():
    """Dữ liệu treemap toàn cảnh: mã, ngành, vốn hóa, %phiên (ưu tiên bảng giá LIVE)."""
    from modules.market_overview.technical import get_board
    from modules.market_overview.market_technical import heatmap_data
    from modules.common.sector_vi import annotate
    board = get_board()
    data = heatmap_data(DB_PATH, board.get("rows") or None)
    data["board_live"] = board.get("live", False)
    # Ảnh 8: gắn tên ngành tiếng Việt ngay tại API — mọi client (heatmap, card
    # nhóm ngành, xu hướng ngành) dùng chung, khỏi mỗi nơi tự dịch một kiểu.
    annotate(data.get("items"))
    annotate(data.get("sectors"))
    return jsonify(data)


@app.route("/api/market/regime")
def market_regime():
    """Chế độ thị trường (5 tín hiệu ±1) + luân chuyển ngành (RS 12 tuần) +
    tập trung thanh khoản. Thuần Python, UI nạp độc lập AI."""
    from modules.market_overview.technical import get_board
    from modules.market_overview.market_technical import (
        compute_regime, sector_rotation, liquidity_concentration)
    from modules.common.sector_vi import annotate
    board = get_board()
    rot = sector_rotation(DB_PATH)
    annotate(rot.get("series"))          # ảnh 8: tên ngành VI cho chart RS
    return jsonify({
        "regime": compute_regime(DB_PATH),
        "rotation": rot,
        "liquidity_concentration": liquidity_concentration(DB_PATH, board.get("rows") or None),
    })


@app.route("/api/market/anomalies")
def market_anomalies():
    """Radar bất thường: tín hiệu lệch chuẩn giá/khối lượng + tin. Thuần Python.

    Truyền board LIVE (:5555) để bù snapshot khối ngoại + turnover chính xác."""
    from modules.market_overview.anomaly import scan_anomalies
    from modules.market_overview.technical import get_board
    try:
        board = get_board()
        rows = board.get("rows") or None
    except Exception:
        rows = None
    return jsonify(_sanitize_json(scan_anomalies(DB_PATH, board_rows=rows)))


# --- Cập nhật giá (P6) chạy nền, khóa chống chạy trùng ---
_refresh_lock = None  # threading.Lock, tạo lazy
_refresh_state = {"running": False, "done": False, "started_at": None,
                  "rc": None, "error": None}


@app.route("/api/market/refresh_prices", methods=["POST"])
def refresh_prices():
    """Chạy scripts/p6_market_prices.py nền (incremental, resume ~1-2 phút).

    Chỉ 1 refresh tại 1 thời điểm. Trả trạng thái đơn giản để UI poll."""
    import threading
    global _refresh_lock
    if _refresh_lock is None:
        _refresh_lock = threading.Lock()

    if _refresh_state["running"]:
        return jsonify({"running": True, "done": False,
                        "msg": "Đang cập nhật giá — vui lòng đợi."})

    def _worker():
        with _refresh_lock:
            _refresh_state.update({"running": True, "done": False, "rc": None,
                                   "error": None, "started_at": __import__("time").time()})
            try:
                script = os.path.normpath(
                    os.path.join(ROOT, "..", "Crawl Data", "scripts", "p6_market_prices.py"))
                cwd = os.path.dirname(os.path.dirname(script))  # Crawl Data/
                env = os.environ.copy()
                env["PYTHONUTF8"] = "1"
                r = subprocess.run([sys.executable, script], cwd=cwd, env=env,
                                   capture_output=True, text=True, timeout=900)
                _refresh_state["rc"] = r.returncode
                if r.returncode != 0:
                    _refresh_state["error"] = (r.stderr or "")[-500:]
            except Exception as e:
                _refresh_state["error"] = str(e)[:500]
                _refresh_state["rc"] = -1
            finally:
                _refresh_state["running"] = False
                _refresh_state["done"] = True

    threading.Thread(target=_worker, daemon=True).start()
    return jsonify({"running": True, "done": False, "msg": "Đã bắt đầu cập nhật giá."})


@app.route("/api/market/refresh_prices/status")
def refresh_prices_status():
    return jsonify({k: _refresh_state[k] for k in ("running", "done", "rc", "error")})


@app.route("/api/gemini/cdp/start", methods=["POST"])
def gemini_cdp_start():
    """Bật worker Gemini Web qua CDP (mở Chrome với profile của Test tool)."""
    from modules.market_overview.gemini_transport import start_cdp_worker
    return jsonify(start_cdp_worker())


@app.route("/api/gemini/cdp/status")
def gemini_cdp_status():
    from modules.market_overview.gemini_transport import cdp_status
    return jsonify(cdp_status())


@app.route("/api/copilot/ask", methods=["POST"])
def copilot_ask():
    """Decision Copilot: câu hỏi + danh mục (tuỳ chọn) → phân tích có phản biện."""
    body = request.get_json(force=True, silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Thiếu câu hỏi."}), 400
    portfolio = body.get("portfolio") or None
    from modules.copilot.engine import ask as copilot
    return jsonify(copilot(question, portfolio))


@app.route("/api/factcheck", methods=["POST"])
def factcheck():
    """Soi Tin: dán tin đồn → nhãn trung tính từng nhận định + dẫn chứng công bố."""
    body = request.get_json(force=True, silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Chưa có nội dung tin để soi."}), 400
    prefer = body.get("prefer", "auto")  # auto | cdp | api
    from modules.factcheck.engine import factcheck as run_factcheck
    result = run_factcheck(text, prefer=prefer)
    return jsonify(_sanitize_json(result))


@app.route("/api/portfolio/analyze", methods=["POST"])
def portfolio_analyze():
    """Phân tích danh mục: [{symbol, qty}] → ngành/tương quan/rủi ro/tái cân bằng."""
    body = request.get_json(force=True, silent=True) or {}
    holdings = body.get("holdings") or []
    from modules.portfolio.analyzer import analyze_portfolio
    result = analyze_portfolio(DB_PATH, holdings)
    status = 400 if "error" in result else 200
    return jsonify(result), status


@app.route("/api/refresh", methods=["POST"])
def refresh():
    """Chạy lại pipeline (blocking, dùng cho demo)."""
    r = subprocess.run([sys.executable, os.path.join(ROOT, "run_pipeline.py")],
                       capture_output=True, text=True, cwd=ROOT, timeout=600)
    ok = r.returncode == 0
    return jsonify({"ok": ok, "log": (r.stdout or "")[-2000:] + (r.stderr or "")[-1000:]})


# --- PILLAR-M: đèn chế độ tiền tệ legal-safe ---
@app.route("/api/macro/regime")
def macro_regime_api():
    from modules.macro_regime.detector import detect
    return jsonify(_sanitize_json(detect(DATA)))


# --- Health tổng hợp: 1 endpoint cho mọi đèn trạng thái (P4) ---
@app.route("/api/health")
def api_health():
    import launcher
    from modules.market_overview.gemini_transport import cdp_status
    data_age = {}
    try:
        for f in os.listdir(DATA):
            if f.endswith(".json"):
                data_age[f] = int(time.time() - os.path.getmtime(os.path.join(DATA, f)))
    except OSError:
        pass
    db_age = None
    if os.path.exists(DB_PATH):
        db_age = int(time.time() - os.path.getmtime(DB_PATH))
    return jsonify({
        "gateway": "ok",
        "children": launcher.child_status(),
        "watchdog": launcher.watchdog_status(),
        "cdp": cdp_status(),                 # gồm cả breaker (P3)
        "db_age_s": db_age,
        "data_age_s": data_age,
    })


# --- App con do gateway tự spawn (crawl :5000 / banggia :5555 / econolens :3333) ---
@app.route("/api/children/status")
def children_status():
    """Trạng thái 3 app con nhúng: {id: {running, pid, port, spawned_by_gateway}}."""
    import launcher
    return jsonify(launcher.child_status())


@app.route("/api/children/restart/<cid>", methods=["POST"])
def children_restart(cid):
    """Khởi động lại 1 app con theo id. 400 nếu id lạ."""
    import launcher
    result = launcher.restart_child(cid)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/children/log/<cid>")
def children_log(cid):
    """100 dòng log cuối của 1 app con (đường dẫn cố định, không nhận path client)."""
    import launcher
    if cid not in launcher._BY_ID:
        return jsonify({"error": f"id không hợp lệ: {cid}"}), 400
    return jsonify({"lines": launcher.tail_log(cid, 100)})


# ============================================================================
# Dữ liệu từ cổng 5000 (Crawl Data) lên 9999
#
# HAI CÁCH KHÁC NHAU, không trộn lẫn:
#   1. Số liệu/tệp TĨNH (coverage, manifest, debug) — đọc THẲNG market.db hoặc
#      companies/*.json, KHÔNG gọi HTTP sang 5000. Vẫn chạy được khi 5000 tắt.
#      (coverage ở đây; manifest/debug đã lên tab "Dữ liệu gốc" — raw_sources.py)
#   2. Điều khiển pipeline SỐNG (bắt đầu/dừng/tiến độ/Gemini) — trạng thái này
#      chỉ tồn tại trong BỘ NHỚ tiến trình :5000, market.db không có, nên BẮT
#      BUỘC phải gọi HTTP. Nếu 5000 tắt, báo lỗi rõ thay vì treo gateway.
# ============================================================================

@app.route("/api/crawl/coverage")
def api_crawl_coverage():
    """Đã crawl/phân tích được bao nhiêu mã — tính thẳng từ market.db.
    group=HOSE|HNX|UPCOM lọc theo sàn; rỗng hoặc giá trị khác → toàn bộ."""
    from modules.common.db import crawl_coverage
    return jsonify(_sanitize_json(
        crawl_coverage(DB_PATH, request.args.get("group", ""))))


CRAWL_URL = os.environ.get("MP_CRAWL_URL", "http://127.0.0.1:5000")


def _crawl_proxy(method: str, path: str, timeout: float = 4.0, **kw):
    """Gọi sang cổng 5000. :5000/run và /stop tự chặn origin lạ (_check_origin)
    nhưng CHO PHÉP request không có header Origin — gọi server-to-server bằng
    `requests` (không phải fetch trình duyệt) nên không gửi Origin, qua được.

    Trả (json, status_code). Mất kết nối → (thông báo lỗi tiếng Việt, 502) thay
    vì để lỗi kết nối thô lọt ra ngoài."""
    import requests
    try:
        r = requests.request(method, f"{CRAWL_URL}{path}", timeout=timeout, **kw)
        return r.json(), r.status_code
    except requests.exceptions.RequestException:
        return ({"ok": False,
                 "msg": "Dịch vụ Crawl Data (cổng 5000) chưa chạy hoặc không phản hồi."},
                502)


@app.route("/api/crawl/start", methods=["POST"])
def api_crawl_start():
    """Bắt đầu 1 lượt pipeline (crawl + phân tích + xuất) cho 1 nhóm mã.
    Validate nhóm/backend NẰM Ở :5000 (nguồn xác thực duy nhất) — ở đây chỉ
    chuyển tiếp, tránh 2 nơi cùng giữ 1 danh sách rồi lệch nhau."""
    body = request.get_json(silent=True) or {}
    payload = {"task": "pipeline",
               "group": str(body.get("group") or "VN30"),
               "backend": str(body.get("backend") or "local_api")}
    if body.get("limit"):
        payload["limit"] = body["limit"]
    if body.get("no_resume"):
        payload["no_resume"] = True
    if body.get("reanalyze"):
        payload["reanalyze"] = True
    data, code = _crawl_proxy("POST", "/run", json=payload)
    return jsonify(data), code


@app.route("/api/crawl/stop", methods=["POST"])
def api_crawl_stop():
    data, code = _crawl_proxy("POST", "/stop")
    return jsonify(data), code


@app.route("/api/crawl/poll")
def api_crawl_poll():
    """Tiến độ lượt đang chạy — client tự poll lặp lại, gửi kèm `since` (con
    trỏ dòng log đã nhận) để chỉ nhận phần MỚI, không tải lại toàn bộ log."""
    since = request.args.get("since", "0")
    data, code = _crawl_proxy("GET", "/poll", params={"since": since})
    return jsonify(data), code


@app.route("/api/crawl/gemini_check", methods=["POST"])
def api_crawl_gemini_check():
    """Kênh AI đang dùng đã sẵn sàng chưa (local_api lên chưa / Gemini đăng
    nhập chưa / bị chặn CAPTCHA...). Không tốn quota — chỉ kiểm tra kết nối."""
    body = request.get_json(silent=True) or {}
    data, code = _crawl_proxy("POST", "/gemini_check", json=body)
    return jsonify(data), code


if __name__ == "__main__":
    # Tự spawn 3 app con trước khi lên (đặt MP_NO_SPAWN=1 để tắt).
    from launcher import start_children
    start_children()
    print("Market Pulse — ALL IN ONE -> http://localhost:9999")
    app.run(host="127.0.0.1", port=9999, debug=False, threaded=True)
