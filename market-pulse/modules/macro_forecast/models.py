# -*- coding: utf-8 -*-
"""Mô hình dự báo vĩ mô & thị trường.

- GDP / CPI: SARIMAX (ARIMA) trên chuỗi năm, kèm khoảng tin cậy 80%.
  Backtest: giữ lại 5 năm cuối, so MAE với mô hình naive (giá trị năm trước).
- VN-Index: DẢI THỐNG KÊ lợi suất 30 phiên (return_distribution) trên VNINDEX
  thật (bảng market_index). Đây là thống kê mô tả phân phối lịch sử, KHÔNG phải
  dự báo mô hình. forecast_market (SARIMAX) giữ lại nhưng đã DEPRECATED — dự báo
  giá chỉ số bằng SARIMAX yếu về học thuật, không đưa vào output chính.
"""
import numpy as np
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

from statsmodels.tsa.statespace.sarimax import SARIMAX


def _fit_forecast(series: pd.Series, steps: int, order=(1, 1, 1)):
    model = SARIMAX(series, order=order, trend="c",
                    enforce_stationarity=False, enforce_invertibility=False)
    res = model.fit(disp=False)
    fc = res.get_forecast(steps=steps)
    mean = fc.predicted_mean
    ci = fc.conf_int(alpha=0.2)  # khoảng tin cậy 80%
    return mean, ci


def backtest_annual(series: pd.Series, holdout: int = 5, order=(1, 1, 1)) -> dict:
    """Backtest walk-forward: dự báo từng năm trong `holdout` năm cuối."""
    preds, actuals = [], []
    for i in range(holdout, 0, -1):
        train = series.iloc[:-i]
        actual = series.iloc[-i]
        try:
            mean, _ = _fit_forecast(train, 1, order)
            preds.append(float(mean.iloc[0]))
        except Exception:
            preds.append(float(train.iloc[-1]))
        actuals.append(float(actual))
    preds, actuals = np.array(preds), np.array(actuals)
    naive = series.shift(1).iloc[-holdout:].values
    return {
        "mae_model": float(np.mean(np.abs(preds - actuals))),
        "mae_naive": float(np.mean(np.abs(naive - actuals))),
        "years": [int(y) for y in series.index[-holdout:]],
        "predicted": [round(p, 2) for p in preds],
        "actual": [round(a, 2) for a in actuals],
    }


def forecast_annual(series: pd.Series, horizon: int = 3, order=(1, 1, 1)) -> dict:
    """Dự báo `horizon` năm tới + backtest 5 năm cuối."""
    series = series.dropna().astype(float)
    mean, ci = _fit_forecast(series, horizon, order)
    last_year = int(series.index.max())
    years = [last_year + i for i in range(1, horizon + 1)]
    return {
        "history": {int(y): round(float(v), 2) for y, v in series.items()},
        "forecast": {
            "years": years,
            "mean": [round(float(v), 2) for v in mean],
            "lower": [round(float(v), 2) for v in ci.iloc[:, 0]],
            "upper": [round(float(v), 2) for v in ci.iloc[:, 1]],
        },
        "backtest": backtest_annual(series),
    }


def _align_panel(wide: pd.DataFrame) -> pd.DataFrame:
    """Căn chỉnh bảng giá nhiều mã về khung thời gian chung.

    Giữ mã có số quan sát >= 75% mã dày nhất, cắt các phiên trước ngày mà
    tất cả mã được giữ đều đã có dữ liệu, rồi ffill lỗ hổng nhỏ.
    """
    counts = wide.count()
    keep = counts[counts >= counts.max() * 0.75].index
    wide = wide[keep]
    start = max(wide[c].first_valid_index() for c in wide.columns)
    return wide.loc[start:].ffill().dropna()


def _connect_ro(db_path: str):
    import sqlite3
    try:
        from modules.common.db import connect_readonly
        return connect_readonly(db_path)
    except Exception:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def build_market_index(db_path: str) -> pd.Series:
    """Chỉ số vốn-hoá-trọng-số (proxy VN-Index) từ bảng price + companies."""
    con = _connect_ro(db_path)
    try:
        px = pd.read_sql("select symbol, time, close from price", con)
        caps = pd.read_sql("select symbol, market_cap from companies", con)
    finally:
        con.close()

    px["date"] = pd.to_datetime(px["time"].str[:10])
    wide = px.pivot_table(index="date", columns="symbol", values="close")
    wide = _align_panel(wide)

    w = caps.set_index("symbol")["market_cap"].reindex(wide.columns).fillna(0)
    if w.sum() <= 0:
        w = pd.Series(1.0, index=wide.columns)
    w = w / w.sum()

    # chuẩn hoá mỗi mã về 100 tại phiên đầu rồi lấy trung bình trọng số
    normed = wide / wide.iloc[0] * 100
    return (normed * w).sum(axis=1).rename("index")


def load_vnindex(db_path: str) -> pd.Series:
    """VNINDEX thật từ bảng market_index (nguồn VNDirect). Fallback rỗng."""
    con = _connect_ro(db_path)
    try:
        df = pd.read_sql(
            "SELECT time, close FROM market_index WHERE code='VNINDEX' ORDER BY time", con)
    except Exception:
        return pd.Series(dtype=float)
    finally:
        con.close()
    if len(df) < 2:
        return pd.Series(dtype=float)
    df["date"] = pd.to_datetime(df["time"].str[:10])
    return df.set_index("date")["close"].astype(float).rename("vnindex")


def return_distribution(index: pd.Series, horizon: int = 30) -> dict:
    """DẢI THỐNG KÊ lợi suất `horizon` phiên — thống kê mô tả, KHÔNG dự báo.

    Lấy TOÀN BỘ lịch sử các đoạn `horizon` phiên (rolling, không chồng lấn quá
    dày — bước 1 phiên), tính phân phối lợi suất %, rồi áp percentile
    5/25/50/75/95 lên giá HIỆN TẠI để ra dải giá trị có thể xảy ra theo lịch sử.

    Đây là "trong quá khứ, sau 30 phiên chỉ số đã dao động trong khoảng này" —
    không phải kỳ vọng tương lai. An toàn học thuật hơn SARIMAX trên giá.
    """
    s = index.dropna().astype(float)
    if len(s) < horizon + 5:
        return {"available": False, "reason": f"cần > {horizon + 5} phiên, có {len(s)}"}
    vals = s.values
    # lợi suất % của mọi đoạn horizon phiên
    rets = (vals[horizon:] / vals[:-horizon] - 1) * 100
    pcts = {p: float(np.percentile(rets, p)) for p in (5, 25, 50, 75, 95)}
    base = float(vals[-1])
    band = {f"p{p}": round(base * (1 + v / 100), 2) for p, v in pcts.items()}
    return {
        "available": True,
        "base": round(base, 2),
        "as_of": s.index[-1].strftime("%Y-%m-%d"),
        "horizon": horizon,
        "n_samples": int(len(rets)),
        "method": "Phân phối lợi suất lịch sử (rolling 30 phiên) — thống kê mô tả, không phải dự báo mô hình.",
        "return_pct": {f"p{p}": round(v, 2) for p, v in pcts.items()},
        "band": band,          # giá trị chỉ số theo percentile lịch sử
        "history": {d.strftime("%Y-%m-%d"): round(float(v), 2)
                    for d, v in s.iloc[-250:].items()},
    }


def forecast_market(index: pd.Series, horizon: int = 30) -> dict:
    """DEPRECATED — dự báo SARIMAX trên giá chỉ số (yếu học thuật, không dùng ở
    output chính; giữ để tham khảo/backtest). Dùng return_distribution thay thế.

    Dự báo `horizon` phiên trên log-index + backtest 60 phiên cuối."""
    log_idx = np.log(index)

    # backtest: dự báo 60 phiên cuối theo từng khối 10 phiên
    holdout = 60
    preds = []
    for start in range(holdout, 0, -10):
        train = log_idx.iloc[:-start]
        try:
            mean, _ = _fit_forecast(train, min(10, start), order=(2, 1, 2))
            preds.extend(np.exp(mean).tolist())
        except Exception:
            preds.extend([float(np.exp(train.iloc[-1]))] * min(10, start))
    actual = index.iloc[-holdout:].values
    preds = np.array(preds[:holdout])
    naive = np.full(holdout, float(index.iloc[-holdout - 1]))

    mean, ci = _fit_forecast(log_idx, horizon, order=(2, 1, 2))
    freq_dates = pd.bdate_range(index.index[-1], periods=horizon + 1)[1:]
    return {
        "history": {d.strftime("%Y-%m-%d"): round(float(v), 2)
                    for d, v in index.iloc[-250:].items()},
        "forecast": {
            "dates": [d.strftime("%Y-%m-%d") for d in freq_dates],
            "mean": [round(float(np.exp(v)), 2) for v in mean],
            "lower": [round(float(np.exp(v)), 2) for v in ci.iloc[:, 0]],
            "upper": [round(float(np.exp(v)), 2) for v in ci.iloc[:, 1]],
        },
        "backtest": {
            "rmse_model": float(np.sqrt(np.mean((preds - actual) ** 2))),
            "rmse_naive": float(np.sqrt(np.mean((naive - actual) ** 2))),
            "mape_model": float(np.mean(np.abs(preds - actual) / actual) * 100),
        },
    }
