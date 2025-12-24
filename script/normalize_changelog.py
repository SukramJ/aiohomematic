#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Normalize changelog.md."""

from __future__ import annotations

from pathlib import Path
import re

FILE = Path(__file__).resolve().parents[1] / "changelog.md"

VERSION_RE = re.compile(r"^# Version ")
WHATS_CHANGED = "## What's Changed"


def normalize(lines: list[str]) -> list[str]:
    """Normalize the changelog."""
    out: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        out.append(line)
        if VERSION_RE.match(line):
            # Ensure there is at least one blank line after the version header
            # and ensure the next non-blank line is the WHATS_CHANGED header.
            # We will inspect following lines without consuming from `out` yet.
            j = i + 1
            # Count blank lines immediately following
            k = j
            while k < n and lines[k].strip() == "":
                k += 1

            # Determine if the next non-blank line is already the desired header
            next_is_wc = k < n and lines[k].startswith(WHATS_CHANGED)

            # We will reconstruct the block after the version header:
            # 1) exactly one blank line
            # 2) WHATS_CHANGED line (if missing)
            # 3) a blank line after WHATS_CHANGED if the original had a blank line there
            #    or if we had to insert WHATS_CHANGED (to match current style)

            # Build a patch that we may need to insert after the header in `out`
            to_insert: list[str] = []

            # Ensure at least one blank line immediately after header
            if j >= n or lines[j].strip() != "":
                to_insert.append("\n")
            else:
                # Keep a single blank line; if there are multiple, we'll collapse to one
                # by skipping extras below
                pass

            if not next_is_wc:
                to_insert.append(f"{WHATS_CHANGED}\n")
                # Add a blank line after the newly inserted header to match existing style
                to_insert.append("\n")
            else:
                # Ensure there is at most one blank line between header and WHATS_CHANGED
                # If there were multiple blank lines, collapse them to one
                # Also ensure there's exactly one blank line AFTER WHATS_CHANGED for readability
                # Look after WHATS_CHANGED
                after_wc = k + 1
                # Determine if there's at least one blank line after WC; if not, add one
                needs_blank_after_wc = not (after_wc < n and lines[after_wc].strip() == "")
                # We will not add here in-place; we will control by skipping duplicates below
                if needs_blank_after_wc:
                    # We cannot insert into `lines`; instead, we will inject into out by setting a marker
                    # Store a sentinel via to_insert with a special tag that we apply later
                    to_insert.append("__ADD_BLANK_AFTER_WC__\n")

            # Append any planned insertions
            out.extend(to_insert)

            # Now skip over the original excess blank lines we've replaced
            # Skip all blank lines we already accounted for
            if j < n and lines[j].strip() == "":
                # We kept one blank in `to_insert` only if needed; skip all consecutive blanks
                while j < n and lines[j].strip() == "":
                    j += 1

            if next_is_wc:
                # We did not re-insert WC, so copy it now and manage spacing
                out.append(lines[k])
                j = k + 1
                # After WC, ensure single blank line exists; collapse multiples
                if j < n and lines[j].strip() == "":
                    # Keep exactly one blank line
                    out.append("\n")
                    j += 1
                    while j < n and lines[j].strip() == "":
                        j += 1
                # No blank after; check if we queued a blank to add
                elif any(x == "__ADD_BLANK_AFTER_WC__\n" for x in to_insert):
                    out.append("\n")

            # Continue from j (we've already handled the post-header area)
            i = j
            continue
        i += 1

    # Remove any sentinels if any made it through (shouldn't)
    out = [line for line in out if line != "__ADD_BLANK_AFTER_WC__\n"]

    # Ensure file ends with a newline
    if out and out[-1] != "\n":
        out.append("\n")

    return out


def main() -> int:
    """CLI entry point."""
    original = FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    normalized = normalize(original)
    if normalized != original:
        FILE.write_text("".join(normalized), encoding="utf-8")
        print("changelog.md normalized.")
    else:
        print("changelog.md already normalized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
