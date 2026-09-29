# Plan 05 — autoflow: Judge Node, Anti-AI-Voice Processor, More Sources

**Repo:** `~/github/autoflow` (WickTech/autoflow) · **Priority:** Medium-Low
**Source guides:**
- [Self-Correcting AI Loop](https://www.raycfu.com/guides/self-correcting-ai-loop)
- [Writing That Doesn't Sound Like AI](https://www.raycfu.com/guides/human-sounding-ai-writing)
- [Make Claude Sound Exactly Like You](https://www.raycfu.com/guides/make-claude-sound-like-you)
- [Scrape Any Platform Free — Agent Reach](https://www.raycfu.com/guides/scrape-platforms-claude-code-free) (github.com/Panniantong/Agent-Reach)
- [Graph Engineering](https://www.raycfu.com/guides/graph-engineering-ai-workflow)

## Why
Pipeline today: `sources → filter → dedup → LLM summarize → sinks` (email, telegram, Slack),
configured in YAML (`autoflow/{sources,processors,sinks,pipeline.py,registry.py}`).
Summaries are never checked against the source article, and output tone is generic.

## New processors (registered in `registry.py`, usable from YAML)
1. **`judge`** — after `summarize`: gives summary + source text to a judge prompt; PASS or cited failures (hallucinated number, missing key point, wrong entity). Re-summarize up to N times; on fail → drop item or mark `unverified`. Counter lives in code.
2. **`humanize`** — deterministic linter + optional LLM edit: banned vocab (delve, tapestry, leverage, seamless, robust, landscape, navigate, underscore, realm, testament, elevate, unlock, harness, foster), em-dash cap, sentence-length variance, "keep facts and structure" edit prompt.
3. **`voice`** — optional style file (`voice.md`, samples of my writing) injected into summarizer.

## New source (optional)
- **`agent_reach`** source — Reddit/YouTube transcripts/X via Agent Reach CLI. Needs session cookies → keep **off** in GitHub Actions; local-only. Document the account-ban risk.

## Graph execution (later)
YAML `depends_on` so multiple sources fetch in parallel and merge (diamond) before dedup.

## Acceptance criteria
- New processors have unit tests with a fake LLM (`autoflow/llm.py` already abstracted).
- Example YAML `examples/verified-digest.yaml` uses summarize → judge → humanize.
- Judge failure stats appear in run log.
