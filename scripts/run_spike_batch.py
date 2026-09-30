#!/usr/bin/env python3
"""Run the next pending pair from second_opinions_queue.csv through ta_spike.py.

One invocation = one run (free tier is ~1 run/day). Intended to be called daily
by cron/loop until the queue is exhausted. On success marks the row 'done'; on
failure marks it 'error' (won't auto-retry — rerun manually after checking why).
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "second_opinions_queue.csv"
TA_PYTHON = ROOT / ".venv-ta" / "bin" / "python"
SPIKE = ROOT / "scripts" / "ta_spike.py"


def main() -> int:
    if not QUEUE.exists():
        print(f"no queue at {QUEUE}; run gen_spike_batch.py first")
        return 1

    with QUEUE.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    idx = next((i for i, r in enumerate(rows) if r["status"] == "pending"), None)
    if idx is None:
        print("queue empty: all pairs done or errored")
        return 0

    row = rows[idx]
    ticker, trade_date = row["ticker"], row["trade_date"]
    print(f"running {ticker} {trade_date} ...")
    result = subprocess.run(
        [str(TA_PYTHON), str(SPIKE), ticker, "--date", trade_date],
        cwd=ROOT,
    )
    row["status"] = "done" if result.returncode == 0 else "error"

    with QUEUE.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["ticker", "trade_date", "status"])
        w.writeheader()
        w.writerows(rows)

    remaining = sum(1 for r in rows if r["status"] == "pending")
    print(f"{ticker} {trade_date}: {row['status']}. {remaining} pending left.")
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
