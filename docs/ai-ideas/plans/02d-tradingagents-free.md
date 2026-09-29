# Plan 02 Phase D — TradingAgents on free / open-source stack

Researched 2026-09-29. Educational only; research second opinion, never a trade trigger.
Tags follow `docs/research-chain.md`.

## Findings

| Claim | Tag | Source (fetched 2026-09-29) |
|---|---|---|
| Apache-2.0 license | VERIFIED | github.com/TauricResearch/TradingAgents README |
| Needs Python ≥ 3.11 (venv here is 3.12.3 — OK) | VERIFIED | README |
| Supports India tickers `RELIANCE.NS`, `.BO` via Yahoo Finance | VERIFIED | README ("India: `RELIANCE.NS`, `.BO`"). Data quality on NSE names not yet tested |
| Local LLMs via Ollama (`llm_provider: "ollama"`, default `http://localhost:11434/v1`) and OpenAI-compatible servers (vLLM, LM Studio, llama.cpp) | VERIFIED | README |
| Yahoo Finance prices/fundamentals need no API key | VERIFIED (via web summary + README) | README |
| Optional: FRED macro (free key), Jev sentiment screening (`TYPESAFE_API_KEY`) | VERIFIED | README. Jev pricing/free tier UNVERIFIED |
| Alpha Vantage key listed as required for technical indicators | PARTLY UNVERIFIED | README lists it; whether yfinance-only mode works without it not tested |
| README disclaimer: research only, not financial advice | VERIFIED | README |
| Gemini free tier limit for `gemini-3.8-flash` | **VERIFIED (spike, 2026-09-29): 20 requests/day/project/model** | API 429 `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, quotaValue 20. One TradingAgents run needs far more calls -> Gemini free tier is NOT viable for a full run on this model |
| Gemini `gemini-2.5-flash` availability | VERIFIED unavailable to new keys | API 404: suggests `gemini-3.8-flash`; transient 503 "high demand" also seen |
| Groq / OpenRouter `:free` limits | UNVERIFIED | not tested yet |
| Small local models (7–8B) give usable multi-agent debate + tool calls | UNVERIFIED | must be tested |

## This machine
- GTX 1070, **8 GB VRAM**; WSL has ~5 GB RAM, 4 cores; Ollama **not installed**; no cloud LLM keys in env.
- Fits 7–8B Q4 models (e.g. qwen2.5:7b, llama3.1:8b) on GPU. Anything larger will not.
- Each TradingAgents run makes many LLM calls (analysts + bull/bear debate + risk debate).
  Expect minutes per ticker on a 1070, and weaker reasoning than frontier models.

## Options (all free)
1. **Local Ollama, 7–8B model** — fully free/open, offline, slow; quality risk. Best for a no-cost demo.
2. **Free cloud tier (Gemini / Groq / OpenRouter free models)** — faster, better quality; rate-limited
   and terms can change (UNVERIFIED). Keys are free but live in `.env` (gitignored; never commit).
3. **Mixed** — cheap/quick model for analysts, best free model for the final debate/decision.

## Proposed build (thin adapter, no fork)
- New `stocky/second_opinion.py` (not in the Phase B editable/read-only sets): `pip install`
  TradingAgents in a separate venv (`.venv-ta`, python 3.12, gitignored) to avoid dependency
  clashes with the stocky venv; call it as a subprocess or via its Python API.
- Input: ticker + date. Output: `docs/second-opinions/<ticker>-<date>.md` (local) with the
  agents' recommendation + rationale.
- **Reflection log:** append `date, ticker, agent call, stocky signal, realized 1/5/20-day
  return` to `second_opinions.csv`; fill realized returns later. Judge only after ≥30 calls,
  with the same rank-IC/Bonferroni discipline — no anecdotes.
- Guardrails: never a trade trigger; paper only; the LLM output is UNVERIFIED until the
  research-chain verification pass tags its numbers.

## Spike plan (smallest first step, ~1 hour)
1. `uv venv .venv-ta --python 3.12 && uv pip install` TradingAgents (README install steps).
2. Install Ollama, `ollama pull qwen2.5:7b`; run one `.NS` ticker with yfinance data only.
3. Record: wall-clock time, whether tool calls succeed, whether it needs Alpha Vantage,
   whether NSE fundamentals come back non-empty. Decide go / no-go from that evidence.

## Decisions needed from owner
- Local Ollama only, or allow free cloud keys (Gemini/Groq/OpenRouter)?
- OK to install Ollama (≈ GB downloads) in WSL and a second venv?
- Jev sentiment: try it (needs `TYPESAFE_API_KEY`; free tier UNVERIFIED) or skip?

## Spike log
- 2026-09-29 TCS.NS: key works, yfinance path reached the Market/Fundamentals analysts; run aborted at the
  Fundamentals Analyst on Gemini free-tier daily quota (20 req/model/day). No decision produced.
  Next: try Groq or OpenRouter free models, or a local Ollama model (no quota).
