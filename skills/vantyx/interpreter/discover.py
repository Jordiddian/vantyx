#!/usr/bin/env python3
"""Capture a site's real network calls during one pass through a flow, so a recipe
can be compiled from what actually happened instead of hand-written from scratch.

Typical use: run this twice for the same flow with two different concrete inputs
(two different dates/search terms/ids), then feed both capture files into
capture_to_recipe.py -- diffing two real examples is what turns a URL into a
template reliably. See ../SKILL.md.
"""
import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

PROFILE_DIR = Path.home() / ".vantyx" / "browser-profile"

SENSITIVE_HEADER_MARKERS = ("cookie", "authorization", "token", "secret", "key", "csrf")
NOISE_DOMAINS = (
    "google-analytics.com", "googletagmanager.com", "doubleclick.net",
    "facebook.net", "connect.facebook.net", "segment.io", "sentry.io",
    "hotjar.com", "fullstory.com", "intercom.io", "amplitude.com", "mixpanel.com",
    "cookielaw.org", "cloudflareinsights.com", "bat.bing.com",
    "google.com", "googleadservices.com", "analytics.google.com",
    "clarity.ms", "sharethis.com", "m.stripe.com", "bzr.openai.com", "bzrcdn.openai.com",
    "dfp.calendly.com",
)
# Path shapes that are almost always telemetry even on a first-party/API-looking
# domain -- real Calendly traffic taught us this: calendly.com itself fires an
# /api/booking/analytics/track call alongside the actual availability lookup.
NOISE_PATH_MARKERS = ("/collect", "/track", "/analytics", "/pixel", "/rmkt", "/beacon")


def redact_headers(headers: dict) -> dict:
    return {
        k: ("<redacted>" if any(m in k.lower() for m in SENSITIVE_HEADER_MARKERS) else v)
        for k, v in headers.items()
    }


def is_noise(url: str) -> bool:
    parts = urlsplit(url)
    if any(d in parts.netloc for d in NOISE_DOMAINS):
        return True
    return any(m in parts.path for m in NOISE_PATH_MARKERS)


def _safe_post_data(req):
    """req.post_data itself can raise (e.g. a gzip/binary/protobuf body that
    Playwright can't utf-8-decode) -- guard the property access, not just what
    we do with the result."""
    try:
        post_data = req.post_data
    except Exception:
        return "<unrepresentable binary body>"
    if not post_data:
        return None
    try:
        return json.loads(post_data)
    except (ValueError, TypeError):
        return post_data[:2000]


def _safe_response_body(response):
    try:
        return response.json()
    except Exception:
        return None


def _scrub(value, secret_values):
    """Best-effort: a site's own response can echo a credential value back (some
    APIs do this in confirmation/debug payloads). Redacting only the header field
    we sent isn't enough -- also blank out the literal secret value anywhere it
    shows up in what we're about to write to disk."""
    if not secret_values:
        return value
    if isinstance(value, str):
        for secret in secret_values:
            if secret in value:
                value = value.replace(secret, "<redacted>")
        return value
    if isinstance(value, dict):
        return {k: _scrub(v, secret_values) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v, secret_values) for v in value]
    return value


def capture(start_url, out_path, headless, auto_actions_path, settle_seconds, no_interactive):
    try:
        from patchright.sync_api import sync_playwright
    except ImportError:
        from playwright.sync_api import sync_playwright

    captured = []

    def on_response(response):
        req = response.request
        if req.resource_type not in ("xhr", "fetch"):
            return
        if is_noise(req.url):
            return
        try:
            raw_headers = req.headers
            secret_values = [
                v for k, v in raw_headers.items()
                if any(m in k.lower() for m in SENSITIVE_HEADER_MARKERS) and v
            ]
            captured.append({
                "method": req.method,
                "url": req.url,
                "resource_type": req.resource_type,
                "request_headers": redact_headers(raw_headers),
                "request_body": _scrub(_safe_post_data(req), secret_values),
                "status": response.status,
                "response_body": _scrub(_safe_response_body(response), secret_values),
                "t": time.time(),
            })
        except Exception as e:
            # A single malformed/binary request (gzip bodies, protobuf, a closed
            # page racing the response, etc.) must never take down the whole
            # capture session -- note it and keep going.
            print(f"[discover] warning: skipped one response ({req.url}): {e}")

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(PROFILE_DIR), headless=headless)
        context.on("response", on_response)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(start_url, timeout=30000)

        if auto_actions_path:
            _run_auto_actions(page, json.loads(Path(auto_actions_path).read_text()))
        elif not no_interactive:
            print(f"[discover] Browser open at {start_url}.")
            print("[discover] Perform the action now. Press Enter here when you're done...")
            input()

        page.wait_for_timeout(settle_seconds * 1000)
        context.close()

    Path(out_path).write_text(json.dumps(captured, indent=2))
    print(f"[discover] Captured {len(captured)} request(s) -> {out_path}")


def _run_auto_actions(page, actions):
    """Scripted steps, for unattended/repeatable capture (e.g. re-discovering a
    stale recipe the same way every time). Deliberately a bit more permissive than
    the replay-time recipe schema -- this never runs unattended against a live
    user's credentials the way a saved recipe would."""
    for step in actions:
        action = step["action"]
        locator = None
        if step.get("target_role"):
            locator = page.get_by_role(step["target_role"], name=step.get("target_name"))
        if action == "navigate":
            page.goto(step["url"], timeout=30000)
        elif action == "click":
            locator.click(timeout=10000)
        elif action == "fill":
            locator.fill(step["value"], timeout=10000)
        elif action == "press":
            locator.press(step["key"], timeout=10000)
        elif action == "wait":
            page.wait_for_timeout(step.get("ms", 1000))
        else:
            raise ValueError(f"Unknown auto action: {action!r}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("start_url")
    ap.add_argument("--out", default="capture.json")
    ap.add_argument("--headless", action="store_true", help="No visible window. Fine for scripted re-capture; prefer headed for first discovery of a protected site.")
    ap.add_argument("--auto-actions", help="JSON file of scripted steps, for unattended/repeatable capture")
    ap.add_argument("--no-interactive", action="store_true", help="Skip the 'press Enter when done' prompt (for when the page load itself is the whole action, or for automated testing)")
    ap.add_argument("--settle-seconds", type=int, default=2, help="Extra wait after the action for trailing async requests")
    args = ap.parse_args()
    capture(args.start_url, args.out, args.headless, args.auto_actions, args.settle_seconds, args.no_interactive)


if __name__ == "__main__":
    main()
