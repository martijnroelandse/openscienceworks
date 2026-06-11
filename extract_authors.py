#!/usr/bin/env python3
"""
extract_authors.py — openscience.works author index builder

Walks all story JSON files, extracts authors correctly per schema,
deduplicates by DOI, resolves identity via ORCID or normalized name,
and writes authors.json.

Usage:
    python3 extract_authors.py [--dir .] [--out authors.json] [--min-pubs 2]

Author fields by story type:
  Books   → data["authors"]  (list of strings) + data["author_orcids"] (dict name→orcid)
  Others  → data["signals"]["contributors"]["authors"]  (list of dicts with name/orcid/institutions)
            fallback: data["signals"]["template_authors"]

Identity key:
  - ORCID (normalized, no URL prefix) if present
  - Otherwise: name lowercased+stripped  (exact match only; no fuzzy merge)

Name normalization:
  - "Lastname, Firstname" → "Firstname Lastname" for display
  - Canonical display name = first non-empty name seen for that key
"""

import argparse
import glob
import json
import os
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


# ── Story type detection ──────────────────────────────────────────────────────

def story_type_from_filename(filename: str) -> str:
    base = os.path.basename(filename).lower()
    if base.startswith("bookstory"):
        return "book"
    if base.startswith("datastory"):
        return "data"
    if base.startswith("softwarestory"):
        return "software"
    return "article"


# ── Name normalization ────────────────────────────────────────────────────────

_LASTNAME_FIRST = re.compile(r"^([^,]+),\s*(.+)$")


def normalize_name_display(name: str) -> str:
    """Flip 'Last, First' → 'First Last'. Leave other formats unchanged."""
    name = name.strip()
    m = _LASTNAME_FIRST.match(name)
    if m:
        return f"{m.group(2).strip()} {m.group(1).strip()}"
    return name


def normalize_name_key(name: str) -> str:
    """Lowercase, strip, collapse whitespace for use as identity key."""
    name = normalize_name_display(name)
    # Normalize unicode (ñ → n etc.) for robust matching — keep original for display
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", ascii_name.lower().strip())


def normalize_orcid(raw: str) -> str:
    """Strip URL prefix, return bare 0000-0001-... form (or empty string)."""
    if not raw:
        return ""
    raw = raw.strip()
    raw = re.sub(r"^https?://orcid\.org/", "", raw)
    # Validate rough pattern
    if re.match(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", raw):
        return raw
    return ""


def orcid_url(orcid: str) -> str:
    return f"https://orcid.org/{orcid}" if orcid else ""


# ── DOI normalization (collapse versioned DOIs) ───────────────────────────────

def normalize_doi(doi: str) -> str:
    """Strip trailing version suffix (.v1, .v2, etc.) for deduplication."""
    if not doi:
        return ""
    doi = doi.strip().lower()
    doi = re.sub(r"\.v\d+$", "", doi)
    return doi


# ── Author extraction per file ────────────────────────────────────────────────

def extract_authors_from_file(path: str):
    """
    Returns list of dicts:
      { name, orcid, institutions: [...], position, is_corresponding }
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    stype = story_type_from_filename(path)

    if stype == "book":
        # Top-level authors list (strings) + optional author_orcids dict
        raw = data.get("authors", [])
        orcid_map = data.get("author_orcids") or {}
        result = []
        for entry in raw:
            if isinstance(entry, str):
                name = entry.strip()
                orcid = normalize_orcid(orcid_map.get(name, "") or orcid_map.get(normalize_name_display(name), ""))
                result.append({"name": normalize_name_display(name), "orcid": orcid,
                                "institutions": [], "position": None, "is_corresponding": None})
            elif isinstance(entry, dict):
                name = normalize_name_display(entry.get("name", "").strip())
                orcid = normalize_orcid(entry.get("orcid", "") or "")
                insts = [i.get("name", "") for i in (entry.get("institutions") or []) if isinstance(i, dict)]
                result.append({"name": name, "orcid": orcid, "institutions": insts,
                                "position": entry.get("position"), "is_corresponding": entry.get("is_corresponding")})
        return result

    else:
        # Article / data / software: use signals.contributors.authors, fallback template_authors
        signals = data.get("signals", {})
        contrib = signals.get("contributors", {})
        authors = contrib.get("authors", []) if isinstance(contrib, dict) else []
        if not authors:
            authors = signals.get("template_authors", [])
        if not authors:
            # Last-resort: top-level authors (usually empty for articles)
            raw = data.get("authors", [])
            authors = [{"name": a, "orcid": ""} for a in raw if isinstance(a, str)]

        result = []
        for entry in authors:
            if isinstance(entry, dict):
                name = normalize_name_display(entry.get("name", "").strip())
                orcid = normalize_orcid(entry.get("orcid", "") or "")
                insts = [i.get("name", "") for i in (entry.get("institutions") or []) if isinstance(i, dict)]
                result.append({"name": name, "orcid": orcid, "institutions": insts,
                                "position": entry.get("position"), "is_corresponding": entry.get("is_corresponding")})
            elif isinstance(entry, str):
                result.append({"name": normalize_name_display(entry.strip()), "orcid": "",
                                "institutions": [], "position": None, "is_corresponding": None})
        return result


# ── Publication metadata from file ───────────────────────────────────────────

def extract_pub_meta(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    stype = story_type_from_filename(path)
    stem = Path(path).stem  # e.g. articlestory_10.1016_j.cell.2023.11.010

    doi = data.get("doi") or data.get("book_id", "")
    title = data.get("title", "")
    year = (data.get("bibliographic", {}) or {}).get("published_year") or data.get("publication_year")
    venue = (data.get("venue", {}) or {}).get("name", "") or data.get("publisher", "")

    # Citations — articles have citations as dict, books have it as list of citing works
    raw_cites = data.get("citations")
    if isinstance(raw_cites, dict):
        cites = raw_cites.get("citation_count")
    elif isinstance(raw_cites, list):
        cites = len(raw_cites)
    else:
        cites = None
    if cites is None:
        cites = (data.get("signals", {}) or {}).get("citation_count", 0)

    # Attention
    signals = data.get("signals", {}) or {}
    mentions = (signals.get("attention_summary", {}) or {}).get("total_mentions", 0)

    # OA
    is_oa = (data.get("access", {}) or {}).get("is_oa", False)

    # Teaching adoption signals
    ta = signals.get("teaching_adoption", {}) or {}
    holdings = ta.get("holdings", {}) or {}
    ocw_count   = len(ta.get("ocw", []) or [])
    yt_count    = len(ta.get("youtube", []) or [])
    ol_holdings = int(holdings.get("ol_holdings", 0) or 0)

    # SDGs
    sdg_count = len(signals.get("sdgs", []) or [])

    # Wikipedia mentions
    wiki_count = len((signals.get("social_mentions", {}) or {}).get("wikipedia", []) or [])

    # Concepts (score >= 0.5 only — lower scores are noisy)
    concepts = [
        {"name": c["display_name"], "score": round(c["score"], 2)}
        for c in (signals.get("concepts", []) or [])
        if c.get("score", 0) >= 0.5 and c.get("display_name")
    ]

    # Science stewardship
    st = signals.get("stewardship", {}) or {}
    data_links = [
        {"label": lnk.get("label", ""), "url": lnk.get("url", "")}
        for lnk in (st.get("data_links") or [])
        if lnk.get("url")
    ]
    clinical_trials = len(st.get("clinical_trials") or [])
    funders = list({
        f.get("funder", "").strip()
        for f in (st.get("funding") or signals.get("funding") or [])
        if f.get("funder", "").strip()
    })

    # RRIDs — named research resources cited (antibodies, software, cell lines, etc.)
    rrid_count = int(
        ((signals.get("rrids") or {}).get("europepmc") or {}).get("count", 0) or 0
    )

    # Citation percentile — used for strengths badge, not displayed directly
    percentile = float((signals.get("percentiles") or {}).get("value", 0) or 0)

    return {
        "doi": doi,
        "doi_norm": normalize_doi(doi),
        "title": title,
        "year": year,
        "story_type": stype,
        "venue": venue,
        "citations": cites or 0,
        "mentions": mentions or 0,
        "is_oa": bool(is_oa),
        "file_stem": stem,
        "html_file": stem + ".html",
        # Teaching & open science signals
        "ocw_count":      ocw_count,
        "yt_count":       yt_count,
        "ol_holdings":    ol_holdings,
        "sdg_count":      sdg_count,
        "wiki_count":     wiki_count,
        "concepts":       concepts,
        # Science stewardship
        "data_links":     data_links,
        "clinical_trials": clinical_trials,
        "funders":        funders,
        "rrid_count":     rrid_count,
        "percentile":     percentile,
    }


# ── Author identity key ───────────────────────────────────────────────────────

def author_key(orcid: str, name: str) -> str:
    if orcid:
        return f"orcid:{orcid}"
    return f"name:{normalize_name_key(name)}"


# ── Main build ────────────────────────────────────────────────────────────────

def build_author_index(story_dir: str, min_pubs: int = 2) -> list:
    """
    Returns list of author dicts sorted by pub_count desc.
    Only authors with >= min_pubs distinct publications are included.
    """
    # Only process story files (prefixed with known story types)
    STORY_PREFIXES = ("articlestory_", "bookstory_", "datastory_", "softwarestory_", "data_")
    files = [
        f for f in glob.glob(os.path.join(story_dir, "*.json"))
        if os.path.basename(f).startswith(STORY_PREFIXES)
    ]

    # Load verified affiliations from cache (written by enrich_affiliations.py)
    aff_cache_path = os.path.join(story_dir, "author_affiliations_cache.json")
    if os.path.isfile(aff_cache_path):
        with open(aff_cache_path, encoding="utf-8") as f:
            aff_cache: dict = json.load(f)
        print(f"Loaded affiliation cache: {len(aff_cache)} entries")
    else:
        aff_cache = {}

    # key → { display_name, orcid, pubs: {doi_norm → pub_meta} }
    # Institutions are NOT collected from per-paper data — they're unreliable.
    # OpenAlex sometimes attributes a co-author's institution to another author.
    # Verified affiliations come from enrich_affiliations.py → aff_cache only.
    author_buckets: dict[str, dict] = {}

    for path in sorted(files):
        pub = extract_pub_meta(path)
        if not pub.get("doi"):
            continue

        authors = extract_authors_from_file(path)
        for a in authors:
            if not a["name"]:
                continue
            key = author_key(a["orcid"], a["name"])
            if key not in author_buckets:
                author_buckets[key] = {
                    "key": key,
                    "display_name": a["name"],
                    "orcid": a["orcid"],
                    "institutions": set(),
                    "pubs": {},
                }
            bucket = author_buckets[key]
            # Update ORCID if we now have one
            if a["orcid"] and not bucket["orcid"]:
                bucket["orcid"] = a["orcid"]
            # First name seen wins for display (keep the fullest form)
            if len(a["name"]) > len(bucket["display_name"]):
                bucket["display_name"] = a["name"]
            # Do NOT collect per-paper institutions — they're unreliable.
            # Affiliations come from enrich_affiliations.py cache only.
            # Deduplicate by normalized DOI
            doi_norm = pub["doi_norm"]
            if doi_norm and doi_norm not in bucket["pubs"]:
                bucket["pubs"][doi_norm] = pub

    # Convert and filter
    result = []
    for bucket in author_buckets.values():
        pubs = sorted(bucket["pubs"].values(),
                      key=lambda p: (p.get("year") or 0), reverse=True)
        if len(pubs) < min_pubs:
            continue

        orcid = bucket["orcid"]
        slug = orcid.replace("/", "-") if orcid else re.sub(r"[^\w-]", "-", normalize_name_key(bucket["display_name"]))
        slug = re.sub(r"-+", "-", slug).strip("-")

        total_citations = sum(p.get("citations", 0) for p in pubs)
        total_mentions = sum(p.get("mentions", 0) for p in pubs)
        oa_count = sum(1 for p in pubs if p.get("is_oa"))
        story_types = sorted(set(p["story_type"] for p in pubs))
        years = [p["year"] for p in pubs if p.get("year")]
        year_range = f"{min(years)}–{max(years)}" if len(years) > 1 else (str(years[0]) if years else "")

        # Verified affiliations from cache only (enrich_affiliations.py).
        verified_affs = aff_cache.get(orcid, []) if orcid else []

        # Aggregate teaching & open science signals across pubs
        ocw_total      = sum(p.get("ocw_count",   0) for p in pubs)
        yt_total       = sum(p.get("yt_count",     0) for p in pubs)
        library_total  = sum(p.get("ol_holdings",  0) for p in pubs)
        sdg_total      = sum(p.get("sdg_count",    0) for p in pubs)
        wiki_total     = sum(p.get("wiki_count",   0) for p in pubs)

        # Preprint count (DOI-based detection)
        PREPRINT_PREFIXES = ("10.1101/", "10.21203/", "10.31219/", "10.20944/", "10.2139/")
        preprint_count = sum(
            1 for p in pubs if any(p["doi"].startswith(x) for x in PREPRINT_PREFIXES)
        )

        # Dominant concepts: tally by frequency (sum of scores as weight)
        concept_weights: dict = {}
        for p in pubs:
            for c in (p.get("concepts") or []):
                name = c["name"]
                concept_weights[name] = concept_weights.get(name, 0) + c["score"]
        top_concepts = [
            {"name": n, "weight": round(w, 2)}
            for n, w in sorted(concept_weights.items(), key=lambda x: -x[1])
        ][:20]

        # Science stewardship aggregation
        all_data_links = []
        seen_urls: set = set()
        for p in pubs:
            for lnk in (p.get("data_links") or []):
                url = lnk.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_data_links.append(lnk)
        total_rrids      = sum(p.get("rrid_count",      0) for p in pubs)
        clinical_total   = sum(p.get("clinical_trials",  0) for p in pubs)
        all_funders      = sorted({
            f for p in pubs for f in (p.get("funders") or []) if f
        })
        top10_count      = sum(1 for p in pubs if p.get("percentile", 0) >= 0.90)
        top1_count       = sum(1 for p in pubs if p.get("percentile", 0) >= 0.99)

        # Inferred author strengths (threshold-based badges)
        strengths = []
        oa_rate = oa_count / len(pubs) if pubs else 0
        if "book" in story_types:
            strengths.append("Book Author")
        if "data" in story_types or all_data_links:
            strengths.append("Data Publisher")
        if "software" in story_types:
            strengths.append("Software Developer")
        if preprint_count > 0:
            strengths.append("Preprint Advocate")
        if oa_rate >= 0.8:
            strengths.append("Open Access Champion")
        if total_rrids > 0:
            strengths.append("Methodologist")
        if all_funders:
            strengths.append("Funded Researcher")
        if top10_count > 0:
            strengths.append("High-Impact")
        if ocw_total > 0 or library_total > 0:
            strengths.append("Educator")
        if sdg_total > 0:
            strengths.append("SDG-Aligned")

        result.append({
            "slug": slug,
            "display_name": bucket["display_name"],
            "orcid": orcid,
            "orcid_url": orcid_url(orcid),
            "institutions": verified_affs,
            "pub_count": len(pubs),
            "story_types": story_types,
            "total_citations": total_citations,
            "total_mentions": total_mentions,
            "oa_count": oa_count,
            "year_range": year_range,
            "years": years,
            "page": f"authorstory_{slug}.html",
            "publications": pubs,
            # Teaching & open science
            "preprint_count":  preprint_count,
            "ocw_count":       ocw_total,
            "yt_count":        yt_total,
            "library_count":   library_total,
            "sdg_count":       sdg_total,
            "wiki_count":      wiki_total,
            "top_concepts":    top_concepts,
            # Science stewardship
            "data_links":      all_data_links,
            "total_rrids":     total_rrids,
            "clinical_count":  clinical_total,
            "funders":         all_funders,
            "top10_count":     top10_count,
            "top1_count":      top1_count,
            # Inferred strengths
            "strengths":       strengths,
        })

    result.sort(key=lambda a: (-a["pub_count"], a["display_name"].lower()))
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build authors.json from story JSON files")
    parser.add_argument("--dir", default=".", help="Directory containing story JSON files")
    parser.add_argument("--out", default="authors.json", help="Output path")
    parser.add_argument("--min-pubs", type=int, default=2, help="Minimum publications to include an author")
    args = parser.parse_args()

    print(f"Scanning {args.dir} ...")
    authors = build_author_index(args.dir, min_pubs=args.min_pubs)

    out_path = os.path.join(args.dir, args.out) if not os.path.isabs(args.out) else args.out
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(authors, f, indent=2, ensure_ascii=False)

    print(f"Found {len(authors)} authors with >= {args.min_pubs} publications.")
    print(f"Wrote {out_path}")

    # Also write authors_data.js for the index (strip full publications list to keep it light)
    js_records = []
    for a in authors:
        js_records.append({
            "slug":            a["slug"],
            "display_name":    a["display_name"],
            "orcid":           a["orcid"],
            "orcid_url":       a["orcid_url"],
            "pub_count":       a["pub_count"],
            "story_types":     a["story_types"],
            "total_citations": a["total_citations"],
            "total_mentions":  a["total_mentions"],
            "oa_count":        a["oa_count"],
            "year_range":      a["year_range"],
            "institutions":    a["institutions"][:3],  # top 3 for display
            "page":            a["page"],
        })
    js_path = os.path.join(args.dir, "authors_data.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("// Auto-generated by extract_authors.py — do not edit manually\n")
        f.write(f"window.AUTHORS_DATA = {json.dumps(js_records, ensure_ascii=False, indent=2)};\n")
    print(f"Wrote {js_path}")

    # Summary
    print("\nTop 15 authors:")
    for a in authors[:15]:
        orcid_tag = f" [{a['orcid']}]" if a['orcid'] else ""
        print(f"  {a['display_name']}{orcid_tag}: {a['pub_count']} pubs, "
              f"{a['total_citations']} citations, types={a['story_types']}")


if __name__ == "__main__":
    main()
