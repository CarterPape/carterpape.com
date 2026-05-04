# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.28"]
# ///
"""Verify Cloudflare Image Transformations accepts every external source
referenced in _site/, before a deploy ships URLs that would 403 in production.

Scans the built site for /cdn-cgi/image/<opts>/<absolute-url> patterns, dedupes
to unique external source URLs, and HEADs each one through carterpape.com's
transformation endpoint. Cloudflare returns non-200 for any source whose
origin (or origin+path prefix) isn't in the dashboard's allowed-sources list,
so a failed probe maps directly to "add this to the dashboard."

The dashboard is the single source of truth — there's intentionally no
in-repo allowlist to drift out of sync with it.

Exit codes:
    0 — every external source returned 200, or no externals referenced.
    1 — at least one source rejected; failures printed grouped by origin.
"""

from __future__ import annotations

import html
import random
import re
import sys
import urllib.parse
import webbrowser
from collections import defaultdict
from pathlib import Path

import httpx

PROJECT_DIR = Path(__file__).resolve().parent.parent
SITE_DIR = PROJECT_DIR / "_site"
SITE_ORIGIN = "https://carterpape.com"

# Dashboard for managing this zone's allowed transformation sources. Account
# and zone IDs aren't credentials — they appear in dashboard URLs and have no
# auth value on their own.
DASHBOARD_URL = (
    "https://dash.cloudflare.com/99fe64e11eb5865bb1024f6fded1eed2/"
    "images/transformations/zone/de377fd064153e454b479c95afac0c68"
)

# /cdn-cgi/image/<opts>/<absolute-url>. Source is absolute (http(s)://) when
# external; relative paths are local and skipped — Cloudflare always accepts
# same-zone sources.
TRANSFORM_RE = re.compile(
    r"""/cdn-cgi/image/[^/\s"'<>]+/(?P<source>https?://[^\s"'<>)]+)""",
)


def find_external_sources(site_dir: Path) -> set[str]:
    sources: set[str] = set()
    for path in site_dir.rglob("*.html"):
        text = path.read_text(errors="replace")
        for match in TRANSFORM_RE.finditer(text):
            # Decode &amp; etc. so the URL we probe matches what the browser
            # would actually request.
            sources.add(html.unescape(match.group("source")))
    return sources


def probe(client: httpx.Client, source: str, cache_buster_width: int) -> int:
    # Each run rolls a fresh width so Cloudflare's transformation cache (keyed
    # on the full /cdn-cgi/image/<opts>/<source> URL) doesn't return a stale
    # 403 from before the user updated the dashboard.
    probe_url = (
        f"{SITE_ORIGIN}/cdn-cgi/image/format=auto,width={cache_buster_width}/{source}"
    )
    try:
        response = client.head(probe_url, follow_redirects=True, timeout=20.0)
    except httpx.HTTPError as exc:
        print(f"    request error: {exc}", file=sys.stderr)
        return -1
    return response.status_code


def main() -> int:
    if not SITE_DIR.exists():
        print(
            f"transform-source check: {SITE_DIR} not found; run a production build first.",
            file=sys.stderr,
        )
        return 1

    sources = find_external_sources(SITE_DIR)
    if not sources:
        print("transform-source check: no external image sources referenced; nothing to probe.")
        return 0

    cache_buster_width = random.randint(100, 8192)  # noqa: S311  (not security-sensitive)
    print(
        f"transform-source check: probing {len(sources)} unique external source(s) "
        f"(width={cache_buster_width} for cache-bust)...",
    )

    failures: list[str] = []
    with httpx.Client() as client:
        for source in sorted(sources):
            status = probe(client, source, cache_buster_width)
            marker = "✅" if status == 200 else "❌"  # noqa: RUF001 (visual cue intentional)
            print(f"  {marker} {status:>4}  {source}")
            if status != 200:
                failures.append(source)

    if not failures:
        print("transform-source check: all external sources accepted by Cloudflare. ✅")
        return 0

    # Group rejected sources by origin, format as markdown bullets.
    by_origin: dict[str, list[str]] = defaultdict(list)
    for source in failures:
        parsed = urllib.parse.urlparse(source)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        by_origin[parsed.netloc].append(path)

    print()
    print(f"❌ {len(failures)} external source(s) rejected by Cloudflare Image Transformations.")
    print("   Add these to the dashboard's allowed-sources list:")
    print()
    for origin in sorted(by_origin):
        print(f"- `{origin}`")
        for path in sorted(by_origin[origin]):
            print(f"    - `{path}`")
    print()
    print(f"Dashboard: {DASHBOARD_URL}")
    print("Press Enter to open it in your browser, or anything else to skip.")
    try:
        response = input("> ")
    except (EOFError, KeyboardInterrupt):
        response = "skip"
    if response == "":
        webbrowser.open(DASHBOARD_URL)

    return 1


if __name__ == "__main__":
    sys.exit(main())
