#!/usr/bin/env python3
"""
Run pytest under cProfile and write both a pstats file and a human-readable summary.

Usage:
    python script/test_profile.py [pytest-args...]

Environment variables:
    PROFILE_OUT     Path to write the raw profile (.pstats). Default: tests_profile_after.out
    PROFILE_SORT    pstats sort key (cumtime|tottime|calls|name etc.). Default: cumtime
    PROFILE_LIMIT   How many lines to print in the summary. Default: 50
"""

from __future__ import annotations

import cProfile
import os
from pathlib import Path
import pstats
import subprocess
import sys


def main(argv: list[str]) -> int:
    """Run pytest under cProfile and write both a pstats file and a human-readable summary."""
    out_file = Path(os.environ.get("PROFILE_OUT", "tests_profile_after.out")).resolve()
    sort_by = os.environ.get("PROFILE_SORT", "cumtime")
    limit = int(os.environ.get("PROFILE_LIMIT", "50"))

    print(f"Profiling pytest → {out_file}")
    cmd = [sys.executable, "-m", "pytest", *argv]

    # Run pytest under cProfile
    profile = cProfile.Profile()
    try:
        profile.enable()
        # Use subprocess to ensure pytest exits cleanly with its own sys.exit handling
        proc = subprocess.run(cmd, check=False)
        returncode = proc.returncode
    finally:
        profile.disable()
        profile.dump_stats(str(out_file))

    # Also emit a human-readable summary next to the .out file
    txt_file = out_file.with_suffix(out_file.suffix + ".txt")
    try:
        stats = pstats.Stats(str(out_file))
        stats.strip_dirs().sort_stats(sort_by)
        with open(txt_file, "w", encoding="utf-8") as fh:
            stats.stream = fh
            stats.print_stats(limit)
        print(f"Wrote profile summary → {txt_file}")
    except Exception as exc:  # pragma: no cover
        print(f"Failed to write stats summary: {exc}")

    return returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
