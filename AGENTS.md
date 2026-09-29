# stocky — agent handoff

Local ML market-intelligence tool. **Educational only. Never live trading, never real-money execution.**

## Layout
- `market_intelligence.py` — per-ticker RandomForest, chronological 80/20 split, reports accuracy only; writes `context_*.txt`.
- `requirements.txt` — deps (pinned with upper bounds).
- `docs/ai-ideas/` — research + plans migrated from a local `AI-Ideas` folder:
  - `README.md` — index, open decisions.
  - `guides-catalog.md` — 95 raycfu.com guides; "Trading & finance" section is the relevant one.
  - `plans/02-stocky-loop-engineering.md` — **the plan for this repo. Start here.**
  - `plans/01,03–07` — plans for other repos (kalakaarian, lumen-rag, axion, autoflow, Samya, ai-orc/nimbus). Reference only; do not implement here.
- `.github/workflows/ci.yml` — syntax check + pytest.

## Work queue (in order)
1. ~~**Plan 02 Phase A**~~ DONE — `stocky/metrics.py`: IC/ICIR, signal half-life, train/val/locked-OOS split, Bonferroni; write results into `context_*.txt`; unit tests on synthetic series with known answers.
2. ~~**Plan 02 Phase B**~~ DONE (0/9 pass OOS; see experiments.md) — Karpathy loop (`program.md`, `experiments.md`), max 5 rounds, no OOS peeking.
3. ~~**Plan 02 Phase C**~~ DONE (docs/research-chain.md) — 5-prompt verified research chain (VERIFIED/STALE/UNVERIFIED tags, decision records).
4. **Trading-bot idea (new, unplanned)** — paper-trading executor that consumes the stocky signal. Reference guide: `claude-fable-trading-bot` (raycfu.com/guides/claude-fable-trading-bot) — not yet read; fetch it and write `docs/ai-ideas/plans/08-trading-bot.md` before coding. LLM agents (TradingAgents, guides #78/#79) = research second opinion, never the trade trigger. Polymarket agent (#91) = separate, high-risk track; do not start without explicit approval.
5. Plan 02 Phase D — `.venv-ta` + `scripts/ta_spike.py` ready; waiting on free API keys in `.env` (see `.env.example`), then run the spike and record results in `docs/ai-ideas/plans/02d-tradingagents-free.md`.

## Acceptance (from plan 02)
- `python market_intelligence.py` still runs end-to-end; CI green.
- Context files show accuracy, ICIR, half-life, OOS pass/fail per ticker.
- README states the Bonferroni-adjusted threshold.

## Open decisions (ask owner before building)
- Goal weighting: revenue vs job-portfolio showpiece.
- LLM budget: paid Claude API / free tiers / mixed.
- Paper-trading only vs any live execution (default: paper only).

## Notes
- `.project_instructions.md` is gitignored (local Claude Project notes); its 5-prompt chain content should be recreated under `docs/` in Phase C.
- `requirements.txt` had an uncommitted change adding upper bounds; included in the migration commit.
- Never commit API keys; `.env*` is gitignored.
