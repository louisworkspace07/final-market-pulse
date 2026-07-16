# -*- coding: utf-8 -*-
"""article_text: hàng rào SSRF và bóc chữ khỏi HTML.

URL truyền vào đến TỪ CLIENT (thân POST /api/stock/<mã>/news_ai), nên nếu không
tự kiểm thì gateway trở thành proxy đọc hộ mọi dịch vụ nội bộ — :5000, :9999,
endpoint metadata của máy chủ. Đây là hàng rào đó, phải có test giữ.
"""
import pytest

from modules.stock_page import article_text as A


@pytest.mark.parametrize("url", [
    "http://localhost:9999/api/stock/FPT",
    "http://127.0.0.1:5000/",
    "http://[::1]/",
    "http://169.254.169.254/latest/meta-data/",   # metadata máy ảo
])
def test_chan_dia_chi_noi_bo(url):
    with pytest.raises(A.ArticleError):
        A._public_url(url)


@pytest.mark.parametrize("url", [
    "file:///C:/Windows/win.ini",
    "ftp://example.com/x",
    "javascript:alert(1)",
    "",
])
def test_chan_giao_thuc_khong_phai_http(url):
    with pytest.raises(A.ArticleError):
        A._public_url(url)


def test_chan_link_google_news_kem_ly_do():
    # Không phải vấn đề an toàn: link này chỉ là trang chuyển tiếp chạy
    # JavaScript, tải về được 0 chữ của bài. Chặn sớm để AI không đọc rác.
    with pytest.raises(A.ArticleError) as e:
        A._public_url("https://news.google.com/rss/articles/CBMiabc")
    assert "Google News" in str(e.value)


def test_bo_script_style_va_the_html():
    html = ("<html><head><style>.a{color:red}</style></head><body>"
            "<script>var x=1</script><p>" + "Câu văn thật đủ dài để giữ lại. " * 4
            + "</p></body></html>")
    out = A._strip(html)
    assert "var x=1" not in out and "color:red" not in out
    assert "Câu văn thật đủ dài để giữ lại." in out


def test_uu_tien_the_article_va_bo_dong_ngan():
    dai = "Đây là một câu văn dài thật sự của bài báo, đủ vượt ngưỡng tám mươi ký tự. "
    html = ("<body><nav>Trang chủ</nav><article><p>" + dai * 6
            + "</p></article><footer>Bản quyền</footer></body>")
    out = A._best_block(html)
    assert "Trang chủ" not in out and "Bản quyền" not in out
    assert dai.strip() in out


def test_giai_ma_thuc_the_html():
    assert "&" in A._strip("<p>Tổng CTCP A &amp; B</p>")
    assert "&amp;" not in A._strip("<p>Tổng CTCP A &amp; B</p>")
