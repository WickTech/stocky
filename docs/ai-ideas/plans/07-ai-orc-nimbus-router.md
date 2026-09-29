# Plan 07 — ai-orc & nimbus-ai: Provider Fallback Router + Council Mode

**Repos:** `~/github/ai-orc` (WickTech/Ai-Orc), `~/github/nimbus-ai` (WickTech/nimbus-ai) · **Priority:** Low-Medium
**Source guides:**
- [Claude Code with Unlimited Tokens — OmniRoute](https://www.raycfu.com/guides/claude-code-unlimited-tokens)
- [Run Claude Code Free with Local Models](https://www.raycfu.com/guides/free-claude-code-local-models)
- [LLM Council](https://www.raycfu.com/guides/llm-council-better-claude-answers)
- [1,000 Agents from One Prompt](https://www.raycfu.com/guides/thousand-agents-one-prompt) / [Agent Team in Loops](https://www.raycfu.com/guides/claude-code-agent-team-loops)
- [Obsidian Personal OS](https://www.raycfu.com/guides/obsidian-personal-operating-system) (ai-orc already has a vault browser)

## nimbus-ai (Next.js 15 AI SaaS, Vercel AI SDK, credit ledger)
1. **Fallback chain** — ordered provider list per plan tier (e.g. primary Claude → cheaper model → free tier). On 429/5xx/quota → next provider, same stream to client. Record actual provider + cost in the credit ledger so billing stays correct.
2. **Cost-aware routing** — short/simple prompts → cheap model; "deep" toggle → strong model. Credits charged by actual model used.
3. **Council mode** — premium feature: 3–5 perspective sub-calls + chairman synthesis; charges N× credits, shown up front.
Acceptance: provider failure simulated in Vitest → request still succeeds, ledger entry correct.

## ai-orc (local web app with xterm.js terminals for AI CLIs)
1. **Router panel** — show which CLI/provider is live, quota status, one-click switch (OmniRoute-style, or just embed OmniRoute's dashboard at `localhost:20128` if installed).
2. **Fan-out runner** — launch N CLI sessions on a task list (worktree per task), status grid, cap concurrency.
3. **Vault loops** — scheduled prompt that tidies Obsidian inbox → daily note (Obsidian OS guide).
Acceptance: fan-out never shares a working directory between sessions.

## Caution
Token-compression proxies can alter prompts; keep off for code-editing sessions unless verified.
