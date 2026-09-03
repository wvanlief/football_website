"""Local smoke check for the football_website frontend and API.

Verifies page routes, the shared frontend utility module, badge assets, core API
endpoints, and the feed/off-season invariants from AGENTS.md section 4.

Start the server first, then run against it:

    .venv\\Scripts\\python.exe -m uvicorn backend.main:app --port 8000
    .venv\\Scripts\\python.exe -m backend.scripts.smoke_check

Exits non-zero if any check fails, so it is usable as a CI or pre-push gate.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

# Routes that must render, keyed by the frontend page they serve.
PAGE_ROUTES = {
    "index": "/",
    "recommended": "/recommended",
    "bracket": "/bracket",
    "calendar": "/calendar",
    "group": "/group/A",
    "team": "/team/Arsenal",
}

# Canonical helpers that must live in shared.js and nowhere else.
SHARED_EXPORTS = [
    "COUNTRY_FLAGS",
    "getFlagUrl",
    "resolveTimezone",
    "getRatingClass",
    "getRatingText",
    "getRatingIcon",
    "showToast",
    "openMatchDetails",
]

# Per-page scripts that must consume shared.js rather than redefine its helpers.
PAGE_SCRIPTS = [
    "app.js",
    "group.js",
    "recommended.js",
    "bracket.js",
    "calendar.js",
    "team.js",
]

# Helpers whose duplication across page scripts caused live divergence bugs.
NO_REDEFINE = [
    "getFlagUrl",
    "resolveTimezone",
    "getRatingClass",
    "showToast",
    "openMatchDetails",
]

GEO_ENDPOINT_RE = re.compile(r"https?://[^\s'\"]*(?:ipapi|ip-api|ipinfo|geojs|geoip)[^\s'\"]*", re.I)


class Report:
    def __init__(self):
        self.failures = []
        self.notes = []

    def check(self, ok, label, detail=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {label}{f'  {detail}' if detail else ''}")
        if not ok:
            self.failures.append(label if not detail else f"{label} ({detail})")
        return ok

    def note(self, message):
        print(f"  NOTE  {message}")
        self.notes.append(message)

    def section(self, title):
        print()
        print("=" * 70)
        print(title)
        print("=" * 70)


def fetch(base, path):
    """Return (status, body). Status is None when the request never completed."""
    req = urllib.request.Request(base + path, headers={"User-Agent": "smoke-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:
        return None, str(exc)


def check_pages(base, report):
    report.section("1. PAGE ROUTES")
    html_by_page = {}
    for page, path in PAGE_ROUTES.items():
        status, body = fetch(base, path)
        ok = report.check(status == 200, f"{path:22} -> {status}", f"{len(body)} bytes")
        html_by_page[page] = body if ok else ""
    return html_by_page


def check_shared_module(base, html_by_page, report):
    report.section("2. SHARED FRONTEND MODULE")
    for page in PAGE_ROUTES:
        report.check("shared.js" in html_by_page.get(page, ""), f"{page:12} loads shared.js")

    status, shared = fetch(base, "/js/shared.js")
    if not report.check(status == 200, f"/js/shared.js -> {status}", f"{len(shared)} bytes"):
        return ""

    for symbol in SHARED_EXPORTS:
        report.check(re.search(rf"\b{symbol}\b", shared) is not None, f"exports {symbol}")

    report.check("api-sports.io" in shared, "club-logo fallback host present")
    report.check("sessionStorage" in shared, "timezone cached in sessionStorage")
    return shared


def check_no_duplication(base, shared, report):
    report.section("3. NO DUPLICATED HELPERS IN PAGE SCRIPTS")
    for script in PAGE_SCRIPTS:
        status, source = fetch(base, f"/js/{script}")
        if status != 200:
            report.note(f"/js/{script} -> {status}, skipped")
            continue
        redefined = [
            symbol
            for symbol in NO_REDEFINE
            if re.search(rf"function\s+{symbol}\s*\(|(?:const|let|var)\s+{symbol}\s*=", source)
        ]
        report.check(not redefined, f"{script:18} does not redefine shared helpers", ", ".join(redefined))

    leaking = []
    for script in PAGE_SCRIPTS:
        status, source = fetch(base, f"/js/{script}")
        if status == 200 and GEO_ENDPOINT_RE.search(source):
            leaking.append(script)
    report.check(not leaking, "geo-IP lookup confined to shared.js", ", ".join(leaking))
    if shared:
        endpoints = sorted(set(GEO_ENDPOINT_RE.findall(shared)))
        report.note(f"geo-IP endpoint(s) in shared.js: {endpoints or 'none'}")


def check_badges(base, html_by_page, report):
    report.section("4. BADGE ASSETS")
    paths = {"/static/badges/default.png"}
    for html in html_by_page.values():
        paths.update(re.findall(r"[\"'](/static/badges/[^\"']+)[\"']", html))
    for path in sorted(paths):
        status, _ = fetch(base, path)
        report.check(status == 200, f"{path} -> {status}")


def check_api(base, report):
    report.section("5. CORE API ENDPOINTS")
    payloads = {}
    for path in ["/api/competitions", "/api/fixtures", "/api/fixtures/recommended", "/api/fixtures/calendar"]:
        status, body = fetch(base, path)
        detail = ""
        if status == 200:
            try:
                payloads[path] = json.loads(body)
                shape = payloads[path]
                detail = f"{len(shape)} items" if isinstance(shape, list) else f"keys={sorted(shape)[:5]}"
            except json.JSONDecodeError:
                detail = "non-JSON body"
        report.check(status == 200, f"{path} -> {status}", detail)
    return payloads


def check_feed_invariants(base, html_by_page, payloads, report):
    """AGENTS.md section 4: non-empty cache and strict off-season gating."""
    report.section("6. FEED & OFF-SEASON INVARIANTS")

    status, competitions = fetch(base, "/api/competitions")
    active = len(json.loads(competitions)) if status == 200 else 0

    match = re.search(
        r'id="initial-fixtures-data"[^>]*>(.*?)</script>', html_by_page.get("index", ""), re.S
    )
    if not match:
        report.note("index hydration script tag not found, skipping cache check")
    else:
        try:
            total = json.loads(match.group(1)).get("total_fixtures", 0)
            if active and total == 0:
                report.check(False, "index hydration non-empty", f"total_fixtures=0 with {active} competitions")
            else:
                report.check(True, "index hydration non-empty", f"total_fixtures={total}")
        except json.JSONDecodeError as exc:
            report.note(f"index hydration not parseable: {exc}")

    grouped = payloads.get("/api/fixtures")
    if not isinstance(grouped, dict):
        report.note("/api/fixtures payload unavailable, skipping gating check")
        return

    today = date.today()
    horizons = {"today": today, "tomorrow": today + timedelta(days=1), "this_week": today}
    for bucket, earliest in horizons.items():
        stale = []
        for fixture in grouped.get(bucket) or []:
            raw = (fixture.get("date") or "")[:10]
            try:
                if date.fromisoformat(raw) < earliest:
                    stale.append(f"#{fixture.get('id')}@{raw}")
            except ValueError:
                report.note(f"unparseable date on fixture {fixture.get('id')}: {raw!r}")
        report.check(not stale, f"{bucket:10} contains no past-dated fixtures", ", ".join(stale[:5]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL of the running server")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    status, _ = fetch(base, "/")
    if status is None:
        print(f"Cannot reach {base}. Start the server first:")
        print("  .venv\\Scripts\\python.exe -m uvicorn backend.main:app --port 8000")
        return 2

    report = Report()
    html_by_page = check_pages(base, report)
    shared = check_shared_module(base, html_by_page, report)
    check_no_duplication(base, shared, report)
    check_badges(base, html_by_page, report)
    payloads = check_api(base, report)
    check_feed_invariants(base, html_by_page, payloads, report)

    print()
    print("=" * 70)
    if report.failures:
        print(f"RESULT: {len(report.failures)} FAILURE(S)")
        for failure in report.failures:
            print(f"  - {failure}")
    else:
        print("RESULT: ALL SMOKE CHECKS PASSED")
    print("=" * 70)
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
