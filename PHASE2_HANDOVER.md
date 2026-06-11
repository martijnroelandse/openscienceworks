# Phase 2 Handover: Clickable Author Names on Story Pages

## What this is

Every article/book/data/software story page has a "Contributors & affiliations" section listing authors. Phase 2 makes those author names clickable links to their AuthorStory pages (`authorstory_{slug}.html`), where one exists.

## Current HTML structure (story pages)

Authors are rendered as `<li>` items inside a `<ul>` in the Contributors section. Each `<li>` contains a `<strong>` with the name and optionally an `.orcid-badge` anchor with the ORCID as the `href`:

```html
<li style="margin-bottom: 0.4rem;">
    <strong>Gerald L. Andriole</strong>
    <span class="badge">First</span>
    <a class="orcid-badge" href="0000-0003-4033-2352" target="_blank">ORCID</a>
</li>

<!-- Author without ORCID — no page exists for these -->
<li style="margin-bottom: 0.4rem;">
    <strong>Robert L. Grubb</strong>
</li>
```

## AuthorStory slug format

- **ORCID-identified authors** (majority): slug = ORCID ID, e.g. `0000-0003-4033-2352` → page = `authorstory_0000-0003-4033-2352.html`
- **Name-only authors** (no ORCID): slug = kebab-case name, e.g. `authorstory_andrew-matus.html`

The complete author index is in `authors.json` — each entry has `slug`, `page`, `display_name`, and `orcid`.

## The approach

**Primary (reliable):** For `<li>` elements that have an `.orcid-badge` link, the ORCID is already in the `href`. Check if `authorstory_{orcid}.html` exists — if yes, wrap the `<strong>` in a link:

```html
<!-- before -->
<strong>Gerald L. Andriole</strong>

<!-- after -->
<strong><a href="authorstory_0000-0003-4033-2352.html">Gerald L. Andriole</a></strong>
```

**Secondary (optional):** For authors without ORCID, do a name-lookup against `authors.json` to catch name-slug matches.

## Implementation options

### Option A — Post-process script (recommended)
Write `patch_author_links.py` that uses BeautifulSoup to patch all existing story HTMLs in-place:

```python
# Pseudocode
for html_file in glob("articlestory_*.html") + glob("bookstory_*.html") + ...:
    soup = BeautifulSoup(html_file)
    for li in soup.find_all("li", ...):  # Contributors section
        orcid_a = li.find("a", class_="orcid-badge")
        strong = li.find("strong")
        if not strong or strong.find("a"):  # skip if already linked
            continue
        if orcid_a:
            orcid = orcid_a["href"]
            page = f"authorstory_{orcid}.html"
            if os.path.exists(page):
                # wrap strong content in <a>
                ...
```

### Option B — Template change
Modify the source templates/generators so future regenerations include the links natively. Requires understanding `transform_articlestory.py` and similar scripts.

Option A is faster and doesn't require understanding the full generation pipeline.

## Files to know

| File | Purpose |
|------|---------|
| `authors.json` | Author index: slug, page, display_name, orcid, pub_count |
| `authorstory_template.html` | Jinja2 template for author pages |
| `generate_authorstory.py` | Renders author pages from authors.json |
| `extract_authors.py` | Builds authors.json from story JSONs |
| `transform_articlestory.py` | Post-processor for article story HTML (UX improvements) |
| `articlestory_*.html` | Article story pages (patch target) |
| `bookstory_*.html` | Book story pages (patch target) |

## Scope

- Target: all `articlestory_`, `bookstory_`, `datastory_`, `softwarestory_` HTML files
- Only link authors where an `authorstory_*.html` page actually exists (don't link stubs)
- Don't double-link if the script is run twice (check `strong.find("a")`)
- The ORCID badge link itself should remain as-is

## What was already done (Phase 1)

- `extract_authors.py` — builds authors.json with full signals (citations, mentions, teaching, SDGs, stewardship, strengths badges)
- `generate_authorstory.py` — renders 189 author pages
- `authorstory_template.html` — layout: header card → timeline → strengths/signals/stewardship → co-authors → concepts → publications
- `backfill_years.py` — fills missing `published_year` from Crossref API
- `enrich_affiliations.py` — ORCID employment history (144 authors enriched)
- `social_hunter.get_wiki_mentions()` updated to use Wikimedia `exturlusage` API (cite-template citations) instead of full-text search
