"""DOM-fallback browser helper for vantyx, built on Patchright.

Only used when a recipe's `kind` is "dom" (no clean API call could be found during
discovery). This drives a real, non-headless Chromium profile.

Honest limits, read before relying on this:
- This is best-effort. It removes some automation tells (avoids Runtime.enable,
  disables the console-API leak) but it does NOT defeat network-level fingerprinting
  (TLS/JA4, IP reputation) or behavioral analysis. It is not a guarantee against bot
  detection, and it is not a substitute for staying under a site's own rate limits.
- It must never be pointed at a CAPTCHA or a payment-challenge step. Those are
  handled exclusively through the human_handoff pause below -- the human completes
  them in the same visible window, and this code just waits and re-checks state.
- It uses a dedicated persistent profile directory (~/.vantyx/browser-profile),
  not your everyday Chrome profile -- recent Chrome versions block remote-debugging
  access to the default profile, and mixing automation into your daily browsing
  profile is a bad idea regardless.
"""
import time
from pathlib import Path
from urllib.parse import urlsplit

PROFILE_DIR = Path.home() / ".vantyx" / "browser-profile"


class DomError(Exception):
    pass


def _origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def run_steps(steps, ctx, allowed_origins, timeout_default_seconds, human_handoff):
    try:
        from patchright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            raise DomError("pip install patchright (preferred) or playwright, then run its `install chromium`")

    extracted = {}
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(PROFILE_DIR), headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            for step in steps:
                _run_step(page, step, ctx, extracted, allowed_origins, timeout_default_seconds, human_handoff, PWTimeout)
                # Enforce allowed_origins after EVERY step, not just navigate --
                # a click can trigger navigation just as easily (e.g. a "Book" button
                # hopping to a payment processor), and the schema's own claim that
                # "the interpreter enforces this; it is not advisory" has to hold for
                # wherever the page actually ends up, not just where we told it to go.
                if _origin_of(page.url) not in allowed_origins:
                    raise DomError(f"Page navigated to {page.url!r}, outside allowed_origins {allowed_origins} -- stopping.")
        finally:
            context.close()

    return extracted


def _run_step(page, step, ctx, extracted, allowed_origins, timeout_default_seconds, human_handoff, PWTimeout):
    action = step["action"]
    timeout_ms = step.get("timeout_seconds", timeout_default_seconds) * 1000
    target = page.frame_locator(step["target_frame"]) if step.get("target_frame") else page
    locator = None
    if step.get("target_role"):
        locator = target.get_by_role(step["target_role"], name=step.get("target_name"))

    try:
        if action == "navigate":
            url = ctx[step["url_param"]]
            if _origin_of(url) not in allowed_origins:
                raise DomError(f"Refusing to navigate to {url!r}: origin not in allowed_origins")
            page.goto(url, timeout=timeout_ms)
        elif action == "click":
            locator.click(timeout=timeout_ms)
        elif action == "fill":
            locator.fill(str(ctx[step["value_param"]]), timeout=timeout_ms)
        elif action == "select":
            locator.select_option(str(ctx[step["value_param"]]), timeout=timeout_ms)
        elif action == "wait_for":
            locator.wait_for(timeout=timeout_ms)
        elif action == "extract_text":
            extracted[step["extract_as"]] = locator.inner_text(timeout=timeout_ms)
        elif action == "extract_attr":
            extracted[step["extract_as"]] = locator.get_attribute(step["attr_name"], timeout=timeout_ms)
        else:
            raise DomError(f"Unknown step action: {action!r}")
    except PWTimeout:
        if not _try_human_handoff(page, human_handoff):
            raise DomError(
                f"Step {action!r} timed out and no human_handoff resolved it. "
                "Recipe may be stale, or the site changed its flow."
            )


def _try_human_handoff(page, human_handoff) -> bool:
    """A step timing out doesn't tell us WHICH declared interruption actually
    happened (a CAPTCHA and an OTP prompt both just look like "the expected
    element never showed up"). Rather than guess by always showing entry[0]'s
    prompt (which would tell the user "enter your OTP" while they're actually
    staring at a CAPTCHA), show all of them and accept whichever resume_condition
    is satisfied first."""
    if not human_handoff:
        return False
    print("\n[vantyx] Needs you -- one of these is probably what's on screen:")
    for entry in human_handoff:
        print(f"  - {entry['prompt']}")
    print("Finish whichever applies in the browser window that's open, then press Enter here...")
    input()
    max_timeout = max(e.get("timeout_seconds", 300) for e in human_handoff)
    deadline = time.time() + max_timeout
    while time.time() < deadline:
        state = {"url": page.url, "text": page.inner_text("body")}
        for entry in human_handoff:
            cond = entry["resume_condition"]
            actual = state.get(cond["field"])
            if actual is not None and _matches(actual, cond["op"], cond["value"]):
                return True
        time.sleep(1)
    return False


def _matches(actual, op, expected) -> bool:
    if op == "eq":
        return actual == expected
    if op == "neq":
        return actual != expected
    if op == "contains":
        return expected in actual
    if op == "exists":
        return True
    return False
