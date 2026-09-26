# Research Brief: AI-Native Web Interaction Layer ("Vantyx")

## Preamble — paste this block before the questions, for both Muse and CoWork

> You are researching for a technical/product feasibility study on a system that lets AI agents interact with arbitrary websites (starting with sites that have no public API, e.g. restaurant reservation platforms) without simulating mouse/screenshot-based UI interaction. The system works by: (1) discovering how a site's flow actually works (either its underlying network calls, or a UI-automation fallback), (2) representing that as a reusable, declarative "recipe" cached in a shared database so it's only solved once, (3) executing recipes locally on each end-user's own device using their own credentials (never centralizing credentials), and (4) exposing the discovery/orchestration layer as a hosted MCP server other AI agents can call.
>
> **Output format requirement: your findings must be delivered as a structured file (Markdown or JSON), not as a chat response — this output will be read and synthesized by an AI agent (Claude), not a human, as the next step in a build plan.** Use clear headers matching the question numbers below. For every claim, cite a source (URL, case name, doc link). Where the honest answer is "unresolved / actively debated / no consensus," say so explicitly rather than guessing — a confirmed unknown is more useful than a confident wrong answer. Flag anything that seems like it could make the whole approach infeasible or illegal, even if it wasn't explicitly asked.

---

## 1. Legal & regulatory risk

1.1. Under the U.S. Computer Fraud and Abuse Act (CFAA), does a user's own agent acting with the user's own valid login credentials, to perform an action the user is authorized to perform themselves, carry meaningfully different legal exposure than third-party scraping-for-resale cases (e.g., *hiQ Labs v. LinkedIn*, *Van Buren v. United States*, *Craigslist v. 3Taps*, *Meta v. Bright Data*)? Summarize current case law on "authorized access performed via automation" specifically.

1.2. Is a website's Terms of Service prohibition on automated/programmatic access enforceable as a civil breach-of-contract matter against an individual end user automating their *own* account, versus a business scraping at scale? Does *Van Buren*'s narrowing of CFAA change this analysis in 2026?

1.3. Does the federal BOTS Act (2016, targeting automated ticket purchasing) or any state-level equivalent extend to categories beyond ticketing (e.g., restaurant reservations, retail checkout, sneaker/GPU drops)? Is there pending 2025-2026 legislation expanding this?

1.4. Could bypassing commercial bot-detection/anti-automation systems (Cloudflare, Akamai, DataDome, PerimeterX/HUMAN, Kasada) be construed as circumventing a "technological protection measure" under DMCA §1201, by analogy to DRM circumvention cases? Has this theory been tested against bot-detection specifically (as opposed to copyright-protection tech)?

1.5. What is the liability allocation, under U.S. and EU consumer-protection and contract law, if an autonomous recipe causes real-world harm to the end user (double-booking, wrong purchase quantity/amount, unauthorized charge) — platform operator, recipe author (if crowd-sourced), or end user? Are there comparable precedents from RPA (robotic process automation) or personal-finance-automation tools (e.g., Plaid-connected apps, Mint, YNAB) misfiring?

1.6. GDPR/CCPA exposure: if a "recipe" or its discovery process incidentally captures structural/content data from a page that includes other users' personal data (e.g., another diner's name on a shared reservation confirmation page), what obligations does storing or caching that create for the recipe database operator?

## 2. Anti-bot-detection technical feasibility

2.1. Survey the current (2026) state of the art in bot-detection used by major providers (Cloudflare Bot Management, Akamai Bot Manager, DataDome, PerimeterX/HUMAN Security, Kasada) — what signals do they use (TLS/JA3/JA4 fingerprinting, canvas/WebGL fingerprinting, behavioral/mouse-movement biometrics, CDP/DevTools-Protocol detection, IP reputation)?

2.2. Evaluate current open-source anti-detection tooling: `undetected-chromedriver`, `playwright-stealth`/`puppeteer-extra-plugin-stealth`, `nodriver`, `camoufox`, `patchright`, `FlareSolverr`, `botright`. For each: maintenance activity in the last 6 months, effectiveness against current-generation bot detection, license terms, and whether their approach could be legally/practically "specialized" as this project's fallback engine.

2.3. How fast is the arms race — how often do major bot-detection vendors ship updates that break current stealth techniques, and is this a one-time integration or a permanent maintenance treadmill? Is there a sustainable way to keep pace as a small/solo team?

2.4. Does executing entirely from the end user's own residential IP and real (non-headless, non-automation-flagged) browser context eliminate most detection risk on its own, or do these systems also fingerprint automation frameworks directly (e.g., detecting CDP attachment) regardless of IP/network origin?

2.5. What specific anti-bot posture do the flows in scope actually have today, concretely — pick 3-5 real reservation/booking platforms (e.g., whichever platform Katsuya-style restaurants run on: Resy, OpenTable, Tock, SevenRooms) and report their known bot-detection stack, ToS language on automation, and any public reporting of enforcement actions against automation tools targeting them.

## 3. Recipe representation & discovery

3.1. Is there existing prior art for a declarative, non-Turing-complete schema for "how to complete a web interaction" (RPA tool formats like UiPath/Robocorp, Zapier's internal connector schema, IFTTT applets, or emerging AI-agent action-space formats used by browser-use, Skyvern, Convergence AI's Proxy)? Should this project adopt/extend one instead of designing from scratch?

3.2. What's the right way to detect that a given URL belongs to an already-solved recipe's pattern versus needing new discovery — URL templating/normalization, DOM-structure fingerprinting/clustering, or something else? Survey how existing "page-type classification" or "content extraction" tools (e.g., readability algorithms, Diffbot, import.io-style extractors) solve this.

3.3. What's a reliable method for detecting that a cached recipe has gone stale because the target site changed, before or as fast as it fails in production (structural diffing, response-shape hashing, canary re-checks)?

3.4. How should multi-step flows with hard interruptions (CAPTCHA prompts, 2FA/SMS codes, payment 3-D Secure challenges) be represented in a declarative schema — is graceful "hand back to a human/the user's own device for this one step" a realistic design, and what does that handoff look like technically?

## 4. Recipe-database security / supply-chain trust

4.1. What sandboxing approaches (ephemeral containers, network-egress allowlisting scoped to the claimed target domain, no real credentials injected) are appropriate for dry-running a newly discovered/updated recipe before it's promoted to "trusted" for other users?

4.2. What automated static/behavioral checks can realistically catch a malicious or buggy recipe (attempted cross-origin requests, embedded secrets/tokens, attempts to exceed its declared scope) given a constrained declarative schema? Survey techniques from software-supply-chain security tooling (Socket.dev, OpenSSF Scorecard, npm/PyPI malware-scanning research) for what transfers to "scanning recipes" instead of scanning code packages.

4.3. Precedent: has any existing crowd-sourced automation/scraping-recipe platform (e.g., browser extension rule-sharing like uBlock/Ghostery filter lists, IFTTT/Zapier community templates, RPA marketplaces) had a security incident from a malicious community-submitted item? What was the failure and the fix?

## 5. Prompt-injection & agent-safety

5.1. Survey current (2024-2026) best practices and published research for isolating untrusted third-party web content from an LLM agent's instruction/reasoning context — structured-extraction-only patterns, "dual-LLM" architectures, taint-tracking of untrusted strings, and any standards emerging from Anthropic, OpenAI, or Google DeepMind specifically for browser/computer-use agents.

5.2. Are there documented real-world cases of AI web agents (OpenAI Operator, Claude computer use, browser-use/Skyvern-class open-source agents) being successfully prompt-injected via page content? What happened, and what mitigation was shipped afterward?

## 6. MCP / distribution architecture

6.1. What does the current Model Context Protocol spec support for remote/hosted MCP servers — auth patterns (OAuth for MCP), session handling, and any existing convention for "the MCP server orchestrates but dispatches sensitive execution to a local companion process on the caller's device"? Has anyone already built this pattern?

6.2. What's required to reliably expose a home-hosted MCP server to the public internet (Cloudflare Tunnel, ngrok, Tailscale Funnel) — and what are the realistic failure modes (dynamic residential IP changes, ISP terms of service on running servers, upload bandwidth, uptime) if usage spikes suddenly (viral-growth scenario)?

## 7. Competitive landscape

7.1. Map the current competitive field: browser-use, Skyvern, Multi-on/Multi, Firecrawl, Apify, Browserbase, Airtop, Tinyfish, Reworkd, Induced AI, Convergence AI (Proxy), OpenAI Operator, Anthropic computer-use reference implementations. For each: what they actually do, pricing, funding/traction, and whether they overlap with "any site becomes an API, credential-safe, locally executed, crowd-sourced recipes" or leave that specific gap unserved.

7.2. What specifically drove OpenClaw's (formerly Clawdbot/Moltbot) growth — launch channel, community mechanics, timing — and which parts of that are actually replicable versus idiosyncratic to that project/creator?

7.3. **Direct question, answer this one plainly and prominently, don't bury it in the survey above:** Has this specific idea — a locally-executed, credential-safe, crowd-sourced-recipe layer that turns arbitrary websites (including ones with no public API) into something an AI agent can call like a function, distributed as a hosted MCP with a local companion for the sensitive steps — already been built by someone else, or is anyone currently and publicly building it right now (recent launches, funded startups, active GitHub repos with real traction, YC/accelerator batches, recent HN/Twitter/X launch threads)? Name the closest existing matches specifically and say exactly what they do differently or the same. Given what you find, give a direct, non-hedging recommendation: is this still worth building, and if so, what's the one thing that would have to be true (a gap, an angle, a timing advantage) for it to be worth it rather than redundant?

## 8. Business model

8.1. Survey open-source-core-plus-hosted-service companies (Sentry, GitLab, n8n, Supabase, Metabase) for how they split free (self-hosted/open client) versus paid (hosted backend, premium features) and what made the split actually convert to revenue rather than just adoption.

8.2. Is "build hype toward an acqui-hire" a strategy that can be deliberately engineered (specific launch tactics, metrics investors/acquirers actually look at), or is it primarily emergent/lucky based on available case studies? What do post-mortems of viral dev-tool launches (OpenClaw, and comparable prior examples) say about what was intentional versus fortunate?

## 9. What could make this impossible or radioactive (explicitly look for reasons to kill the idea)

9.1. Are there specific target-site categories (banking, anything in PCI-DSS scope, healthcare/insurance portals, government benefits systems) where this kind of automation is unambiguously illegal or contractually catastrophic regardless of technique, and should be permanently out of scope?

9.2. Can a site's fraud-detection system flag or ban a real user's own account for "non-human" access patterns — meaning the tool could get the very user it's helping locked out of their own account? How common is this, and is it avoidable?

9.3. Are there fundamental (not just currently-hard) technical barriers to automating flows gated by mandatory human-verification steps (CAPTCHA solving at scale, SMS/TOTP 2FA, biometric confirmation, card-network 3-D Secure)? Where is the line between "hard but solvable" and "structurally requires a human in the loop no matter what"?

9.4. Is there a credible scenario where a major browser vendor, payments network, or site-side anti-bot vendor could unilaterally shut this entire class of tool down (e.g., a browser API change, a payments-network rule change) with little warning? How exposed would this architecture be to that?
