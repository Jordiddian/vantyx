# Vantyx — Synthesis, Go/No-Go, and V1 Plan

Synthesized from the Muse and CoWork research reports (2026-09-24/25) plus live verification of the competitive claims. Where the two reports agreed, that's the strongest signal in this document. Where they conflicted, I checked it rather than picking a side.

---

## 1. The competitive picture, corrected

Muse named Klura/ApiTap/NoUI as the closest matches. CoWork named Unbrowse/Kampala/Integuru. Zero overlap between the two lists was the first red flag — enough that I stopped and verified the top name from each before writing anything else. **Unbrowse, Klura, and Kampala are all real:**

- **Unbrowse** (github.com/unbrowse-ai/unbrowse, 628 stars, live) — "route layer for web agents." Discovers first-party API routes from browser traffic, generates skills, calls APIs directly. Ships an MCP, a CLI, a TypeScript SDK, and a route marketplace with reliability scoring (routes under 0.2 get dropped) and creator/site-owner payment splits. Client is MIT; backend (route graph, ranking, settlement) is closed.
- **Klura** (github.com/klura-ai/klura, live) — "browser once, learn the interface, replay as API forever." Has a self-healing loop (classify failure → re-capture → re-learn) and a tiered fallback (direct HTTP → in-page script → UI replay).
- **Kampala** (Zatanna, YC W26, launched HN April 2026) — MITM proxy that reverse-engineers websites/mobile/desktop apps into scripts or hosted APIs, reuses the user's existing session/auth so there's no separate credential store, ships both an MCP and an agent harness.
- **Integuru** (github.com/Integuru-AI/Integuru, ~4.6k stars per CoWork, AGPL-3.0) — captures network requests, builds a dependency graph, compiles to executable Python for internal APIs. The open-source "v0" is reportedly archived; the team moved to a hosted product.

I did not independently re-verify Muse's ApiTap/NoUI or CoWork's exact Unbrowse star count (628 vs. 759 — likely just different snapshot dates) — not load-bearing given the picture is already clear without them.

**What this means:** this is not a two-report coincidence turning up the same project from different angles. It's a genuinely crowded field, with at least one YC-backed entrant five months old. The "capture once, compile to API, replay locally" mechanism — the technical core of everything we designed in this conversation — is not a moat. Both reports converge on the same conclusion independently: **the only unclaimed piece is a trusted, audited, cross-user recipe network with real verification**, and neither report found anyone who has actually built that, or found evidence anyone will pay for it yet.

---

## 2. Go / No-Go

**Conditional go — narrower than the original pitch, and only on the trust layer, not the compiler.**

What kills the original framing:
- The compiler ("browser once, learn the API, replay it") is a commodity now, built by at least four teams, one straight out of YC. Building it as the product is building a feature three funded competitors already ship.
- The original launch example — restaurant reservations — is close to the worst possible category to lead with: NY, and per CoWork's more careful read also a CA bill (AB 1640) and an IL bill in motion, all specifically target reservation-booking automation; Resy has already banned real users for exactly this behavior (hundreds of requests/hour); and as of August 2026 Yelp/Resy/OpenTable have an *official* ChatGPT-integrated booking channel, which directly undercuts the "no API exists" premise for that vertical specifically.
- Payment-touching flows hit a licensing wall (money-transmitter law, FinCEN, NACHA) that needs counsel, not engineering, before anything ships.

What keeps it alive:
- Both reports, independently, converge on the same gap: nobody has shipped a signed, sandboxed, cross-user-verified recipe registry. Unbrowse's reliability scoring is the closest thing that exists, and it's a usage-based heuristic, not a security/trust system.
- The legal architecture we already converged on independently (local execution, user's own device, user's own credentials) is the one the Ninth Circuit favored in *Amazon v. Perplexity* (Aug. 2026) — both reports found this case and read it the same way. That's real tailwind for the local-first design, even though the compiler built on top of it is commoditized.
- Demand-side validation is real and immediate: Instinct raised a large round and users are actively trying to get agents to do this (badly enough to get banned). The appetite exists; the differentiator has to be trustworthiness, not novelty.

**The condition for "go": don't build a compiler. Build the verification/trust layer, and make it interoperate with or sit in front of the compilers that already exist rather than racing them.** If that's not an interesting problem to you, this is a no-go — the horizontal "any site becomes an API" product by itself is not defensible.

---

## 3. What to build instead — the actual wedge

Two changes from the original framing, both forced by the research:

**3a. Change the launch vertical away from restaurant reservations.**
Every other candidate use case discussed in this conversation (Google Sheets edits, generic small-business booking) is cleaner than reservations specifically, because reservations are the one category that's actively being legislated against *right now*, has documented account-ban enforcement, and just got an official competing channel from the platforms themselves. Recommended replacement: **long-tail small-business booking/scheduling tools** — salons, gyms, dentists, auto shops, tutors — running on generic SaaS widgets (Setmore, Vagaro, Square Appointments, Booker, Mindbody-adjacent tools) rather than a big, defended platform. This is deliberately *not* Kampala's turf either (Kampala's examples are enterprise legacy dashboards — insurance payers, dental back-office) — the wedge here is consumer-initiated personal-life bookings on small-vendor tools, which have no anti-piracy legislation, materially less bot-defense budget, and no official-agent-channel competitor yet. This is a recommendation, not a settled decision — worth a quick sanity pass on 3-5 real target sites before committing.

**3b. Build the trust/verification layer as the product identity, not a feature.**
Concretely: Vantyx doesn't try to out-build Unbrowse/Klura/Kampala's discovery engines. It defines a narrow, declarative, non-Turing-complete recipe schema (no free-text/code fields — both reports independently flagged that free-text/code fields are exactly what OpenClaw's ClawHub poisoning campaign exploited), a signed/provenance-tracked registry, and a sandboxed dry-run gate before any recipe is trusted cross-user. If a compatible recipe format from Unbrowse or Klura can be ingested/re-verified rather than reinvented, that's a faster path than building a fourth discovery engine from scratch — worth a spike early rather than assuming we must write our own compiler.

---

## 4. V1 architecture (locking in this conversation's decisions + research corrections)

| Decision | What we're doing | Why |
|---|---|---|
| Execution locality | **Local-first.** Recipes execute on the end user's own device, their own session/browser, their own credentials. | Legally favored post-*Amazon v. Perplexity*; avoids the IP/fingerprint aggregation problem entirely. |
| Distribution | **Hosted MCP as the orchestrator/brain** (recipe matching, registry access) + **local companion** for anything credentialed. | Matches what we designed; MCP's 2026-07-28 spec is now stateless, so the hosted side is cheap to run (per CoWork, can live on edge/serverless — Unbrowse's backend is literally a Cloudflare Worker, validating this is viable). |
| Recipe format | **Declarative, non-Turing-complete schema.** No code fields, no free-text fields an LLM ever reads as instructions. | Both reports independently identify free-text/code fields as the exact attack surface that got OpenClaw's marketplace poisoned. |
| Recipe trust | **Sandboxed dry-run (synthetic fixtures, egress allowlisted to declared origins) + capability-manifest diffing + tiered trust (unverified → replay-verified → N-independent-clients-succeeded → human-reviewed for elevated capabilities).** | This is the actual product/moat per §2 above. |
| Credential handling | **Never centralized.** Companion holds session/credentials locally; hosted MCP never sees or transits them. | MCP spec itself now bans token passthrough (confused-deputy protection) — this is a spec requirement, not just our preference. |
| CAPTCHA / 2FA / payment challenges | **Typed human-handoff states**, resumed on the user's own already-authenticated session. **No built-in CAPTCHA-solving, ever.** | *Ticketmaster v. RMG* treats CAPTCHA-solving as DMCA §1201 trafficking liability — both reports flag this independently. Some gates (SCA/3-D Secure, passkeys) are structurally human and can't be automated regardless. |
| Bot-defense stance | **Don't try to win the fingerprint arms race.** Prefer replaying first-party API calls from the user's own real session over browser stealth; browser automation is last-resort fallback, paced far below documented ban thresholds (Resy's trigger was ~200 req/hr — stay orders of magnitude under that). | Both reports' benchmarks show JS-level stealth patches are losing to protocol-level (CDP) fingerprinting; Chrome 136+ also blocks remote-debugging on a user's default profile, closing off the "piggyback on the user's real logged-in Chrome via CDP" shortcut specifically. |
| Money movement | **Out of scope for V1, full stop.** No payment flows until counsel confirms the money-transmitter/FinCEN/NACHA question. | Licensing wall, not an engineering problem. |
| Launch vertical | **Small-business scheduling/booking (see §3a), not restaurant reservations.** | Reservations are actively being legislated against and just got an official competing channel. |

---

## 5. V1 build sequence

1. **Recipe schema + interpreter.** Define the declarative format (request/DOM-path templates, typed params, pre/postconditions, capability manifest, human-handoff states) and a reference interpreter. This is the thing that has to be safe-by-construction — get it reviewed before building anything on top of it.
2. **Local companion (single-user, no sharing yet).** Holds credentials, executes recipes, handles human handoff for interruptions. Prove the core loop end-to-end on 3-5 real target sites in the chosen vertical before anything else.
3. **Discovery, manual-assisted first.** Don't build an autonomous discovery/LIFT engine yet — that's the commoditized part. Hand-author the first 10-20 recipes for real target sites to validate the schema is expressive enough, and to have something real to show.
4. **Hosted MCP orchestrator (stateless).** Recipe matching/lookup, no credentials ever pass through it. Deploy on edge/serverless per the 2026-07-28 spec's stateless design — this is cheap and doesn't need home-hosting infrastructure.
5. **Sandbox + signing pipeline** for promoting a recipe from "works on my machine" to "trusted for other users." This is the part that has to exist *before* opening submissions to anyone else — do not repeat ClawHub's mistake of launching the marketplace before the vetting gate.
6. **Open recipe contribution, gated by the sandbox.** Only at this point does the crowd-sourced network effect start.
7. **Revisit the vertical/vertical expansion, and revisit whether to interoperate with Unbrowse/Klura's formats instead of only our own**, once the trust layer is proven on the first vertical.

---

## 6. Open items before/while building

- **Legal counsel, before V1 ships anything beyond a personal prototype:** the cease-and-desist → CFAA question (*Power Ventures* line of cases) that *Amazon v. Perplexity* left open; any future payment flow; confirm the chosen vertical's sites don't have their own version of a reservation-anti-piracy-style statute.
- **Pick and sanity-check the actual launch vertical** — 3-5 concrete real small-business booking sites, checked for bot-defense posture and ToS language, before committing engineering time.
- **Decide build-vs-interoperate on discovery**: spike whether Unbrowse's or Klura's recipe/skill format can be ingested and re-verified through our sandbox, versus writing a fourth capture-and-compile engine from scratch.
- **Revisit AGPL exposure**: several candidate fallback tools (nodriver, Skyvern, Integuru's core) are AGPL — fine for local client code the user runs, a real constraint if any of it ends up inside a hosted service.
- **Test willingness to pay for verified recipes** among the people who'd actually integrate against the registry (agent-host builders, not end consumers) — both reports flag this as unresolved and it's the actual bet the whole "go" decision rests on.
