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

### 3. Discover
Perform the action **once**, using whatever browser tooling is available in this session, while paying attention to:
- **Network calls** (the site's own XHR/fetch/GraphQL requests) — this is the preferred discovery outcome. If the site's frontend calls a clean, parameterizable backend endpoint to do the thing, that's what the recipe should replay directly (`kind: "api"` in the schema) — faster, more deterministic, and it never touches the DOM again.
- **DOM steps**, only if no clean request exists (heavily obfuscated/signed payloads, or a genuinely UI-only flow). Record the minimal ordered sequence of typed actions (`kind: "dom"`) — navigate, click, fill, select, wait_for, extract — using accessible names/roles/stable selectors, never pixel coordinates.
- **Any interruption** (login, CAPTCHA, OTP, WebAuthn/passkey, payment challenge) — record it as a named `human_handoff` state in the recipe (see schema), not as something to script through.

### 4. Compile the recipe
Write a `<name>.recipe.json` conforming to `schema/recipe.schema.json`. Keep it strictly declarative — no code fields, no free-text fields that a future agent run would read back as instructions. If the schema can't express something the task needs, that's a signal to simplify the task, not to add an escape hatch to the schema.

Validate it before saving:
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
- `interpreter/run_recipe.py` — validates and executes a recipe.
- `interpreter/stealth_fetch.py` — the DOM-fallback browser helper (Patchright-based). Optional dependency; only needed for `kind: "dom"` recipes.
- `docs/LEGAL-NOTES.md` — the reasoning behind the hard rules above. Not legal advice; read it, don't cite it as legal advice to anyone.
- `examples/example.recipe.json` — a minimal, low-stakes example (checking a public status page) showing the shape, not a real target site.
