# Verified research chain (Plan 02 Phase C)

Five prompts, run in order in the stocky Claude Project, one ticker at a time. Educational
only — never live trading, never a directive. Source: raycfu "Analyze Any Stock with 5 Prompts".

The stocky ML signal is **input, not evidence**. If the context file shows `OOS Verdict: FAIL`
(currently true for every ticker; see `experiments.md`), the chain must not cite the model
direction as support for a thesis.

## Tags (applied in Prompt 4)

| Tag | Meaning |
|---|---|
| **VERIFIED** | Checked against a named primary source, source + date given, fresh enough for its type. |
| **STALE** | Real, but older than the freshness window below. Number may have moved. |
| **UNVERIFIED** | No source found, sources conflict, or it came from memory. Cannot support a decision. |

Freshness windows: price / valuation multiples ≤ 1 trading day; quarterly financials ≤ 1
quarter after the latest result date; annual figures ≤ 12 months; shareholding pattern ≤ 1
quarter; qualitative claims need a dated source ≤ 6 months.

## Prompts

Replace `{TICKER}` (NSE symbol, e.g. `TCS.NS`) and `{DATE}`.

### 1. Deep Dive
> Deep-dive {TICKER} as of {DATE}. Cover: business model and segment revenue mix; last 8
> quarters of revenue, EBITDA margin, PAT; balance sheet (debt/equity, cash, working capital);
> valuation (P/E, P/B, EV/EBITDA vs its own 5y range); promoter/FII/DII holding trend;
> upcoming catalysts. For every number give the source and its date. Mark anything you cannot
> source as "no source" — do not estimate.

### 2. Peer Comparison
> Compare {TICKER} against its 3–4 closest NSE-listed peers (name them and justify the peer
> set). Table: growth, margins, ROE/ROCE, leverage, valuation multiples. Say where {TICKER}
> is cheap/expensive *and whether the gap is explained by fundamentals*. Source + date per cell.

### 3. Bear Case
> Argue the strongest case against owning {TICKER} now: the three most likely ways the thesis
> breaks, with evidence. End with an **invalidation level** — a concrete price and/or
> fundamental condition (e.g. "closes below ₹X" or "margin < Y% for two quarters") at which
> the bullish view is wrong and the idea is abandoned.

### 4. Verification pass
> Re-read prompts 1–3. List every factual number and claim in a table:
> `claim | value | source | source date | tag`. Tag each VERIFIED / STALE / UNVERIFIED using
> the freshness windows. Re-check the ten most decision-relevant items against a primary
> source (exchange filing, company results, NSE/BSE data) again rather than trusting your
> earlier answer. Then list what changes in the thesis if all STALE and UNVERIFIED items are
> wrong. Do not repair gaps by guessing.

### 5. Decision Record
> Produce the decision record using `decisions/TEMPLATE.md`: decision (Buy / Watch / Avoid),
> thesis in three sentences, entry / stop / target with 1:2 risk-reward math (per
> `.project_instructions.md` §3.3), the invalidation level from prompt 3, position-size
> risk, the count of UNVERIFIED items that remain, and a review date 6 months out. Any
> UNVERIFIED item that the thesis depends on forces the decision to **Watch**.

Save the result as `decisions/<ticker>-<YYYY-MM-DD>.md` (local; gitignored except the template).

## 6-month review
On the review date: record actual price vs entry/stop/target, whether the invalidation level
hit, which VERIFIED numbers proved wrong, and one lesson. Aggregate reviews to learn whether
the chain helps — do not trust it on faith.
