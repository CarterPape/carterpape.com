# /// script
# requires-python = ">=3.11"
# ///
"""Scan _site/ for directories whose name contains '.', which Cloudflare's
"add trailing slash" redirect rule can't handle.

Jekyll's pretty permalinks make every page's URL path equivalent to its
location on disk: a page at /foo/bar/ lives at _site/foo/bar/index.html.
So a directory under _site/ whose name contains a period means a page is
served at a URL like /foo.bar/..., where the trailing-slash redirect (which
skips paths containing '.') won't rescue visitors who strip the slash.

Files with extensions (style.css, feed.xml, etc.) are fine: Cloudflare
serves them directly and there's no redirect to miss.

Exit codes:
    0 — no offending directories.
    1 — at least one offending directory; offenders printed.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SITE_DIR = PROJECT_DIR / "_site"


def find_dot_bearing_directories(site_dir: Path) -> list[Path]:
    return sorted(
        path.relative_to(site_dir)
        for path in site_dir.rglob("*")
        if path.is_dir() and "." in path.name
    )


def main() -> int:
    if not SITE_DIR.exists():
        print(
            f"path-period check: {SITE_DIR} not found; run a production build first.",
            file=sys.stderr,
        )
        return 1

    bad = find_dot_bearing_directories(SITE_DIR)
    if not bad:
        print("path-period check: no _site/ directories contain a period. ✅")
        return 0

    print(
        f"❌ path-period check: {len(bad)} directory(ies) under _site/ contain "
        f"'.' in their name.",
    )
    print(
        "   Cloudflare's trailing-slash redirect skips paths containing '.', so "
        "any page reachable through these directories 404s if someone strips "
        "the trailing slash.",
    )
    print()
    for rel in bad:
        print(f"  ❌ /{rel}/")
    return 1


if __name__ == "__main__":
    sys.exit(main())
