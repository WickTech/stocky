#!/usr/bin/env python3
"""stocky — local market intelligence engine.

Fetches 5 years of daily history for a fixed universe of Indian equities and forex
pairs, engineers a small set of technical features (14-day RSI, 20/50-day SMA, daily
returns), trains a per-ticker Random Forest classifier to predict next-day direction,
backtests it on a chronological hold-out, and writes two scannable plain-text context
files:

    context_indian_stocks.txt   (NSE swing/delivery profiles)
    context_forex.txt           (relative-strength / macro profiles, 4-decimal prices)

These files are designed to be fed back into a Claude Project configured by
`.project_instructions.md`, which applies the risk-management rules on top of the raw
signals.

The pipeline is defensive: a ticker that yfinance fails to return, or that has too
little clean history to train on, is logged and given a "data unavailable" profile —
it never crashes the whole run.

Run:  python market_intelligence.py
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - dependency guard
    sys.exit(
        "Missing dependency 'yfinance'. Install requirements first:\n"
        "    pip install -r requirements.txt"
    )

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

INDIAN_STOCKS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "SBIN.NS"]
FOREX_PAIRS = ["USDINR=X", "EURUSD=X", "GBPUSD=X", "AUDUSD=X"]

HISTORY_PERIOD = "5y"        # 5 years of daily candles
DATA_INTERVAL = "1d"
RSI_PERIOD = 14
SMA_FAST = 20
SMA_SLOW = 50

# Minimum number of clean (NaN-free) rows required to bother training. With a
# 50-day SMA we lose ~50 rows up front; this leaves a healthy training sample.
MIN_TRAINING_ROWS = 150

TEST_SIZE = 0.20             # chronological 80/20 split
RANDOM_STATE = 42
N_ESTIMATORS = 200

EQUITY_OUTPUT = "context_indian_stocks.txt"
FOREX_OUTPUT = "context_forex.txt"

FEATURE_COLUMNS = [
    "rsi14",
    "sma20",
    "sma50",
    "daily_return",
    "close_vs_sma20",   # price positioning relative to fast SMA
    "close_vs_sma50",   # price positioning relative to slow SMA
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("stocky")


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #


@dataclass
class TickerProfile:
    """Everything we need to render one ticker's text block."""

    ticker: str
    available: bool = False
    reason: str = ""                       # populated when available is False

    # Latest live metrics
    close: float = float("nan")
    rsi14: float = float("nan")
    sma20: float = float("nan")
    sma50: float = float("nan")
    daily_return: float = float("nan")

    # Model output
    accuracy: float = float("nan")         # backtested test-set accuracy (0..1)
    prediction: Optional[int] = None       # 1 = UP, 0 = DOWN
    confidence: float = float("nan")       # probability of the predicted class (0..1)
    n_rows: int = 0

    extra: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Small numeric helpers (defensive)
# --------------------------------------------------------------------------- #


def _safe(value, default: float = float("nan")) -> float:
    """Coerce a scalar (possibly numpy / NaN / None) to a plain float, defensively."""
    try:
        if value is None:
            return default
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _flatten_columns(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Collapse yfinance's (sometimes MultiIndex) columns into flat OHLCV names.

    yfinance returns either flat columns (single ticker, older behavior) or a
    MultiIndex like ('Close', 'RELIANCE.NS'). This normalizes both into flat
    columns: Open / High / Low / Close / Volume.
    """
    if df is None or df.empty:
        return df

    if isinstance(df.columns, pd.MultiIndex):
        # Prefer the level that holds the OHLCV field names.
        level0 = set(df.columns.get_level_values(0))
        ohlcv = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}
        if ohlcv & level0:
            # Field names are on level 0; select this ticker's slice on level 1.
            try:
                df = df.xs(ticker, axis=1, level=1)
            except (KeyError, ValueError):
                df.columns = df.columns.get_level_values(0)
        else:
            # Field names are on level 1.
            try:
                df = df.xs(ticker, axis=1, level=0)
            except (KeyError, ValueError):
                df.columns = df.columns.get_level_values(-1)

    # If "Close" is absent but "Adj Close" exists, alias it.
    if "Close" not in df.columns and "Adj Close" in df.columns:
        df = df.rename(columns={"Adj Close": "Close"})

    return df


# --------------------------------------------------------------------------- #
# Indicator math (pure pandas / numpy — no TA-Lib dependency)
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# Data fetch + feature engineering
# --------------------------------------------------------------------------- #


def fetch_history(ticker: str) -> Optional[pd.DataFrame]:
    """Download 5y of daily data for one ticker and return a flat OHLCV frame.

    Returns None on any failure or empty response.
    """
    try:
        raw = yf.download(
            ticker,
            period=HISTORY_PERIOD,
            interval=DATA_INTERVAL,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception as exc:  # network / yfinance internal errors
        log.warning("  fetch failed for %s: %s", ticker, exc)
        return None

    if raw is None or raw.empty:
        log.warning("  no data returned for %s", ticker)
        return None

    df = _flatten_columns(raw, ticker)
    if df is None or df.empty or "Close" not in df.columns:
        log.warning("  unusable column structure for %s", ticker)
        return None

    return df


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

    # Target: next-day direction.
    out["target"] = (close.shift(-1) > close).astype(int)
    # The shifted-in NaN on the last row marks "no future" -> excluded on dropna.
    out.loc[out.index[-1], "target"] = np.nan

    return out


# --------------------------------------------------------------------------- #
# Modeling pipeline
# --------------------------------------------------------------------------- #


def analyze_ticker(ticker: str) -> TickerProfile:
    """Full per-ticker pipeline: fetch -> features -> train -> predict.

    Always returns a TickerProfile; on any data problem it returns one with
    `available=False` and a human-readable `reason`.
    """
    log.info("Analyzing %s ...", ticker)
    profile = TickerProfile(ticker=ticker)

    df = fetch_history(ticker)
    if df is None:
        profile.reason = "data unavailable (fetch returned nothing)"
        return profile

    featured = build_features(df)

    # Capture the latest live snapshot BEFORE dropping rows for training, so we
    # always report current metrics even if the target row is NaN.
    last = featured.iloc[-1]
    profile.close = _safe(last.get("Close"))
    profile.rsi14 = _safe(last.get("rsi14"))
    profile.sma20 = _safe(last.get("sma20"))
    profile.sma50 = _safe(last.get("sma50"))
    profile.daily_return = _safe(last.get("daily_return"))

    # Clean training set: features + target all present.
    model_cols = FEATURE_COLUMNS + ["target"]
    clean = featured[model_cols].replace([np.inf, -np.inf], np.nan).dropna()
    profile.n_rows = len(clean)

    if len(clean) < MIN_TRAINING_ROWS:
        profile.reason = (
            f"insufficient clean history ({len(clean)} rows < "
            f"{MIN_TRAINING_ROWS} required)"
        )
        log.warning("  %s skipped: %s", ticker, profile.reason)
        return profile

    X = clean[FEATURE_COLUMNS].values
    y = clean["target"].values.astype(int)

    # Chronological (non-shuffled) 80/20 split — never leak the future.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, shuffle=False
    )

    if len(X_train) == 0 or len(X_test) == 0 or len(np.unique(y_train)) < 2:
        profile.reason = "not enough class variety / samples after split"
        log.warning("  %s skipped: %s", ticker, profile.reason)
        return profile

    model = RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    try:
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        profile.accuracy = _safe(accuracy_score(y_test, y_pred))
    except Exception as exc:
        profile.reason = f"model training failed: {exc}"
        log.warning("  %s skipped: %s", ticker, profile.reason)
        return profile

    # Predict on today's latest fully-formed feature row.
    latest_feat = featured[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).dropna()
    if latest_feat.empty:
        profile.reason = "no complete feature row for live prediction"
        log.warning("  %s skipped: %s", ticker, profile.reason)
        return profile

    live_row = latest_feat.iloc[[-1]].values
    try:
        pred = int(model.predict(live_row)[0])
        proba = model.predict_proba(live_row)[0]
        # Confidence = probability mass on the predicted class.
        class_index = list(model.classes_).index(pred)
        profile.prediction = pred
        profile.confidence = _safe(proba[class_index])
    except Exception as exc:
        profile.reason = f"live prediction failed: {exc}"
        log.warning("  %s skipped: %s", ticker, profile.reason)
        return profile

    profile.available = True
    log.info(
        "  %s -> %s  (acc %.1f%%, conf %.1f%%)",
        ticker,
        "UP" if profile.prediction == 1 else "DOWN",
        profile.accuracy * 100.0,
        profile.confidence * 100.0,
    )
    return profile


# --------------------------------------------------------------------------- #
# Rendering / output
# --------------------------------------------------------------------------- #


def _fmt(value: float, decimals: int) -> str:
    """Format a possibly-NaN float, or 'n/a'."""
    v = _safe(value)
    if np.isnan(v):
        return "n/a"
    return f"{v:.{decimals}f}"


def _pct(value: float) -> str:
    v = _safe(value)
    if np.isnan(v):
        return "n/a"
    return f"{v * 100.0:.1f}%"


def _direction(pred: Optional[int]) -> str:
    if pred is None:
        return "n/a"
    return "UP" if pred == 1 else "DOWN"


def render_profile(profile: TickerProfile, decimals: int) -> str:
    """Render one ticker block. `decimals` controls price precision
    (2 for equities, 4 for forex pip precision)."""
    lines = [f"### {profile.ticker}"]

    if not profile.available:
        lines.append(f"  STATUS        : DATA UNAVAILABLE — {profile.reason}")
        # Still surface whatever live metrics we managed to capture.
        if not np.isnan(_safe(profile.close)):
            lines.append(f"  Last Close    : {_fmt(profile.close, decimals)}")
            lines.append(f"  RSI(14)       : {_fmt(profile.rsi14, 1)}")
        lines.append("")
        return "\n".join(lines)

    rsi = _safe(profile.rsi14)
    rsi_flag = ""
    if not np.isnan(rsi):
        if rsi > 70:
            rsi_flag = "  [OVERBOUGHT >70]"
        elif rsi < 30:
            rsi_flag = "  [OVERSOLD <30]"

    # Trend read from SMA stack.
    trend = "n/a"
    c, s20, s50 = _safe(profile.close), _safe(profile.sma20), _safe(profile.sma50)
    if not any(np.isnan(x) for x in (c, s20, s50)):
        if c > s20 and c > s50 and s20 > s50:
            trend = "Uptrend (price > SMA20 > SMA50)"
        elif c < s20 and c < s50 and s20 < s50:
            trend = "Downtrend (price < SMA20 < SMA50)"
        else:
            trend = "Mixed / no clean trend"

    lines.extend(
        [
            f"  Last Close    : {_fmt(profile.close, decimals)}",
            f"  Daily Return  : {_pct(profile.daily_return)}",
            f"  RSI(14)       : {_fmt(profile.rsi14, 1)}{rsi_flag}",
            f"  SMA(20)       : {_fmt(profile.sma20, decimals)}",
            f"  SMA(50)       : {_fmt(profile.sma50, decimals)}",
            f"  Trend Read    : {trend}",
            f"  Model Accuracy: {_pct(profile.accuracy)}  (backtested on 20% hold-out)",
            f"  Prediction    : {_direction(profile.prediction)} (next-day direction)",
            f"  Confidence    : {_pct(profile.confidence)}",
            f"  Train Rows    : {profile.n_rows}",
            "",
        ]
    )
    return "\n".join(lines)


def write_context_file(
    path: str,
    title: str,
    profiles: list[TickerProfile],
    decimals: int,
    header_notes: list[str],
) -> None:
    """Write a full context file with header, per-ticker profiles, and a summary."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    available = [p for p in profiles if p.available]

    out: list[str] = []
    out.append("=" * 70)
    out.append(title)
    out.append(f"Generated: {stamp}")
    out.append(f"Universe: {len(profiles)} tickers  |  Modeled OK: {len(available)}")
    out.append("=" * 70)
    out.append("")
    for note in header_notes:
        out.append(note)
    out.append("")

    for profile in profiles:
        out.append(render_profile(profile, decimals))

    # Scannable summary table.
    out.append("-" * 70)
    out.append("SUMMARY")
    out.append("-" * 70)
    out.append(f"{'Ticker':<14}{'Signal':<8}{'Conf':<9}{'Acc':<9}{'RSI':<8}")
    for p in profiles:
        if p.available:
            out.append(
                f"{p.ticker:<14}{_direction(p.prediction):<8}"
                f"{_pct(p.confidence):<9}{_pct(p.accuracy):<9}{_fmt(p.rsi14, 1):<8}"
            )
        else:
            out.append(f"{p.ticker:<14}{'N/A':<8}{'-':<9}{'-':<9}{'-':<8}")
    out.append("")
    out.append("NOTE: Signals are probabilistic tilts, not certainties. Apply the")
    out.append("stocky risk rules (RSI Reality Check, 1:2 R:R, confidence filters)")
    out.append("before acting. Educational use only — not financial advice.")
    out.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))

    log.info("Wrote %s (%d/%d tickers modeled).", path, len(available), len(profiles))


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def run_batch(tickers: list[str]) -> list[TickerProfile]:
    """Analyze a list of tickers, isolating failures per ticker."""
    results: list[TickerProfile] = []
    for ticker in tickers:
        try:
            results.append(analyze_ticker(ticker))
        except Exception as exc:  # last-resort guard — never let one ticker abort the run
            log.exception("Unexpected error on %s: %s", ticker, exc)
            results.append(
                TickerProfile(ticker=ticker, reason=f"unexpected error: {exc}")
            )
    return results


def main() -> int:
    log.info("stocky market intelligence run starting.")

    # --- Indian equities ---------------------------------------------------- #
    log.info("=== Indian Equities (NSE) ===")
    equity_profiles = run_batch(INDIAN_STOCKS)
    write_context_file(
        EQUITY_OUTPUT,
        "STOCKY :: INDIAN EQUITY TECHNICAL CONTEXT (NSE swing/delivery)",
        equity_profiles,
        decimals=2,
        header_notes=[
            "Lens: NSE swing/delivery setups. RSI > 70 = overbought (RSI Reality",
            "Check). Targets should respect a minimum 1:2 risk-to-reward once the",
            "operator constructs entry/stop/target levels.",
        ],
    )

    # --- Forex -------------------------------------------------------------- #
    log.info("=== Forex Pairs ===")
    forex_profiles = run_batch(FOREX_PAIRS)
    write_context_file(
        FOREX_OUTPUT,
        "STOCKY :: FOREX TECHNICAL CONTEXT (relative strength / macro)",
        forex_profiles,
        decimals=4,
        header_notes=[
            "Lens: relative currency strength + macro. Prices quoted to 4 decimals",
            "(1 pip = 0.0001). USDINR strength = tailwind for IT/Pharma exporters,",
            "headwind for import-heavy sectors and banks.",
        ],
    )

    eq_ok = sum(p.available for p in equity_profiles)
    fx_ok = sum(p.available for p in forex_profiles)
    log.info(
        "Done. Equities modeled %d/%d, Forex modeled %d/%d.",
        eq_ok,
        len(equity_profiles),
        fx_ok,
        len(forex_profiles),
    )
    log.info("Outputs: %s, %s", EQUITY_OUTPUT, FOREX_OUTPUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
