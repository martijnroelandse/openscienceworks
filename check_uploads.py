#!/usr/bin/env python3
"""
check_uploads.py — detect duplicate or stray story uploads before deploy.

Catches the launch-day issue: identical story slugs uploaded twice, often with a
trailing underscore (articlestory_foo_.html vs articlestory_foo.html) or workflow
suffixes (_new, _orig, copy).

Usage:
    python3 check_uploads.py
    python3 check_uploads.py --dir .
    python3 check_uploads.py --live https://openscience.works
    python3 check_uploads.py --json duplicates-report.json

Exit code 1 when errors are found (safe to run from build_index.py / CI).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Iterable
from urllib.parse import urljoin

STORY_PREFIXES = ("articlestory_", "bookstory_", "datastory_", "softwarestory_")
STORY_RE = re.compile(
    r"^(article|book|data|software)story_(.+)\.(html|json)$",
    re.IGNORECASE,
)
WORKFLOW_SUFFIXES = ("_new", "_orig", "_orig_new", " copy")


@dataclass
class Issue:
    severity: str  # error | warning
    kind: str
    message: str
    files: list[str]


def _story_files(directory: str) -> list[str]:
    names = []
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        if name.startswith(STORY_PREFIXES) and name.endswith((".html", ".json")):
            names.append(name)
    return sorted(names)


def _parse_story_name(filename: str) -> tuple[str, str, str] | None:
    match = STORY_RE.match(filename)
    if not match:
        return None
    return match.group(1).lower(), match.group(2), match.group(3).lower()


def canonical_slug(slug: str) -> str:
    """Normalize a story slug for duplicate comparison."""
    base = slug
    for suffix in WORKFLOW_SUFFIXES:
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return base.rstrip("_")


def _story_key(prefix: str, slug: str, ext: str) -> str:
    return f"{prefix}story_{canonical_slug(slug)}.{ext}"


def _doi_from_json(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    doi = data.get("doi") or data.get("book_id") or ""
    doi = str(doi).strip().lower()
    return doi or None


def _file_hash(path: str) -> str | None:
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def scan_directory(
    directory: str,
    *,
    hash_duplicates: bool = True,
    strict: bool = False,
) -> list[Issue]:
    directory = os.path.abspath(directory)
    files = _story_files(directory)
    issues: list[Issue] = []

    by_story_key: dict[str, list[str]] = defaultdict(list)
    html_keys: set[str] = set()
    json_keys: set[str] = set()
    parsed_files: list[tuple[str, str, str, str]] = []

    for filename in files:
        parsed = _parse_story_name(filename)
        if not parsed:
            continue
        prefix, slug, ext = parsed
        key = _story_key(prefix, slug, ext)
        by_story_key[key].append(filename)
        parsed_files.append((filename, prefix, slug, ext))
        if ext == "html":
            html_keys.add(_story_key(prefix, slug, "html"))
        else:
            json_keys.add(_story_key(prefix, slug, "json"))

    for story_key, variants in sorted(by_story_key.items()):
        if len(variants) <= 1:
            continue
        issues.append(
            Issue(
                severity="error",
                kind="duplicate_upload",
                message=f"Multiple files map to the same story key ({story_key})",
                files=sorted(variants),
            )
        )

    duplicate_files = {name for issue in issues for name in issue.files if issue.kind == "duplicate_upload"}

    for filename, prefix, slug, ext in parsed_files:
        if filename in duplicate_files:
            continue
        canon = canonical_slug(slug)
        if slug == canon:
            continue
        canonical_name = f"{prefix}story_{canon}.{ext}"
        issues.append(
            Issue(
                severity="error",
                kind="stray_variant",
                message=(
                    f"Non-canonical upload ({filename}); "
                    f"expected {canonical_name}"
                ),
                files=[filename],
            )
        )

    doi_by_prefix: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for filename in files:
        if not filename.endswith(".json"):
            continue
        parsed = _parse_story_name(filename)
        if not parsed:
            continue
        prefix, _, _ = parsed
        doi = _doi_from_json(os.path.join(directory, filename))
        if doi:
            doi_by_prefix[prefix][doi].append(filename)

    if strict:
        for story_key in sorted(html_keys - json_keys):
            issues.append(
                Issue(
                    severity="warning",
                    kind="orphan_html",
                    message=f"HTML without matching JSON ({story_key})",
                    files=by_story_key[story_key],
                )
            )
        for story_key in sorted(json_keys - html_keys):
            issues.append(
                Issue(
                    severity="warning",
                    kind="orphan_json",
                    message=f"JSON without matching HTML ({story_key})",
                    files=by_story_key[story_key],
                )
            )

    for prefix, doi_map in sorted(doi_by_prefix.items()):
        for doi, json_files in sorted(doi_map.items()):
            if len(json_files) <= 1:
                continue
            issues.append(
                Issue(
                    severity="error",
                    kind="duplicate_doi",
                    message=(
                        f"Same DOI appears in multiple {prefix}story JSON files "
                        f"({doi})"
                    ),
                    files=sorted(json_files),
                )
            )

    if hash_duplicates:
        hash_map: dict[str, list[str]] = defaultdict(list)
        for filename in files:
            digest = _file_hash(os.path.join(directory, filename))
            if digest:
                hash_map[digest].append(filename)
        for names in hash_map.values():
            if len(names) <= 1:
                continue
            prefixes = {_parse_story_name(name)[0] for name in names if _parse_story_name(name)}
            if len(prefixes) != 1:
                continue
            issues.append(
                Issue(
                    severity="warning",
                    kind="identical_content",
                    message="Identical file content with different names",
                    files=sorted(names),
                )
            )

    return issues


def _fetch(url: str, timeout: float = 20.0) -> tuple[int, bytes]:
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "openscience-upload-check/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def _story_files_from_live(base_url: str) -> list[str]:
    base_url = base_url.rstrip("/") + "/"
    status, body = _fetch(urljoin(base_url, "stories_data.js"))
    if status != 200:
        raise RuntimeError(f"Could not fetch stories_data.js from {base_url} (HTTP {status})")

    text = body.decode("utf-8", errors="replace")
    marker = "window.STORIES_DATA = "
    start = text.find(marker)
    if start < 0:
        raise RuntimeError("stories_data.js missing window.STORIES_DATA")
    start += len(marker)
    end = text.find(";\n", start)
    if end < 0:
        raise RuntimeError("Could not parse stories_data.js payload")
    stories = json.loads(text[start:end])
    return sorted({story["file"] for story in stories if story.get("file")})


def scan_live(base_url: str) -> list[Issue]:
    """Probe the deployed site for duplicate URL variants of indexed stories."""
    base_url = base_url.rstrip("/") + "/"
    issues: list[Issue] = []
    indexed_html = _story_files_from_live(base_url)

    for html_name in indexed_html:
        parsed = _parse_story_name(html_name)
        if not parsed:
            continue
        prefix, slug, _ = parsed
        canon = canonical_slug(slug)
        candidates = set()

        if slug != canon:
            candidates.add(f"{prefix}story_{canon}.html")
            candidates.add(f"{prefix}story_{canon}.json")

        for suffix in WORKFLOW_SUFFIXES:
            candidates.add(f"{prefix}story_{canon}{suffix}.html")
            candidates.add(f"{prefix}story_{canon}{suffix}.json")

        candidates.add(f"{prefix}story_{canon}_.html")
        candidates.add(f"{prefix}story_{canon}_.json")

        found = []
        for candidate in sorted(candidates):
            if candidate == html_name:
                continue
            url = urljoin(base_url, candidate)
            status, _ = _fetch(url)
            if status == 200:
                found.append(candidate)

        if found:
            issues.append(
                Issue(
                    severity="error",
                    kind="live_duplicate_url",
                    message=f"Indexed story {html_name} has extra reachable duplicates",
                    files=[html_name, *found],
                )
            )

    return issues


def print_report(issues: list[Issue], directory: str | None = None) -> None:
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]

    if directory:
        print(f"Scanning: {directory}")
    print(f"Found {len(errors)} error(s), {len(warnings)} warning(s)")

    for label, bucket in (("ERROR", errors), ("WARNING", warnings)):
        if not bucket:
            continue
        print(f"\n{label}S")
        for issue in bucket:
            print(f"  [{issue.kind}] {issue.message}")
            for filename in issue.files:
                print(f"    - {filename}")

    if not issues:
        print("No duplicate upload issues detected.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect duplicate story uploads")
    parser.add_argument(
        "--dir",
        default=os.path.dirname(os.path.abspath(__file__)),
        help="Directory containing story HTML/JSON files (default: repo root)",
    )
    parser.add_argument(
        "--live",
        metavar="URL",
        help="Also crawl deployed site for duplicate reachable URLs",
    )
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="Write machine-readable report to JSON",
    )
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Skip identical-content hash comparison",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Also warn on orphan HTML/JSON pairs",
    )
    args = parser.parse_args(argv)

    issues = scan_directory(args.dir, hash_duplicates=not args.no_hash, strict=args.strict)
    if args.live:
        try:
            issues.extend(scan_live(args.live))
        except RuntimeError as exc:
            print(f"Live scan failed: {exc}", file=sys.stderr)
            return 2

    print_report(issues, args.dir)

    if args.json:
        payload = {
            "directory": os.path.abspath(args.dir),
            "live": args.live,
            "issues": [asdict(issue) for issue in issues],
        }
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        print(f"\nWrote report to {args.json}")

    return 1 if any(issue.severity == "error" for issue in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
