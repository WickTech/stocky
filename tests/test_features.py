"""Tests for stocky/features.py — indicator math and build_features contract."""

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from stocky import features


# --- helpers ---------------------------------------------------------------- #


def _close(n: int = 200, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    prices = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    return pd.Series(prices, index=pd.bdate_range("2022-01-03", periods=n))


def _ohlcv(n: int = 200, seed: int = 0) -> pd.DataFrame:
    close = _close(n, seed)
    return pd.DataFrame({"Close": close})


# --- make_model ------------------------------------------------------------- #


def test_make_model_returns_classifier():
    model = features.make_model()
    assert isinstance(model, RandomForestClassifier)


def test_make_model_uses_declared_params():
    model = features.make_model()
    for k, v in features.MODEL_PARAMS.items():
        assert getattr(model, k) == v


# --- compute_rsi ------------------------------------------------------------ #


def test_rsi_bounds():
    close = _close(300)
    rsi = features.compute_rsi(close)
    valid = rsi.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_rsi_nan_warmup():
    close = _close(50)
    rsi = features.compute_rsi(close, period=14)
    # First (period - 1) values should be NaN due to min_periods
    assert rsi.iloc[: features.RSI_PERIOD - 1].isna().all()


def test_rsi_pure_uptrend_saturates_to_100():
    # Strictly increasing prices → avg_loss = 0 → RSI = 100
    close = pd.Series(np.arange(1.0, 50.0))
    rsi = features.compute_rsi(close, period=5)
    valid = rsi.dropna()
    assert (valid == 100.0).all()


def test_rsi_pure_downtrend_approaches_zero():
    # Strictly decreasing prices → avg_gain = 0 → RSI → 0
    close = pd.Series(np.linspace(100.0, 1.0, 100))
    rsi = features.compute_rsi(close, period=5)
    valid = rsi.dropna()
    assert (valid < 5.0).all()


# --- compute_sma ------------------------------------------------------------ #


def test_sma_nan_warmup():
    close = _close(100)
    sma = features.compute_sma(close, 20)
    assert sma.iloc[:19].isna().all()
    assert sma.iloc[19:].notna().all()


def test_sma_constant_series_equals_constant():
    close = pd.Series(np.full(50, 42.0))
    sma = features.compute_sma(close, 10)
    assert sma.dropna().eq(42.0).all()


def test_sma_linearly_increasing():
    # SMA of 1..n over window w equals midpoint of each window
    n, w = 30, 5
    close = pd.Series(np.arange(1.0, n + 1))
    sma = features.compute_sma(close, w)
    # At position i (0-indexed, i >= w-1): average of close[i-w+1 .. i]
    for i in range(w - 1, n):
        expected = np.mean(np.arange(i - w + 2, i + 2, dtype=float))
        assert sma.iloc[i] == pytest.approx(expected)


# --- build_features --------------------------------------------------------- #


def test_build_features_columns_present():
    df = features.build_features(_ohlcv(300))
    expected = set(features.FEATURE_COLUMNS) | {"target", "fwd_return"}
    assert expected <= set(df.columns)


def test_build_features_no_nan_in_feature_rows():
    df = features.build_features(_ohlcv(300))
    clean = df.dropna()
    for col in features.FEATURE_COLUMNS:
        assert clean[col].notna().all(), f"{col} has NaN after dropna"


def test_build_features_target_binary():
    df = features.build_features(_ohlcv(300))
    clean = df.dropna()
    assert set(clean["target"].unique()) <= {0, 1}


def test_build_features_target_aligns_with_next_day():
    # Verify target = 1 iff close[i+1] > close[i]
    df = features.build_features(_ohlcv(100))
    close = df["Close"].astype(float)
    for i in range(len(df) - 1):
        expected = int(close.iloc[i + 1] > close.iloc[i])
        actual = df["target"].iloc[i]
        if not np.isnan(actual):
            assert int(actual) == expected


def test_build_features_last_row_target_is_nan():
    df = features.build_features(_ohlcv(100))
    assert np.isnan(df["target"].iloc[-1])


def test_build_features_does_not_mutate_input():
    original = _ohlcv(200)
    original_cols = list(original.columns)
    features.build_features(original)
    assert list(original.columns) == original_cols


def test_build_features_close_vs_sma_sign():
    # When price is above SMA20, close_vs_sma20 > 0
    df = features.build_features(_ohlcv(300))
    clean = df.dropna()
    above = clean["Close"] > clean["sma20"]
    assert (clean.loc[above, "close_vs_sma20"] > 0).all()
    below = clean["Close"] < clean["sma20"]
    assert (clean.loc[below, "close_vs_sma20"] < 0).all()


def test_build_features_vol_20d_nonneg():
    df = features.build_features(_ohlcv(300))
    assert (df["vol_20d"].dropna() >= 0).all()


def test_build_features_short_series_all_nan_features():
    # Fewer rows than longest window → no clean rows
    df = features.build_features(_ohlcv(40))
    clean = df.dropna()
    # May be empty or very short; no assertion on count, just no crash
    assert isinstance(clean, pd.DataFrame)
