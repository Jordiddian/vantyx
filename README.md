# vantyx / site-recipe

A Claude Code skill: turn a repeated action on a website that has no public API into a
small, declarative, reusable "recipe" — discovered once, replayed directly afterward —
instead of re-doing screenshot-driven browser automation every time.

**Start here:** [`skills/site-recipe/SKILL.md`](skills/site-recipe/SKILL.md)

## What this is, and isn't

This is a **personal, single-user, local-execution tool**. There is no hosted server, no
shared recipe registry, no credential storage beyond what your own browser/environment
already holds, and no anti-bot bypass service. Those were all considered and deliberately
scoped out for now — see [`build-plan.md`](build-plan.md) for why, and
[`research-brief.md`](research-brief.md) for the legal/technical research behind that
decision.

## Layout

```
skills/site-recipe/
  SKILL.md                    -- the workflow Claude follows
  schema/recipe.schema.json   -- the declarative recipe format (no code fields)
  interpreter/run_recipe.py   -- validates + executes a recipe
  interpreter/stealth_fetch.py-- optional DOM-fallback browser helper (Patchright)
  docs/LEGAL-NOTES.md         -- why the hard rules in SKILL.md exist
  examples/example.recipe.json-- placeholder showing the shape
```

## Setup

```bash
pip install -r skills/site-recipe/requirements.txt
# Optional, only if a recipe needs the DOM fallback:
pip install patchright && patchright install chromium
```

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
