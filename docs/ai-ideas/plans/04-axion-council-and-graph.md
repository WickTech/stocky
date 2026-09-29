# Plan 04 — axion: LLM Council Advisor + Graph Orchestrator

**Repo:** `~/github/axion` (local, not on GitHub) · **Priority:** Medium (personal productivity)
**Already applied:** [Personal Jarvis](https://www.raycfu.com/guides/personal-jarvis-with-claude) — scout/operator/advisor prompts, UNAVAILABLE rule, approval gates.
**Source guides:**
- [LLM Council](https://www.raycfu.com/guides/llm-council-better-claude-answers)
- [Graph Engineering](https://www.raycfu.com/guides/graph-engineering-ai-workflow)
- [Claude PhD Research System](https://www.raycfu.com/guides/claude-phd-research-system) (researcher upgrade)
- [Claude Code Routines](https://www.raycfu.com/guides/claude-code-routines-automate-workflows) / [Claude Dispatch](https://www.raycfu.com/guides/claude-dispatch-beginner-guide) (triggers)

## Idea 1 — `--council` mode for big decisions
New registry agent `council` (risk class `read`):
1. **Frame** — read `data/mission-control.json`, `recommendations-log.md`, relevant CLAUDE.md; rewrite question neutrally (decision, context, stakes).
2. **5 advisors in parallel** — Contrarian, First-Principles, Expansionist, Outsider, Executor; 150–300 words each. New prompts in `prompts/council/*.md`.
3. **Anonymous peer review** — responses shuffled as A–E; each reviewer names strongest, biggest blind spot, collective gap.
4. **Chairman** — agreement, disagreement, blind spots, recommendation, ONE next action.
Output: `data/council/<date>-<slug>.md` (+ mapping) and an HTML panel in `dashboard/`.
Safety: read-only; next action goes into recommendations log, not executed.

## Idea 2 — Graph-shaped plans in orchestrator
`src/orchestrator/plan.mjs` today builds a step list. Extend plan schema with `dependsOn: []`:
- Topological run; independent nodes run concurrently (cap 10); approval still per write/shell/claude node.
- **Checker node** type before convergence: flags empty, contradictory, off-topic, low-confidence, malformed outputs → blocks synthesis.
- Remove "fake edges": scout collectors (GitHub, Vercel, Gmail, Supabase) become parallel nodes → `build-data` diamond.
- `--dry-run` prints the DAG.

## Idea 3 — Researcher upgrade
Apply PhD-research method to `prompts/researcher.md`: explicit question decomposition, source grading, contradiction table, confidence per claim.

## Acceptance criteria
- `npm test` covers DAG ordering, cycle detection, checker-node blocking, council anonymisation mapping.
- No approval-bypass path introduced (existing invariant).
