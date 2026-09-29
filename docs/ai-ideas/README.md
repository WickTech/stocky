# AI-Ideas

Ideas from [raycfu.com/guides](https://www.raycfu.com/guides), mapped onto my projects (researched 2026-09-28).

- [`guides-catalog.md`](guides-catalog.md) — all 95 guides, grouped, with slug and which project each fits.
- [`plans/`](plans/) — one implementation plan per best-fit project.

## Plans

| # | Plan | Repo | Key guides | Priority |
|---|---|---|---|---|
| 01 | [Real AI brief analysis + script writer](plans/01-kalakaarian-real-ai.md) | kalakaarian | Self-correcting loop, human-sounding writing | High |
| 02 | [Loop engineering + verified research](plans/02-stocky-loop-engineering.md) | stocky | Loop engineering (ICIR), 5 prompts, TradingAgents | Medium |
| 03 | [Self-improving retrieval](plans/03-lumen-rag-autotune-loop.md) | lumen-rag | Karpathy loop, bilevel loops | Medium-High |
| 04 | [Council advisor + graph orchestrator](plans/04-axion-council-and-graph.md) | axion | LLM council, graph engineering | Medium |
| 05 | [Judge node + anti-AI voice](plans/05-autoflow-judge-and-voice.md) | autoflow | Self-correcting loop, human writing, Agent Reach | Medium-Low |
| 06 | [Menu chatbot + scroll hero](plans/06-samya-chatbot-and-scroll.md) | Samya | Restaurant chatbot, scroll animations, local SEO | Medium |
| 07 | [Provider fallback + council mode](plans/07-ai-orc-nimbus-router.md) | ai-orc, nimbus-ai | OmniRoute, local models, LLM council | Low-Medium |

## Already applied
- Personal Jarvis → `axion`
- Automated GTA 6 channel → `Youtube-Channel-Automation`
- Resume unrejectable → `resume-builder`
- 4-agent dev team → global `/ship` pipeline

## How to run a plan
Open the target repo, then: `/ship <paste plan section>` — or hand the plan file to `pipeline-planner` to turn into `.pipeline/spec.md`.

## Open decisions (answer before building)
1. Goal weighting: revenue/launch vs job portfolio.
2. LLM budget for runtime features: paid Claude API, free tiers, or mixed (cheap builder + strong judge).
3. Order of execution.
