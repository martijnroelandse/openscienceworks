#!/usr/bin/env python3
"""
openscience.works DataStory / SoftwareStory UX Transformer
Applies the same 6 UX improvements as the article/book transforms,
adapted for the sections that appear in datastory and softwarestory pages.
"""

import re
import json
from pathlib import Path
from bs4 import BeautifulSoup

SRC = Path("/sessions/loving-great-brown/mnt/openscienceworks/datastory_10.5061_dryad.585t4.html")
DST = Path("/sessions/loving-great-brown/mnt/openscienceworks/datastory_10.5061_dryad.585t4_new.html")

html = SRC.read_text("utf-8")
soup = BeautifulSoup(html, "html.parser")


# ══════════════════════════════════════════════════════════════
# STEP 1 — Extract citation table rows to JS data array
# ══════════════════════════════════════════════════════════════
cit_section = None
for s in soup.find_all("section"):
    h2 = s.find("h2")
    if h2 and "Citations" in h2.get_text() and "context" not in h2.get_text().lower() and "who" not in h2.get_text().lower():
        cit_section = s
        break

rows_data = []
if cit_section:
    tbody = cit_section.find("tbody")
    if tbody:
        for tr in tbody.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            year  = cells[0].get_text(strip=True)
            title = cells[1].get_text(strip=True)
            venue = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            doi_text = doi_url = ""
            if len(cells) > 3:
                a = cells[3].find("a")
                if a:
                    doi_text = a.get_text(strip=True)
                    doi_url  = a.get("href", "")
                else:
                    doi_text = cells[3].get_text(strip=True)
            rows_data.append({"year": year, "title": title,
                              "venue": venue, "doi": doi_text, "doi_url": doi_url})
        tbody.clear()
        tbody["id"] = "cit-tbody"

print(f"Extracted {len(rows_data)} citation rows")


# ══════════════════════════════════════════════════════════════
# STEP 2 — Extract key stats for the stats strip
# ══════════════════════════════════════════════════════════════
def first_match(pattern, text, default="—"):
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else default

raw = str(soup)

downloads   = first_match(r'Downloads.*?:</strong>\s*([\d,]+)', raw, "")
views       = first_match(r'Views.*?:</strong>\s*([\d,]+)', raw, "")
total_cit   = first_match(r'Total Citations.*?</strong>\s*([\d,]+)', raw, "0")
total_men   = first_match(r'Total Online mentions.*?</strong>\s*([\d,]+)', raw, "—")
top_badge   = first_match(r'(Top \d+% Cited)', raw, "")

# OA status
oa_status = ""
for _li in soup.find_all("li"):
    _t = _li.get_text(" ", strip=True)
    if "OA status" in _t:
        oa_status = _t.replace("OA status:", "").strip()
        break

# Teaching signals
yt_count     = len(re.findall(r'youtube\.com/watch', raw))
has_worldcat = "worldcat.org" in raw.lower()
has_ocw      = bool(re.search(r'OpenCourseWare|open.*?syllab', raw, re.I))
has_wiki     = "wikipedia.org" in raw.lower()
datasets     = list(dict.fromkeys(re.findall(
                r'zenodo\.org|figshare\.com|dryad|b2share|pangaea', raw, re.I)))

grant_count = 0
country_count = 0

# Country count
for _el in soup.find_all(["section", "div"]):
    if "Global Reach" in _el.get_text()[:300]:
        _ctags = _el.find_all("span", class_="tag")
        country_count = sum(
            1 for t in _ctags
            if re.search(r'\(\d+\)\s*$', t.get_text(strip=True))
        )
        if country_count:
            break


# ══════════════════════════════════════════════════════════════
# STEP 3 — Add anchor IDs to main sections
# ══════════════════════════════════════════════════════════════
SECTION_MAP = {
    "The Story So Far":            "sec-story",
    "Impact metrics":              "sec-impact",
    "Inferred roles":              "sec-roles",
    "Access":                      "sec-access",
    "Attention landscape":         "sec-mentions",
    "Citation context":            "sec-credibility",
    "Scientific Stewardship":      "sec-stewardship",
    "Who is citing":               "sec-citing",
    "Teaching, Practice":          "sec-teaching",
    "Contributors":                "sec-contributors",
    "Concepts & topics":           "sec-concepts",
    "Citations":                   "sec-citations",
}

def tag_sections():
    for el in soup.find_all(["section", "div"]):
        h2 = el.find("h2")
        if not h2:
            continue
        txt = h2.get_text()
        for label, sec_id in SECTION_MAP.items():
            if label.lower() in txt.lower():
                if not el.get("id"):
                    el["id"] = sec_id
                break

tag_sections()

hero = soup.find("header", class_="hero")
if hero:
    hero["id"] = "sec-hero"


# ══════════════════════════════════════════════════════════════
# STEP 3a — Enrich hero badges with tooltips and source labels
# ══════════════════════════════════════════════════════════════

BADGE_ENHANCEMENTS = {
    "methodologically supported": {
        "title": "scite found more citations supporting than contrasting this work's methodology",
        "suffix": "· scite",
    },
    "linked to data": {
        "title": "Linked research datasets are registered via DataCite or a similar registry",
        "suffix": "· DataCite",
    },
    "clinical trial": {
        "title": "This study is a registered clinical trial",
        "suffix": "· registered",
    },
    "correction published": {
        "title": "A correction or erratum has been published for this work — see publisher site",
        "suffix": "· notice",
    },
    "expression of concern": {
        "title": "The publisher has issued an expression of concern about this work",
        "suffix": "· notice",
    },
    "retracted": {
        "title": "This work has been retracted by the publisher",
        "suffix": "· notice",
    },
    "peer-reviewed": {
        "title": "Published in a peer-reviewed academic journal",
        "suffix": "· journal",
    },
    "early sharing": {
        "title": "An early or preprint version of this work was shared before formal publication",
        "suffix": "· preprint",
    },
    "proven reuse": {
        "title": "This dataset or software has been reused in downstream publications",
        "suffix": "· DataCite",
    },
}

DISCIPLINE_ENHANCEMENTS = {
    "open access (gold)": {
        "label": "Access",
        "title": "Immediate free access with an open licence — published in a fully OA venue",
    },
    "open access (hybrid)": {
        "label": "Access",
        "title": "Free to read in a subscription journal; OA enabled by author or institution payment",
    },
    "open access (green)": {
        "label": "Access",
        "title": "Freely available via an institutional or subject repository (self-archiving)",
    },
    "open access (bronze)": {
        "label": "Access",
        "title": "Free to read on the publisher's site but without an explicit open licence",
    },
    "open access (diamond)": {
        "label": "Access",
        "title": "Fully open access with no charges to authors or readers",
    },
    "humanities": {
        "label": "Field",
        "title": "Classified in Humanities disciplines (literature, philosophy, history, arts, etc.)",
    },
    "social sciences": {
        "label": "Field",
        "title": "Classified in Social Sciences (sociology, economics, political science, etc.)",
    },
    "stem": {
        "label": "Field",
        "title": "Science, Technology, Engineering & Mathematics",
        "expand": "STEM",
    },
    "biomedicine": {
        "label": "Field",
        "title": "Classified in Biomedicine or Life Sciences",
    },
    "unknown": {
        "label": "Field",
        "title": "Subject classification not available for this work",
        "expand": "Unclassified",
    },
}

def enrich_hero_badges(hero_el, bs_soup):
    badge_div = hero_el.find(
        "div",
        style=lambda x: x and "flex-wrap: wrap" in x and "margin-top: 0.75rem" in x,
    )
    if badge_div:
        for span in badge_div.find_all("span", recursive=False):
            raw_text = span.get_text(strip=True).lower().rstrip(" ↗")
            for badge_key, enh in BADGE_ENHANCEMENTS.items():
                if badge_key in raw_text:
                    span["title"] = enh["title"]
                    sfx = bs_soup.new_tag(
                        "span",
                        style=(
                            "opacity:0.55;font-weight:400;font-size:0.65em;"
                            "margin-left:0.35em;text-transform:none;letter-spacing:0;"
                        ),
                    )
                    sfx.string = enh["suffix"]
                    span.append(sfx)
                    break
    for db in hero_el.find_all("div", class_="discipline-badge"):
        raw_text = db.get_text(strip=True)
        key = raw_text.lower()
        for disc_key, enh in DISCIPLINE_ENHANCEMENTS.items():
            if disc_key in key:
                db["title"] = enh["title"]
                display_text = enh.get("expand", raw_text)
                label_str    = enh["label"]
                svg = db.find("svg")
                db.clear()
                if svg:
                    db.append(svg)
                frag = BeautifulSoup(
                    f'<span style="opacity:0.58;font-size:0.72em;font-weight:500;'
                    f'margin-right:0.25em;text-transform:uppercase;letter-spacing:0.04em;'
                    f'vertical-align:middle;">{label_str}:</span>'
                    f'<span style="vertical-align:middle;">{display_text}</span>',
                    "html.parser",
                )
                db.append(frag)
                break

if hero:
    enrich_hero_badges(hero, soup)
    print("Enriched hero badges")


# ══════════════════════════════════════════════════════════════
# STEP 3b — Redesign Inferred Roles section (if present)
# ══════════════════════════════════════════════════════════════

ROLE_LOOKUP = [
    ("scholarly",        "academic",   "Foundational building block cited heavily in core academic journals and monographs."),
    ("rapid uptake",     "academic",   "Accumulated high citations or downloads unusually fast after publication."),
    ("synthesis",        "academic",   "Frequently cited in literature reviews and meta-analyses as a shorthand reference."),
    ("methodological",   "academic",   "Standard protocol or framework used as a tool by other researchers."),
    ("evidence",         "academic",   "Explicitly applied as hard data or methodology — high 'supporting' citation tallies."),
    ("usage-driven",     "readership", "Value through direct consumption: high downloads, HTML views, or library holdings."),
    ("pedagogical",      "readership", "Widely adopted for teaching in OER syllabi, reading lists, or textbooks."),
    ("public discourse", "public",     "Heavy social-platform engagement — the work has sparked ongoing community conversation."),
    ("public visibility","public",     "Trusted public reference cited on Wikipedia, Stack Exchange, or non-academic wikis."),
    ("high-visibility",  "public",     "Mentioned in mainstream news, broadsheets, or high-impact professional media."),
    ("sustainability",   "practical",  "Cited in government reports, WHO/NGO briefs, or UN policy documents."),
    ("policy",           "practical",  "Cited in government reports, WHO/NGO briefs, or UN policy documents."),
    ("commercial",       "practical",  "Present on Amazon, Goodreads, or in patents — commercial or consumer crossover."),
]

DOMAINS = {
    "academic":   {"label":"Academic & Scientific",     "icon":"🎓","dot":"#3b82f6","str_bg":"#dbeafe","str_c":"#1d4ed8","lbl_c":"#1d4ed8","pill_cls":"role-pill-academic"},
    "readership": {"label":"Readership & Educational",  "icon":"📚","dot":"#8b5cf6","str_bg":"#ede9fe","str_c":"#6d28d9","lbl_c":"#7c3aed","pill_cls":"role-pill-readership"},
    "public":     {"label":"Public Engagement & Media", "icon":"📢","dot":"#f59e0b","str_bg":"#fef3c7","str_c":"#92400e","lbl_c":"#b45309","pill_cls":"role-pill-public"},
    "practical":  {"label":"Practical & Real-World",    "icon":"🏛","dot":"#10b981","str_bg":"#dcfce7","str_c":"#166534","lbl_c":"#065f46","pill_cls":"role-pill-practical"},
}

def parse_role_tag(text):
    m = re.match(r'^(.*?)\s*\((\d+\.\d+)\)\s*$', text.strip())
    return (m.group(1).strip(), float(m.group(2))) if m else (text.strip(), 0.5)

def lookup_role(name):
    n = name.lower()
    for substr, domain, desc in ROLE_LOOKUP:
        if substr in n:
            return domain, desc
    return "academic", "Heuristic role based on citation and usage signals from the literature."

def strength(score):
    if score >= 0.80: return "Strong"
    if score >= 0.50: return "Moderate"
    if score >= 0.20: return "Emerging"
    return "Weak"

def opacity(score):
    if score >= 0.80: return "1"
    if score >= 0.50: return "0.9"
    if score >= 0.20: return "0.75"
    return "0.6"

roles_sec = soup.find(id="sec-roles")
if roles_sec:
    tags_div = roles_sec.find("div", style=re.compile(r"display\s*:\s*flex", re.I))
    muted_p  = roles_sec.find("p", class_="muted")

    if tags_div:
        parsed = []
        for span in tags_div.find_all("span", class_="tag"):
            name, score = parse_role_tag(span.get_text(strip=True))
            domain, desc = lookup_role(name)
            parsed.append({"name": name, "score": score, "domain": domain, "desc": desc})

        dom_order, dom_roles = [], {}
        for r in parsed:
            d = r["domain"]
            if d not in dom_roles:
                dom_order.append(d)
                dom_roles[d] = []
            dom_roles[d].append(r)

        groups_html = ""
        for dom in dom_order:
            dinfo = DOMAINS[dom]
            pills = ""
            for r in dom_roles[dom]:
                str_lbl  = strength(r["score"])
                op       = opacity(r["score"])
                desc_safe = r["desc"].replace('"', '&quot;')
                pills += (
                    f'<span class="role-pill {dinfo["pill_cls"]}" '
                    f'style="opacity:{op};" title="{desc_safe}">'
                    f'<span class="role-dot" style="background:{dinfo["dot"]};"></span>'
                    f'{r["name"]}'
                    f'<span class="role-strength" style="background:{dinfo["str_bg"]};color:{dinfo["str_c"]};">'
                    f'{str_lbl}</span></span>'
                )
            groups_html += (
                f'<div class="roles-domain">'
                f'<div class="roles-domain-label" style="color:{dinfo["lbl_c"]};">'
                f'{dinfo["icon"]} {dinfo["label"]}</div>'
                f'<div class="roles-row">{pills}</div></div>'
            )

        legend = (
            '<div class="roles-legend">'
            '<span class="roles-leg-item"><span class="roles-leg-dot" style="background:#374151;"></span>Strong (≥0.80)</span>'
            '<span class="roles-leg-item"><span class="roles-leg-dot" style="background:#9ca3af;"></span>Moderate (0.50–0.79)</span>'
            '<span class="roles-leg-item"><span class="roles-leg-dot" style="background:#d1d5db;"></span>Emerging (&lt;0.50)</span>'
            '</div>'
        )
        new_subhead = (
            '<p class="muted" style="margin-top:-.2rem;margin-bottom:.85rem;">'
            'Heuristic signals from citation composition, usage, and media activity. '
            '<a href="https://www.openscience.works/about.html" target="_blank" '
            'style="color:#2563eb;text-decoration:none;font-weight:600;">Learn about all roles ↗</a>'
            '</p>'
        )
        new_block = BeautifulSoup(new_subhead + groups_html + legend, "html.parser")

        if muted_p:
            muted_p.replace_with(new_block)
            tags_div.decompose()
        else:
            tags_div.replace_with(new_block)

        print(f"Redesigned Inferred Roles: {len(parsed)} roles across {len(dom_order)} domain(s)")
    else:
        print("  No roles tags div found — skipping roles redesign")
else:
    print("  No sec-roles section — skipping roles redesign")


# ══════════════════════════════════════════════════════════════
# STEP 3c — Enrich Impact Metrics section
# ══════════════════════════════════════════════════════════════

def make_sparkline(labels, values, width=120, height=36):
    if not values or max(values, default=0) == 0:
        return ""
    mx = float(max(values))
    n  = len(values)
    pts = []
    for i, v in enumerate(values):
        x = i / max(n - 1, 1) * width
        y = height - (v / mx) * (height - 4) - 2
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    area = ("M" + pts[0] + " " + " ".join("L" + p for p in pts[1:])
            + f" L{width:.1f},{height:.1f} L0,{height:.1f} Z")
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block;overflow:visible;">'
        f'<path d="{area}" fill="#ccfbf1" opacity="0.6"/>'
        f'<polyline points="{poly}" fill="none" stroke="#0d9488" '
        f'stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>'
        f'</svg>'
    )

# Primary card: Downloads (teal theme for data/software)
if downloads:
    dl_card = (
        '<div class="im-card im-card-dl-primary">'
        '<div class="im-card-top"><div>'
        f'<div class="im-num" style="color:#0d9488;">{downloads}</div>'
        '<div class="im-label">Downloads</div>'
        '</div></div>'
        '</div>'
    )
elif views:
    dl_card = (
        '<div class="im-card im-card-dl-primary">'
        f'<div class="im-num" style="color:#0d9488;">{views}</div>'
        '<div class="im-label">Views</div>'
        '</div>'
    )
else:
    dl_card = (
        '<div class="im-card im-card-dl-primary">'
        '<div class="im-num" style="color:#0d9488;">—</div>'
        '<div class="im-label">Downloads</div>'
        '</div>'
    )

# Second card: Views (if downloads is primary) or Citations
if downloads and views:
    second_card = (
        '<div class="im-card">'
        f'<div class="im-num">{views}</div>'
        '<div class="im-label">Views</div>'
        '</div>'
    )
elif total_cit and total_cit != "0":
    second_card = (
        '<div class="im-card">'
        f'<div class="im-num">{total_cit}</div>'
        '<div class="im-label">Citations</div>'
        + (f'<div class="im-top-badge">🏆 {top_badge}</div>' if top_badge else "")
        + '</div>'
    )
else:
    second_card = ""

# Third card: mentions or citations
if total_men and total_men != "—":
    third_card = (
        '<div class="im-card">'
        f'<div class="im-num">{total_men}</div>'
        '<div class="im-label">Online Mentions</div>'
        '</div>'
    )
else:
    third_card = ""

cards_block = f'<div class="im-cards">{dl_card}{second_card}{third_card}</div>'

# Signals pills
sig_pills = ""
if yt_count:
    sig_pills += (f'<a href="#sec-teaching" class="sig-pill sig-red">'
                  f'▶ YouTube · {yt_count} video{"s" if yt_count != 1 else ""}</a>')
if has_wiki:
    sig_pills += '<a href="#sec-teaching" class="sig-pill sig-slate">📖 Wikipedia</a>'
if has_worldcat:
    sig_pills += '<a href="#sec-teaching" class="sig-pill sig-slate">📚 WorldCat</a>'
if has_ocw:
    sig_pills += '<a href="#sec-teaching" class="sig-pill sig-indigo">🎓 Course syllabus</a>'
if datasets:
    _ds_label = f'Dataset{"s" if len(datasets) > 1 else ""} · {len(datasets)} repo{"s" if len(datasets) > 1 else ""}'
    sig_pills += f'<a href="#sec-stewardship" class="sig-pill sig-teal">🗂 {_ds_label}</a>'
if country_count:
    sig_pills += (f'<a href="#sec-citing" class="sig-pill sig-blue">'
                  f'🌍 {country_count} countries</a>')

signals_block = ""
if sig_pills:
    signals_block = (
        '<div class="im-signals">'
        '<div class="im-signals-title">Additional signals</div>'
        f'<div class="im-signals-pills">{sig_pills}</div>'
        '</div>'
    )

impact_sec = soup.find(id="sec-impact")
if impact_sec:
    h2_im = impact_sec.find("h2")
    if h2_im:
        for _el in list(h2_im.find_next_siblings()):
            _el.extract()
        impact_sec.append(BeautifulSoup(
            f'<div class="im-wrapper">{cards_block}{signals_block}</div>',
            "html.parser"
        ))
        print("Enriched Impact Metrics section")
    else:
        print("  Warning: no h2 in impact section")
else:
    print("  Warning: sec-impact not found")


# ══════════════════════════════════════════════════════════════
# STEP 4 — Restructure "Who is citing" sub-tabs (if present)
# ══════════════════════════════════════════════════════════════
citing_sec = soup.find(id="sec-citing")
if citing_sec:
    grid   = citing_sec.find("div", style=re.compile(r"grid-template-columns.*auto-fit", re.I))
    bottom = citing_sec.find("div", style=re.compile(r"border-top.*padding-top", re.I))

    if grid and bottom:
        cols = [c for c in grid.children if getattr(c, "name", None) == "div"]
        if len(cols) >= 3:
            geo_html  = str(cols[0])
            inst_html = str(cols[1])
            ppl_html  = str(cols[2])
            anal_html = str(bottom)

            tab_block = BeautifulSoup(f"""
<div class="cite-analysis-always">{anal_html}</div>
<div class="cite-tabs">
  <button class="cite-tab-btn active" onclick="citeSwitchTab(this,'cite-geo')">🌍 Geography</button>
  <button class="cite-tab-btn" onclick="citeSwitchTab(this,'cite-inst')">🏛 Institutions</button>
  <button class="cite-tab-btn" onclick="citeSwitchTab(this,'cite-ppl')">👤 Top Citers</button>
</div>
<div id="cite-geo"  class="cite-tab-pane active">{geo_html}</div>
<div id="cite-inst" class="cite-tab-pane">{inst_html}</div>
<div id="cite-ppl"  class="cite-tab-pane">{ppl_html}</div>
""", "html.parser")

            grid.replace_with(tab_block)
            bottom.decompose()
            print("Restructured 'Who is citing' into sub-tabs")
        else:
            print(f"  Who is citing: expected ≥3 cols, found {len(cols)} — skipping tabs")
    else:
        print("  Who is citing: no grid/bottom found — skipping tabs")


# ══════════════════════════════════════════════════════════════
# STEP 5 — Add pagination UI after citations table (if present)
# ══════════════════════════════════════════════════════════════
if cit_section:
    scroll_div = cit_section.find("div", class_="table-scroll-wrapper")
    if scroll_div:
        pag = BeautifulSoup("""
<div class="cit-pagination">
  <span class="cit-pagination-info" id="cit-info">Loading…</span>
  <div class="cit-pagination-btns">
    <button class="cit-btn" id="cit-prev" onclick="citPrev()" disabled>← Prev</button>
    <span id="cit-page-nums" style="display:flex;gap:0.3rem;flex-wrap:wrap;align-items:center;"></span>
    <button class="cit-btn" id="cit-next" onclick="citNext()">Next →</button>
  </div>
</div>
""", "html.parser")
        scroll_div.insert_after(pag)


# ══════════════════════════════════════════════════════════════
# STEP 6 — Inject CSS
# ══════════════════════════════════════════════════════════════
new_css = """
/* ── UX Enhancements ── */

.stats-strip{display:grid;grid-template-columns:repeat(4,1fr);background:white;border-radius:.9rem;
  box-shadow:0 10px 30px rgba(15,23,42,.08);margin-bottom:1.75rem;overflow:hidden;}
.stats-strip-item{padding:1rem 1.25rem;text-align:center;border-right:1px solid #f3f4f6;}
.stats-strip-item:last-child{border-right:none;}
.stats-strip-num{font-size:1.7rem;font-weight:800;color:#0d9488;line-height:1.1;}
.stats-strip-label{font-size:.68rem;color:#6b7280;text-transform:uppercase;letter-spacing:.06em;margin-top:.25rem;}
.stats-strip-badge{display:inline-block;font-size:.6rem;background:#fef9c3;color:#b45309;border:1px solid #fde68a;
  border-radius:999px;padding:.1rem .35rem;font-weight:700;margin-top:.25rem;}
@media(max-width:600px){.stats-strip{grid-template-columns:repeat(2,1fr);}}

.sticky-nav{position:sticky;top:0;z-index:100;background:white;border-radius:.9rem;
  box-shadow:0 4px 16px rgba(15,23,42,.1);margin-bottom:1.75rem;overflow-x:auto;
  white-space:nowrap;-webkit-overflow-scrolling:touch;scrollbar-width:none;}
.sticky-nav::-webkit-scrollbar{display:none;}
.sticky-nav-inner{display:flex;padding:0 .5rem;}
.sticky-nav a{display:inline-block;padding:.65rem .9rem;font-size:.78rem;font-weight:600;
  color:#6b7280;text-decoration:none;border-bottom:2px solid transparent;
  transition:color .15s,border-color .15s;white-space:nowrap;}
.sticky-nav a:hover{color:#111827;}
.sticky-nav a.snav-active{color:#0d9488;border-bottom-color:#0d9488;}
@media print{.sticky-nav,.stats-strip{display:none!important;}}

.card-collapsible > h2{cursor:pointer;user-select:none;display:flex;justify-content:space-between;align-items:center;}
.card-collapsible > h2 .chevron{font-size:.85rem;color:#9ca3af;margin-left:.5rem;
  flex-shrink:0;transition:transform .2s;display:inline-block;}
.card-collapsible.is-collapsed > h2 .chevron{transform:rotate(-90deg);}
.card-body-wrap{overflow:hidden;max-height:9999px;opacity:1;
  transition:max-height .35s ease,opacity .28s ease;}
.card-collapsible.is-collapsed .card-body-wrap{max-height:0!important;opacity:0;pointer-events:none;}

.cite-tabs{display:flex;gap:0;border-bottom:2px solid #e5e7eb;margin-bottom:1rem;overflow-x:auto;scrollbar-width:none;}
.cite-tabs::-webkit-scrollbar{display:none;}
.cite-tab-btn{background:none;border:none;padding:.5rem 1rem;font-size:.82rem;font-weight:600;
  color:#6b7280;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px;
  white-space:nowrap;transition:all .15s;}
.cite-tab-btn.active{color:#0d9488;border-bottom-color:#0d9488;}
.cite-tab-pane{display:none;}
.cite-tab-pane.active{display:block;}
.cite-analysis-always{margin-top:1rem;}

.roles-domain{margin-bottom:.85rem;}
.roles-domain:last-of-type{margin-bottom:0;}
.roles-domain-label{font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;
  margin-bottom:.4rem;display:flex;align-items:center;gap:.3rem;}
.roles-row{display:flex;flex-wrap:wrap;gap:.35rem;}
.role-pill{display:inline-flex;align-items:center;gap:.3rem;padding:.28rem .65rem .28rem .45rem;
  border-radius:999px;font-size:.78rem;font-weight:600;border:1.5px solid;cursor:help;
  position:relative;transition:opacity .15s;}
.role-pill-academic  {background:#eff6ff;color:#1e40af;border-color:#bfdbfe;}
.role-pill-readership{background:#f5f3ff;color:#4c1d95;border-color:#ddd6fe;}
.role-pill-public    {background:#fffbeb;color:#92400e;border-color:#fde68a;}
.role-pill-practical {background:#f0fdf4;color:#065f46;border-color:#bbf7d0;}
.role-pill:hover{opacity:1!important;}
.role-pill[title]:hover::after{
  content:attr(title);position:absolute;bottom:calc(100% + 8px);left:50%;transform:translateX(-50%);
  background:#111827;color:white;padding:.5rem .75rem;border-radius:.5rem;font-size:.72rem;
  width:230px;line-height:1.5;white-space:normal;font-weight:400;z-index:200;
  pointer-events:none;box-shadow:0 4px 16px rgba(0,0,0,.25);}
.role-pill[title]:hover::before{
  content:'';position:absolute;bottom:calc(100% + 3px);left:50%;transform:translateX(-50%);
  border:5px solid transparent;border-top-color:#111827;z-index:201;pointer-events:none;}
.role-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}
.role-strength{font-size:.6rem;font-weight:700;padding:.05rem .3rem;border-radius:999px;margin-left:.1rem;}
.roles-legend{display:flex;gap:.75rem;flex-wrap:wrap;margin-top:.75rem;
  padding-top:.65rem;border-top:1px solid #f3f4f6;}
.roles-leg-item{display:flex;align-items:center;gap:.3rem;font-size:.62rem;color:#6b7280;}
.roles-leg-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}

.cit-pagination{display:flex;align-items:center;justify-content:space-between;
  padding:.75rem .25rem 0;font-size:.82rem;flex-wrap:wrap;gap:.5rem;border-top:1px solid #f3f4f6;margin-top:.5rem;}
.cit-pagination-info{color:#6b7280;}
.cit-pagination-btns{display:flex;gap:.35rem;flex-wrap:wrap;align-items:center;}
.cit-btn{padding:.3rem .7rem;border:1px solid #e5e7eb;border-radius:.4rem;background:white;
  color:#374151;font-size:.78rem;font-weight:600;cursor:pointer;transition:all .15s;}
.cit-btn:hover:not(:disabled):not(.cit-active){background:#f9fafb;border-color:#d1d5db;}
.cit-btn.cit-active{background:#0d9488;color:white;border-color:#0d9488;}
.cit-btn:disabled{opacity:.4;cursor:default;}

.im-wrapper{display:flex;flex-direction:column;gap:.85rem;}
.im-cards{display:grid;grid-template-columns:2fr 1fr 1fr;gap:.65rem;}
@media(max-width:640px){.im-cards{grid-template-columns:1fr 1fr;}}
.im-card{background:#f8fafc;border:1px solid #e2e8f0;border-radius:.75rem;padding:.8rem 1rem;}
.im-card-dl-primary{background:linear-gradient(135deg,#f0fdfa 0%,#ecfdf5 100%);border-color:#99f6e4;}
.im-card-top{display:flex;justify-content:space-between;align-items:flex-start;gap:.4rem;}
.im-num{font-size:1.75rem;font-weight:800;color:#0d9488;line-height:1.05;}
.im-label{font-size:.63rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-top:.2rem;}
.im-top-badge{margin-top:.4rem;display:inline-block;font-size:.6rem;background:#fef9c3;
  color:#b45309;border:1px solid #fde68a;border-radius:999px;padding:.1rem .4rem;font-weight:700;}
.im-signals{background:#f8fafc;border:1px solid #e2e8f0;border-radius:.75rem;padding:.8rem 1rem;}
.im-signals-title{font-size:.72rem;font-weight:700;color:#374151;margin-bottom:.45rem;}
.im-signals-pills{display:flex;flex-wrap:wrap;gap:.3rem;}
.sig-pill{display:inline-flex;align-items:center;padding:.2rem .55rem;border-radius:999px;
  font-size:.7rem;font-weight:600;text-decoration:none;transition:opacity .15s;cursor:pointer;}
.sig-pill:hover{opacity:.75;}
.sig-red   {background:#fee2e2;color:#b91c1c;}
.sig-slate {background:#f1f5f9;color:#475569;}
.sig-indigo{background:#e0e7ff;color:#4338ca;}
.sig-teal  {background:#ccfbf1;color:#0f766e;}
.sig-amber {background:#fef3c7;color:#b45309;}
.sig-blue  {background:#dbeafe;color:#1d4ed8;}
"""

head_style = soup.find("style")
if head_style:
    head_style.string = (head_style.string or "") + "\n" + new_css


# ══════════════════════════════════════════════════════════════
# STEP 7 — Inject stats strip + sticky nav after hero
# ══════════════════════════════════════════════════════════════
top_badge_html = f'<div class="stats-strip-badge">🏆 {top_badge}</div>' if top_badge else ""

# Build stat strip using downloads/views as primary metrics
stat1_num   = downloads if downloads else "—"
stat1_label = "Downloads"
stat2_num   = views if views else "—"
stat2_label = "Views"
stat3_num   = total_cit if total_cit != "0" else "—"
stat3_label = "Citations"
stat4_num   = oa_status if oa_status else "—"
stat4_label = "Open Access Status"

stats_html = f"""
<div class="stats-strip no-print">
  <div class="stats-strip-item">
    <div class="stats-strip-num">{stat1_num}</div>
    <div class="stats-strip-label">{stat1_label}</div>
    {top_badge_html}
  </div>
  <div class="stats-strip-item">
    <div class="stats-strip-num">{stat2_num}</div>
    <div class="stats-strip-label">{stat2_label}</div>
  </div>
  <div class="stats-strip-item">
    <div class="stats-strip-num">{stat3_num}</div>
    <div class="stats-strip-label">{stat3_label}</div>
  </div>
  <div class="stats-strip-item">
    <div class="stats-strip-num" style="font-size:1.15rem;padding-top:.3rem;">{stat4_num}</div>
    <div class="stats-strip-label">{stat4_label}</div>
  </div>
</div>
"""

# Build nav — only include sections that actually exist
has_roles    = bool(soup.find(id="sec-roles"))
has_citing   = bool(soup.find(id="sec-citing"))
has_teaching = bool(soup.find(id="sec-teaching"))
has_concepts = bool(soup.find(id="sec-concepts"))
has_credits  = bool(soup.find(id="sec-contributors"))
has_citations = bool(soup.find(id="sec-citations"))

nav_links = [('Overview', '#sec-hero'), ('Story', '#sec-story'), ('Impact', '#sec-impact')]
if has_roles:    nav_links.append(('Roles', '#sec-roles'))
nav_links.append(('Access', '#sec-access'))
nav_links.append(('Attention', '#sec-mentions'))
if has_citing:   nav_links.append(("Who's Citing", '#sec-citing'))
if has_teaching: nav_links.append(('Teaching', '#sec-teaching'))
if has_credits:  nav_links.append(('Contributors', '#sec-contributors'))
if has_concepts: nav_links.append(('Concepts', '#sec-concepts'))
if has_citations: nav_links.append(('All Citations', '#sec-citations'))

nav_items = "".join(f'<a href="{href}">{label}</a>' for label, href in nav_links)
nav_html = f"""
<nav class="sticky-nav no-print" id="sticky-nav" aria-label="Page sections">
  <div class="sticky-nav-inner">{nav_items}</div>
</nav>
"""

if hero:
    hero.insert_after(BeautifulSoup(nav_html, "html.parser"))
    hero.insert_after(BeautifulSoup(stats_html, "html.parser"))


# ══════════════════════════════════════════════════════════════
# STEP 8 — JavaScript blocks
# ══════════════════════════════════════════════════════════════
PAGE_SIZE = 25
rows_json = json.dumps(rows_data, ensure_ascii=False)

cit_js = f"""
<script>
(function() {{
  var DATA = {rows_json};
  var PER  = {PAGE_SIZE};
  var _p   = 1;
  var _tot = Math.ceil(DATA.length / PER);

  function esc(s) {{
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }}

  function render(page) {{
    _p = page;
    var tbody = document.getElementById('cit-tbody');
    var info  = document.getElementById('cit-info');
    var prev  = document.getElementById('cit-prev');
    var next  = document.getElementById('cit-next');
    var nums  = document.getElementById('cit-page-nums');
    if (!tbody) return;
    var s = (page-1)*PER, e = Math.min(s+PER, DATA.length), rows = '';
    for (var i=s; i<e; i++) {{
      var r = DATA[i];
      var d = r.doi_url
        ? '<a href="'+esc(r.doi_url)+'" target="_blank" style="word-break:break-all;">'+esc(r.doi)+'</a>'
        : esc(r.doi||'');
      rows += '<tr><td>'+esc(r.year)+'</td><td>'+esc(r.title)+'</td><td>'+esc(r.venue)+'</td><td>'+d+'</td></tr>';
    }}
    tbody.innerHTML = rows;
    if (info) info.textContent = 'Showing '+(s+1)+'–'+e+' of '+DATA.length+' citing works';
    if (prev) prev.disabled = (page===1);
    if (next) next.disabled = (page===_tot);
    if (nums) {{
      var shown = [], html = '', prev2 = null;
      for (var p=1; p<=_tot; p++) {{
        if (p===1||p===_tot||(p>=page-2&&p<=page+2)) shown.push(p);
      }}
      for (var i=0; i<shown.length; i++) {{
        var p=shown[i];
        if (prev2!==null&&p-prev2>1) html+='<span style="padding:0 .2rem;color:#9ca3af;">…</span>';
        html+='<button class="cit-btn'+(p===_p?' cit-active':'')+'" onclick="citGoTo('+p+')">'+p+'</button>';
        prev2=p;
      }}
      nums.innerHTML = html;
    }}
  }}
  window.citGoTo = function(p) {{
    if(p<1||p>_tot) return;
    render(p);
    var sec=document.getElementById('sec-citations');
    if(sec) sec.scrollIntoView({{behavior:'smooth',block:'start'}});
  }};
  window.citPrev = function() {{ window.citGoTo(_p-1); }};
  window.citNext = function() {{ window.citGoTo(_p+1); }};
  if(document.readyState==='loading')
    document.addEventListener('DOMContentLoaded',function(){{render(1);}});
  else render(1);
}})();
</script>
"""

collapsible_js = """
<script>
(function() {
  function init() {
    document.querySelectorAll('section.card, .card').forEach(function(card) {
      if (card.tagName === 'HEADER') return;
      var h2 = null;
      for (var i=0; i<card.children.length; i++) {
        if (card.children[i].tagName === 'H2') { h2 = card.children[i]; break; }
      }
      if (!h2) return;
      card.classList.add('card-collapsible');
      var chev = document.createElement('span');
      chev.className = 'chevron';
      chev.setAttribute('aria-hidden','true');
      chev.textContent = '▾';
      h2.appendChild(chev);
      var wrap = document.createElement('div');
      wrap.className = 'card-body-wrap';
      var kids = Array.from(card.children), after = false;
      kids.forEach(function(c) {
        if (c===h2){after=true;return;}
        if (after) wrap.appendChild(c);
      });
      card.appendChild(wrap);
      h2.addEventListener('click', function() { card.classList.toggle('is-collapsed'); });
    });
  }
  if (document.readyState==='loading')
    document.addEventListener('DOMContentLoaded', init);
  else init();
})();
</script>
"""

cite_tab_js = """
<script>
function citeSwitchTab(btn, tabId) {
  var tabsEl = btn.closest('.cite-tabs');
  if (!tabsEl) return;
  var parent = tabsEl.parentElement;
  parent.querySelectorAll('.cite-tab-btn').forEach(function(b){b.classList.remove('active');});
  parent.querySelectorAll('.cite-tab-pane').forEach(function(p){p.classList.remove('active');});
  btn.classList.add('active');
  var pane = document.getElementById(tabId);
  if (pane) pane.classList.add('active');
}
</script>
"""

nav_active_js = """
<script>
(function() {
  function init() {
    var nav = document.getElementById('sticky-nav');
    if (!nav) return;
    var links = Array.from(nav.querySelectorAll('a'));
    var targets = links.map(function(l) {
      var id = l.getAttribute('href').slice(1);
      return {el: document.getElementById(id), link: l};
    }).filter(function(t){return t.el;});
    var obs = new IntersectionObserver(function(entries) {
      entries.forEach(function(e) {
        if (e.isIntersecting) {
          links.forEach(function(l){l.classList.remove('snav-active');});
          var match = links.find(function(l){
            return l.getAttribute('href')==='#'+e.target.id;
          });
          if (match) match.classList.add('snav-active');
        }
      });
    }, {rootMargin:'-5% 0px -80% 0px', threshold:0});
    targets.forEach(function(t){obs.observe(t.el);});
  }
  if (document.readyState==='loading')
    document.addEventListener('DOMContentLoaded', init);
  else init();
})();
</script>
"""

body = soup.find("body")
for chunk in [cit_js, cite_tab_js, collapsible_js, nav_active_js]:
    body.append(BeautifulSoup(chunk, "html.parser"))


# ══════════════════════════════════════════════════════════════
# OUTPUT
# ══════════════════════════════════════════════════════════════
DST.write_text(str(soup), "utf-8")
orig_size = SRC.stat().st_size
new_size  = DST.stat().st_size
print(f"Output: {DST.name}")
print(f"  Original size : {orig_size:>10,} bytes  ({orig_size // 1024:,} KB)")
print(f"  New size      : {new_size:>10,} bytes  ({new_size // 1024:,} KB)")
print(f"  Reduction     : {(1 - new_size/orig_size)*100:.1f}%")
print(f"  Citation rows : {len(rows_data)}")
