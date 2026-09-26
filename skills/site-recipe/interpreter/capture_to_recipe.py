#!/usr/bin/env python3
"""Compile one or more discover.py captures into a DRAFT recipe (schema/recipe.schema.json).

Give it captures from 2+ runs of the *same flow* with different concrete inputs
(two different search terms, two different dates) and it can tell which parts of
a request are constant (kept literal) vs which parts changed ({{params}}) far
more reliably than guessing from a single capture.

The output is always a draft: metadata.status is "needs_review", and `extract`
is left empty on purpose -- deciding which response fields you actually care
about needs a human (or Claude) to look at the real response once. This script
removes the tedious part (typing out request shape by hand); it doesn't remove
the judgment part.
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urlencode


def load_captures(paths):
    return [json.loads(Path(p).read_text()) for p in paths]


def rank_candidates(entries):
    """Heuristic only -- a first pass to shrink a real page's ~50 requests down to a
    short list a human/Claude can glance at, not a claim of knowing "the" answer.
    Real-world lesson (see git history): don't penalize GET -- read-only
    availability/lookup calls are very often GET, not POST; the earlier version of
    this scored real Calendly availability calls below Stripe/Clarity/GA beacons."""
    def score(e):
        s = 0
        if e.get("response_body") is not None:
            s += 2
        if e.get("request_body") is not None:
            s += 1
        path = urlsplit(e["url"]).path
        if any(seg in path for seg in ("/range", "/availability", "/available", "/slots", "/search", "/lookup")):
            s += 2
        return s

    return sorted(range(len(entries)), key=lambda i: score(entries[i]), reverse=True)


def find_by_url_substring(entries, substring):
    matches = [i for i, e in enumerate(entries) if substring in e["url"]]
    return matches


def _diff_scalar(values):
    """Same field's value across N examples: ('literal', v) if constant, else ('param', None)."""
    uniq = {json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v for v in values}
    return ("literal", values[0]) if len(uniq) <= 1 else ("param", None)


def diff_urls(urls):
    parts = [urlsplit(u) for u in urls]
    origin = f"{parts[0].scheme}://{parts[0].netloc}"

    path_segs = [p.path.split("/") for p in parts]
    detected = {}
    if len({len(s) for s in path_segs}) != 1:
        path_template = parts[0].path  # different shapes entirely; leave literal, flag for review
    else:
        out_segs = []
        for i, seg_values in enumerate(zip(*path_segs)):
            kind, lit = _diff_scalar(list(seg_values))
            if kind == "literal":
                out_segs.append(lit)
            else:
                name = f"path_param_{i}"
                out_segs.append("{{" + name + "}}")
                detected[name] = list(seg_values)
        path_template = "/".join(out_segs)

    query_dicts = [dict(parse_qsl(p.query)) for p in parts]
    all_keys = set().union(*query_dicts) if query_dicts else set()
    query_template = {}
    for key in sorted(all_keys):
        values = [q.get(key) for q in query_dicts]
        if any(v is None for v in values):
            query_template[key] = "{{query_" + key + "}}"
            detected["query_" + key] = values
            continue
        kind, lit = _diff_scalar(values)
        if kind == "literal":
            query_template[key] = lit
        else:
            name = "query_" + key
            query_template[key] = "{{" + name + "}}"
            detected[name] = values

    return origin, path_template, query_template, detected


def build_url_template(origin, path_template, query_template):
    if not query_template:
        return origin + path_template
    qs = urlencode(query_template, safe="{}")
    return f"{origin}{path_template}?{qs}"


def draft_recipe(name, picked):
    urls = [e["url"] for e in picked]
    origin, path_template, query_template, detected_params = diff_urls(urls)
    url_template = build_url_template(origin, path_template, query_template)

    params = [
        {"name": pname, "type": "string", "required": True, "description": "auto-detected -- rename and describe me"}
        for pname in detected_params
    ]

    # A real request can need more than one distinct secret (a session cookie AND a
    # separate CSRF token, say -- exactly what a real capture turned up). Collapsing
    # every redacted header into the same {{credential}} placeholder would silently
    # send the wrong value in at least one of them, with no error to catch it.
    redacted_headers = [k for k, v in picked[0]["request_headers"].items() if v == "<redacted>"]
    placeholder_of = {}
    if len(redacted_headers) == 1:
        placeholder_of[redacted_headers[0]] = "credential"
    else:
        for i, k in enumerate(redacted_headers, start=1):
            placeholder_of[k] = "credential" if i == 1 else f"credential_{i}"

    clean_headers = {}
    for k, v in picked[0]["request_headers"].items():
        if k in placeholder_of:
            clean_headers[k] = "{{" + placeholder_of[k] + "}}"
        elif k.lower() not in ("host", "content-length"):
            clean_headers[k] = v

    credential_ref = None
    if len(redacted_headers) == 1:
        credential_ref = redacted_headers[0].lower().replace("-", "_")
    elif len(redacted_headers) > 1:
        credential_ref = {
            placeholder_of[k]: k.lower().replace("-", "_") for k in redacted_headers
        }

    recipe = {
        "name": name,
        "version": "0.1.0",
        "description": "AUTO-GENERATED DRAFT from capture_to_recipe.py -- review before use.",
        "kind": "api",
        "target": {"origin": origin, "path_pattern": path_template},
        "capability_manifest": {
            "allowed_origins": [origin],
            "max_steps": 1,
            "timeout_seconds": 10,
            "rate_limit": {"max_calls": 6, "per_seconds": 60},
        },
        "params": params,
        "request": {
            "method": picked[0]["method"],
            "url_template": url_template,
            "headers": clean_headers,
        },
        "extract": [],
        # Default safety net: without this, a recipe with no extract/postconditions
        # would report "success" on a 404/500 exactly as happily as a 200 -- run_recipe.py's
        # "status" field is always populated even when extract is empty. Expand or replace
        # this once you know what a real success response actually looks like; don't delete
        # it without replacing it.
        "postconditions": [{"field": "status", "op": "eq", "value": 200}],
        "metadata": {"status": "needs_review", "recent_failures": 0},
    }
    if credential_ref:
        recipe["credential_ref"] = credential_ref
    return recipe


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--captures", nargs="+", required=True, help=">=1 capture.json files from discover.py; 2+ enables diffing")
    ap.add_argument("--pick", type=int, help="Index into the first capture's request list to compile (requires all captures to have identical entry counts/order). Omit to see a ranked shortlist first.")
    ap.add_argument("--pick-url-contains", help="Instead of a fixed index, pick the first request whose URL contains this substring, independently in each capture file. More robust when captures pick up different numbers of ads/analytics calls.")
    ap.add_argument("--name", default="draft-recipe")
    ap.add_argument("--out", default="draft.recipe.json")
    args = ap.parse_args()

    captures = load_captures(args.captures)

    if args.pick is None and args.pick_url_contains is None:
        ranked = rank_candidates(captures[0])
        print("Ranked candidates (most-likely-the-real-action first):")
        for rank, idx in enumerate(ranked[:15]):
            e = captures[0][idx]
            print(f"  [{idx}] {e['method']} {e['url']} -> {e['status']}")
        print("\nRe-run with --pick <index>, or --pick-url-contains <substring>, to compile that one.")
        return

    if args.pick_url_contains:
        picked = []
        for cap_path, entries in zip(args.captures, captures):
            matches = find_by_url_substring(entries, args.pick_url_contains)
            if not matches:
                sys.exit(f"No request in {cap_path} contains {args.pick_url_contains!r}")
            if len(matches) > 1:
                # Real-world lesson: a page-load default call (e.g. current month's
                # availability) often fires before the interaction we actually
                # care about; the LAST match is what the interaction produced, not
                # whatever loaded first.
                print(f"Note: {len(matches)} matches in {cap_path}, using the last (most likely reflects the actual interaction, not the page's default load)")
            picked.append(entries[matches[-1]])
    else:
        if len({len(c) for c in captures}) != 1:
            sys.exit("All capture files need the same number of entries in the same order "
                     "(run discover.py the same way, same number of steps, each time) "
                     "-- or use --pick-url-contains instead, which doesn't require that.")
        picked = [entries[args.pick] for entries in captures]

    recipe = draft_recipe(args.name, picked)
    Path(args.out).write_text(json.dumps(recipe, indent=2))
    print(f"Draft written to {args.out}. It is NOT ready to run yet:")
    print("  - metadata.status is 'needs_review'")
    print("  - `extract` is empty -- add the response fields you actually care about")
    print("  - confirm any {{credential}} header is really required, name credential_ref sensibly")
    print("  - rename the auto-detected param names to something meaningful")


if __name__ == "__main__":
    main()
