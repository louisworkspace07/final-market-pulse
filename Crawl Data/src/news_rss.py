"""Tin báo chí THẬT qua Google News RSS (khác tin công bố thông tin của vnstock).

vnstock news = công bố/nghị quyết (trọng số thấp, nhiều nhiễu). RSS báo chí bổ sung
góc nhìn thị trường: bài phân tích, sự kiện ngành, tin vĩ mô liên quan doanh nghiệp.

Parse bằng xml.etree (không thêm dependency). Phụ thuộc mạng ngoài → luôn có
timeout + chịu được lỗi/chặn (trả list rỗng, không ném ra ngoài).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests

TIMEOUT = 10
LIMIT = 25   # số bài mới nhất giữ lại
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MarketPulse/1.0)"}
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return _TAG_RE.sub("", text or "").strip()


def _iso_date(v: str) -> str:
    """RFC-2822 của RSS ('Mon, 27 Jul 2026 10:21:19 GMT') → '2026-07-27'.

    LỖI ĐÃ SỬA: chuỗi thô này được ghi thẳng vào reasons.jsonl, rồi analyzer cắt
    `date[:10]` để đưa vào prompt ⇒ AI đọc được đúng "Mon, 27 Ju". Tệ hơn,
    `_load_reasons` sắp xếp tin theo chuỗi ngày này nên thứ tự "gần đây nhất"
    thực ra là thứ tự bảng chữ cái của tên thứ trong tuần.
    """
    s = (v or "").strip()
    if not s:
        return ""
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).date().isoformat()
    except Exception:                                        # noqa: BLE001
        return s[:10] if len(s) >= 10 and s[4] == "-" else ""


def _split_publisher(title: str, publisher: str) -> str:
    """Google News nối " - <Tên báo>" vào cuối tiêu đề. Đã có cột riêng cho tên
    báo thì phần đuôi đó chỉ tổ ăn mất 15–20 ký tự của tiêu đề trong prompt."""
    if publisher and title.endswith(" - " + publisher):
        return title[: -(len(publisher) + 3)].strip()
    return title


def fetch(symbol: str, company_name: str = "", limit: int = LIMIT) -> list[dict]:
    """Lấy tin báo chí mới nhất cho 1 mã. Trả [] nếu lỗi mạng/parse."""
    query = f"{symbol} cổ phiếu"
    if company_name:
        query = f"{symbol} {company_name}"
    url = ("https://news.google.com/rss/search?q="
           + quote(query) + "&hl=vi&gl=VN&ceid=VN:vi")
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception:
        return []

    out: list[dict] = []
    for item in root.iter("item"):
        title = _clean(item.findtext("title", ""))
        if not title:
            continue
        # LỖI ĐÃ SỬA: tìm theo namespace `{http://news.google.com}source` — nhưng
        # Google News RSS trả thẻ `<source url="https://vnbusiness.vn">VnBusiness</source>`
        # KHÔNG có namespace. `find()` luôn None ⇒ mọi bài rơi vào nhánh dự phòng
        # `description[:60]`, tức lấy chính TIÊU ĐỀ bị cắt cụt làm "tên báo"
        # (đo thật trên FPT: 25/25 bài sai). Tìm không namespace, và giữ cả URL
        # toà soạn để giao diện hiện được nguồn có thể kiểm chứng.
        source_el = item.find("source")
        if source_el is None:
            source_el = item.find("{http://news.google.com}source")
        publisher = (source_el.text or "").strip() if source_el is not None else ""
        out.append({
            "title": _split_publisher(title, publisher),
            "link": (item.findtext("link", "") or "").strip(),
            "public_date": _iso_date(item.findtext("pubDate", "")),
            "source": publisher or _clean(item.findtext("description", ""))[:60],
            "source_url": (source_el.get("url", "") if source_el is not None else ""),
        })
        if len(out) >= limit:
            break
    return out
