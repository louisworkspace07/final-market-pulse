# -*- coding: utf-8 -*-
"""Lấy NỘI DUNG bài báo về để AI đọc, thay vì bắt AI đoán từ mỗi cái tiêu đề.

Vì sao cần: tin trong market.db là công bố thông tin của vnstock/VCI, và đo thật
trên FPT thì 0/50 bản ghi có `news_short_content`. Nút "AI phân tích hộ" vì thế
xưa nay chỉ gửi đi đúng một dòng tiêu đề pháp lý — AI không có gì để đọc.

Chỉ tải khi người dùng BẤM (1 request/lần bấm), không tải hàng loạt lúc crawl:
1.531 mã × 25 bài là 38.000 request tới các toà soạn, vừa chậm vừa bất lịch sự.

Trích nội dung bằng regex trên HTML thô, không thêm thư viện. Không đòi hỏi trích
hoàn hảo — AI chỉ cần đủ chữ để hiểu bài viết nói gì.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

TIMEOUT = 12
MAX_BYTES = 1_500_000     # trần tải về; bài dài nhất đo được ~700 KB
MAX_CHARS = 4_000         # trần chữ gửi cho AI

# Link Google News (news.google.com/rss/articles/CBMi...) KHÔNG chuyển hướng phía
# máy chủ — tải về chỉ được trang trung gian chạy JavaScript, đo thật: 579.914 byte
# toàn khung Google, không một chữ nào của bài. Chặn thẳng và nói rõ lý do thay vì
# gửi rác cho AI rồi để nó bịa.
_NO_BODY_HOSTS = ("news.google.com", "google.com", "google.com.vn")

_DROP_BLOCKS = re.compile(
    r"<(script|style|noscript|iframe|svg|nav|header|footer|form)\b[^>]*>.*?</\1>",
    re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")
_NL = re.compile(r"\n{3,}")


class ArticleError(Exception):
    """Không lấy được nội dung — thông điệp đã viết sẵn cho người đọc."""


def _public_url(url: str) -> str:
    """Chặn SSRF: URL đến từ client nên phải tự kiểm, không tin đầu vào.

    Chỉ cho http/https tới địa chỉ công cộng. Loopback/private/link-local đều bị
    từ chối — nếu không thì một POST tự chế có thể biến gateway thành proxy đọc
    dịch vụ nội bộ (:5000, :9999, metadata máy chủ…).
    """
    u = urlparse((url or "").strip())
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ArticleError("Đường dẫn không hợp lệ")
    host = u.hostname.lower()
    if any(host == h or host.endswith("." + h) for h in _NO_BODY_HOSTS):
        raise ArticleError(
            "Link Google News chỉ là trang chuyển tiếp chạy JavaScript, không có "
            "nội dung bài để đọc. Mở bài gốc bằng nút ↗ rồi dán lại nội dung nếu cần.")
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        raise ArticleError("Không phân giải được tên miền của bài báo") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast):
            raise ArticleError("Địa chỉ không được phép truy cập")
    return u.geturl()


def _strip(html: str) -> str:
    txt = _DROP_BLOCKS.sub(" ", html)
    txt = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", txt, flags=re.I)
    txt = _TAGS.sub(" ", txt)
    for ent, ch in (("&nbsp;", " "), ("&amp;", "&"), ("&quot;", '"'),
                    ("&#39;", "'"), ("&lt;", "<"), ("&gt;", ">")):
        txt = txt.replace(ent, ch)
    txt = _WS.sub(" ", txt)
    return _NL.sub("\n\n", txt).strip()


def _best_block(html: str) -> str:
    """Ưu tiên <article>; không có thì lấy toàn trang rồi lọc dòng rác.

    Menu/breadcrumb/quảng cáo là những dòng RẤT ngắn; câu văn thật của báo tiếng
    Việt gần như luôn dài hơn 80 ký tự. Lọc theo độ dài là đủ mà không phải nuôi
    một bộ selector riêng cho từng toà soạn.
    """
    m = re.search(r"<article\b[^>]*>(.*?)</article>", html, re.I | re.S)
    text = _strip(m.group(1) if m else html)
    lines = [ln.strip() for ln in text.split("\n")]
    keep = [ln for ln in lines if len(ln) >= 80]
    return "\n\n".join(keep) if len("\n\n".join(keep)) >= 400 else text


def fetch(url: str) -> str:
    """Nội dung bài, đã cắt còn MAX_CHARS. Lỗi → ném ArticleError có lời giải thích."""
    import requests

    safe = _public_url(url)
    try:
        r = requests.get(safe, timeout=TIMEOUT, stream=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MarketPulse/1.0",
            "Accept-Language": "vi,en;q=0.8"})
        r.raise_for_status()
        if "html" not in (r.headers.get("Content-Type") or "").lower():
            raise ArticleError("Đường dẫn không trả về trang HTML")
        raw = r.raw.read(MAX_BYTES, decode_content=True) or b""
    except ArticleError:
        raise
    except Exception as exc:                                   # noqa: BLE001
        raise ArticleError(f"Không tải được bài gốc: {str(exc)[:120]}") from exc

    html = raw.decode(r.encoding or "utf-8", errors="replace")
    body = _best_block(html)
    if len(body) < 200:
        raise ArticleError("Trang không có đủ nội dung chữ để phân tích")
    return body[:MAX_CHARS]
