#!/usr/bin/env python3
"""
build_index.py — openscience.works manifest builder
Run from the openscienceworks directory:
    python3 build_index.py
Outputs: stories_data.js (loaded by index.html)
"""

import json
import glob
import os
import re
from html.parser import HTMLParser

# ── helpers ──────────────────────────────────────────────────────────────────

class _TagStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []
    def handle_data(self, d):
        self._parts.append(d)
    def get_text(self):
        return " ".join(self._parts)

def strip_html(raw):
    if not raw:
        return ""
    p = _TagStripper()
    p.feed(raw)
    return re.sub(r"\s+", " ", p.get_text()).strip()

def first_sentence(html_str, max_chars=200):
    """Return first meaningful sentence from an HTML blob."""
    text = strip_html(html_str)
    # Skip short headings / labels
    for sent in re.split(r"(?<=[.!?])\s+", text):
        sent = sent.strip()
        if len(sent) > 40:
            return sent[:max_chars] + ("…" if len(sent) > max_chars else "")
    return text[:max_chars]

def get_val(d, *keys, default=None):
    """Safely navigate nested dicts."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
        if d is None:
            return default
    return d

# ── extract one story ─────────────────────────────────────────────────────────

def extract(filepath):
    with open(filepath, encoding="utf-8") as f:
        d = json.load(f)

    signals = d.get("signals", {}) or {}
    basename = os.path.basename(filepath)
    html_file = basename.replace(".json", ".html")

    # ── type ── (filename prefix wins for data/software, then work_type, then story_type)
    work_type = d.get("work_type", "")
    if basename.startswith("datastory") or work_type == "dataset":
        story_type = "DataStory"
    elif basename.startswith("softwarestory") or work_type in ("software", "other") and basename.startswith("softwarestory"):
        story_type = "SoftwareStory"
    else:
        story_type = d.get("story_type", "")
        if not story_type:
            if basename.startswith("articlestory"):
                story_type = "ArticleStory"
            elif basename.startswith("bookstory"):
                story_type = "BookStory"
            else:
                story_type = "Story"

    # ── title ──
    title = d.get("title", "")

    # ── doi / id ──
    doi = d.get("doi") or d.get("book_id") or ""

    # ── year ──
    year = None
    bib = d.get("bibliographic")
    if isinstance(bib, dict):
        year = bib.get("year") or bib.get("published_year")
    if not year:
        year = d.get("publication_year")
    if not year:
        # identifiers.pub_year (used by dataset / software records)
        ids = d.get("identifiers") or {}
        if isinstance(ids, dict):
            year = ids.get("pub_year")
    if not year:
        # Try to find in signals
        pub = signals.get("published_metrics") or {}
        if isinstance(pub, dict):
            year = pub.get("year")
    if not year and doi:
        # Recover year from DOI patterns
        # bioRxiv/medRxiv, Elsevier: /2023.01.15... or .2023.
        m = re.search(r"/20(\d\d)\.", doi)
        if m:
            year = 2000 + int(m.group(1))
        if not year:
            m = re.search(r"\.(20\d\d)\.", doi)
            if m:
                y = int(m.group(1))
                if 2000 <= y <= 2030:
                    year = y
        if not year:
            # Springer/Nature short suffix: s12345-023- → 2023
            m = re.search(r"s\d+[-.](\d{3})[-.]", doi)
            if not m:
                m = re.search(r"s\d+-(\d{3})-", doi)
            if m:
                yr2 = int(m.group(1)) % 100
                y = 2000 + yr2 if yr2 <= 30 else 1900 + yr2
                if 2000 <= y <= 2030:
                    year = y
    year = int(year) if year else None

    # ── venue / publisher ──
    venue_name = ""
    publisher_name = ""
    venue = d.get("venue")
    if isinstance(venue, dict):
        venue_name = venue.get("name", "") or ""
        publisher_name = venue.get("publisher", "") or ""
    elif isinstance(venue, str):
        venue_name = venue
    pub = d.get("publisher")
    if pub and not publisher_name:
        publisher_name = str(pub)
    display_venue = venue_name or publisher_name or ""

    # ── concepts ──
    concepts = []
    raw_concepts = signals.get("concepts") or d.get("concepts") or []
    for c in raw_concepts:
        if isinstance(c, dict):
            name = c.get("display_name") or c.get("name") or ""
        elif isinstance(c, str):
            name = c
        else:
            continue
        if name and name not in concepts:
            concepts.append(name)
    concepts = concepts[:8]  # keep top 8

    # ── roles ──
    roles = []
    for r in d.get("roles", []):
        if isinstance(r, dict):
            label = r.get("label", "")
            if label and label not in roles:
                roles.append(label)
        elif isinstance(r, str):
            roles.append(r)
    # Normalise casing
    roles = [r for r in roles if r]

    # ── OA ──
    is_oa = signals.get("is_oa")
    if is_oa is None:
        acc = d.get("access")
        if isinstance(acc, dict):
            is_oa = acc.get("is_oa")
    oa_status = signals.get("oa_status") or ""
    if not oa_status:
        acc = d.get("access")
        if isinstance(acc, dict):
            oa_status = acc.get("oa_status", "")

    # ── citation count ──
    citation_count = signals.get("citation_count")
    if citation_count is None:
        impact = d.get("impact") or {}
        if isinstance(impact, dict):
            cits = impact.get("citations") or []
            citation_count = len(cits) if cits else 0
        else:
            citation_count = 0
    if isinstance(citation_count, dict):
        citation_count = citation_count.get("total", 0) or 0
    try:
        citation_count = int(citation_count)
    except (TypeError, ValueError):
        citation_count = 0

    # ── SDGs ──
    sdgs = signals.get("sdgs") or []
    sdg_ids = []
    if isinstance(sdgs, list):
        for s in sdgs:
            if isinstance(s, dict):
                sid = s.get("id") or s.get("display_name") or ""
                if sid:
                    sdg_ids.append(str(sid))
            elif isinstance(s, str):
                sdg_ids.append(s)
    has_sdgs = len(sdg_ids) > 0

    # ── teaching adoption ──
    # Only count as True when there are actual substantive signals, not just
    # a bare worldcat_url stub that appears on every record.
    ta = signals.get("teaching_adoption")
    has_teaching = False
    if isinstance(ta, dict):
        has_teaching = (
            bool(ta.get("ocw"))                           # OCW mentions list
            or bool(ta.get("youtube"))                    # YouTube lectures
            or bool(ta.get("otl"))                        # Open Textbook Library
            or bool(ta.get("syllabi"))                    # syllabi list
            or (isinstance(ta.get("holdings"), dict)
                and ta["holdings"].get("ol_holdings", 0) > 0)  # real OL holdings
        )
    elif isinstance(ta, list):
        has_teaching = len(ta) > 0
    elif isinstance(ta, (int, float)):
        has_teaching = ta > 0
    # Sub-counts for richer display
    ta_ocw_count = len(ta.get("ocw") or []) if isinstance(ta, dict) else 0
    ta_yt_count  = len(ta.get("youtube") or []) if isinstance(ta, dict) else 0
    ta_ol_count  = (ta.get("holdings") or {}).get("ol_holdings", 0) if isinstance(ta, dict) else 0
    ta_otl       = bool(ta.get("otl")) if isinstance(ta, dict) else False

    # ── peer review ──
    pr = signals.get("peer_reviews")
    has_peer_review = bool(pr and (
        (isinstance(pr, dict) and any(pr.values())) or
        (isinstance(pr, list) and len(pr) > 0)
    ))

    # ── reuse / data ──
    rg = signals.get("reuse_graph")
    has_reuse = bool(rg and (
        (isinstance(rg, dict) and any(rg.values())) or
        (isinstance(rg, list) and len(rg) > 0)
    ))

    # ── attention / events ──
    att = d.get("attention") or signals.get("attention_summary") or {}
    event_count = 0
    if isinstance(att, dict):
        event_count = att.get("event_count") or att.get("total") or 0
    try:
        event_count = int(event_count)
    except (TypeError, ValueError):
        event_count = 0

    # ── downloads ──
    # OA books (OAPEN): impact.downloads.totals.downloads
    # Datasets / software (DataCite): signals.datacite.downloads
    download_count = 0
    impact_block = d.get("impact") or {}
    if isinstance(impact_block, dict):
        dl = impact_block.get("downloads") or {}
        if isinstance(dl, dict):
            totals = dl.get("totals") or {}
            download_count = totals.get("downloads", 0) or 0
    if not download_count:
        dc = signals.get("datacite") or {}
        if isinstance(dc, dict):
            raw = dc.get("downloads") or 0
            # DataCite may return a string like "3,224"
            try:
                download_count = int(str(raw).replace(",", "").strip())
            except (TypeError, ValueError):
                download_count = 0
    try:
        download_count = int(download_count)
    except (TypeError, ValueError):
        download_count = 0

    # ── institutions — unique affiliations from template_authors ──
    institutions = []
    seen_inst = set()
    for a in signals.get("template_authors") or []:
        if not isinstance(a, dict):
            continue
        aff = a.get("affiliation") or ""
        if aff and aff not in seen_inst:
            institutions.append(aff)
            seen_inst.add(aff)
    institutions = institutions[:10]  # cap per story

    # ── narrative excerpt ──
    narrative = d.get("narrative") or ""
    excerpt = first_sentence(narrative) if narrative else ""

    # ── cover image ──
    cover_url = signals.get("cover_url") or d.get("cover_image_url") or ""

    # ── authors (first 3) ──
    authors = []
    for a in (d.get("authors") or [])[:3]:
        if isinstance(a, dict):
            name = a.get("name", "")
        elif isinstance(a, str):
            # may be "Name|||orcid"
            name = a.split("|||")[0]
        else:
            continue
        if name:
            authors.append(name)
    author_str = ", ".join(authors)
    if len(d.get("authors") or []) > 3:
        author_str += " et al."

    return {
        "file": html_file,
        "title": title,
        "type": story_type,
        "doi": doi,
        "year": year,
        "venue": display_venue,
        "venue_name": venue_name,
        "publisher": publisher_name,
        "concepts": concepts,
        "roles": roles,
        "is_oa": bool(is_oa) if is_oa is not None else None,
        "oa_status": oa_status,
        "citation_count": citation_count,
        "event_count": event_count,
        "has_sdgs": has_sdgs,
        "sdg_ids": sdg_ids,
        "has_teaching": has_teaching,
        "ta_ocw": ta_ocw_count,
        "ta_youtube": ta_yt_count,
        "ta_ol_holdings": ta_ol_count,
        "ta_otl": ta_otl,
        "has_peer_review": has_peer_review,
        "has_reuse": has_reuse,
        "excerpt": excerpt,
        "cover_url": cover_url,
        "authors": author_str,
        "institutions": institutions,
        "download_count": download_count,
    }

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    pattern = os.path.join(base, "*.json")
    files = sorted(glob.glob(pattern))

    # Exclude any non-story JSON (e.g. package.json)
    story_prefixes = ("articlestory_", "bookstory_", "datastory_", "softwarestory_")
    files = [f for f in files if os.path.basename(f).startswith(story_prefixes)]

    stories = []
    errors = []
    for f in files:
        try:
            stories.append(extract(f))
        except Exception as e:
            errors.append((f, str(e)))

    # Sort: most cited first
    stories.sort(key=lambda s: s["citation_count"], reverse=True)

    # ── aggregate stats for the landing hero ──
    total = len(stories)
    total_articles = sum(1 for s in stories if s["type"] == "ArticleStory")
    total_books = sum(1 for s in stories if s["type"] == "BookStory")
    total_data = sum(1 for s in stories if s["type"] == "DataStory")
    total_software = sum(1 for s in stories if s["type"] == "SoftwareStory")
    total_oa = sum(1 for s in stories if s["is_oa"] is True)
    total_citations = sum(s["citation_count"] for s in stories)
    all_concepts = {}
    for s in stories:
        for c in s["concepts"]:
            all_concepts[c] = all_concepts.get(c, 0) + 1
    top_concepts = sorted(all_concepts.items(), key=lambda x: -x[1])[:30]
    num_disciplines = len([c for c, n in top_concepts if n >= 2])

    stats = {
        "total": total,
        "total_articles": total_articles,
        "total_books": total_books,
        "total_data": total_data,
        "total_software": total_software,
        "total_oa": total_oa,
        "pct_oa": round(100 * total_oa / total) if total else 0,
        "total_citations": total_citations,
        "num_disciplines": num_disciplines,
    }

    out_path = os.path.join(base, "stories_data.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("// Auto-generated by build_index.py — do not edit manually\n")
        f.write("window.STORIES_DATA = ")
        json.dump(stories, f, ensure_ascii=False, indent=0)
        f.write(";\n")
        f.write("window.STORIES_STATS = ")
        json.dump(stats, f, ensure_ascii=False)
        f.write(";\n")

    print(f"✓ Wrote {total} stories to stories_data.js")
    print(f"  Articles: {total_articles}  Books: {total_books}  Data: {total_data}  Software: {total_software}")
    print(f"  OA: {total_oa} ({stats['pct_oa']}%)   Total citations: {total_citations:,}")
    if errors:
        print(f"\n⚠ {len(errors)} errors:")
        for fname, err in errors:
            print(f"  {os.path.basename(fname)}: {err}")

if __name__ == "__main__":
    main()
