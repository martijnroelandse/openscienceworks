#!/usr/bin/env python3
"""
backfill_years.py — fetch missing publication years from Crossref

For each story JSON with bibliographic.published_year = null, queries
the Crossref API (no key required) and writes the year into the file's
bibliographic.published_year field.

Run from the openscienceworks directory:
    python3 backfill_years.py [--dir .]

Then rebuild:
    python3 extract_authors.py --dir . --out authors.json
    python3 generate_authorstory.py --dir .

Uses a cache file (years_cache.json) so partial runs are safe.
"""

import argparse
import glob
import json
import os
import re
import time
import urllib.request
import urllib.error

CROSSREF_BASE = "https://api.crossref.org/works"
SLEEP_BETWEEN = 0.15  # polite — Crossref asks for < 50 rps
MAX_RETRIES = 3
STORY_PREFIXES = ("articlestory_", "bookstory_", "datastory_", "softwarestory_", "data_")

MAILTO = "martijn@openscience.works"  # included in User-Agent — Crossref "polite pool"


def fetch_year_from_crossref(doi: str) -> int | None:
    """
    Query Crossref for a DOI and return the published year, or None on failure.
    """
    # Crossref expects raw DOI (no url prefix) but we must URL-encode it
    doi_encoded = urllib.parse.quote(doi, safe="")
    url = f"{CROSSREF_BASE}/{doi_encoded}"
    headers = {
        "User-Agent": f"openscience.works/1.0 (mailto:{MAILTO})",
    }

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.load(resp)
            msg = data.get("message") or {}
            # Prefer published-print > published-online > issued
            for field in ("published-print", "published-online", "issued"):
                parts = (msg.get(field) or {}).get("date-parts")
                if parts and parts[0]:
                    year = parts[0][0]
                    if year and isinstance(year, int) and 1900 < year < 2100:
                        return year
            return None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429:
                wait = 2 ** attempt
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"    HTTP {e.code} for {doi}")
            return None
        except Exception as exc:
            print(f"    Error fetching {doi}: {exc}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)

    return None


def main():
    import urllib.parse  # noqa: import here since we use it above

    parser = argparse.ArgumentParser(description="Backfill missing publication years from Crossref")
    parser.add_argument("--dir", default=".", help="Story directory")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but do not write back to JSON files")
    args = parser.parse_args()

    story_dir = args.dir
    cache_path = os.path.join(story_dir, "years_cache.json")

    # Load existing cache
    if os.path.isfile(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            cache: dict = json.load(f)
        print(f"Loaded years cache: {len(cache)} entries")
    else:
        cache = {}

    # Find files with missing years
    files = sorted(
        f for f in glob.glob(os.path.join(story_dir, "*.json"))
        if os.path.basename(f).startswith(STORY_PREFIXES)
    )

    missing = []
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        bib = data.get("bibliographic") or {}
        year = bib.get("published_year") or data.get("publication_year")
        if not year:
            doi = data.get("doi") or data.get("book_id", "")
            if doi:
                missing.append((path, doi, data))

    print(f"Files with missing year: {len(missing)} / {len(files)}")

    to_fetch = [(p, doi, d) for p, doi, d in missing if doi not in cache]
    print(f"To fetch from Crossref: {len(to_fetch)}\n")

    updated = 0

    for i, (path, doi, data) in enumerate(to_fetch, 1):
        print(f"  [{i}/{len(to_fetch)}] {doi}", end=" ", flush=True)
        year = fetch_year_from_crossref(doi)
        cache[doi] = year
        if year:
            print(f"→ {year}")
        else:
            print("→ not found")
        time.sleep(SLEEP_BETWEEN)

        if i % 25 == 0:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
            print(f"    (saved cache, {i} done)")

    # Save final cache
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {cache_path}")

    # Write years back into story JSON files
    if args.dry_run:
        print("\n--dry-run: skipping writes back to story files")
    else:
        print("\nWriting years back to story files...")
        for path, doi, data in missing:
            year = cache.get(doi)
            if not year:
                continue
            # Re-read to avoid writing stale data if the file changed
            try:
                with open(path, encoding="utf-8") as f:
                    fresh = json.load(f)
            except Exception:
                continue
            bib = fresh.get("bibliographic") or {}
            if bib.get("published_year"):
                continue  # already set — skip
            if "bibliographic" not in fresh:
                fresh["bibliographic"] = {}
            fresh["bibliographic"]["published_year"] = year
            if not args.dry_run:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(fresh, f, indent=2, ensure_ascii=False)
                updated += 1

        print(f"Updated {updated} story files")

    print("\nNext: rebuild authors and regenerate pages:")
    print("  python3 extract_authors.py --dir . --out authors.json")
    print("  python3 generate_authorstory.py --dir .")


if __name__ == "__main__":
    main()
