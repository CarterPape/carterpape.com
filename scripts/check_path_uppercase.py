# /// script
# requires-python = ">=3.11"
# ///
"""Scan _site/ for directories whose name contains an ASCII uppercase letter.

The URL convention for this site is all-lowercase path components. Asset
filenames (IMG_6686.jpg, DSC*.jpg, KUTV snapshot.png, etc.) are allowed
to keep their casing — they're served directly from R2 by Cloudflare,
they're not part of any redirect logic, and case-meaningful filenames
come from cameras and proper nouns where lowercasing would be
destructive. The issue is uppercase in *directory* names: those become
non-canonical URL path segments, and there's intentionally no edge rule
to normalize them (see CLAUDE.md § "Cloudflare edge ruleset" — Apple
and NYT both 404 on case-typo'd URLs, so a blanket lowercase redirect
isn't worth the SEO and double-hop cost for the rare cases where it'd
help).

To fix a flagged path: rename the source file or directory in the repo
to lowercase so Jekyll generates a lowercase slug. Watch out for
`redirect_from` entries that differ from the canonical only in case —
on APFS those collide with the canonical post directory and pin its
casing to the legacy form.

Exit codes:
    0 — no offending directories.
    1 — at least one directory has uppercase in its name; offenders printed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SITE_DIR = PROJECT_DIR / "_site"

UPPERCASE_RE = re.compile(r"[A-Z]")


def find_uppercase_directories(site_dir: Path) -> list[Path]:
    return sorted(
        path.relative_to(site_dir)
        for path in site_dir.rglob("*")
        if path.is_dir() and UPPERCASE_RE.search(path.name)
    )


def main() -> int:
    if not SITE_DIR.exists():
        print(
            f"path-case check: {SITE_DIR} not found; run a production build first.",
            file=sys.stderr,
        )
        return 1

    bad = find_uppercase_directories(SITE_DIR)
    if not bad:
        print("path-case check: no _site/ directories contain uppercase letters. ✅")
        return 0

    print(
        f"❌ path-case check: {len(bad)} directory(ies) under _site/ contain "
        f"an uppercase letter in their name.",
    )
    print(
        "   URL convention here is lowercase-only path components. Rename the "
        "source file or directory in the repo to lowercase so Jekyll generates "
        "a lowercase slug. (Asset filenames like IMG_*.jpg are intentionally "
        "exempt — those are files, not directories, served directly from R2.)",
    )
    print()
    for rel in bad:
        print(f"  ❌ /{rel}/")
    return 1


if __name__ == "__main__":
    sys.exit(main())
