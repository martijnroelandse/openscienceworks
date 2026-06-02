#!/usr/bin/env python3
"""Attach shared role_tooltips.js to story HTML pages and remove legacy inline tooltip blocks."""

import glob
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
INJECT = (
    '\n<script src="role_tooltips.js"></script>\n'
    "<script>initRoleTooltips();</script>\n"
)

LEGACY_TOOLTIP = re.compile(
    r'<div id="role-tooltip" style="[^"]*">.*?</div>\s*'
    r"<script>\s*\(function\(\)\{.*?"
    r"document\.querySelectorAll\([^)]+\)\.forEach\(function\(pill\)\{.*?"
    r"\}\)\(\);\s*</script>",
    re.DOTALL,
)


def patch_file(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    original = html

    if "role-pill" not in html and 'id="sec-roles"' not in html:
        return False

    html = LEGACY_TOOLTIP.sub("", html)

    if not re.search(r'<script[^>]+src="role_tooltips\.js"', html):
        idx = html.lower().rfind("</body>")
        if idx >= 0:
            html = html[:idx] + INJECT + html[idx:]
        else:
            html += INJECT

    if html != original:
        path.write_text(html, encoding="utf-8")
        return True
    return False


def main():
    changed = 0
    for path in sorted(BASE.glob("*story*.html")):
        if patch_file(path):
            changed += 1
            print(f"patched {path.name}")
    print(f"Done — {changed} file(s) updated.")


if __name__ == "__main__":
    main()
