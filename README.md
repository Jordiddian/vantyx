# vantyx

A Claude Code skill: turn a repeated action on a website that has no public API into a
small, declarative, reusable "recipe" — discovered once, replayed directly afterward —
instead of re-doing screenshot-driven browser automation every time.

**Start here:** [`skills/vantyx/SKILL.md`](skills/vantyx/SKILL.md)

## What this is, and isn't

This is a **personal, single-user, local-execution tool**. There is no hosted server, no
shared recipe registry, no credential storage beyond what your own browser/environment
already holds, and no anti-bot bypass service. Those were all considered and deliberately
scoped out for now — see [`build-plan.md`](build-plan.md) for why, and
[`research-brief.md`](research-brief.md) for the legal/technical research behind that
decision.

## Layout

```
skills/vantyx/
  SKILL.md                       -- the workflow Claude follows
  schema/recipe.schema.json      -- the declarative recipe format (no code fields)
  interpreter/discover.py        -- captures a site's real network calls (Playwright/Patchright)
  interpreter/capture_to_recipe.py -- diffs 2+ captures, drafts a recipe automatically
  interpreter/run_recipe.py      -- validates + executes a recipe
  interpreter/stealth_fetch.py   -- optional DOM-fallback browser helper (Patchright)
  docs/LEGAL-NOTES.md            -- why the hard rules in SKILL.md exist
  examples/example.recipe.json   -- placeholder showing the shape
```

## Setup

```bash
pip install -r skills/vantyx/requirements.txt
pip install playwright && playwright install chromium   # needed for discover.py
# Optional, only if a recipe needs the DOM fallback at replay time:
pip install patchright && patchright install chromium
```

## The discover -> compile loop (verified working, 2026-09-26)

Run the same flow twice with two different concrete inputs, then compile:
```bash
python skills/vantyx/interpreter/discover.py https://example.com/start --out run1.json
# perform the action once, e.g. with input "cat"
python skills/vantyx/interpreter/discover.py https://example.com/start --out run2.json
# perform the same action again with input "dog"
python skills/vantyx/interpreter/capture_to_recipe.py --captures run1.json run2.json
# shows a ranked shortlist of which captured request is probably "the action"
python skills/vantyx/interpreter/capture_to_recipe.py --captures run1.json run2.json --pick 0 --out my-recipe.json
# writes a schema-valid draft: "cat"/"dog" becomes {{a_param}}, constants stay literal,
# anything credential-shaped becomes credential_ref. Status is always "needs_review" --
# fill in `extract` (which response fields you care about), then validate and run.
```
This was built and tested end-to-end in this repo's history: capture against a real live
endpoint, secret redaction (headers *and* response body) confirmed to leave no leak on
disk, diff-based parameterization confirmed correct, and the compiled draft confirmed to
run successfully against a brand-new input value it never saw during discovery.

## Hard rules (see SKILL.md and LEGAL-NOTES.md for the reasoning)

- Own account only. Never someone else's data or login.
- Never solve or bypass a CAPTCHA.
- Never automate a payment or money-movement step.
- Stop immediately on any ban / cease-and-desist from a site — don't try to route around it.
- Rate-limit hard, with jitter. Recipes carry their own limits; don't loosen them to "make it work."
- Credentials never live in a recipe file.

This is a personal tool for automating your own accounts, not legal advice, not a
guarantee against bot detection, and not something to point at a second person's
credentials without redoing the legal homework in `research-brief.md` first.
