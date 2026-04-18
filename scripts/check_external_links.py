# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.28"]
# ///
"""Supplementary external-link verifier for the carterpape.com deploy pipeline.

Called after htmlproofer fails. Parses htmlproofer's captured output to extract
the failed URLs, then for each:

  1. Skip if a recent cache entry confirms it's alive (2-week TTL).
  2. Retry via the locally self-hosted FireCrawl (http://localhost:3002). If
     FireCrawl can fetch it with a 2xx/3xx status, mark it alive.
  3. For anything still unresolved, batch into Safari (5 at a time) and ask
     the human to confirm. Answers persist to the cache.

Exits 0 if every failed URL is verified alive; 1 if any is confirmed dead or
the user aborts.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

PROJECT_DIR = Path(__file__).resolve().parent.parent
CACHE_PATH = PROJECT_DIR / "tmp" / "link-verification-cache.json"
CACHE_TTL = timedelta(weeks=2)
FIRECRAWL_URL = "http://localhost:3002/v1/scrape"
FIRECRAWL_TIMEOUT = 120.0
SAFARI_BATCH_SIZE = 5

HTMLPROOFER_FAILURE_RE = re.compile(r"External link (\S+) failed")


def load_cache() -> dict[str, dict]:
    if not CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(CACHE_PATH.read_text())
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_cache(cache: dict[str, dict]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n")


def is_fresh(entry: dict) -> bool:
    raw = entry.get("verified_at")
    if not isinstance(raw, str):
        return False
    try:
        verified_at = datetime.fromisoformat(raw)
    except ValueError:
        return False
    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - verified_at) < CACHE_TTL


def extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in HTMLPROOFER_FAILURE_RE.finditer(text):
        url = match.group(1)
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


def firecrawl_check(url: str, client: httpx.Client) -> tuple[bool, str]:
    """Return (is_alive, human-readable reason)."""
    try:
        response = client.post(
            FIRECRAWL_URL,
            json={"url": url},
            timeout=FIRECRAWL_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        return False, f"request error: {exc}"
    except json.JSONDecodeError as exc:
        return False, f"bad json: {exc}"

    if not payload.get("success"):
        return False, f"firecrawl error: {payload.get('error')!r}"

    metadata = payload.get("data", {}).get("metadata", {})
    status = metadata.get("statusCode")
    if isinstance(status, int) and 200 <= status < 400:
        return True, f"status {status}"
    return False, f"status {status}"


def _as_quote(value: str) -> str:
    """Quote a Python string as an AppleScript string literal."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def open_in_safari(urls: list[str]) -> None:
    """Open urls as tabs in a fresh Safari window (not the frontmost one)."""
    if not urls:
        return
    first, *rest = urls
    lines = [
        'tell application "Safari"',
        "  activate",
        f"  make new document with properties {{URL:{_as_quote(first)}}}",
    ]
    for url in rest:
        lines.append(
            f"  tell window 1 to make new tab with properties {{URL:{_as_quote(url)}}}",
        )
    lines.append("end tell")
    subprocess.run(
        ["osascript", "-e", "\n".join(lines)],
        check=False,
        capture_output=True,
    )


def _osascript_dialog(message: str, buttons: list[str], default: str) -> str:
    button_list = "{" + ", ".join(_as_quote(b) for b in buttons) + "}"
    script = (
        f"display dialog {_as_quote(message)} "
        f"buttons {button_list} "
        f"default button {_as_quote(default)} "
        f"with title {_as_quote('deploy: verify links')}"
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # Most commonly: user hit escape / "cancel button was pressed".
        raise RuntimeError(
            f"osascript aborted (rc={result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}",
        )
    out = result.stdout.strip()
    prefix = "button returned:"
    if out.startswith(prefix):
        return out[len(prefix) :]
    raise RuntimeError(f"unexpected osascript output: {out!r}")


def prompt_batch(urls: list[str]) -> dict[str, bool]:
    """Open URLs in Safari and ask the user via native dialog."""
    open_in_safari(urls)
    listing = "\n".join(f"{i}. {u}" for i, u in enumerate(urls, start=1))
    message = (
        f"{len(urls)} URL(s) opened in Safari:\n\n{listing}\n\n"
        "Are they all alive?"
    )
    choice = _osascript_dialog(
        message=message,
        buttons=["All dead", "Review each", "All alive"],
        default="All alive",
    )
    if choice == "All alive":
        return dict.fromkeys(urls, True)
    if choice == "All dead":
        return dict.fromkeys(urls, False)
    if choice == "Review each":
        return prompt_each(urls)
    msg = f"unexpected dialog choice: {choice!r}"
    raise RuntimeError(msg)


def prompt_each(urls: list[str]) -> dict[str, bool]:
    answers: dict[str, bool] = {}
    for url in urls:
        choice = _osascript_dialog(
            message=f"Alive?\n\n{url}",
            buttons=["dead", "alive"],
            default="alive",
        )
        answers[url] = choice == "alive"
    return answers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--htmlproofer-output",
        type=Path,
        required=True,
        help="Path to captured htmlproofer stdout+stderr.",
    )
    args = parser.parse_args()

    if not args.htmlproofer_output.exists():
        print(f"error: {args.htmlproofer_output} does not exist", file=sys.stderr)
        return 1

    text = args.htmlproofer_output.read_text(errors="replace")
    urls = extract_urls(text)
    if not urls:
        print(
            "no 'External link ... failed' lines found in htmlproofer output; "
            "the failure was probably non-link (images, scripts, favicon, etc.)."
        )
        return 1

    print(f"htmlproofer reported {len(urls)} unique failing external link(s).")

    cache = load_cache()
    now_iso = datetime.now(timezone.utc).isoformat()

    cached_alive: list[str] = []
    pending: list[str] = []
    for url in urls:
        entry = cache.get(url)
        if entry and is_fresh(entry):
            cached_alive.append(url)
        else:
            pending.append(url)

    if cached_alive:
        print(f"  {len(cached_alive)} already verified within {CACHE_TTL.days}d")

    if not pending:
        print("all reported URLs are cached-verified. passing.")
        return 0

    print(f"  {len(pending)} to re-check\n")
    print("== firecrawl stage ==")

    firecrawl_verified: list[str] = []
    unresolved: list[str] = []

    with httpx.Client() as client:
        for url in pending:
            print(f"  {url} ... ", end="", flush=True)
            alive, reason = firecrawl_check(url, client)
            if alive:
                firecrawl_verified.append(url)
                cache[url] = {"verified_at": now_iso, "method": "firecrawl"}
                print(f"alive ({reason})")
            else:
                unresolved.append(url)
                print(f"needs human ({reason})")

    if firecrawl_verified:
        save_cache(cache)

    if not unresolved:
        print("\nall URLs verified by firecrawl. passing.")
        return 0

    print(f"\n== human stage ==")
    print(f"{len(unresolved)} URL(s) need manual confirmation.\n")

    confirmed_dead: list[str] = []
    for start in range(0, len(unresolved), SAFARI_BATCH_SIZE):
        batch = unresolved[start : start + SAFARI_BATCH_SIZE]
        try:
            answers = prompt_batch(batch)
        except RuntimeError as exc:
            print(f"\nhuman verification aborted: {exc}")
            save_cache(cache)
            return 1
        for url, alive in answers.items():
            if alive:
                cache[url] = {"verified_at": now_iso, "method": "human"}
            else:
                confirmed_dead.append(url)
        save_cache(cache)

    if confirmed_dead:
        print("\nconfirmed dead:")
        for url in confirmed_dead:
            print(f"  - {url}")
        return 1

    print("\nall URLs verified alive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
