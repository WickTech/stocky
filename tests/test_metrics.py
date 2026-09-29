"""Unit tests on synthetic series with known answers."""

import math

import numpy as np
import pandas as pd
import pytest

from stocky import metrics as m


def _daily_index(n: int) -> pd.DatetimeIndex:
    return pd.bdate_range("2022-01-03", periods=n)


def _ar1(phi: float, n: int, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    eps = rng.standard_normal(n)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + eps[i]
    return pd.Series(x)


# --- IC -------------------------------------------------------------------- #


def test_ic_perfect_and_inverse():
    r = pd.Series(np.random.default_rng(1).standard_normal(200))
    assert m.information_coefficient(r, r) == pytest.approx(1.0)
    assert m.information_coefficient(-r, r) == pytest.approx(-1.0)


def test_spearman_ic_ignores_monotone_transform():
    r = pd.Series(np.random.default_rng(2).standard_normal(200))
    assert m.information_coefficient(np.exp(r), r) == pytest.approx(1.0)


def test_ic_noisy_signal_matches_theory():
    # signal = r + N(0,1) noise  ->  Pearson corr = 1/sqrt(2) ~= 0.707
    rng = np.random.default_rng(3)
    r = pd.Series(rng.standard_normal(20000))
    s = r + rng.standard_normal(20000)
    assert m.information_coefficient(s, r, method="pearson") == pytest.approx(
        1 / math.sqrt(2), abs=0.02
    )


def test_ic_constant_signal_is_nan():
    r = pd.Series([0.1, -0.2, 0.3, 0.0])
    assert math.isnan(m.information_coefficient(pd.Series([1.0] * 4), r))


def test_monthly_ic_one_value_per_full_month_skips_short_months():
    idx = _daily_index(63)  # ~3 months of business days
    r = pd.Series(np.random.default_rng(4).standard_normal(63), index=idx)
    ic = m.monthly_ic(r, r, min_obs=10)
    assert len(ic) >= 2
    assert (ic.round(6) == 1.0).all()
    # min_obs above any month's size -> nothing survives
    assert m.monthly_ic(r, r, min_obs=100).empty


# --- ICIR ------------------------------------------------------------------ #


def test_icir_known_value():
    # mean 0.3, sample std 0.1414... -> 2.1213
    assert m.icir(pd.Series([0.2, 0.4])) == pytest.approx(0.3 / math.sqrt(0.02))


def test_icir_degenerate_cases_are_nan():
    assert math.isnan(m.icir(pd.Series([0.5])))
    assert math.isnan(m.icir(pd.Series([0.3, 0.3, 0.3])))


def test_icir_bands():
    assert m.icir_band(0.8) == "strong"
    assert m.icir_band(0.4) == "moderate"
    assert m.icir_band(0.1) == "noise"
    assert m.icir_band(-0.9) == "noise"
    assert m.icir_band(float("nan")) == "n/a"


def test_pure_noise_signal_has_low_icir():
    rng = np.random.default_rng(5)
    idx = _daily_index(1260)
    r = pd.Series(rng.standard_normal(1260), index=idx)
    s = pd.Series(rng.standard_normal(1260), index=idx)
    assert m.icir(m.monthly_ic(s, r)) < m.ICIR_MODERATE


# --- half-life ------------------------------------------------------------- #


def test_autocorr_of_ar1_decays_geometrically():
    ac = m.signal_autocorr(_ar1(0.9, 50000), lags=(1, 5, 10))
    for lag, val in ac.items():
        assert val == pytest.approx(0.9**lag, abs=0.03)


def test_half_life_of_ar1():
    # ln(.5)/ln(.9) = 6.58 days
    assert m.half_life(_ar1(0.9, 50000)) == pytest.approx(6.58, abs=0.6)


def test_half_life_white_noise_is_zero_and_random_walk_is_inf():
    assert m.half_life(_ar1(0.0, 50000)) < 1.0
    assert m.half_life(pd.Series(np.arange(500, dtype=float))) == float("inf")


def test_autocorr_short_series_is_nan():
    ac = m.signal_autocorr(pd.Series([1.0, 2.0, 3.0]), lags=(1, 50))
    assert math.isnan(ac[50])


# --- split ----------------------------------------------------------------- #


def test_three_way_split_is_chronological_and_covers_everything():
    sp = m.three_way_split(1000)
    assert (sp.train.start, sp.train.stop) == (0, 500)
    assert (sp.val.start, sp.val.stop) == (500, 700)
    assert (sp.oos.start, sp.oos.stop) == (700, 1000)


def test_three_way_split_rejects_bad_fractions():
    with pytest.raises(ValueError):
        m.three_way_split(100, train_frac=0.9, val_frac=0.2)
    with pytest.raises(ValueError):
        m.three_way_split(100, train_frac=0.0, val_frac=0.2)


# --- Bonferroni / significance -------------------------------------------- #


def test_bonferroni_alpha():
    assert m.bonferroni_alpha(0.05, 5) == pytest.approx(0.01)
    with pytest.raises(ValueError):
        m.bonferroni_alpha(0.05, 0)


def test_ic_pvalue_known_cases():
    assert m.ic_pvalue(0.0, 100) == pytest.approx(1.0)
    assert m.ic_pvalue(1.0, 100) == 0.0
    # r=0.5, n=30 -> t = 3.055, df=28 -> p ~= 0.0049
    assert m.ic_pvalue(0.5, 30) == pytest.approx(0.0049, abs=0.0005)
    assert math.isnan(m.ic_pvalue(0.5, 2))


def test_oos_verdict():
    assert m.oos_verdict(0.5, 30, alpha_adj=0.01) == "PASS"
    assert m.oos_verdict(0.5, 30, alpha_adj=0.001) == "FAIL"   # stricter gate
    assert m.oos_verdict(-0.5, 30, alpha_adj=0.01) == "FAIL"   # significant but wrong sign
    assert m.oos_verdict(float("nan"), 30, alpha_adj=0.01) == "n/a"
