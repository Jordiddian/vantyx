#!/usr/bin/env python3
"""Validate and execute a site-recipe recipe. See ../SKILL.md for the workflow this belongs to."""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

try:
    import jsonschema
except ImportError:
    sys.exit("Missing dependency: pip install jsonschema")

try:
    import requests
except ImportError:
    requests = None  # only required for kind == "api"

SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "recipe.schema.json"
STATE_DIR = Path.home() / ".site-recipe" / "state"
TEMPLATE_RE = re.compile(r"\{\{(\w+)\}\}")


class RecipeError(Exception):
    pass


def load_schema():
    return json.loads(SCHEMA_PATH.read_text())


def load_recipe(path: Path) -> dict:
    recipe = json.loads(path.read_text())
    jsonschema.validate(instance=recipe, schema=load_schema())
    if recipe["kind"] == "api" and "request" not in recipe:
        raise RecipeError("kind=api recipe is missing 'request'")
    if recipe["kind"] == "dom" and "steps" not in recipe:
        raise RecipeError("kind=dom recipe is missing 'steps'")
    return recipe


def origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def assert_allowed_origin(url: str, allowed_origins: list[str]):
    if origin_of(url) not in allowed_origins:
        raise RecipeError(
            f"Refusing to touch {url!r}: origin not in capability_manifest.allowed_origins {allowed_origins}"
        )


def _resolve_one_credential(ref_name: str) -> str:
    env_name = "SITE_RECIPE_CRED_" + ref_name.upper()
    value = os.environ.get(env_name)
    if value is None:
        raise RecipeError(
            f"Recipe needs credential '{ref_name}'. "
            f"Set it locally first: export {env_name}=<value from your own logged-in session>"
        )
    return value


def resolve_credentials(credential_ref) -> dict:
    """String form -> {"credential": <value>}. Object form ({placeholder: ref_name})
    resolves each entry independently, so a request needing two distinct secrets
    (e.g. a session cookie AND a separate CSRF token) doesn't collapse them into one."""
    if not credential_ref:
        return {}
    if isinstance(credential_ref, str):
        return {"credential": _resolve_one_credential(credential_ref)}
    return {placeholder: _resolve_one_credential(ref_name) for placeholder, ref_name in credential_ref.items()}


def validate_param_values(recipe: dict, params: dict):
    for p in recipe["params"]:
        name = p["name"]
        if name not in params:
            continue  # already checked required-ness elsewhere; optional+absent is fine
        value = params[name]
        if p["type"] == "enum":
            allowed = p.get("enum_values", [])
            if allowed and value not in allowed:
                raise RecipeError(f"Param '{name}' must be one of {allowed}, got {value!r}")
        elif p["type"] == "number":
            try:
                float(value)
            except (TypeError, ValueError):
                raise RecipeError(f"Param '{name}' must be a number, got {value!r}")
        elif p["type"] == "boolean":
            if str(value).lower() not in ("true", "false"):
                raise RecipeError(f"Param '{name}' must be true/false, got {value!r}")


def substitute(template: str, ctx: dict) -> str:
    def repl(m):
        key = m.group(1)
        if key not in ctx:
            raise RecipeError(f"Template references undeclared value '{{{{{key}}}}}'")
        return str(ctx[key])

    return TEMPLATE_RE.sub(repl, template)


class RateLimiter:
    """Simple sliding-window limiter, persisted per recipe so limits hold across separate runs.
    Keyed on name+origin, not name alone -- the schema only requires `name` to match a
    slug pattern, not to be globally unique, so two unrelated recipes named e.g.
    "availability-check" from different discovery sessions would otherwise share a
    rate-limit budget."""

    def __init__(self, recipe_name: str, origin: str, max_calls: int, per_seconds: int):
        key = re.sub(r"[^a-z0-9]+", "-", f"{recipe_name}-{origin}".lower()).strip("-")
        self.path = STATE_DIR / f"{key}.ratelimit.json"
        self.max_calls = max_calls
        self.per_seconds = per_seconds

    def check_and_record(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        history = []
        if self.path.exists():
            history = json.loads(self.path.read_text())
        history = [t for t in history if now - t < self.per_seconds]
        if len(history) >= self.max_calls:
            wait = self.per_seconds - (now - history[0])
            raise RecipeError(
                f"Rate limit hit ({self.max_calls}/{self.per_seconds}s). "
                f"Wait ~{wait:.0f}s before trying again. This limit is intentional; do not raise it to work around it."
            )
        history.append(now)
        self.path.write_text(json.dumps(history))


def check_condition(cond: dict, ctx: dict) -> bool:
    field, op, expected = cond["field"], cond["op"], cond["value"]
    actual = ctx.get(field)
    if op == "exists":
        return actual is not None
    if actual is None:
        return False
    if op == "eq":
        return actual == expected
    if op == "neq":
        return actual != expected
    if op == "gt":
        return actual > expected
    if op == "lt":
        return actual < expected
    if op == "contains":
        try:
            return expected in actual
        except TypeError:
            return False  # e.g. actual is an int/bool -- "contains" just doesn't apply, not a crash
    raise RecipeError(f"Unknown condition op {op!r}")


def run_api(recipe: dict, ctx: dict) -> dict:
    if requests is None:
        raise RecipeError("kind=api needs: pip install requests")
    req = recipe["request"]
    allowed = recipe["capability_manifest"]["allowed_origins"]

    url = substitute(req["url_template"], ctx)
    assert_allowed_origin(url, allowed)
    headers = {k: substitute(v, ctx) for k, v in req.get("headers", {}).items()}
    body = req.get("body_template")
    if isinstance(body, dict):
        body = json.loads(substitute(json.dumps(body), ctx))

    timeout = recipe["capability_manifest"]["timeout_seconds"]
    resp = requests.request(req["method"], url, headers=headers, json=body, timeout=timeout)

    result = {"status": resp.status_code}
    try:
        result["_json"] = resp.json()
    except ValueError:
        result["_json"] = None

    for field in recipe.get("extract", []):
        if field["from"] == "status":
            result[field["name"]] = resp.status_code
        elif field["from"] == "header":
            result[field["name"]] = resp.headers.get(field["path"])
        elif field["from"] == "json":
            node = result["_json"]
            for part in field["path"].split("."):
                node = None if node is None else node.get(part) if isinstance(node, dict) else None
            result[field["name"]] = node
    return result


def run_dom(recipe: dict, ctx: dict) -> dict:
    try:
        from stealth_fetch import run_steps  # local import: optional heavy dependency
    except ImportError:
        raise RecipeError(
            "kind=dom needs the Patchright-based helper: pip install patchright && patchright install chromium"
        )
    allowed = recipe["capability_manifest"]["allowed_origins"]
    timeout = recipe["capability_manifest"]["timeout_seconds"]
    return run_steps(recipe["steps"], ctx, allowed, timeout, recipe.get("human_handoff", []))


def run(recipe_path: Path, params: dict):
    recipe = load_recipe(recipe_path)

    for p in recipe["params"]:
        if p["required"] and p["name"] not in params:
            raise RecipeError(f"Missing required param: {p['name']}")
    validate_param_values(recipe, params)

    ctx = dict(params)
    ctx.update(resolve_credentials(recipe.get("credential_ref")))

    for cond in recipe.get("preconditions", []):
        if not check_condition(cond, ctx):
            raise RecipeError(f"Precondition failed: {cond}")

    limiter = RateLimiter(
        recipe["name"],
        recipe["target"]["origin"],
        recipe["capability_manifest"]["rate_limit"]["max_calls"],
        recipe["capability_manifest"]["rate_limit"]["per_seconds"],
    )
    limiter.check_and_record()

    try:
        result = run_api(recipe, ctx) if recipe["kind"] == "api" else run_dom(recipe, ctx)
    except RecipeError:
        _record_outcome(recipe_path, recipe, success=False)
        raise
    except Exception as e:
        # A network error, a Playwright crash, a timeout -- anything unexpected -- is
        # still a failure the staleness tracker needs to see, not just a postcondition
        # mismatch. Without this, the "3 failures -> needs_review" self-healing signal
        # in SKILL.md silently never fires for the most common real-world failure mode.
        _record_outcome(recipe_path, recipe, success=False)
        raise RecipeError(f"Execution failed ({type(e).__name__}): {e}") from e

    for cond in recipe.get("postconditions", []):
        if not check_condition(cond, {**ctx, **result}):
            _record_outcome(recipe_path, recipe, success=False)
            raise RecipeError(f"Postcondition failed, recipe may be stale: {cond}")

    _record_outcome(recipe_path, recipe, success=True)
    return result


def _record_outcome(recipe_path: Path, recipe: dict, success: bool):
    meta = recipe.setdefault("metadata", {})
    if success:
        meta["last_success_at"] = datetime.now(timezone.utc).isoformat()
        meta["recent_failures"] = 0
        meta["status"] = "active"
    else:
        meta["recent_failures"] = meta.get("recent_failures", 0) + 1
        if meta["recent_failures"] >= 3:
            meta["status"] = "needs_review"
    recipe_path.write_text(json.dumps(recipe, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("recipe", type=Path)
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--param", action="append", default=[], help="key=value, repeatable")
    args = ap.parse_args()

    if args.validate_only:
        try:
            load_recipe(args.recipe)
        except jsonschema.exceptions.ValidationError as e:
            sys.exit(f"Invalid recipe: {e.message} (at {'/'.join(str(p) for p in e.path) or '<root>'})")
        except RecipeError as e:
            sys.exit(f"Invalid recipe: {e}")
        print(f"OK: {args.recipe} is a valid recipe.")
        return

    params = {}
    for kv in args.param:
        if "=" not in kv:
            sys.exit(f"--param must be key=value, got {kv!r}")
        k, v = kv.split("=", 1)
        params[k] = v

    try:
        result = run(args.recipe, params)
    except RecipeError as e:
        sys.exit(f"Refused / failed: {e}")
    except jsonschema.exceptions.ValidationError as e:
        sys.exit(f"Invalid recipe: {e.message} (at {'/'.join(str(p) for p in e.path) or '<root>'})")

    print(json.dumps({k: v for k, v in result.items() if not k.startswith("_")}, indent=2))


if __name__ == "__main__":
    main()
