# -*- coding: utf-8 -*-
"""macro_forecast.models.return_distribution — dải thống kê lợi suất (không dự báo)."""
import numpy as np
import pandas as pd
import pytest

from modules.macro_forecast.models import return_distribution


def _series(n=300, drift=0.001):
    dates = pd.bdate_range("2023-01-01", periods=n)
    vals = 1000 * np.cumprod(1 + np.full(n, drift))
    return pd.Series(vals, index=dates, name="idx")


def test_available_and_percentiles_ordered():
    rd = return_distribution(_series(), horizon=30)
    assert rd["available"] is True
    b = rd["band"]
    assert b["p5"] <= b["p25"] <= b["p50"] <= b["p75"] <= b["p95"]


def test_base_is_last_value():
    s = _series()
    rd = return_distribution(s, horizon=30)
    assert abs(rd["base"] - float(s.iloc[-1])) < 0.01   # base làm tròn 2 chữ số


def test_n_samples_matches_rolling_windows():
    s = _series(200)
    rd = return_distribution(s, horizon=30)
    assert rd["n_samples"] == 200 - 30


def test_positive_drift_median_positive():
    rd = return_distribution(_series(drift=0.002), horizon=30)
    assert rd["return_pct"]["p50"] > 0


def test_too_short_not_available():
    rd = return_distribution(_series(20), horizon=30)
    assert rd["available"] is False


def test_method_labels_as_descriptive_not_forecast():
    rd = return_distribution(_series(), horizon=30)
    assert "không phải dự báo" in rd["method"].lower()
