# -*- coding: utf-8 -*-
"""news_rss: tên toà soạn và ngày tháng.

Hai lỗi ĐÃ XẢY RA THẬT trên dữ liệu FPT và đều im lặng — không ngoại lệ, không
log, chỉ là nội dung sai trôi thẳng vào prompt AI:

1. `find("{http://news.google.com}source")` không khớp vì thẻ `<source>` của
   Google News RSS KHÔNG có namespace ⇒ 25/25 bài rơi vào nhánh dự phòng, lấy
   tiêu đề cắt 60 ký tự làm "tên báo".
2. `pubDate` dạng RFC-2822 được ghi thẳng vào reasons.jsonl, rồi analyzer cắt
   `[:10]` ⇒ AI đọc được "Mon, 27 Ju", và danh sách tin bị sắp theo tên thứ.
"""
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import news_rss  # noqa: E402

RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item>
  <title>FPT rời Top 10 vốn hoá - VnBusiness</title>
  <link>https://news.google.com/rss/articles/CBMiabc</link>
  <pubDate>Mon, 27 Jul 2026 10:21:19 GMT</pubDate>
  <description>&lt;a href="x"&gt;FPT rời Top 10 vốn hoá&lt;/a&gt;</description>
  <source url="https://vnbusiness.vn">VnBusiness</source>
</item>
</channel></rss>"""


def _parse_one():
    item = next(ET.fromstring(RSS).iter("item"))
    el = item.find("source")
    publisher = (el.text or "").strip()
    return {
        "title": news_rss._split_publisher(
            news_rss._clean(item.findtext("title", "")), publisher),
        "source": publisher,
        "source_url": el.get("url", ""),
        "public_date": news_rss._iso_date(item.findtext("pubDate", "")),
    }


def test_lay_dung_ten_toa_soan_khong_namespace():
    assert _parse_one()["source"] == "VnBusiness"


def test_giu_url_toa_soan():
    assert _parse_one()["source_url"] == "https://vnbusiness.vn"


def test_cat_duoi_ten_bao_khoi_tieu_de():
    # Đã có cột riêng cho tên báo thì hậu tố " - VnBusiness" chỉ ăn chỗ của prompt.
    assert _parse_one()["title"] == "FPT rời Top 10 vốn hoá"


def test_ngay_rfc2822_ve_iso():
    assert _parse_one()["public_date"] == "2026-07-27"


def test_iso_giu_nguyen_va_rac_ve_rong():
    assert news_rss._iso_date("2026-07-27T10:00:00") == "2026-07-27"
    assert news_rss._iso_date("") == ""
    assert news_rss._iso_date("hôm qua") == ""


def test_khong_cat_khi_ten_bao_khong_o_cuoi():
    # Chỉ cắt đúng hậu tố " - <tên báo>"; không được đụng tiêu đề có gạch giữa câu.
    assert news_rss._split_publisher("FPT - quý 2 tăng trưởng", "CafeF") \
        == "FPT - quý 2 tăng trưởng"
