# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.28"]
# ///
"""Purge Cloudflare cache for files that rclone just synced to S3.

Reads tmp/rclone.log (produced by `scripts/main push` with `-v
--log-file=...`), extracts the paths rclone copied or deleted, maps them
to the URLs a visitor actually hits (including the pretty-permalink form
for */index.html), and POSTs them to Cloudflare's purge_cache endpoint
in batches of 30 (the per-call limit).

Requires CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID in the environment.
Exits non-zero if any batch fails or credentials are missing. rclone's
sync has already landed at this point, so purge failures log a warning
but don't un-do the deploy.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.parse
from pathlib import Path

import httpx

PROJECT_DIR = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_DIR / "tmp" / "rclone.log"
SITE_ORIGIN = "https://carterpape.com"
CLOUDFLARE_PURGE_ENDPOINT_TEMPLATE = (
    "https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache"
)
BATCH_SIZE = 30

# rclone with -v emits lines like:
#   2026/04/18 02:52:02 INFO  : the-blog/foo/index.html: Copied (replaced existing)
#   2026/04/18 02:52:02 INFO  : the-blog/bar.html: Deleted
# We capture any path that was copied or deleted.
RCLONE_LINE_RE = re.compile(
    r"INFO\s*:\s*(?P<path>.+?):\s*(?P<action>Copied|Updated|Deleted|Removed)",
)


def extract_paths(log_text: str) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for match in RCLONE_LINE_RE.finditer(log_text):
        path = match.group("path").strip()
        if path and path not in seen:
            seen.add(path)
            paths.append(path)
    return paths


def paths_to_urls(paths: list[str]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    def add(url: str) -> None:
        if url not in seen:
            seen.add(url)
            urls.append(url)

    for path in paths:
        encoded = "/".join(
            urllib.parse.quote(segment, safe="") for segment in path.split("/")
        )
        add(f"{SITE_ORIGIN}/{encoded}")

        # Pretty-permalink variant: visitors usually hit /foo/ rather
        # than /foo/index.html, and Cloudflare keys those as distinct
        # cache entries, so we purge both.
        if encoded == "index.html":
            add(f"{SITE_ORIGIN}/")
        elif encoded.endswith("/index.html"):
            add(f"{SITE_ORIGIN}/{encoded[: -len('index.html')]}")

    return urls


def purge_batch(
    client: httpx.Client,
    endpoint: str,
    token: str,
    batch: list[str],
) -> tuple[bool, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        response = client.post(endpoint, headers=headers, json={"files": batch})
    except httpx.HTTPError as exc:
        return False, f"request error: {exc}"
    try:
        data = response.json()
    except ValueError:
        return False, f"non-json response (http {response.status_code}): {response.text[:200]}"
    if response.is_success and data.get("success"):
        return True, "ok"
    errors = data.get("errors") or [{"message": f"http {response.status_code}"}]
    return False, "; ".join(str(e.get("message", e)) for e in errors)


def main() -> int:
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    zone_id = os.environ.get("CLOUDFLARE_ZONE_ID")
    if not token or not zone_id:
        print(
            "cloudflare purge: CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID "
            "must be set in .env; skipping purge.",
            file=sys.stderr,
        )
        return 1

    if not LOG_PATH.exists():
        print(f"cloudflare purge: {LOG_PATH} not found; did rclone run?", file=sys.stderr)
        return 1

    paths = extract_paths(LOG_PATH.read_text(errors="replace"))
    if not paths:
        print("cloudflare purge: rclone log had no Copied/Deleted entries; nothing to purge.")
        return 0

    urls = paths_to_urls(paths)
    print(
        f"cloudflare purge: {len(paths)} path(s) → {len(urls)} URL(s), "
        f"batched by {BATCH_SIZE}.",
    )

    endpoint = CLOUDFLARE_PURGE_ENDPOINT_TEMPLATE.format(zone_id=zone_id)
    failures: list[str] = []
    with httpx.Client(timeout=30.0) as client:
        for start in range(0, len(urls), BATCH_SIZE):
            batch = urls[start : start + BATCH_SIZE]
            batch_num = start // BATCH_SIZE + 1
            ok, detail = purge_batch(client, endpoint, token, batch)
            if ok:
                print(f"  batch {batch_num} ({len(batch)} URL(s)): purged")
            else:
                print(f"  batch {batch_num} ({len(batch)} URL(s)): FAILED — {detail}")
                failures.append(detail)

    if failures:
        print(f"\ncloudflare purge: {len(failures)} batch(es) failed.")
        return 1
    print("\ncloudflare purge: all batches succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
