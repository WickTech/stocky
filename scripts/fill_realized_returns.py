#!/usr/bin/env python3
"""Fill ret_1d/5d/20d in second_opinions.csv from yfinance closes.

Run with the main venv (needs yfinance): .venv/bin/python scripts/fill_realized_returns.py
Only touches rows that already have a decision and blank returns; skips rows where
not enough trading days have elapsed yet.
"""

from __future__ import annotations

import csv
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "second_opinions.csv"


def realized_returns(ticker: str, trade_date: str) -> dict[str, str]:
    hist = yf.Ticker(ticker).history(start=trade_date, period="3mo")
    closes = hist["Close"]
    if closes.empty:
        return {}
    dates = [d.strftime("%Y-%m-%d") for d in closes.index]
    if trade_date not in dates:
        return {}  # trade_date wasn't a trading day / no data at start
    i0 = dates.index(trade_date)

    out: dict[str, str] = {}
    for label, offset in (("ret_1d", 1), ("ret_5d", 5), ("ret_20d", 20)):
        j = i0 + offset
        if j < len(closes):
            out[label] = f"{(closes.iloc[j] / closes.iloc[i0] - 1) * 100:.2f}"
    return out


def main() -> int:
    if not LOG.exists():
        print(f"no log at {LOG}")
        return 1

    with LOG.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    filled = 0
    for row in rows:
        if row.get("ret_1d") and row.get("ret_5d") and row.get("ret_20d"):
            continue
        try:
            rets = realized_returns(row["ticker"], row["trade_date"])
        except Exception as exc:  # network/yfinance errors: leave row as-is
            print(f"skip {row['ticker']} {row['trade_date']}: {exc}")
            continue
        if rets:
            row.update(rets)
            filled += 1

    with LOG.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)

    print(f"filled returns for {filled} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
