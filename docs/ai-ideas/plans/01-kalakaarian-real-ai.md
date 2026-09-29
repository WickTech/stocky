# Plan 01 — Kalakaarian: Real AI Brief Analysis & Script Writer

**Repo:** `~/github/kalakaarian` (WickTech/Kalakaarian) · **Priority:** High (revenue + trust)
**Source guides:**
- [Self-Correcting AI Loop](https://www.raycfu.com/guides/self-correcting-ai-loop) — Builder / Judge / Manager
- [Writing That Doesn't Sound Like AI](https://www.raycfu.com/guides/human-sounding-ai-writing)
- [20-Agent Script System](https://www.raycfu.com/guides/ai-writing-pipeline-agents) (optional, later)
- [How to Prompt Claude Fable 5](https://www.raycfu.com/guides/claude-fable-5-prompting)

## Why
`server/src/services/aiService.ts` (78 lines) still ships keyword heuristics:
`analyzeBrief()` and `generateScript()` both carry `// TODO(real AI)`. Callers: `routes/ai.ts`
(`/analyze-brief`, `/generate-script`), `modules/campaigns/service.ts` (voice brief → match),
`pages/ScriptWriter.tsx`, `pages/AiCampaignBuilderPage.tsx`. Users see "AI" features backed by a stub.

## Target design
```
request ─▶ Builder (LLM)  ─▶ Judge (LLM, sees only requirements + output) ─▶ PASS → return
              ▲                         │ FAIL + cited reasons
              └──── fix named issues ◀──┘   Manager (code): max 3 attempts → fallback to heuristic + flag
```
- **Builder** — `analyzeBrief`: returns the existing `BriefAnalysis` shape via structured output (JSON schema). `generateScript`: returns `ScriptResult` (hook, body, CTA, hashtags), Hinglish/Hindi/English per request.
- **Judge** — rubric checks: schema-valid, matches brief's platform/format/duration, brand name + mandatory mentions present, no banned AI vocab (delve, leverage, seamless, robust, unlock, elevate…), ≤1 em-dash, sentence-length variance, no disallowed claims (ASCI influencer ad rules: `#ad`/`#collab` disclosure).
  Deterministic checks run in code first (cheap); LLM judge only for tone/fit.
- **Manager** — plain TS: attempt counter, logs verdicts to `ai_generation_logs` table, returns heuristic result with `source: "fallback"` if 3 fails or API down. Never blocks the request path > N seconds.
- **lessons.md equivalent** — store recurring judge failure reasons; inject top 5 into Builder system prompt (weekly job).

## Phases
1. **Provider layer** — `server/src/services/llm/` client (Anthropic SDK), model via env (`AI_MODEL_BUILDER`, `AI_MODEL_JUDGE`), timeout, retries, cost logging. Keep heuristics as fallback.
2. **analyzeBrief** — Builder + deterministic judge only. Behind feature flag `AI_REAL_BRIEF=1`.
3. **generateScript** — full Builder/Judge/Manager loop + anti-AI-voice rules.
4. **Observability** — admin panel tab: pass rate, avg attempts, fallback rate, cost/day.
5. **Eval set** — 20 real (anonymised) briefs in `server/test/fixtures/briefs/` + golden expectations; `node --test` runs judge on them (becomes the verifier for a later Karpathy loop on prompts).

## Acceptance criteria
- Both endpoints return same TS types as today; client needs no changes.
- Fallback path covered by tests (API key missing, timeout, 3× judge fail).
- Judge pass rate ≥ 85% on eval set; p95 latency documented.
- No PII (phone/email) sent to the LLM — strip before call.

## Decisions to make later
- Model/budget: Haiku 4.5 builder + Sonnet 5 judge, vs. single model.
- Whether AI features are metered (membership tier quota) — check current fee model first; `AI_FEE_RATE` no longer appears in `server/src`.

## Related ideas (separate, smaller)
- **Brand-prospecting agent** ([Agent that finds clients](https://www.raycfu.com/guides/claude-code-agent-finds-clients)): ICP from existing brand accounts → signals (funding, D2C launches, hiring marketers) → top-20 daily list → human-approved outreach. Run as a Claude Code Routine, outside the app.
- **SEO** ([SEO agency with Cowork](https://www.raycfu.com/guides/seo-agency-claude-cowork)): "page-2 goldmine" keywords (positions 11–20 in GSC) → programmatic `/creators/<niche>/<city>` pages. Cross-check `docs/SEO/SEO_IMPLEMENTATION_PLAN.md` first.
- **Twin avatar video** (`twinVideoService.ts` stub) — see [AI influencer system](https://www.raycfu.com/guides/ai-influencer-system) for the character-file approach.
