# Repo Restructure Handover: bookstories as engine, openscienceworks as frontend

## Goal

Enforce a clean separation:
- **bookstories** (private) — build pipeline: all Python logic, enrichment, generators, templates
- **openscienceworks** (public) — static site output only: HTML, CSS, JS, generated data files

openscienceworks should contain nothing a browser doesn't need. No Python scripts, no Jinja2 templates, no cache files.

## Current state (what's wrong)

These files landed in openscienceworks but belong in bookstories:

| File | Move to |
|------|---------|
| `extract_authors.py` | `bookstories/generator/` |
| `generate_authorstory.py` | `bookstories/generator/` |
| `authorstory_template.html` | `bookstories/generator/templates/` |
| `backfill_years.py` | `bookstories/scripts/` |
| `enrich_affiliations.py` | `bookstories/scripts/` |
| `years_cache.json` | `bookstories/bookstories/data/` (or gitignored) |
| `author_affiliations_cache.json` | `bookstories/bookstories/data/` (or gitignored) |

These files should stay in openscienceworks (they are outputs):

- `authors.json` / `authors_data.js` — consumed by the platform JS
- `authorstory_*.html` — generated pages
- `articlestory_*.html`, `bookstory_*.html` etc. — generated pages
- All static assets (CSS, JS, images)

## What needs updating after the move

### 1. `generate_authorstory.py` — `--dir` argument
Currently defaults to `.` (openscienceworks). After moving to bookstories, the default should point to the openscienceworks checkout:

```python
parser.add_argument("--dir", default="../openscienceworks", help="Output directory")
parser.add_argument("--template", default="generator/templates/authorstory_template.html")
```

Or better, read from an env var / config file so the path isn't hardcoded.

### 2. `extract_authors.py` — input and output paths
Reads story JSONs from `--dir` (openscienceworks) and writes `authors.json` there. That's fine — openscienceworks is still the data source for story JSONs. Just the script itself moves.

### 3. `backfill_years.py` and `enrich_affiliations.py`
Both operate on story JSONs in openscienceworks. After moving, update default `--dir` similarly.

### 4. Cache files
`years_cache.json` and `author_affiliations_cache.json` are build-time caches, not site content. Options:
- Move to `bookstories/bookstories/data/` alongside `social_cache.json`
- Or add to `.gitignore` in openscienceworks and keep them local

### 5. `.gitignore` additions for openscienceworks
```
years_cache.json
author_affiliations_cache.json
*.py
```

## bookstories generator structure (target)

```
bookstories/
  generator/
    extract_authors.py       ← moved
    generate_authorstory.py  ← moved
    templates/
      authorstory_template.html  ← moved
  scripts/
    backfill_years.py        ← moved
    enrich_affiliations.py   ← moved
    fetch_wiki_mentions.py   ← already here
    overnight_social_hunter_refresh.py
    ...
  bookstories/
    data/
      years_cache.json       ← moved
      author_affiliations_cache.json  ← moved
      social_cache.json      ← already here
```

## Suggested run sequence (after restructure)

```bash
# From bookstories root, targeting openscienceworks as output dir
PYTHONPATH=. python3 scripts/backfill_years.py --dir ../openscienceworks
PYTHONPATH=. python3 scripts/enrich_affiliations.py --dir ../openscienceworks
PYTHONPATH=. python3 generator/extract_authors.py --dir ../openscienceworks --out ../openscienceworks/authors.json
PYTHONPATH=. python3 generator/generate_authorstory.py --dir ../openscienceworks
```

## Notes

- `transform_articlestory.py`, `transform_bookstory.py` etc. are already in openscienceworks and are one-off UX patchers — decide whether these move too (they probably should)
- `build_index.py` in openscienceworks builds the site index — same situation
- Phase 2 work (clickable author links — see `PHASE2_HANDOVER.md`) should be implemented as a script in `bookstories/scripts/` or `bookstories/generator/`, not in openscienceworks
