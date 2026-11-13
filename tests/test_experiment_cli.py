"""stocky.experiment: data cache and CLI (no network, all paths in tmp_path)."""

import numpy as np
import pandas as pd
import pytest

from stocky import experiment as ex


def _ohlcv(n: int = 700, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame({"Close": close}, index=idx)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Redirect every file the harness touches into tmp_path."""
    monkeypatch.setattr(ex, "STATE_PATH", tmp_path / "experiments.json")
    monkeypatch.setattr(ex, "LOG_PATH", tmp_path / "experiments.md")
    monkeypatch.setattr(ex, "CACHE_DIR", tmp_path / ".cache")
    monkeypatch.setattr(ex, "UNIVERSE", ["AAA", "BBB"])
    # State.load's default arg was bound at import; patch via load wrapper.
    real_load = ex.State.load.__func__
    monkeypatch.setattr(
        ex.State, "load",
        classmethod(lambda cls, path=None: real_load(cls, path or ex.STATE_PATH)),
    )
    return tmp_path


def _frames():
    return {"AAA": _ohlcv(seed=1), "BBB": _ohlcv(seed=2)}


def test_load_frames_fetches_then_reads_cache(sandbox, monkeypatch):
    import market_intelligence as mi

    calls = []

    def fake_fetch(ticker):
        calls.append(ticker)
        return _ohlcv(60)

    monkeypatch.setattr(mi, "fetch_history", fake_fetch)
    first = ex.load_frames()
    assert set(first) == {"AAA", "BBB"} and calls == ["AAA", "BBB"]
    assert (sandbox / ".cache" / "AAA.csv").exists()

    second = ex.load_frames()          # served from cache, no new fetches
    assert calls == ["AAA", "BBB"]
    assert isinstance(second["AAA"].index, pd.DatetimeIndex)

    ex.load_frames(refresh=True)       # refresh forces a re-fetch
    assert calls == ["AAA", "BBB", "AAA", "BBB"]


def test_load_frames_skips_tickers_that_fail(sandbox, monkeypatch):
    import market_intelligence as mi

    monkeypatch.setattr(mi, "fetch_history", lambda t: None if t == "AAA" else _ohlcv(60))
    assert set(ex.load_frames()) == {"BBB"}


def test_main_rejects_unknown_command(capsys):
    assert ex.main([]) == 2
    assert ex.main(["bogus"]) == 2
    assert "Phase B experiment harness" in capsys.readouterr().out


def test_cli_baseline_round_final_flow(sandbox, monkeypatch, capsys):
    monkeypatch.setattr(ex, "load_frames", lambda refresh=False: _frames())

    assert ex.main(["baseline"]) == 0
    state = ex.State.load()
    assert state.baseline is not None and state.configs_tried == 1
    assert "baseline mean validation ICIR" in capsys.readouterr().out

    assert ex.main(["round", "same", "features"]) == 0
    out = capsys.readouterr().out
    state = ex.State.load()
    assert state.rounds[0]["hypothesis"] == "same features"
    # Identical config can't beat best by MIN_GAIN -> reverted, but still counted.
    assert state.rounds[0]["decision"] == "REVERT"
    assert state.configs_tried == 2
    assert "REVERT your features.py" in out

    assert ex.main(["final"]) == 0
    out = capsys.readouterr().out
    assert "AAA" in out and "BBB" in out
    assert ex.State.load().finalized is True

    log = (sandbox / "experiments.md").read_text(encoding="utf-8")
    assert "baseline (current features.py)" in log
    assert "Final locked-OOS gate" in log
    assert "alpha_adj = 0.01250" in log        # 0.05 / (2 configs x 2 tickers)

    with pytest.raises(RuntimeError, match="scored once"):
        ex.main(["final"])


def test_cli_round_without_baseline_errors(sandbox, monkeypatch):
    monkeypatch.setattr(ex, "load_frames", lambda refresh=False: _frames())
    with pytest.raises(RuntimeError, match="baseline"):
        ex.main(["round", "x"])


def test_cli_round_with_default_hypothesis(sandbox, monkeypatch):
    monkeypatch.setattr(ex, "load_frames", lambda refresh=False: _frames())
    ex.main(["baseline"])
    ex.main(["round"])
    assert ex.State.load().rounds[0]["hypothesis"] == "(unspecified)"


def test_oos_report_short_history_is_na():
    out = ex.oos_report({"S": _ohlcv(80)}, alpha_adj=0.05)
    assert out["S"]["verdict"] == "n/a" and out["S"]["n"] == 0


def test_oos_report_full_history_has_ic_and_verdict():
    out = ex.oos_report({"L": _ohlcv(700)}, alpha_adj=0.05)
    assert out["L"]["n"] > 0
    assert out["L"]["verdict"] in {"PASS", "FAIL"}


def test_universe_score_ignores_nan_tickers_and_is_nan_when_all_nan():
    assert np.isnan(ex.universe_score({"S": _ohlcv(80)}))
    only_short_plus_long = ex.universe_score({"S": _ohlcv(80), "L": _ohlcv(700)})
    assert only_short_plus_long == pytest.approx(ex.validation_icir(_ohlcv(700)))


def test_decide_nan_cases():
    assert ex.decide(float("nan"), 0.1) == "REVERT"
    assert ex.decide(0.1, float("nan")) == "KEEP"
