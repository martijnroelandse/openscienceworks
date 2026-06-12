#!/usr/bin/env python3
"""Thin launcher — delegates to bookstories/scripts/build_index.py.

Usage (from this directory):
    python3 build_index.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOOKSTORIES = ROOT.parent / "bookstories"
TARGET = BOOKSTORIES / "scripts" / "build_index.py"

if not TARGET.is_file():
    sys.exit(
        f"error: expected {TARGET}\n"
        "Clone bookstories next to openscienceworks, or set BOOKSTORIES to its path."
    )

env = os.environ.copy()
env["OSW_DIR"] = str(ROOT)
raise SystemExit(
    subprocess.call([sys.executable, str(TARGET), *sys.argv[1:]], env=env)
)
