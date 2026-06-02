#!/usr/bin/env python3
"""Repair mistaken </body> replacement inside CSS comments and inject scripts at document end."""

import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
BROKEN = re.compile(
    r"/\* Tooltip affordance: any element carrying a data-tip gets a help cursor\.\s*"
    r"Positioning/visibility is handled by the JS tooltip near\s*"
    r'<script src="role_tooltips\.js"></script>\s*'
    r"<script>initRoleTooltips\(\);</script>\s*"
    r"</body>\. \*/",
    re.DOTALL,
)
FIXED_COMMENT = (
    "/* Tooltip affordance: any element carrying a data-tip gets a help cursor.\n"
    "   Positioning/visibility is handled by the JS tooltip near </body>. */"
)
INJECT = (
    '\n<script src="role_tooltips.js"></script>\n'
    "<script>initRoleTooltips();</script>\n"
)


def fix_file(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    original = html

    html = BROKEN.sub(FIXED_COMMENT, html)

  # Remove duplicate inject blocks that appear before the real document end.
    html = re.sub(
        r'(\n<script src="role_tooltips\.js"></script>\n<script>initRoleTooltips\(\);</script>\n)+',
        INJECT,
        html,
    )

    if "role_tooltips.js" not in html or html.count("role_tooltips.js") < 1:
        pass
    elif not re.search(r'</body>\s*</html>\s*$', html, re.I | re.S):
        if "</body>" in html.lower():
            idx = html.lower().rfind("</body>")
            if 'role_tooltips.js' not in html[idx - 200 : idx]:
                html = html[:idx] + INJECT + html[idx:]

    if html != original:
        path.write_text(html, encoding="utf-8")
        return True
    return False


def main():
    n = 0
    for path in sorted(BASE.glob("*story*.html")):
        if fix_file(path):
            n += 1
    print(f"Repaired {n} file(s).")


if __name__ == "__main__":
    main()
