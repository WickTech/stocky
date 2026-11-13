"""market_intelligence: helpers, fetch, per-ticker pipeline and rendering.

No network: yfinance.download is monkeypatched everywhere.
"""

import math

import numpy as np
import pandas as pd
import pytest

import market_intelligence as mi


def _ohlcv(n: int = 700, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=idx,
    )


# --------------------------- small helpers ---------------------------------- #


@pytest.mark.parametrize(
    "value,expected",
    [(1, 1.0), (np.float64(2.5), 2.5), ("3.5", 3.5)],
)
def test_safe_passes_through_numbers(value, expected):
    assert mi._safe(value) == expected


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), -float("inf"), "abc", [1]])
def test_safe_returns_default_for_bad_values(value):
    assert math.isnan(mi._safe(value))
    assert mi._safe(value, default=-1.0) == -1.0


def test_fmt_pct_and_half_life_handle_nan():
    nan = float("nan")
    assert mi._fmt(nan, 2) == "n/a"
    assert mi._fmt(1.23456, 2) == "1.23"
    assert mi._pct(nan) == "n/a"
    assert mi._pct(0.1234) == "12.3%"
    assert mi._fmt_half_life(nan) == "n/a"
    assert mi._fmt_half_life(3.14159) == "3.1 days"


def test_fmt_autocorr_and_direction():
    assert mi._fmt_autocorr({}) == "n/a"
    assert mi._fmt_autocorr({1: 0.5, 5: float("nan")}) == "L1=0.50, L5=n/a"
    assert mi._direction(None) == "n/a"
    assert mi._direction(1) == "UP"
    assert mi._direction(0) == "DOWN"


# --------------------------- column flattening ------------------------------ #


def test_flatten_columns_noop_for_flat_frame():
    df = _ohlcv(5)
    out = mi._flatten_columns(df, "AAPL")
    assert list(out.columns) == list(df.columns)


def test_flatten_columns_none_and_empty_passthrough():
    assert mi._flatten_columns(None, "X") is None
    empty = pd.DataFrame()
    assert mi._flatten_columns(empty, "X") is empty


def test_flatten_columns_fields_on_level0():
    df = _ohlcv(5)
    df.columns = pd.MultiIndex.from_product([df.columns, ["AAPL"]])
    out = mi._flatten_columns(df, "AAPL")
    assert list(out.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_flatten_columns_fields_on_level1():
    df = _ohlcv(5)
    df.columns = pd.MultiIndex.from_product([["AAPL"], df.columns])
    out = mi._flatten_columns(df, "AAPL")
    assert "Close" in out.columns and not isinstance(out.columns, pd.MultiIndex)


def test_flatten_columns_unknown_ticker_falls_back_to_field_level():
    df = _ohlcv(5)
    df.columns = pd.MultiIndex.from_product([df.columns, ["AAPL"]])
    out = mi._flatten_columns(df, "OTHER")
    assert "Close" in out.columns


def test_flatten_columns_aliases_adj_close():
    df = _ohlcv(5).rename(columns={"Close": "Adj Close"})
    out = mi._flatten_columns(df, "X")
    assert "Close" in out.columns and "Adj Close" not in out.columns


# --------------------------- fetch_history ---------------------------------- #


def test_fetch_history_returns_flat_frame(monkeypatch):
    raw = _ohlcv(10)
    raw.columns = pd.MultiIndex.from_product([raw.columns, ["AAPL"]])
    calls = {}

    def fake_download(ticker, **kw):
        calls["ticker"], calls["kw"] = ticker, kw
        return raw

    monkeypatch.setattr(mi.yf, "download", fake_download)
    df = mi.fetch_history("AAPL")
    assert df is not None and "Close" in df.columns
    assert calls["ticker"] == "AAPL"
    assert calls["kw"]["period"] == mi.HISTORY_PERIOD
    assert calls["kw"]["progress"] is False


def test_fetch_history_none_on_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(mi.yf, "download", boom)
    assert mi.fetch_history("AAPL") is None


@pytest.mark.parametrize("raw", [None, pd.DataFrame()])
def test_fetch_history_none_on_empty(monkeypatch, raw):
    monkeypatch.setattr(mi.yf, "download", lambda *a, **k: raw)
    assert mi.fetch_history("AAPL") is None


def test_fetch_history_none_when_close_missing(monkeypatch):
    raw = pd.DataFrame({"Foo": [1, 2, 3]})
    monkeypatch.setattr(mi.yf, "download", lambda *a, **k: raw)
    assert mi.fetch_history("AAPL") is None


# --------------------------- analyze_ticker --------------------------------- #


def test_analyze_ticker_unavailable_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(mi, "fetch_history", lambda t: None)
    p = mi.analyze_ticker("ZZZ")
    assert not p.available
    assert "data unavailable" in p.reason
    assert p.prediction is None


def test_analyze_ticker_insufficient_history(monkeypatch):
    monkeypatch.setattr(mi, "fetch_history", lambda t: _ohlcv(120))
    p = mi.analyze_ticker("ZZZ")
    assert not p.available
    assert "insufficient clean history" in p.reason
    # Live snapshot is still captured before the training gate.
    assert not math.isnan(p.close)
    assert not math.isnan(p.sma20)


def test_analyze_ticker_full_pipeline(monkeypatch):
    monkeypatch.setattr(mi, "fetch_history", lambda t: _ohlcv(700))
    p = mi.analyze_ticker("ZZZ", alpha_adj=0.01)
    assert p.available, p.reason
    assert p.prediction in (0, 1)
    assert 0.5 <= p.confidence <= 1.0   # probability of the predicted (max) class
    assert 0.0 <= p.accuracy <= 1.0
    assert p.n_rows > mi.MIN_TRAINING_ROWS
    assert p.oos_alpha == 0.01
    assert p.oos_verdict in {"PASS", "FAIL", "n/a"}
    assert p.oos_n == p.n_rows - int(p.n_rows * (mi.TRAIN_FRAC + mi.VAL_FRAC))
    assert set(p.autocorr) == set(mi.metrics.DEFAULT_LAGS)


def test_analyze_ticker_single_class_target_is_skipped(monkeypatch):
    n = 400
    idx = pd.bdate_range("2020-01-01", periods=n)
    close = pd.Series(np.linspace(100, 300, n), index=idx)  # strictly rising -> target always 1
    df = pd.DataFrame({"Close": close})
    monkeypatch.setattr(mi, "fetch_history", lambda t: df)
    p = mi.analyze_ticker("ZZZ")
    assert not p.available
    assert "class variety" in p.reason


def test_analyze_ticker_reports_model_failure(monkeypatch):
    class Broken:
        def fit(self, *a, **k):
            raise ValueError("kaput")

    monkeypatch.setattr(mi, "fetch_history", lambda t: _ohlcv(700))
    monkeypatch.setattr(mi, "make_model", lambda: Broken())
    p = mi.analyze_ticker("ZZZ")
    assert not p.available
    assert p.reason == "model training failed: kaput"


# --------------------------- run_batch -------------------------------------- #


def test_run_batch_isolates_failures_and_adjusts_alpha(monkeypatch):
    seen = []

    def fake_analyze(ticker, alpha_adj):
        seen.append((ticker, alpha_adj))
        if ticker == "BAD":
            raise RuntimeError("explode")
        return mi.TickerProfile(ticker=ticker, available=True)

    monkeypatch.setattr(mi, "analyze_ticker", fake_analyze)
    monkeypatch.setattr(mi, "N_CONFIGS_TRIED", 2)
    out = mi.run_batch(["A", "BAD", "C"])
    assert [p.ticker for p in out] == ["A", "BAD", "C"]
    assert [p.available for p in out] == [True, False, True]
    assert out[1].reason == "unexpected error: explode"
    # alpha / (3 tickers x 2 configs)
    assert all(a == pytest.approx(mi.metrics.ALPHA / 6) for _, a in seen)


# --------------------------- rendering -------------------------------------- #


def _profile(**kw) -> mi.TickerProfile:
    base = dict(
        ticker="TST", available=True, close=110.0, rsi14=55.0, sma20=105.0,
        sma50=100.0, daily_return=0.012, accuracy=0.52, prediction=1,
        confidence=0.61, n_rows=500, val_icir=0.4, val_icir_months=12,
        oos_ic=0.05, oos_n=150, oos_alpha=0.005, oos_verdict="FAIL",
        half_life_days=2.5, autocorr={1: 0.3},
    )
    base.update(kw)
    return mi.TickerProfile(**base)


def test_render_unavailable_profile_shows_reason_and_snapshot():
    p = mi.TickerProfile(ticker="X", reason="no data", close=12.3456, rsi14=40.0)
    text = mi.render_profile(p, 2)
    assert "DATA UNAVAILABLE" in text and "no data" in text
    assert "Last Close    : 12.35" in text
    assert "RSI(14)       : 40.0" in text


def test_render_unavailable_without_close_has_no_snapshot():
    text = mi.render_profile(mi.TickerProfile(ticker="X", reason="r"), 2)
    assert "Last Close" not in text


@pytest.mark.parametrize(
    "rsi,flag",
    [(75.0, "OVERBOUGHT"), (25.0, "OVERSOLD"), (50.0, None)],
)
def test_render_rsi_flags(rsi, flag):
    text = mi.render_profile(_profile(rsi14=rsi), 2)
    if flag:
        assert flag in text
    else:
        assert "OVERBOUGHT" not in text and "OVERSOLD" not in text


@pytest.mark.parametrize(
    "close,s20,s50,expected",
    [
        (110, 105, 100, "Uptrend"),
        (90, 95, 100, "Downtrend"),
        (102, 105, 100, "Mixed"),
        (float("nan"), 105, 100, "n/a"),
    ],
)
def test_render_trend_read(close, s20, s50, expected):
    text = mi.render_profile(_profile(close=close, sma20=s20, sma50=s50), 2)
    trend_line = next(l for l in text.splitlines() if "Trend Read" in l)
    assert expected in trend_line


def test_render_uses_requested_price_decimals():
    text = mi.render_profile(_profile(close=1.234567, sma20=1.2, sma50=1.1), 4)
    assert "Last Close    : 1.2346" in text


def test_render_prediction_and_confidence_lines():
    text = mi.render_profile(_profile(prediction=0, confidence=0.7), 2)
    assert "Prediction    : DOWN" in text
    assert "Confidence    : 70.0%" in text


def test_write_context_file_contains_all_sections(tmp_path):
    ok = _profile(ticker="OK1")
    bad = mi.TickerProfile(ticker="BAD1", reason="nope")
    out = tmp_path / "ctx.txt"
    mi.write_context_file(str(out), "TITLE", [ok, bad], 2, ["note line"])
    text = out.read_text(encoding="utf-8")
    assert "TITLE" in text and "note line" in text
    assert "Universe: 2 tickers  |  Modeled OK: 1" in text
    assert "### OK1" in text and "### BAD1" in text
    summary = text.split("SUMMARY")[1]
    ok_row = next(l for l in summary.splitlines() if l.startswith("OK1"))
    bad_row = next(l for l in summary.splitlines() if l.startswith("BAD1"))
    assert "UP" in ok_row and "FAIL" in ok_row
    assert "N/A" in bad_row
    assert "Educational use only" in text


# --------------------------- main ------------------------------------------- #


def test_main_writes_three_outputs_without_network(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mi, "fetch_history", lambda t: None)
    assert mi.main() == 0
    for name in (mi.EQUITY_OUTPUT, mi.GLOBAL_OUTPUT, mi.FOREX_OUTPUT):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "Modeled OK: 0" in text
