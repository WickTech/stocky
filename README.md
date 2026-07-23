# stocky

A **localized machine-learning workspace** for daily Indian-equity and forex direction
signals. `stocky` runs entirely on your machine: it pulls 5 years of price history,
engineers technical features, trains a per-ticker Random Forest, backtests it, and emits
two plain-text context files. Those files are then fed into a Claude Project — governed by
`.project_instructions.md` — where Claude acts as your **Risk Manager & Trading Co-Pilot**
to turn the raw signals into disciplined, risk-first trade plans.

> ⚠️ **Educational use only. Not financial advice.** Every signal is a probabilistic tilt,
> not a guarantee. You own every decision.

---

## Data flow

```
                 ┌──────────────────────────────────────────────┐
                 │            market_intelligence.py            │
                 │                                              │
  yfinance ──▶   │  fetch 5y daily  ──▶  features (RSI/SMA/ret) │
  (Indian +      │        ──▶  RandomForest train + backtest    │
   forex)        │              ──▶  next-day direction + conf  │
                 └───────────────┬──────────────────────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
     context_indian_stocks.txt         context_forex.txt
                 │                               │
                 └───────────────┬───────────────┘
                                 ▼
                 Claude Project  (governed by .project_instructions.md)
                 → risk-managed swing/forex plans (RSI Reality Check, 1:2 R:R)
```

---

## Files

| File | Purpose |
|------|---------|
| `requirements.txt` | External Python dependencies. |
| `market_intelligence.py` | The daily engine — fetch, model, write context files. |
| `.project_instructions.md` | Standing rulebook uploaded **once** to your Claude Project. |
| `context_indian_stocks.txt` | **Generated** daily — NSE equity technical profiles. |
| `context_forex.txt` | **Generated** daily — forex profiles (4-decimal pip prices). |
| `README.md` | This file. |

The default universe (edit the constants at the top of `market_intelligence.py` to change):

- **Indian stocks:** `RELIANCE.NS`, `TCS.NS`, `INFY.NS`, `HDFCBANK.NS`, `SBIN.NS`
- **Forex pairs:** `USDINR=X`, `EURUSD=X`, `GBPUSD=X`, `AUDUSD=X`

---

## 1. Install dependencies (one time)

Run inside **WSL / Linux / macOS** (a Unix-style shell is the supported environment).

```bash
cd ~/github/stocky

# Create and activate an isolated virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

> **WSL note:** run the Python tooling from inside WSL, not from Windows, to avoid the
> mount/symlink quirks that affect node tooling on the WSL share. `pip` itself is fine, but
> keeping everything in the WSL shell avoids cross-OS path surprises.

---

## 2. Run the engine (daily)

With the virtualenv active:

```bash
cd ~/github/stocky
source .venv/bin/activate        # if not already active
python market_intelligence.py
```

What happens:

1. Downloads 5 years of daily candles for each ticker (needs internet).
2. Computes 14-day RSI, 20- & 50-day SMAs, and daily returns.
3. Trains a Random Forest per ticker with a **chronological 80/20** train/test split
   (no shuffling — the future is never leaked into training).
4. Backtests on the 20% hold-out and reads next-day direction + confidence on today's data.
5. Writes the two context files into the current directory, overwriting yesterday's:
   - `context_indian_stocks.txt`
   - `context_forex.txt`

**Robustness:** if a ticker can't be fetched or has too little clean history, it is logged
with a warning and given a `DATA UNAVAILABLE` line in the output — the run continues for
every other ticker.

You'll see a console summary like:

```
12:01:07  INFO     Done. Equities modeled 5/5, Forex modeled 4/4.
12:01:07  INFO     Outputs: context_indian_stocks.txt, context_forex.txt
```

### Optional: schedule it

Run it each morning before the session via cron (example: 8:30 AM IST on weekdays):

```cron
30 8 * * 1-5  cd ~/github/stocky && ./.venv/bin/python market_intelligence.py >> ~/github/stocky/run.log 2>&1
```

---

## 3. Feed the context back into Claude

**One-time setup:**

1. Create a Claude Project for stocky.
2. Upload **`.project_instructions.md`** to the Project's **Knowledge**. This installs the
   risk-management rules permanently (persona, RSI Reality Check, 1:2 R:R, forex 4-decimal
   pip formatting, confidence filters).

**Each trading day:**

1. Run `python market_intelligence.py` to refresh the two context files.
2. Upload (or paste) the freshly generated **`context_indian_stocks.txt`** and/or
   **`context_forex.txt`** into the Project chat.
3. Ask for a plan, e.g.:
   - *"Using context_indian_stocks.txt, give me today's qualifying swing longs with full
     1:2 entry/stop/target levels."*
   - *"Using context_forex.txt, what's the relative-strength read on USDINR and its macro
     implication for Indian IT vs banks?"*

Claude will apply the standing rules: filter out low-confidence/low-accuracy signals, run
the RSI Reality Check on equities, build explicit risk-first levels, and quote forex prices
to 4 decimals.

---

## How to read the output

Each context file contains, per ticker: last close, daily return, RSI(14) (flagged when
>70 / <30), SMA(20) & SMA(50), a trend read, **backtested model accuracy**, the **predicted
next-day direction**, and the **signal confidence %** — followed by a scannable summary
table.

Key conventions baked into the rules:

- **RSI Reality Check (equities):** a fresh long is *not* endorsed when RSI > 70, even on a
  bullish model signal.
- **1:2 Risk-to-Reward (equities):** every actionable idea needs entry, stop, and a target
  at ≥ 2× the risk.
- **4-decimal pip precision (forex):** all forex levels are quoted to 4 decimals; risk and
  reward are expressed in pips (1 pip = 0.0001).
- **Confidence filter:** signals below ~55% confidence, or from models near coin-flip
  accuracy, are treated as *no edge*.

---

## Configuration

Edit the constants near the top of `market_intelligence.py`:

| Constant | Meaning |
|----------|---------|
| `INDIAN_STOCKS`, `FOREX_PAIRS` | The ticker universe. |
| `HISTORY_PERIOD` | History window (default `"5y"`). |
| `RSI_PERIOD`, `SMA_FAST`, `SMA_SLOW` | Indicator lookbacks (14 / 20 / 50). |
| `MIN_TRAINING_ROWS` | Minimum clean rows before a ticker is modeled. |
| `TEST_SIZE`, `N_ESTIMATORS` | Hold-out fraction and forest size. |

---

## Troubleshooting

- **A ticker shows `DATA UNAVAILABLE`:** yfinance returned nothing or too little history.
  Re-run later (rate limits / transient outages) or verify the symbol on Yahoo Finance.
- **`Missing dependency 'yfinance'`:** activate the venv and `pip install -r requirements.txt`.
- **Everything is `DATA UNAVAILABLE`:** likely no network access from the shell, or yfinance
  is being rate-limited. Confirm connectivity and retry.

---

## Disclaimer

`stocky` is a personal research and educational tool. It does not execute trades and does not
constitute financial advice. Markets carry risk; you are solely responsible for any decisions
made with this information.
