#!/usr/bin/env python3
"""
enrich_affiliations.py — fetch verified author affiliations from ORCID

Uses the ORCID public API (no API key required) to get self-curated employment
history for each ORCID-identified author. ORCID data is authoritative because
people enter it themselves — unlike OpenAlex, which machine-infers affiliations
from paper metadata and can attribute co-authors' institutions to the wrong person.

Run from the openscienceworks directory before extract_authors.py:
    python3 enrich_affiliations.py [--dir .]

Then rebuild:
    python3 extract_authors.py --dir . --out authors.json
    python3 generate_authorstory.py --dir .

Cache file: author_affiliations_cache.json
    Maps orcid → list of { name, role, start_year, end_year }
    end_year is null for current positions.
"""

import argparse
import json
import os
import time
import urllib.request
import urllib.error

ORCID_BASE = "https://pub.orcid.org/v3.0"
SLEEP_BETWEEN = 0.2   # seconds — ORCID public API rate limit is generous
MAX_RETRIES = 3


def fetch_orcid_employments(orcid: str) -> list:
    """
    Fetch employment records from the ORCID public API.
    Returns list of { name, role, start_year, end_year } dicts,
    sorted by start_year desc (most recent first).
    Returns empty list on 404 or error.
    """
    url = f"{ORCID_BASE}/{orcid}/employments"
    headers = {
        "Accept": "application/vnd.orcid+json",
        "User-Agent": "openscience.works/1.0 (mailto:martijn@openscience.works)",
    }

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.load(resp)
            return _parse_employments(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            if e.code == 429:
                wait = 2 ** attempt
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"    HTTP {e.code} for {orcid}")
            return []
        except Exception as e:
            print(f"    Error fetching {orcid}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)

    return []


def _parse_employments(data: dict) -> list:
    """
    Parse ORCID /employments response into a clean list.

    ORCID JSON structure:
    {
      "affiliation-group": [
        {
          "summaries": [
            {
              "employment-summary": {
                "organization": { "name": "Springer" },
                "role-title": "Product Owner",
                "department-name": "Open Access Books",
                "start-date": { "year": { "value": "2010" }, ... },
                "end-date": null | { "year": { "value": "2015" }, ... }
              }
            }
          ]
        }
      ]
    }
    """
    results = []
    for group in (data.get("affiliation-group") or []):
        for summary_wrap in (group.get("summaries") or []):
            emp = summary_wrap.get("employment-summary") or {}

            org = emp.get("organization") or {}
            name = (org.get("name") or "").strip()
            if not name:
                continue

            role = (emp.get("role-title") or "").strip() or None
            dept = (emp.get("department-name") or "").strip() or None

            start_year = _extract_year(emp.get("start-date"))
            end_year   = _extract_year(emp.get("end-date"))   # None = current position

            results.append({
                "name":       name,
                "role":       role,
                "department": dept,
                "start_year": start_year,
                "end_year":   end_year,
            })

    # Sort: current positions first (end_year=None), then by start_year desc
    results.sort(key=lambda x: (x["end_year"] is not None, -(x["start_year"] or 0)))
    return results


def _extract_year(date_obj) -> int | None:
    """Extract integer year from ORCID date object, or None."""
    if not date_obj:
        return None
    year_obj = date_obj.get("year")
    if not year_obj:
        return None
    try:
        return int(year_obj.get("value", 0)) or None
    except (TypeError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Enrich author affiliations from ORCID")
    parser.add_argument("--dir", default=".", help="Story directory")
    parser.add_argument("--authors", default="authors.json", help="Path to authors.json")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if already cached")
    args = parser.parse_args()

    authors_path = args.authors if os.path.isabs(args.authors) else os.path.join(args.dir, args.authors)
    cache_path = os.path.join(args.dir, "author_affiliations_cache.json")

    with open(authors_path, encoding="utf-8") as f:
        authors = json.load(f)

    orcid_authors = [a for a in authors if a.get("orcid")]
    print(f"Authors with ORCID: {len(orcid_authors)} / {len(authors)}")

    # Load existing cache
    if os.path.isfile(cache_path) and not args.force:
        with open(cache_path, encoding="utf-8") as f:
            cache: dict = json.load(f)
        print(f"Existing cache: {len(cache)} entries")
    else:
        cache = {}

    to_fetch = [a for a in orcid_authors if args.force or a["orcid"] not in cache]
    print(f"To fetch: {len(to_fetch)}\n")

    for i, author in enumerate(to_fetch, 1):
        orcid = author["orcid"]
        name  = author["display_name"]
        print(f"  [{i}/{len(to_fetch)}] {name} ({orcid})", end=" ", flush=True)

        emps = fetch_orcid_employments(orcid)
        cache[orcid] = emps

        if emps:
            preview = [
                f"{e['name']}" + (f" ({e['start_year']}–{e['end_year'] or 'present'})" if e['start_year'] else "")
                for e in emps[:3]
            ]
            print(f"→ {len(emps)} positions: {preview}")
        else:
            print("→ no public employment data")

        time.sleep(SLEEP_BETWEEN)

        if i % 10 == 0:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
            print(f"    (saved cache, {i} done)")

    # Final write
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {cache_path} ({len(cache)} entries)")
    print("\nNext: rebuild authors and regenerate pages:")
    print("  python3 extract_authors.py --dir . --out authors.json")
    print("  python3 generate_authorstory.py --dir .")


if __name__ == "__main__":
    main()
