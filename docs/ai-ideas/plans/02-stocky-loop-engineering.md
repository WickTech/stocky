# Plan 02 — stocky: Loop Engineering, Verified Research Chain, Bull/Bear Debate

**Repo:** `~/github/stocky` (WickTech/stocky) · **Priority:** Medium (portfolio showpiece) · Educational only, never live trading.
**Source guides:**
- [Loop Engineering for Trades](https://www.raycfu.com/guides/loop-engineering-for-trades) — ICIR, half-life, OOS gate, Bonferroni
- [Analyze Any Stock with 5 Prompts](https://www.raycfu.com/guides/analyze-any-stock-five-prompts) — VERIFIED / STALE / UNVERIFIED
- [Trading Firm with AI Agents](https://www.raycfu.com/guides/trading-firm-ai-agents) — TradingAgents (github.com/TauricResearch/TradingAgents)
- [Karpathy Loop](https://www.raycfu.com/guides/karpathy-loop-ai-improvement) — program.md / experiments.md

## Why
`market_intelligence.py` trains per-ticker RandomForest, chronological 80/20 split, reports
**accuracy** only. Accuracy on next-day direction is weak evidence (class imbalance, no decay view,
no multiple-testing control). The guides give a more rigorous, explainable scorecard.

## Phase A — Scorecard upgrade (no LLM needed)
Add `stocky/metrics.py`:
- **IC** per month = Spearman/Pearson corr(predicted prob, next-day return); **ICIR** = mean(IC)/std(IC). Bands: >0.5 strong, 0.3–0.5 moderate, <0.3 noise.
- **Signal half-life** — autocorr of signal at lags 1/5/10/20/50 days.
- **Three-way split** — train / validation / **locked OOS (last 20–30%)**, OOS touched once per round.
- **Bonferroni** — α / total configs tried across all rounds; logged in `experiments.md`.
- Write ICIR + half-life + OOS verdict into `context_*.txt` next to accuracy.

## Phase B — Karpathy loop on features/params
- `program.md`: goal = maximize validation ICIR; editable = `features.py`, model params; read-only = `metrics.py`, data split, OOS set.
- `experiments.md`: hypothesis → one change → score → keep/revert.
- Hard caps: 5 rounds, no OOS peeking, Bonferroni gate at the end.

## Phase C — Verified research chain (Claude Project side)
Update `.project_instructions.md` with the 5-prompt chain: Deep Dive → Peer Comparison (NSE peers)
→ Bear Case (+ invalidation level) → **Verification pass** (tag every number VERIFIED/STALE/UNVERIFIED
with source + date) → Decision Record saved to `decisions/<ticker>-<date>.md` for 6-month review.

## Phase D (optional) — Bull/Bear debate
Try TradingAgents with `.NS` tickers (FinnHub coverage for India is limited — verify first; may need yfinance adapter).
Use as research second opinion only; log outputs vs. real outcomes (reflection layer).

## Acceptance criteria
- `python market_intelligence.py` still runs end-to-end; CI green.
- Context files show accuracy, ICIR, half-life, OOS pass/fail per ticker.
- Unit tests for IC/ICIR/half-life on synthetic series with known answers.
- README states Bonferroni-adjusted threshold used.
