# -*- coding: utf-8 -*-
"""Soi Tin — factcheck tin đồn thị trường (P1).

extractor  → bóc claim + mã CK + loại claim từ đoạn text người dùng dán.
checker    → đối chiếu mỗi claim với market.db (news/events/financials/price).
engine     → tổng hợp AI (có nguồn) + fallback thuần Python; gán nhãn trung tính.
"""
