#!/usr/bin/env python3
"""
Phase 2: make author names in the "Contributors & affiliations" section of
story pages clickable links to their AuthorStory pages.

- Primary match: ORCID from the `.orcid-badge` href (bare id or full
  https://orcid.org/... URL) -> authorstory_{orcid}.html
- Fallback match: normalized name lookup against authors.json (covers
  name-only authors with kebab-case slugs)
- Only links when the target authorstory_*.html actually exists
- Idempotent: skips <strong> elements that already contain an <a>
- Patches only the Authors <ul> region; the rest of each file is untouched

Usage: python3 patch_author_links.py
"""

import glob
import json
import re
import unicodedata
from html import unescape
from pathlib import Path

ROOT = Path(__file__).parent
STORY_GLOBS = ["articlestory_*.html", "bookstory_*.html",
               "datastory_*.html", "softwarestory_*.html"]

ORCID_RE = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])")
LI_RE = re.compile(r"<li\b.*?</li>", re.DOTALL)
STRONG_RE = re.compile(r"<strong>([^<]+)</strong>")
BADGE_HREF_RE = re.compile(r'class="orcid-badge"\s+href="([^"]+)"')


def norm_name(name: str) -> str:
    """Accent-insensitive, order-insensitive token key for a person name."""
    name = unicodedata.normalize("NFKD", unescape(name))
    name = "".join(c for c in name if not unicodedata.combining(c))
    tokens = re.findall(r"[a-z0-9]+", name.lower())
    return " ".join(sorted(tokens))


def build_index():
    authors = json.loads((ROOT / "authors.json").read_text("utf-8"))
    by_orcid = {}
    by_name = {}
    ambiguous = set()
    for a in authors:
        page = a.get("page") or f"authorstory_{a['slug']}.html"
        if not (ROOT / page).exists():
            continue
        if a.get("orcid"):
            by_orcid[a["orcid"]] = page
        key = norm_name(a.get("display_name", ""))
        if key:
            if key in by_name and by_name[key] != page:
                ambiguous.add(key)
            else:
                by_name[key] = page
    for key in ambiguous:
        by_name.pop(key, None)
    return by_orcid, by_name


def find_authors_ul_span(html: str):
    """Return (start, end) of the Authors <ul>...</ul> in the Contributors
    section, or None."""
    h2 = html.find("Contributors &amp; affiliations")
    if h2 == -1:
        h2 = html.find("Contributors & affiliations")
    if h2 == -1:
        return None
    h3 = html.find(">Authors</h3>", h2)
    anchor = h3 if h3 != -1 else h2
    start = html.find("<ul", anchor)
    if start == -1:
        return None
    end = html.find("</ul>", start)
    if end == -1:
        return None
    return start, end + len("</ul>")


def patch_li(li: str, by_orcid, by_name):
    """Return (patched_li, linked) for one <li> block."""
    if "<strong><a" in li:
        return li, False
    m = STRONG_RE.search(li)
    if not m:
        return li, False
    page = None
    badge = BADGE_HREF_RE.search(li)
    if badge:
        orcid = ORCID_RE.search(badge.group(1))
        if orcid:
            page = by_orcid.get(orcid.group(1))
    if page is None:
        page = by_name.get(norm_name(m.group(1)))
    if page is None:
        return li, False
    linked = f'<strong><a href="{page}">{m.group(1)}</a></strong>'
    return li[:m.start()] + linked + li[m.end():], True


def patch_file(path: Path, by_orcid, by_name):
    html = path.read_text("utf-8")
    span = find_authors_ul_span(html)
    if span is None:
        return 0
    start, end = span
    region = html[start:end]
    count = 0

    def repl(m):
        nonlocal count
        patched, linked = patch_li(m.group(0), by_orcid, by_name)
        count += linked
        return patched

    new_region = LI_RE.sub(repl, region)
    if count:
        path.write_text(html[:start] + new_region + html[end:], "utf-8")
    return count


def main():
    by_orcid, by_name = build_index()
    print(f"Index: {len(by_orcid)} ORCID entries, {len(by_name)} name entries")
    total_files = patched_files = total_links = 0
    for pattern in STORY_GLOBS:
        for fname in sorted(glob.glob(str(ROOT / pattern))):
            total_files += 1
            n = patch_file(Path(fname), by_orcid, by_name)
            if n:
                patched_files += 1
                total_links += n
    print(f"Scanned {total_files} story pages; "
          f"patched {patched_files} files, added {total_links} author links")


if __name__ == "__main__":
    main()
