"""Signal-quality metrics: IC / ICIR, signal half-life, three-way split, Bonferroni.

Accuracy on next-day direction is weak evidence. These metrics give a stricter
scorecard (Plan 02 Phase A). Pure numpy / pandas / scipy — no model code here.

Read-only for the Phase B experiment loop: the loop may not edit this file.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
import pandas as pd
from scipy import stats

ALPHA = 0.05
TRAIN_FRAC = 0.50   # chronological split; the remaining 30% is the locked OOS set
VAL_FRAC = 0.20
DEFAULT_LAGS = (1, 5, 10, 20, 50)
ICIR_STRONG = 0.5
ICIR_MODERATE = 0.3


# --------------------------------------------------------------------------- #
# Information coefficient
# --------------------------------------------------------------------------- #


def information_coefficient(
    signal: pd.Series, fwd_ret: pd.Series, method: str = "spearman"
) -> float:
    """Correlation between signal and the forward return it tries to predict.

    NaN pairs are dropped. Returns NaN when fewer than 3 pairs remain or either
    side is constant (correlation undefined).
    """
    df = pd.concat([signal, fwd_ret], axis=1, keys=["s", "r"]).dropna()
    if len(df) < 3 or df["s"].nunique() < 2 or df["r"].nunique() < 2:
        return float("nan")
    return float(df["s"].corr(df["r"], method=method))


def monthly_ic(
    signal: pd.Series,
    fwd_ret: pd.Series,
    method: str = "spearman",
    min_obs: int = 10,
) -> pd.Series:
    """IC computed separately per calendar month (index must be a DatetimeIndex).

    Months with fewer than `min_obs` valid pairs are skipped. Result is indexed by
    'YYYY-MM' strings.
    """
    df = pd.concat([signal, fwd_ret], axis=1, keys=["s", "r"]).dropna()
    out: dict[str, float] = {}
    for (year, month), grp in df.groupby([df.index.year, df.index.month]):
        if len(grp) < min_obs:
            continue
        ic = information_coefficient(grp["s"], grp["r"], method=method)
        if not math.isnan(ic):
            out[f"{year}-{month:02d}"] = ic
    return pd.Series(out, dtype=float)


def icir(ic_series: pd.Series) -> float:
    """mean(IC) / std(IC), sample std (ddof=1).

    NaN when fewer than 2 observations or zero dispersion (ratio undefined).
    """
    ic = ic_series.dropna()
    if len(ic) < 2:
        return float("nan")
    sd = float(ic.std(ddof=1))
    if sd == 0.0 or math.isnan(sd):
        return float("nan")
    return float(ic.mean()) / sd


def icir_band(value: float) -> str:
    """Guide bands: >0.5 strong, 0.3-0.5 moderate, <0.3 noise (signed; negative = noise)."""
    if math.isnan(value):
        return "n/a"
    if value > ICIR_STRONG:
        return "strong"
    if value >= ICIR_MODERATE:
        return "moderate"
    return "noise"


# --------------------------------------------------------------------------- #
# Signal persistence
# --------------------------------------------------------------------------- #


def signal_autocorr(
    signal: pd.Series, lags: Sequence[int] = DEFAULT_LAGS
) -> dict[int, float]:
    """Autocorrelation of the signal at each lag (NaN if series too short)."""
    s = signal.dropna()
    out: dict[int, float] = {}
    for lag in lags:
        if lag < 1 or len(s) <= lag + 2:
            out[lag] = float("nan")
        else:
            out[lag] = float(s.autocorr(lag))
    return out


def half_life(signal: pd.Series) -> float:
    """Days for the signal's autocorrelation to halve, from an AR(1) fit.

    phi = lag-1 autocorr; half-life = ln(0.5) / ln(phi).
    phi <= 0 -> 0.0 (no persistence); phi >= 1 -> inf; too short -> NaN.
    """
    phi = signal_autocorr(signal, (1,))[1]
    if math.isnan(phi):
        return float("nan")
    if phi <= 0.0:
        return 0.0
    if phi >= 1.0 - 1e-9:
        return float("inf")
    return math.log(0.5) / math.log(phi)


# --------------------------------------------------------------------------- #
# Splits and significance
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Split:
    train: slice
    val: slice
    oos: slice


def three_way_split(
    n: int, train_frac: float = TRAIN_FRAC, val_frac: float = VAL_FRAC
) -> Split:
    """Chronological train / validation / locked-OOS split (OOS = the remainder,
    default last 30%). Never shuffled."""
    if not (train_frac > 0 and val_frac > 0 and train_frac + val_frac < 1):
        raise ValueError("need train_frac > 0, val_frac > 0, train_frac + val_frac < 1")
    a = int(n * train_frac)
    b = int(n * (train_frac + val_frac))
    return Split(train=slice(0, a), val=slice(a, b), oos=slice(b, n))


def bonferroni_alpha(alpha: float, n_tests: int) -> float:
    """Family-wise alpha divided across `n_tests` (all configs tried, all rounds)."""
    if n_tests < 1:
        raise ValueError("n_tests must be >= 1")
    return alpha / n_tests


def ic_pvalue(ic: float, n: int) -> float:
    """Two-sided p-value that a correlation `ic` over `n` pairs is zero (t-test)."""
    if math.isnan(ic) or n < 3:
        return float("nan")
    if abs(ic) >= 1.0:
        return 0.0
    t = ic * math.sqrt((n - 2) / (1.0 - ic * ic))
    return float(2.0 * stats.t.sf(abs(t), df=n - 2))


def oos_verdict(oos_ic: float, n: int, alpha_adj: float) -> str:
    """PASS when OOS IC is positive and significant at the Bonferroni-adjusted alpha."""
    p = ic_pvalue(oos_ic, n)
    if math.isnan(p):
        return "n/a"
    return "PASS" if (oos_ic > 0 and p < alpha_adj) else "FAIL"
