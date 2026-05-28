#!/usr/bin/env python3
"""
openscience.works — Bulk UX Transformer
Applies UX improvements to all articlestory_*.html and bookstory_*.html files.

Usage:
  python3 transform_all.py                  # process all files
  python3 transform_all.py --dry-run        # list files without processing
  python3 transform_all.py --limit 5        # process first 5 of each type
  python3 transform_all.py --overwrite      # re-process already-transformed files

Outputs are written as <original_name>_new.html alongside each source file.
Files that already have a _new.html counterpart are skipped unless --overwrite.
"""

import sys
import time
import traceback
from pathlib import Path

HERE    = Path(__file__).parent
FOLDER  = Path("/sessions/loving-great-brown/mnt/openscienceworks")

# ── CLI flags ─────────────────────────────────────────────────────────────────
DRY_RUN   = "--dry-run"   in sys.argv
OVERWRITE = "--overwrite" in sys.argv
LIMIT     = None
for i, arg in enumerate(sys.argv):
    if arg == "--limit" and i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[i + 1])

# ── Collect source files ───────────────────────────────────────────────────────
article_files = sorted(
    f for f in FOLDER.glob("articlestory_*.html")
    if "_new" not in f.name
)
book_files = sorted(
    f for f in FOLDER.glob("bookstory_*.html")
    if "_new" not in f.name
)

if LIMIT:
    article_files = article_files[:LIMIT]
    book_files    = book_files[:LIMIT]

print(f"Found {len(article_files)} article story files")
print(f"Found {len(book_files)} book story files")
print(f"Total: {len(article_files) + len(book_files)} files to process")
if DRY_RUN:
    print("\n[DRY RUN] Files that would be processed:")
    for f in article_files + book_files:
        dst = f.with_name(f.stem + "_new.html")
        status = "EXISTS" if dst.exists() else "NEW"
        skip   = "SKIP" if dst.exists() and not OVERWRITE else ""
        print(f"  [{status:<6}] {f.name}  {skip}")
    sys.exit(0)

# ── Load transform scripts ─────────────────────────────────────────────────────
# We read the script source once, then exec() per file with SRC/DST pre-set.
# The scripts use SRC/DST as Path variables at the top — we inject those into
# the exec namespace so each run targets the right file.

article_script_src = (HERE / "transform_articlestory.py").read_text("utf-8")
book_script_src    = (HERE / "transform_bookstory.py").read_text("utf-8")

def strip_src_dst_lines(code: str) -> str:
    """Remove the hardcoded SRC = ... / DST = ... lines from a script's source
    so the injected values from the exec namespace are used instead."""
    out = []
    for line in code.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("SRC = Path(") or stripped.startswith("DST = Path("):
            out.append("# " + line)  # comment out — use injected value
        elif stripped.startswith("html = SRC.read_text") and out and out[-1].startswith("#"):
            # also skip the immediate read so we control it
            out.append(line)
        else:
            out.append(line)
    return "".join(out)

article_code = strip_src_dst_lines(article_script_src)
book_code    = strip_src_dst_lines(book_script_src)

# ── Process helper ─────────────────────────────────────────────────────────────
def process_file(src: Path, code: str, label: str) -> bool:
    """Run the transform code against a single file. Returns True on success."""
    dst = src.with_name(src.stem + "_new.html")
    if dst.exists() and not OVERWRITE:
        print(f"  SKIP  {src.name}  (already transformed)")
        return True

    ns = {
        "__file__": str(HERE / f"transform_{label}.py"),
        "SRC": src,
        "DST": dst,
    }
    try:
        exec(compile(code, ns["__file__"], "exec"), ns)
        return True
    except Exception as exc:
        print(f"  ERROR {src.name}: {exc}")
        if "--verbose" in sys.argv:
            traceback.print_exc()
        return False


# ── Run ────────────────────────────────────────────────────────────────────────
ok_count = err_count = skip_count = 0
t0 = time.time()

print("\n── Article stories ──────────────────────────────────────────────────────")
for i, src in enumerate(article_files, 1):
    dst = src.with_name(src.stem + "_new.html")
    if dst.exists() and not OVERWRITE:
        print(f"  [{i:>3}/{len(article_files)}] SKIP  {src.name}")
        skip_count += 1
        continue
    print(f"  [{i:>3}/{len(article_files)}] Processing {src.name} …", end="", flush=True)
    t1 = time.time()
    ok = process_file(src, article_code, "articlestory")
    elapsed = time.time() - t1
    if ok:
        new_size = dst.stat().st_size // 1024
        print(f" ✓  ({elapsed:.1f}s, {new_size} KB)")
        ok_count += 1
    else:
        print(f" ✗")
        err_count += 1

print("\n── Book stories ─────────────────────────────────────────────────────────")
for i, src in enumerate(book_files, 1):
    dst = src.with_name(src.stem + "_new.html")
    if dst.exists() and not OVERWRITE:
        print(f"  [{i:>3}/{len(book_files)}] SKIP  {src.name}")
        skip_count += 1
        continue
    print(f"  [{i:>3}/{len(book_files)}] Processing {src.name} …", end="", flush=True)
    t1 = time.time()
    ok = process_file(src, book_code, "bookstory")
    elapsed = time.time() - t1
    if ok:
        new_size = dst.stat().st_size // 1024
        print(f" ✓  ({elapsed:.1f}s, {new_size} KB)")
        ok_count += 1
    else:
        print(f" ✗")
        err_count += 1

total_time = time.time() - t0
print(f"""
─────────────────────────────────────────────────────────────────────────────
Done in {total_time:.1f}s
  Transformed : {ok_count}
  Skipped     : {skip_count}
  Errors      : {err_count}
─────────────────────────────────────────────────────────────────────────────""")
