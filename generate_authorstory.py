#!/usr/bin/env python3
"""
generate_authorstory.py — render AuthorStory HTML pages from authors.json

Usage:
    python3 generate_authorstory.py [--dir .] [--authors authors.json] [--template authorstory_template.html]

For each author with >= 2 publications in authors.json, writes:
    authorstory_{slug}.html

Requires: jinja2 (pip install jinja2)
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError:
    sys.exit("jinja2 is required: pip install jinja2")


# ── Co-author computation ─────────────────────────────────────────────────────

def compute_coauthors(author: dict, all_authors: list, author_page_map: dict) -> list:
    """
    Return list of co-authors (sorted by shared pub count desc) who appear
    in at least one of this author's publications.
    author_page_map: doi_norm → set of (name, slug) tuples
    """
    my_dois = {p["doi_norm"] for p in author["publications"]}
    coauthor_counts: dict[str, dict] = {}

    for other in all_authors:
        if other["slug"] == author["slug"]:
            continue
        other_dois = {p["doi_norm"] for p in other["publications"]}
        shared = my_dois & other_dois
        if shared:
            coauthor_counts[other["display_name"]] = {
                "name": other["display_name"],
                "shared": len(shared),
                "page": other["page"],
            }

    result = sorted(coauthor_counts.values(), key=lambda x: -x["shared"])
    return result


# ── Timeline data ─────────────────────────────────────────────────────────────

def build_timeline(author: dict) -> list:
    """Return list of {year, article, book, data, software} dicts for Chart.js."""
    by_year: dict[int, dict] = {}
    for pub in author["publications"]:
        year = pub.get("year")
        if not year:
            continue
        if year not in by_year:
            by_year[year] = {"year": year, "article": 0, "book": 0, "data": 0, "software": 0}
        stype = pub.get("story_type", "article")
        by_year[year][stype] = by_year[year].get(stype, 0) + 1

    return sorted(by_year.values(), key=lambda d: d["year"])


# ── HTML existence check ──────────────────────────────────────────────────────

def check_html_exists(pub: dict, story_dir: str) -> bool:
    """Check if a story HTML file exists for this publication."""
    html_path = os.path.join(story_dir, pub["html_file"])
    return os.path.isfile(html_path)


# ── Jinja2 filter ─────────────────────────────────────────────────────────────

def tojson_filter(value, indent=None):
    return json.dumps(value, ensure_ascii=False)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate authorstory HTML pages")
    parser.add_argument("--dir", default=".", help="Story directory (where HTML files live)")
    parser.add_argument("--authors", default="authors.json", help="Path to authors.json")
    parser.add_argument("--template", default="authorstory_template.html", help="Jinja2 template path")
    parser.add_argument("--only", default=None, help="Only generate page for this slug (for testing)")
    args = parser.parse_args()

    story_dir = args.dir

    # Load authors
    authors_path = args.authors if os.path.isabs(args.authors) else os.path.join(story_dir, args.authors)
    with open(authors_path, encoding="utf-8") as f:
        all_authors: list = json.load(f)

    print(f"Loaded {len(all_authors)} authors from {authors_path}")

    # Set up Jinja2
    template_path = args.template if os.path.isabs(args.template) else os.path.join(story_dir, args.template)
    template_dir = os.path.dirname(os.path.abspath(template_path))
    template_file = os.path.basename(template_path)

    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["tojson"] = tojson_filter
    template = env.get_template(template_file)

    # Generate pages
    generated = 0
    skipped = 0

    for author in all_authors:
        if args.only and author["slug"] != args.only:
            continue

        # Annotate each pub with html_exists
        for pub in author["publications"]:
            pub["html_exists"] = check_html_exists(pub, story_dir)

        coauthors = compute_coauthors(author, all_authors, {})
        timeline_data = build_timeline(author)
        pubs_without_year = sum(1 for p in author["publications"] if not p.get("year"))

        html = template.render(
            author=author,
            coauthors=coauthors,
            timeline_data=timeline_data,
            pubs_without_year=pubs_without_year,
        )

        out_path = os.path.join(story_dir, author["page"])
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        generated += 1
        if args.only or generated <= 5:
            print(f"  → {author['page']}  ({author['pub_count']} pubs, {len(coauthors)} co-authors)")

    if not args.only:
        print(f"\nGenerated {generated} author pages in {story_dir}")
    print("Done.")


if __name__ == "__main__":
    main()
