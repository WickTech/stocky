"""Phase B experiment harness (read-only for the loop — see program.md).

Scores a feature/model config by mean *validation* ICIR over the universe on
frozen cached data, enforces the round cap and keep/revert rule, and runs the
locked-OOS gate exactly once at the end. The OOS slice is never used by
`validation_icir`.

CLI (run from repo root):
    python -m stocky.experiment baseline
    python -m stocky.experiment round "<hypothesis>"
    python -m stocky.experiment final
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from stocky import metrics
from stocky.features import FEATURE_COLUMNS, build_features, make_model

MAX_ROUNDS = 5
MIN_GAIN = 0.05            # validation-ICIR gain needed to KEEP a change
MIN_CLEAN_ROWS = 150
STATE_PATH = Path("experiments.json")
LOG_PATH = Path("experiments.md")
CACHE_DIR = Path(".cache")

UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "SBIN.NS",
    "USDINR=X", "EURUSD=X", "GBPUSD=X", "AUDUSD=X",
]


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


def _clean(raw: pd.DataFrame) -> pd.DataFrame:
    feats = build_features(raw)
    cols = FEATURE_COLUMNS + ["target", "fwd_return"]
    return feats[cols].replace([np.inf, -np.inf], np.nan).dropna()


def _fit_signal(clean: pd.DataFrame, split: metrics.Split) -> pd.Series:
    """Fit on the train slice only; return P(up) for every clean row."""
    X = clean[FEATURE_COLUMNS].values
    y = clean["target"].values.astype(int)
    if len(np.unique(y[split.train])) < 2:
        return pd.Series(np.nan, index=clean.index)
    model = make_model().fit(X[split.train], y[split.train])
    up = list(model.classes_).index(1)
    return pd.Series(model.predict_proba(X)[:, up], index=clean.index)


def validation_icir(raw: pd.DataFrame) -> float:
    """ICIR of monthly rank-IC on the validation slice. Never reads OOS labels
    beyond the single boundary day's forward return."""
    clean = _clean(raw)
    if len(clean) < MIN_CLEAN_ROWS:
        return float("nan")
    split = metrics.three_way_split(len(clean))
    signal = _fit_signal(clean, split)
    idx = clean.index[split.val]
    ic = metrics.monthly_ic(signal.loc[idx], clean["fwd_return"].loc[idx])
    return metrics.icir(ic)


def universe_score(frames: dict[str, pd.DataFrame]) -> float:
    """Mean validation ICIR over tickers with a finite score."""
    vals = [validation_icir(df) for df in frames.values()]
    vals = [v for v in vals if not math.isnan(v)]
    return float(np.mean(vals)) if vals else float("nan")


def oos_report(frames: dict[str, pd.DataFrame], alpha_adj: float) -> dict[str, dict]:
    """Locked-OOS rank-IC and verdict per ticker. Call once, via `final`."""
    out: dict[str, dict] = {}
    for ticker, raw in frames.items():
        clean = _clean(raw)
        if len(clean) < MIN_CLEAN_ROWS:
            out[ticker] = {"ic": float("nan"), "n": 0, "verdict": "n/a"}
            continue
        split = metrics.three_way_split(len(clean))
        signal = _fit_signal(clean, split)
        idx = clean.index[split.oos]
        ic = metrics.information_coefficient(signal.loc[idx], clean["fwd_return"].loc[idx])
        out[ticker] = {
            "ic": ic,
            "n": len(idx),
            "verdict": metrics.oos_verdict(ic, len(idx), alpha_adj),
        }
    return out


# --------------------------------------------------------------------------- #
# Keep / revert + state
# --------------------------------------------------------------------------- #


def decide(score: float, best: float, min_gain: float = MIN_GAIN) -> str:
    if math.isnan(score):
        return "REVERT"
    if math.isnan(best):
        return "KEEP"
    return "KEEP" if score - best >= min_gain else "REVERT"


@dataclass
class State:
    path: Path
    baseline: Optional[float] = None
    best: float = float("nan")
    configs_tried: int = 0
    rounds: list = field(default_factory=list)
    finalized: bool = False

    @classmethod
    def load(cls, path: Path = STATE_PATH) -> "State":
        path = Path(path)
        if not path.exists():
            return cls(path=path)
        d = json.loads(path.read_text())
        return cls(
            path=path,
            baseline=d.get("baseline"),
            best=d["best"] if d.get("best") is not None else float("nan"),
            configs_tried=d.get("configs_tried", 0),
            rounds=d.get("rounds", []),
            finalized=d.get("finalized", False),
        )

    def save(self) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "baseline": self.baseline,
                    "best": None if math.isnan(self.best) else self.best,
                    "configs_tried": self.configs_tried,
                    "rounds": self.rounds,
                    "finalized": self.finalized,
                },
                indent=2,
            )
        )

    def record_baseline(self, score: float) -> None:
        if self.baseline is not None:
            raise RuntimeError("baseline already recorded")
        self.baseline = score
        self.best = score
        self.configs_tried = 1

    def record_round(self, hypothesis: str, score: float) -> str:
        if self.finalized:
            raise RuntimeError("experiment already finalized")
        if self.baseline is None:
            raise RuntimeError("record a baseline first")
        if len(self.rounds) >= MAX_ROUNDS:
            raise RuntimeError(f"round cap reached ({MAX_ROUNDS})")
        decision = decide(score, self.best)
        self.configs_tried += 1  # reverted configs still count toward Bonferroni
        if decision == "KEEP":
            self.best = score
        self.rounds.append(
            {
                "round": len(self.rounds) + 1,
                "hypothesis": hypothesis,
                "score": None if math.isnan(score) else score,
                "decision": decision,
            }
        )
        return decision

    def mark_finalized(self) -> None:
        if self.finalized:
            raise RuntimeError("final OOS already run; it is scored once")
        self.finalized = True


def final_alpha(state: State, n_tickers: int) -> float:
    """Bonferroni over every config tried x every ticker tested."""
    return metrics.bonferroni_alpha(metrics.ALPHA, max(1, state.configs_tried) * n_tickers)


# --------------------------------------------------------------------------- #
# Data (frozen cache so scores are comparable across rounds)
# --------------------------------------------------------------------------- #


def load_frames(refresh: bool = False) -> dict[str, pd.DataFrame]:
    CACHE_DIR.mkdir(exist_ok=True)
    frames: dict[str, pd.DataFrame] = {}
    for ticker in UNIVERSE:
        path = CACHE_DIR / f"{ticker}.csv"
        if refresh or not path.exists():
            import market_intelligence as mi

            df = mi.fetch_history(ticker)
            if df is None:
                continue
            df.to_csv(path)
        frames[ticker] = pd.read_csv(path, index_col=0, parse_dates=True)
    return frames


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _append_log(line: str) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in {"baseline", "round", "final"}:
        print(__doc__)
        return 2
    cmd = argv[0]
    state = State.load()
    frames = load_frames()

    if cmd == "baseline":
        score = universe_score(frames)
        state.record_baseline(score)
        state.save()
        _append_log(f"| 0 | baseline (current features.py) | {score:.3f} | - | {date.today()} |")
        print(f"baseline mean validation ICIR = {score:.3f} over {len(frames)} tickers")
    elif cmd == "round":
        hypothesis = " ".join(argv[1:]) or "(unspecified)"
        score = universe_score(frames)
        decision = state.record_round(hypothesis, score)
        state.save()
        n = len(state.rounds)
        _append_log(f"| {n} | {hypothesis} | {score:.3f} | {decision} | {date.today()} |")
        print(f"round {n}: score {score:.3f} vs best {state.best:.3f} -> {decision}")
        if decision == "REVERT":
            print("REVERT your features.py / MODEL_PARAMS change now (git checkout stocky/features.py).")
    else:
        state.mark_finalized()
        alpha = final_alpha(state, len(frames))
        report = oos_report(frames, alpha)
        state.save()
        _append_log(f"\n## Final locked-OOS gate (alpha_adj = {alpha:.5f}; "
                    f"{state.configs_tried} configs x {len(frames)} tickers)\n")
        _append_log("| ticker | OOS IC | n | verdict |\n|---|---|---|---|")
        for t, r in report.items():
            _append_log(f"| {t} | {r['ic']:.3f} | {r['n']} | {r['verdict']} |")
            print(f"{t:<14} IC {r['ic']:+.3f}  n={r['n']}  {r['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
