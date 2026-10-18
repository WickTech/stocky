# program.md — Phase B Karpathy loop (stocky)

Educational only. Never live trading.

## Goal
Maximize **mean validation ICIR** across the 9-ticker universe, as printed by
`python -m stocky.experiment round "<hypothesis>"`.

## Editable (only these)
- `stocky/features.py` — feature definitions, `FEATURE_COLUMNS`, `MODEL_PARAMS`.

## Read-only (never edit, never work around)
- `stocky/metrics.py`, `stocky/experiment.py` — scoring, split, Bonferroni, round cap.
- The train/validation/OOS split (50/20/30) and the frozen data in `.cache/`.
- `experiments.json` (harness state) — written only by the harness CLI.

## Loop (max 5 rounds)
1. Once: `python -m stocky.experiment baseline`.
2. Per round: state ONE hypothesis → make ONE change in `features.py` → run
   `python -m stocky.experiment round "<hypothesis>"`.
3. The harness prints KEEP (gain ≥ 0.05 over best) or REVERT. On REVERT,
   `git checkout stocky/features.py`. Reverted rounds still count as configs tried.
4. After round 5 (or earlier if out of ideas): `python -m stocky.experiment final`.
   This scores the locked OOS set **once** at Bonferroni α = 0.05 / (configs × tickers).

## Hard rules
- No OOS peeking: never compute or print OOS metrics before `final`. `final` runs once.
- No new data, no target changes, no edits to the split, no editing the harness.
- Selection uses validation ICIR only. Tuning to OOS results is forbidden; after `final`,
  the experiment is over — a new experiment needs new held-out data.
- Every round is logged in `experiments.md` by the harness; do not hand-edit rows.
- A validation gain that fails the OOS gate is a **negative result to report**, not a bug.
