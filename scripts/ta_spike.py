#!/usr/bin/env python3
"""TradingAgents spike (Plan 02 Phase D). Run with the SEPARATE venv:

    .venv-ta/bin/python scripts/ta_spike.py TCS.NS
    .venv-ta/bin/python scripts/ta_spike.py AAPL --date 2026-09-26 --provider google \
        --deep gemini-3-flash-preview --quick gemini-3.5-flash-lite

Research second opinion only — never a trade trigger. Keys are read from .env
(gitignored) or the environment. Writes local files under second_opinions/ (gitignored)
and appends one row to second_opinions.csv (the reflection log; fill realized returns later).
"""

from __future__ import annotations

import argparse
import csv
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "second_opinions"
LOG = ROOT / "second_opinions.csv"
LOG_FIELDS = [
    "run_at", "ticker", "trade_date", "provider", "deep_model", "quick_model",
    "decision", "seconds", "jev_enabled", "ret_1d", "ret_5d", "ret_20d",
]


def load_env(path: Path) -> None:
    """Minimal .env loader (no extra dependency); never overrides the shell."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.split(" #")[0].strip().strip("'\"")
        if val:
            os.environ.setdefault(key.strip(), val)


def last_weekday(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: last weekday)")
    ap.add_argument("--provider", default="google")
    ap.add_argument("--deep", default="gemini-3-flash-preview")
    ap.add_argument("--quick", default="gemini-3.5-flash-lite")
    args = ap.parse_args()

    load_env(ROOT / ".env")

    from tradingagents.dataflows import router
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    # Register a stub so prediction markets (Polymarket) stay off: the router raises on
    # an unregistered vendor name instead of degrading, even for optional categories.
    router.VENDOR_METHODS["get_prediction_markets"]["none"] = (
        lambda *a, **k: "Prediction-market data disabled for this run."
    )

    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = args.provider
    config["deep_think_llm"] = args.deep
    config["quick_think_llm"] = args.quick
    config["llm_max_retries"] = 6   # free tier returns transient 503s under load
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    # Free / keyless-friendly: yfinance for everything; no SEC key needed for non-US.
    config["data_vendors"] = {
        **config["data_vendors"],
        "fundamental_data": "yfinance",
        "prediction_markets": "none",   # optional category; disabled, degrades to a sentinel
    }
    config["results_dir"] = str(OUT_DIR / "runs")

    trade_date = args.date or last_weekday(date.today() - timedelta(days=1)).isoformat()
    jev = bool(os.environ.get("TYPESAFE_API_KEY"))
    print(f"ticker={args.ticker} date={trade_date} provider={args.provider} "
          f"models={args.deep}/{args.quick} jev={'on' if jev else 'off'}")

    t0 = time.time()
    ta = TradingAgentsGraph(debug=False, config=config)
    state, decision = ta.propagate(args.ticker, trade_date)
    secs = time.time() - t0

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"{args.ticker}-{trade_date}.md"
    out.write_text(f"# {args.ticker} {trade_date}\n\nDecision: {decision}\n\n"
                   f"```\n{state}\n```\n", encoding="utf-8")

    new = not LOG.exists()
    with LOG.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow({
            "run_at": datetime.now().isoformat(timespec="seconds"),
            "ticker": args.ticker, "trade_date": trade_date, "provider": args.provider,
            "deep_model": args.deep, "quick_model": args.quick,
            "decision": str(decision).replace("\n", " ")[:200],
            "seconds": round(secs, 1), "jev_enabled": jev,
            "ret_1d": "", "ret_5d": "", "ret_20d": "",
        })
    print(f"decision: {decision}\nwall-clock: {secs:.0f}s\nsaved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
