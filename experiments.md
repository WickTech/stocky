# experiments.md — Phase B log

Appended by `python -m stocky.experiment`. Score = mean validation ICIR over the universe.
Keep rule: gain ≥ 0.05 over best so far. Max 5 rounds. See `program.md`.

| round | hypothesis | val ICIR | decision | date |
|---|---|---|---|---|
| 0 | baseline (current features.py) | 0.338 | - | 2026-09-29 |
| 1 | Drop raw sma20/sma50 price levels (non-stationary); keep only scale-free features | 0.120 | REVERT | 2026-09-29 |
| 2 | Add 5d and 20d momentum returns | 0.367 | REVERT | 2026-09-29 |
| 3 | Regularize RF: min_samples_leaf=20, max_depth=6 (noisy target) | 0.416 | KEEP | 2026-09-29 |
| 4 | Add 20d realized volatility (regime feature) | 0.486 | KEEP | 2026-09-29 |
| 5 | Add 5d return (short-term reversal) on regularized+vol base | 0.509 | REVERT | 2026-09-29 |

## Final locked-OOS gate (alpha_adj = 0.00093; 6 configs x 9 tickers)

| ticker | OOS IC | n | verdict |
|---|---|---|---|
| RELIANCE.NS | 0.075 | 358 | FAIL |
| TCS.NS | -0.027 | 358 | FAIL |
| INFY.NS | -0.070 | 358 | FAIL |
| HDFCBANK.NS | 0.007 | 358 | FAIL |
| SBIN.NS | -0.051 | 358 | FAIL |
| USDINR=X | 0.116 | 375 | FAIL |
| EURUSD=X | 0.071 | 375 | FAIL |
| GBPUSD=X | -0.069 | 375 | FAIL |
| AUDUSD=X | 0.052 | 375 | FAIL |

## Conclusion (2026-09-29)
Validation ICIR rose 0.338 → 0.486 (kept: RF regularization, 20d realized vol; reverted:
drop raw SMAs, 5d/20d momentum, 5d reversal). The locked-OOS gate then passed for **0 of 9**
tickers (best OOS IC +0.116 USDINR, several negative). The validation gains did not generalize:
this is selection on noisy validation (12 monthly IC obs per ticker, 6 configs), not an edge.
Negative result. No trading use; experiment closed (OOS has been scored once — a new
experiment needs fresh held-out data).
