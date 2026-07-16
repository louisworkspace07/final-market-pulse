# -*- coding: utf-8 -*-
"""Đưa gốc dự án (Crawl Data/) vào sys.path để `import src.*` chạy được khi
pytest gọi từ bất kỳ cwd nào."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
