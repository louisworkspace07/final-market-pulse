# -*- coding: utf-8 -*-
"""Đưa gốc market-pulse/ vào sys.path để `import modules.*` chạy được."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
