# Plan 06 — Samya: Menu Chatbot + Scroll-Sequence Hero (+ sellable template)

**Repo:** `~/github/Samya` (WickTech/samya) · Live: https://samya-tawny.vercel.app · **Priority:** Medium (real client value, reusable as a product)
**Source guides:**
- [$12K/mo AI Chatbot for Restaurants](https://www.raycfu.com/guides/restaurant-ai-chatbot-business)
- [$8K Website Scroll Animations](https://www.raycfu.com/guides/website-scroll-animations-8k)
- [SEO Agency with Cowork](https://www.raycfu.com/guides/seo-agency-claude-cowork) — Google Business Profile weeks 1–6
- [Automate Instagram DMs with Muse](https://www.raycfu.com/guides/automate-instagram-dms-muse) — US/CA only today; watch for India rollout

## Why
Samya is static-first Next.js 15; ordering goes through WhatsApp links (header/footer/hero).
All menu data is typed in `src/data/menu.json` (price tiers, kcal, macros, dietary tags) —
perfect grounding for a chatbot that can't invent dishes.

## Idea 1 — Menu assistant (web first, WhatsApp later)
- `src/app/api/chat/route.ts` — LLM call grounded **only** on `menu.json` + an `faq.md` (hours, area, delivery fee rules, subscriptions). Unknown → "Message us on WhatsApp" hand-off (Jarvis faq.md escalation pattern).
- Capabilities: "high-protein under ₹300", "vegan options", macros per item, build a WhatsApp order draft (pre-filled `wa.me` text) — no payments.
- Widget: small floating chat, lazy-loaded, respects reduced motion.
- Guardrails: rate-limit per IP, max tokens, no free-form medical/nutrition claims beyond listed macros.
- Phase 2: WhatsApp Business Cloud API webhook (reuse Kalakaarian's signature-verification pattern from `server/src/routes/whatsapp.ts`).

## Idea 2 — Scroll-sequence hero
- Generate matched start/end frames (same bowl, lighting, background; one change, e.g. ingredients dropping in) → 3–6 s clip → 90–150 frames → WebP q80, < 10 MB total.
- `components/hero-sequence.tsx`: canvas render, preload with loading state, GSAP ScrollTrigger pin + `scrub: true`, static frame on mobile / `prefers-reduced-motion`.
- Check Lighthouse LCP before/after; keep current hero as fallback.

## Idea 3 — Local SEO checklist
GBP categories/attributes, 2–3 posts/week, review-response templates with dish + "Bhilai/Durg" keywords, service+area pages (`/delivery/bhilai`, `/delivery/durg`).

## Productize (→ SoftwareToSell)
Extract chatbot as `menu-bot` template: any restaurant supplies `menu.json` + `faq.md`. Pricing reference from guide: base ₹/month + WhatsApp add-on + monthly report.

## Acceptance criteria
- Bot refuses/redirects for dishes not in menu.json (test cases).
- No new client JS on pages without the widget opened (lazy).
- Hero passes Lighthouse perf ≥ current score − 5.
