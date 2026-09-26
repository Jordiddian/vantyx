---
name: site-recipe
description: Turn a repeated action on a website with no public API into a small, declarative, reusable "recipe" instead of re-doing screenshot-driven browser automation every time. Use when asked to automate checking, filling, or extracting something on a site that has no API, especially when the same action will be repeated later and speed/determinism matters more than one-off flexibility. Do NOT use for one-off tasks, for anything involving another person's account, payment/money movement, or any site that requires solving a CAPTCHA, 2FA, or a payment challenge to complete the action.
---

# site-recipe

Discover how a site's own frontend actually talks to its backend (or, failing that, exactly which UI steps complete the task), compile that into a small typed "recipe" file, and replay the recipe directly on future runs instead of driving a browser and reading screenshots every time.

This skill is scoped deliberately small: single user, local execution only, no shared registry, no hosted service, no credential storage beyond what the user's own browser/environment already holds. It exists to make *this session's* repeated automation faster and more inspectable — not to be a platform.

## Hard rules — read before doing anything

These come directly from legal/technical research on this category of tool (see `docs/LEGAL-NOTES.md` for the reasoning). They are not optional and not something to reason your way around for a specific site:

1. **Only automate the user's own account, doing something the user could do themselves.** Never a flow that touches someone else's account or data.
2. **Never solve, bypass, or work around a CAPTCHA.** If one appears, stop and hand control back to the user in their own browser (see "Human handoff" below). Treat this as a hard stop, not an obstacle to route around.
3. **Never automate a payment, transfer, or any money-movement step.** If completing the task requires submitting a payment, stop before that step and let the user complete it manually.
4. **Never continue against a site that has told the user (or the account) it doesn't want automated access** — an explicit ban, suspension notice, or cease-and-desist means stop, not "try harder to look human."
5. **Rate-limit aggressively.** Default to at most a few requests per minute against any one site, with jitter. Documented account bans in this space (e.g., reservation platforms) started at roughly 200 requests/hour — stay far below anything like that.
6. **Never write credentials, session tokens, or cookies into a recipe file.** Recipes describe *shape* (what to request, what to click), never secrets. Secrets are resolved locally, at run time, from the user's own already-authenticated browser session or environment — never persisted alongside the recipe.
7. **If the user hasn't said explicitly that this is their own account/action, ask before doing discovery.**

If a requested task conflicts with any of these, say so plainly and stop — don't quietly work around the rule.

## Procedure

### 1. Confirm scope
Before touching a site, confirm in one line: whose account this is, what the single action is, and that none of the hard rules above are triggered (payment step, CAPTCHA-gated flow, someone else's data). If anything is unclear, ask.

### 2. Check for an existing recipe
Look in the working directory (or wherever the user keeps them) for a `*.recipe.json` file whose `target.origin` and `target.path_pattern` (see `schema/recipe.schema.json`) match the site and action. If one exists and hasn't failed its last few runs, skip to step 5 (Execute).

### 3. Discover — use `discover.py`, don't hand-transcribe network traffic
Don't manually read screenshots/network tabs and type out a recipe from memory. Use the capture tool, and **run the same flow twice with two different concrete inputs** (two different dates, search terms, ids — whatever the action's real parameter is). Diffing two real examples is what reliably tells you which parts of a request are the fixed template and which parts vary; guessing that from a single capture is unreliable and is exactly the kind of hand-authoring this tool exists to avoid.

```
python skills/site-recipe/interpreter/discover.py https://example.com/start --out run1.json
# ... perform the action once in the browser window that opens, e.g. with input "cat" ...
python skills/site-recipe/interpreter/discover.py https://example.com/start --out run2.json
# ... perform the same action again with a different input, e.g. "dog" ...
```
This captures the site's own XHR/fetch calls (filtered clear of analytics/tracking noise), with anything credential-shaped redacted before it ever touches disk — both in headers and in the response body, in case the site echoes a token back.

If no clean request exists at all (heavily obfuscated/signed payloads, or a genuinely UI-only flow), fall back to recording the minimal ordered sequence of typed DOM actions by hand (`kind: "dom"` in the schema) — navigate, click, fill, select, wait_for, extract — using accessible names/roles, never pixel coordinates.

Either way, note **any interruption** (login, CAPTCHA, OTP, WebAuthn/passkey, payment challenge) as a named `human_handoff` state in the recipe — never as something to script through.

### 4. Compile the recipe — use `capture_to_recipe.py`, don't write JSON from scratch
```
python skills/site-recipe/interpreter/capture_to_recipe.py --captures run1.json run2.json
# prints a ranked shortlist of which captured request is probably "the action"
python skills/site-recipe/interpreter/capture_to_recipe.py --captures run1.json run2.json --pick 0 --name my-recipe --out my-recipe.json
```
Real sites are noisy (a single page load easily fires 40-50 xhr/fetch calls once you count analytics/ads/trackers). Use `--captures ... ` alone first to see a ranked shortlist, or if you already know a URL fragment that identifies the right call (e.g. `"calendar/range"`, `"/search"`), use `--pick-url-contains <substring>` instead of `--pick <index>` — it matches independently in each capture file, so it doesn't break when different runs happen to pick up different numbers of third-party beacons. When a URL fragment matches more than once in a capture (a page-load default call plus one from the actual interaction), the *last* match is used, since that's the one that reflects what you actually did, not what loaded by default.
This diffs the two captures and drafts a `schema/recipe.schema.json`-valid recipe automatically: the field that changed between "cat" and "dog" becomes `{{a_param}}`, everything constant stays literal, and anything credential-shaped becomes a `credential_ref`. **The draft always comes out `needs_review` with `extract` left empty on purpose** — deciding which response fields actually matter still takes a human or Claude looking at the real response once. That's the one part of this that's still worth your judgment; everything before it shouldn't be.

If a task can't produce a clean two-example diff (steps look identical because the varying part didn't show up in the network layer, or the request shapes genuinely differ across runs), write the recipe by hand instead. Keep it strictly declarative either way — no code fields, no free-text fields a future agent run would read back as instructions.

Validate before trusting it:
```
python skills/site-recipe/interpreter/run_recipe.py --validate-only path/to/thing.recipe.json
```

### 5. Execute
```
python skills/site-recipe/interpreter/run_recipe.py path/to/thing.recipe.json --param key=value ...
```
The interpreter (see `interpreter/run_recipe.py`):
- Refuses to run if the recipe references an origin outside its own declared `capability_manifest.allowed_origins`.
- Applies the recipe's rate limit itself (don't rely on the caller to remember).
- For `kind: "api"` recipes, resolves credentials from the environment/local browser session at call time — never from the recipe file.
- For `kind: "dom"` recipes, falls back to a real (non-headless) browser via the `stealth_fetch` helper, which is best-effort only (see its docstring) — it is not a guarantee against bot detection, and it must never be pointed at a CAPTCHA or payment step.
- On hitting a declared `human_handoff` state, pauses and tells the user what to do in their own browser window, then re-checks the recipe's postcondition before resuming — never guesses that the human finished.

### 6. Report and save
Tell the user what happened in plain terms (succeeded / needs the human for X / site rejected the request — recipe may be stale). If a recipe's success rate drops, mark it stale in its own metadata rather than silently continuing to trust it.

## Files in this skill

- `schema/recipe.schema.json` — the recipe format. Read this before writing a recipe by hand.
- `interpreter/discover.py` — captures a site's real network calls during one pass through a flow. Run it twice with different inputs; see step 3.
- `interpreter/capture_to_recipe.py` — diffs two (or more) captures and drafts a recipe automatically; see step 4.
- `interpreter/run_recipe.py` — validates and executes a recipe.
- `interpreter/stealth_fetch.py` — the DOM-fallback browser helper (Patchright-based). Optional dependency; only needed for `kind: "dom"` recipes.
- `docs/LEGAL-NOTES.md` — the reasoning behind the hard rules above. Not legal advice; read it, don't cite it as legal advice to anyone.
- `examples/example.recipe.json` — a minimal, low-stakes example (checking a public status page) showing the shape, not a real target site.
