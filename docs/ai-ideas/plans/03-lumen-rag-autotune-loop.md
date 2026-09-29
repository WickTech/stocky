# Plan 03 — lumen-rag: Self-Improving Retrieval (Karpathy + Bilevel Loops)

**Repo:** `~/github/lumen-rag` (WickTech/lumen-rag) · **Priority:** Medium-High (strong portfolio story: "agent improved nDCG from X to Y")
**Source guides:**
- [Karpathy Loop](https://www.raycfu.com/guides/karpathy-loop-ai-improvement)
- [Bilevel Loops](https://www.raycfu.com/guides/bilevel-loops-system)

## Why
Lumen already has the hard part: a verifier. `lumen_rag/eval/{harness,metrics}.py` computes
recall@k / precision@k / MRR / nDCG@k / hit-rate over `data/eval.jsonl`, and
`scripts/check_eval.py` gates CI. "No verifier = no loop" is satisfied.

## Design
```
loop/
  program.md      human-written: goal, editable vs read-only, constraints, stop rules
  playbook.md     search directions (coach-owned)
  attempts.log    ts | idea | category | nDCG@5 | kept/discarded
  experiments.md  hypothesis, change, result, lesson
```
- **Editable:** chunking params, hybrid/RRF weights, top-k, reranker toggle, query rewriting in `lumen_rag/retrieval/` + `config.py`.
- **Read-only:** `lumen_rag/eval/`, `data/eval.jsonl`, `scripts/check_eval.py`, tests.
- **Metric:** primary nDCG@5 on hybrid mode; guardrails: recall@5 must not drop, latency p95 must stay < budget.
- **Held-out split:** split `eval.jsonl` into `eval_dev.jsonl` (loop sees) and `eval_holdout.jsonl` (checked only at the end) — prevents overfitting to the eval set.

## Phases
1. **Bigger eval set** — current set likely small; generate 50–100 Q/A pairs from `data/docs` with an LLM, hand-verify a sample. Split dev/holdout.
2. **Inner loop (Karpathy)** — Claude Code session driven by `program.md`; one change per cycle; ratchet (revert if worse).
3. **Outer loop (Bilevel coach)** — every 15–25 attempts, coach reads `attempts.log`, marks exhausted directions, rewrites `playbook.md`. Coach never touches metric or eval files.
4. **Report** — `docs/autotune-report.md` + chart of nDCG over attempts; update README badge/numbers.

## Acceptance criteria
- Loop runnable via `make autotune` (or documented prompt).
- Holdout nDCG improvement reported honestly (including if zero).
- CI thresholds in `check_eval.py` raised only to holdout-verified values.
