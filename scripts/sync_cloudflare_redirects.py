# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.28"]
# ///
"""Sync the carterpape.com bulk redirect list on Cloudflare.

Reads _site/redirects.json (produced by jekyll-redirect-from), translates
each entry into a Cloudflare bulk-redirect item, diffs against the current
contents of the `intrasite_redirects` list, and (unless --dry-run) PUTs the
new items to replace the list. PUT is async on Cloudflare's side — the script
polls the returned operation until completion.

The Jekyll plugin still emits the per-alias meta-refresh HTML stubs to _site/
and rclone still uploads them to R2 — they serve as a fallback for any path
that doesn't get caught by the edge redirect rule.

Requires CLOUDFLARE_API_TOKEN (with `Account Filter Lists:Read` and
`Account Filter Lists:Edit`), CLOUDFLARE_ACCOUNT_ID, and
CLOUDFLARE_INTRASITE_REDIRECTS_LIST_ID in the environment.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

PROJECT_DIR = Path(__file__).resolve().parent.parent
REDIRECTS_PATH = PROJECT_DIR / "_site" / "redirects.json"
# `source_url` must match `http.request.full_uri` literally — that field always
# carries the scheme, so list items without `https://` never match. The
# OpenAPI example shows a scheme-less form, but the JSON-objects reference
# and the Terraform/country-redirect docs all include the scheme. Origin: a
# scheme-less PUT silently produced 200s instead of 301s on every request.
SOURCE_ORIGIN = "https://carterpape.com"
API_BASE = "https://api.cloudflare.com/client/v4"
POLL_TIMEOUT_SECONDS = 60.0
POLL_INTERVAL_SECONDS = 1.0

# Fields in the redirect object that participate in equality. Anything else
# Cloudflare returns (id, created_on, modified_on) is bookkeeping and gets
# stripped before diffing so the diff reflects intent, not metadata.
REDIRECT_FIELDS = (
    "source_url",
    "target_url",
    "status_code",
    "include_subdomains",
    "subpath_matching",
    "preserve_query_string",
    "preserve_path_suffix",
)


def build_local_items(redirects_map: dict[str, str]) -> list[dict[str, Any]]:
    """Translate jekyll-redirect-from's flat map into Cloudflare items.

    Input keys look like "/news-clips/" or "/blog/decompiling-facebook/...".
    Cloudflare's `source_url` is matched against `http.request.full_uri` after
    the zone-level URL Rewrite phase — and that phase has a "trailing slash →
    /index.html" rewrite to make R2 serve directory-style paths. So a request
    for "/news-clips/" reaches the bulk-redirect rule as
    "https://carterpape.com/news-clips/index.html". We mirror that suffix
    here so the list entries actually match.
    """
    items: list[dict[str, Any]] = []
    for source_path, target_url in redirects_map.items():
        # Source path always begins with "/" in jekyll-redirect-from output.
        # Normalize to "/.../index.html" so the entry matches whatever the
        # URL Rewrite produces, regardless of whether the original front
        # matter had a trailing slash. (A no-slash path like
        # "/foo/whatsapp" gets a trailing slash added by the
        # http_request_dynamic_redirect rule, then /index.html appended by
        # the URL Rewrite.)
        rewritten_path = source_path.rstrip("/") + "/index.html"
        source_url = f"{SOURCE_ORIGIN}{rewritten_path}"
        items.append(
            {
                "redirect": {
                    "source_url": source_url,
                    "target_url": target_url,
                    "status_code": 301,
                    "include_subdomains": False,
                    "subpath_matching": False,
                    "preserve_query_string": True,
                    "preserve_path_suffix": False,
                },
            },
        )
    items.sort(key=lambda item: item["redirect"]["source_url"])
    return items


def fetch_remote_items(
    client: httpx.Client,
    account_id: str,
    list_id: str,
    token: str,
) -> list[dict[str, Any]]:
    """Paginate through the list's current items; strip Cloudflare metadata."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_BASE}/accounts/{account_id}/rules/lists/{list_id}/items"
    raw_items: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"per_page": 100}
        if cursor:
            params["cursor"] = cursor
        response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if not data.get("success"):
            raise RuntimeError(f"list fetch failed: {data}")
        raw_items.extend(data.get("result") or [])
        cursor = ((data.get("result_info") or {}).get("cursors") or {}).get("after")
        if not cursor:
            break

    cleaned: list[dict[str, Any]] = []
    for item in raw_items:
        redirect = item.get("redirect") or {}
        cleaned.append(
            {"redirect": {field: redirect.get(field) for field in REDIRECT_FIELDS}},
        )
    cleaned.sort(key=lambda item: item["redirect"]["source_url"])
    return cleaned


def diff_items(
    local: list[dict[str, Any]],
    remote: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[dict[str, Any], dict[str, Any]]]]:
    local_by_source = {item["redirect"]["source_url"]: item for item in local}
    remote_by_source = {item["redirect"]["source_url"]: item for item in remote}
    added = [local_by_source[s] for s in local_by_source if s not in remote_by_source]
    removed = [remote_by_source[s] for s in remote_by_source if s not in local_by_source]
    changed = [
        (remote_by_source[s], local_by_source[s])
        for s in local_by_source
        if s in remote_by_source and remote_by_source[s] != local_by_source[s]
    ]
    return added, removed, changed


def print_diff(
    added: list[dict[str, Any]],
    removed: list[dict[str, Any]],
    changed: list[tuple[dict[str, Any], dict[str, Any]]],
) -> None:
    for item in added:
        redirect = item["redirect"]
        print(f"  ➕ {redirect['source_url']} → {redirect['target_url']}")
    for item in removed:
        redirect = item["redirect"]
        print(f"  ➖ {redirect['source_url']} → {redirect['target_url']}")
    for old, new in changed:
        print(f"  ✏️  {old['redirect']['source_url']}")
        print(f"      was: {old['redirect']['target_url']}")
        print(f"      now: {new['redirect']['target_url']}")


def put_items(
    client: httpx.Client,
    account_id: str,
    list_id: str,
    token: str,
    items: list[dict[str, Any]],
) -> str:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = f"{API_BASE}/accounts/{account_id}/rules/lists/{list_id}/items"
    response = client.put(url, headers=headers, json=items)
    response.raise_for_status()
    data = response.json()
    if not data.get("success"):
        raise RuntimeError(f"PUT failed: {data}")
    operation_id = (data.get("result") or {}).get("operation_id")
    if not operation_id:
        raise RuntimeError(f"PUT response missing operation_id: {data}")
    return operation_id


def poll_operation(
    client: httpx.Client,
    account_id: str,
    token: str,
    operation_id: str,
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_BASE}/accounts/{account_id}/rules/lists/bulk_operations/{operation_id}"
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if not data.get("success"):
            raise RuntimeError(f"operation poll failed: {data}")
        result = data.get("result") or {}
        status = result.get("status")
        if status == "completed":
            return
        if status == "failed":
            raise RuntimeError(f"operation failed: {result.get('error') or result}")
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(
        f"operation {operation_id} did not complete within {POLL_TIMEOUT_SECONDS}s",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the diff without making changes.",
    )
    args = parser.parse_args()

    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    list_id = os.environ.get("CLOUDFLARE_INTRASITE_REDIRECTS_LIST_ID")
    missing = [
        name
        for name, value in {
            "CLOUDFLARE_API_TOKEN": token,
            "CLOUDFLARE_ACCOUNT_ID": account_id,
            "CLOUDFLARE_INTRASITE_REDIRECTS_LIST_ID": list_id,
        }.items()
        if not value
    ]
    if missing:
        print(
            f"redirects sync: missing env vars: {', '.join(missing)}; skipping.",
            file=sys.stderr,
        )
        return 1

    if not REDIRECTS_PATH.exists():
        print(
            f"redirects sync: {REDIRECTS_PATH} not found; did jekyll build run?",
            file=sys.stderr,
        )
        return 1

    redirects_map = json.loads(REDIRECTS_PATH.read_text())
    local = build_local_items(redirects_map)

    with httpx.Client(timeout=30.0) as client:
        try:
            remote = fetch_remote_items(client, account_id, list_id, token)
        except (httpx.HTTPError, RuntimeError) as exc:
            print(f"redirects sync: failed to fetch remote list: {exc}", file=sys.stderr)
            return 1

        added, removed, changed = diff_items(local, remote)
        if not (added or removed or changed):
            print(
                f"✅ redirects sync: no changes ({len(local)} items already in sync).",
            )
            return 0

        print(
            f"🔄 redirects sync: {len(added)} added, "
            f"{len(removed)} removed, {len(changed)} changed.",
        )
        print_diff(added, removed, changed)

        if args.dry_run:
            print("⏭️  redirects sync: --dry-run; no changes pushed.")
            return 0

        try:
            operation_id = put_items(client, account_id, list_id, token, local)
            print(f"redirects sync: PUT submitted (operation {operation_id}); polling…")
            poll_operation(client, account_id, token, operation_id)
        except (httpx.HTTPError, RuntimeError, TimeoutError) as exc:
            print(f"❌ redirects sync: FAILED — {exc}", file=sys.stderr)
            return 1

    print("✅ redirects sync: operation completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
