"""Harness rules for the Phase B loop: round cap, keep/revert, no OOS peeking."""

import math

import numpy as np
import pandas as pd
import pytest

from stocky import experiment as ex
from stocky import features


def _ohlcv(n: int = 900, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    return pd.DataFrame(
        {"Close": close}, index=pd.bdate_range("2021-01-04", periods=n)
    )


# --- features module ------------------------------------------------------- #


def test_features_module_exposes_columns_and_model():
    df = features.build_features(_ohlcv())
    assert set(features.FEATURE_COLUMNS) <= set(df.columns)
    assert {"target", "fwd_return"} <= set(df.columns)
    assert hasattr(features.make_model(), "fit")


# --- scoring: no OOS peeking ---------------------------------------------- #


def test_validation_score_ignores_oos_rows():
    base = _ohlcv()
    s1 = ex.validation_icir(base)

    perturbed = base.copy()
    cut = int(len(perturbed) * 0.8)  # deep inside the locked-OOS tail
    perturbed.iloc[cut:, 0] *= np.random.default_rng(9).uniform(0.5, 1.5, len(perturbed) - cut)
    s2 = ex.validation_icir(perturbed)

    assert not math.isnan(s1)
    assert s1 == pytest.approx(s2)


def test_validation_score_nan_when_too_short():
    assert math.isnan(ex.validation_icir(_ohlcv(60)))


# --- keep / revert --------------------------------------------------------- #


def test_decide_requires_min_gain():
    assert ex.decide(score=0.30, best=0.20, min_gain=0.05) == "KEEP"
    assert ex.decide(score=0.22, best=0.20, min_gain=0.05) == "REVERT"
    assert ex.decide(score=float("nan"), best=0.20, min_gain=0.05) == "REVERT"


# --- state machine --------------------------------------------------------- #


def test_baseline_then_rounds_track_best_and_configs(tmp_path):
    st = ex.State.load(tmp_path / "s.json")
    st.record_baseline(0.10)
    assert st.configs_tried == 1 and st.best == 0.10

    assert st.record_round("h1", 0.30) == "KEEP"
    assert st.best == 0.30 and st.configs_tried == 2

    assert st.record_round("h2", 0.31) == "REVERT"  # gain < min_gain
    assert st.best == 0.30 and st.configs_tried == 3  # reverted still counts


def test_round_cap_enforced(tmp_path):
    st = ex.State.load(tmp_path / "s.json")
    st.record_baseline(0.0)
    for i in range(ex.MAX_ROUNDS):
        st.record_round(f"h{i}", 0.0)
    with pytest.raises(RuntimeError, match="round"):
        st.record_round("one too many", 1.0)


def test_round_requires_baseline(tmp_path):
    st = ex.State.load(tmp_path / "s.json")
    with pytest.raises(RuntimeError, match="baseline"):
        st.record_round("h", 0.5)


def test_state_roundtrips_to_disk(tmp_path):
    p = tmp_path / "s.json"
    st = ex.State.load(p)
    st.record_baseline(0.1)
    st.record_round("h1", 0.4)
    st.save()
    again = ex.State.load(p)
    assert again.configs_tried == 2 and again.best == 0.4
    assert again.rounds[0]["hypothesis"] == "h1"


def test_final_oos_runs_once(tmp_path):
    st = ex.State.load(tmp_path / "s.json")
    st.record_baseline(0.1)
    st.mark_finalized()
    assert st.finalized
    with pytest.raises(RuntimeError, match="final"):
        st.mark_finalized()
    with pytest.raises(RuntimeError, match="final"):
        st.record_round("late", 0.9)


# --- Bonferroni denominator ------------------------------------------------ #


def test_final_alpha_counts_all_configs_and_tickers(tmp_path):
    st = ex.State.load(tmp_path / "s.json")
    st.record_baseline(0.1)
    st.record_round("a", 0.5)
    st.record_round("b", 0.5)
    # 3 configs x 9 tickers = 27 tests
    assert ex.final_alpha(st, n_tickers=9) == pytest.approx(0.05 / 27)
