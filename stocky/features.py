"""Feature engineering and model parameters.

This is the ONLY file the Phase B experiment loop may edit (see program.md).
metrics.py, the split, and the locked OOS set are read-only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

RSI_PERIOD = 14
SMA_FAST = 20
SMA_SLOW = 50

FEATURE_COLUMNS = [
    "rsi14",
    "sma20",
    "sma50",
    "daily_return",
    "close_vs_sma20",   # price positioning relative to fast SMA
    "close_vs_sma50",   # price positioning relative to slow SMA
]

MODEL_PARAMS = {
    "n_estimators": 200,
    "random_state": 42,
    "n_jobs": -1,
}


def make_model() -> RandomForestClassifier:
    return RandomForestClassifier(**MODEL_PARAMS)


def compute_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Wilder-smoothed Relative Strength Index over `period` days."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    # Wilder's smoothing == EWMA with alpha = 1/period.
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    # When avg_loss is 0 (pure uptrend), RSI saturates to 100.
    rsi = rsi.where(avg_loss != 0.0, 100.0)
    return rsi


def compute_sma(close: pd.Series, window: int) -> pd.Series:
    """Simple moving average over `window` days."""
    return close.rolling(window=window, min_periods=window).mean()


def compute_daily_returns(close: pd.Series) -> pd.Series:
    """Day-over-day percentage return."""
    return close.pct_change()


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Attach indicator columns, the feature set, and the ML target.

    Target = 1 if the NEXT day's close is higher than today's, else 0.
    The final row (which has no "next day") is dropped by the NaN filter.
    """
    out = df.copy()
    close = out["Close"].astype(float)

    out["rsi14"] = compute_rsi(close, RSI_PERIOD)
    out["sma20"] = compute_sma(close, SMA_FAST)
    out["sma50"] = compute_sma(close, SMA_SLOW)
    out["daily_return"] = compute_daily_returns(close)

    # Relative positioning features (how far price sits above/below each SMA).
    out["close_vs_sma20"] = (close - out["sma20"]) / out["sma20"]
    out["close_vs_sma50"] = (close - out["sma50"]) / out["sma50"]

    # Target: next-day direction. fwd_return is the realized next-day return the
    # signal is scored against (IC); it is never a model input.
    out["target"] = (close.shift(-1) > close).astype(int)
    out["fwd_return"] = close.shift(-1) / close - 1.0
    # The shifted-in NaN on the last row marks "no future" -> excluded on dropna.
    out.loc[out.index[-1], "target"] = np.nan

    return out
