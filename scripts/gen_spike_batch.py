#!/usr/bin/env python3
"""Generate the 30-sample TradingAgents spike queue (Plan 02 Phase D reflection log).

Historical (ticker, trade_date) pairs only, picked far enough before today that
ret_1d/5d/20d are already computable once the LLM call is made — no waiting on
future price data, only on the free-tier LLM quota (~1 run/day).

Writes second_opinions_queue.csv (gitignored): ticker,trade_date,status.
Run once; re-running skips pairs already in the queue.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "second_opinions_queue.csv"

TICKERS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "SBIN.NS"]

# 6 weekday dates spread over Jun-Aug 2026, each >20 trading days before 2026-09-30
# so ret_20d is already computable today.
DATES = [
    "2026-06-02", "2026-06-16", "2026-06-30",
    "2026-07-14", "2026-07-28", "2026-08-11",
]


def main() -> int:
    existing: set[tuple[str, str]] = set()
    if QUEUE.exists():
        with QUEUE.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                existing.add((row["ticker"], row["trade_date"]))

    rows = [(t, d) for d in DATES for t in TICKERS]
    new = not QUEUE.exists()
    with QUEUE.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["ticker", "trade_date", "status"])
        added = 0
        for ticker, trade_date in rows:
            if (ticker, trade_date) in existing:
                continue
            w.writerow([ticker, trade_date, "pending"])
            added += 1
    print(f"queue: {len(rows)} target pairs, {added} newly added, "
          f"{len(rows) - added} already present -> {QUEUE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
