#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Documentation translation status checker and coordinator.

This script manages the translation lifecycle for mkdocs documentation.
English source files (docs/*.md) are tracked against their German translations
(docs/*.de.md) using content hashes. Uses suffix-based i18n structure.

Translation is done **manually** via Claude Code (local), not via API.
This script only handles status checking, hash tracking, and file scaffolding.

Usage::

    # Show status of all translatable files
    python script/translate_docs.py

    # Check which files need translation (CI-friendly, exit code 1 if outdated)
    python script/translate_docs.py --check

    # Scaffold missing DE files with placeholder
    python script/translate_docs.py --scaffold

    # Mark a DE file as up-to-date (after manual translation via Claude Code)
    python script/translate_docs.py --mark-current docs/quickstart.de.md

Exit codes:
    0 - All translations are up to date (--check) or operation succeeded
    1 - Translations are outdated or missing (--check)
"""

import argparse
import hashlib
from pathlib import Path

# Docs root
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
GLOSSARY_FILE = DOCS_DIR / "glossary_terms.yml"

# Phase 1 files (highest priority for translation)
PHASE_1_FILES = [
    "index.md",
    "quickstart.md",
    "user/homeassistant_integration.md",
    "user/features/week_profile.md",
    "user/features/config_panel.md",
    "user/features/homeassistant_actions.md",
    "user/troubleshooting/homeassistant_troubleshooting.md",
    "user/troubleshooting/troubleshooting_flowchart.md",
    "faq.md",
    "user/device_support.md",
]

# Phase 2 files
PHASE_2_FILES = [
    "user/advanced/cuxd_ccu_jack.md",
    "user/advanced/optional_settings.md",
    "user/advanced/unignore.md",
    "user/advanced/security.md",
    "user/features/backup.md",
    "user/features/optimistic_updates.md",
    "troubleshooting/index.md",
    "troubleshooting/paramset_inconsistency.md",
]

HEADER_TEMPLATE = """---
translation_source: docs/{rel_path}
translation_date: {date}
translation_source_hash: {source_hash}
---

"""

SCAFFOLD_CONTENT = """<!-- This file needs translation from English to German.

Source: docs/{rel_path}

To translate:
1. Open this file and the English source side by side
2. Use Claude Code: "Translate docs/{rel_path} to German, write to {de_path}"
3. Run: python script/translate_docs.py --mark-current {de_path}

Translation rules are defined in docs/glossary_terms.yml
-->

!!! warning "Diese Seite ist noch nicht übersetzt"

    Diese Seite ist noch nicht auf Deutsch verfügbar.
    Bitte nutzen Sie die [englische Version]({en_name}).
"""


def _en_to_de_path(en_path: Path) -> Path:
    """Convert an English doc path to its German suffix-based counterpart."""
    return en_path.with_suffix(".de.md")


def _de_to_en_path(de_path: Path) -> Path:
    """Convert a German suffix-based path to its English counterpart."""
    # foo.de.md -> foo.md
    name = de_path.name
    if name.endswith(".de.md"):
        en_name = name.removesuffix(".de.md") + ".md"
        return de_path.with_name(en_name)
    return de_path


def compute_hash(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def parse_translation_header(content: str) -> dict[str, str]:
    """Extract translation metadata from frontmatter."""
    metadata: dict[str, str] = {}
    if not content.startswith("---\n"):
        return metadata
    end = content.find("\n---\n", 4)
    if end == -1:
        return metadata
    for line in content[4:end].splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            metadata[key.strip()] = value.strip()
    return metadata


def get_file_status(en_path: Path) -> tuple[str, str]:
    """
    Return translation status for an EN file.

    Returns:
        Tuple of (status, detail) where status is one of:
        - "current": DE file exists and is up to date
        - "outdated": DE file exists but EN source changed
        - "missing": No DE file exists
        - "scaffold": DE file exists but is a placeholder

    """
    rel = en_path.relative_to(DOCS_DIR)
    de_path = _en_to_de_path(en_path)

    if not de_path.exists():
        return "missing", str(rel)

    de_content = de_path.read_text(encoding="utf-8")

    # Check if it's a scaffold placeholder
    if "Diese Seite ist noch nicht übersetzt" in de_content:
        return "scaffold", str(rel)

    metadata = parse_translation_header(de_content)
    source_hash = metadata.get("translation_source_hash", "")

    current_hash = compute_hash(en_path)
    if source_hash == current_hash:
        return "current", str(rel)
    return "outdated", f"{rel} (source changed)"


def get_target_files(files: list[str] | None) -> list[Path]:
    """Get list of EN files to process."""
    if files:
        result = []
        for f in files:
            p = Path(f)
            if not p.is_absolute():
                name = str(p)
                if name.endswith(".de.md"):
                    # Convert DE path to EN path
                    en_name = name.removesuffix(".de.md") + ".md"
                    p = DOCS_DIR.parent / en_name if en_name.startswith("docs/") else DOCS_DIR / en_name
                elif name.startswith("docs/"):
                    p = DOCS_DIR.parent / name
                else:
                    p = DOCS_DIR / f
            if p.exists():
                result.append(p)
        return result

    targets = PHASE_1_FILES + PHASE_2_FILES
    return [DOCS_DIR / f for f in targets if (DOCS_DIR / f).exists()]


def cmd_status(files: list[str] | None) -> int:
    """Show status of all translatable files."""
    all_files = get_target_files(files)
    counts = {"current": 0, "outdated": 0, "missing": 0, "scaffold": 0}

    for en_path in all_files:
        status, detail = get_file_status(en_path)
        counts[status] += 1
        icon = {"current": "+", "outdated": "~", "missing": "-", "scaffold": "?"}[status]
        print(f"  [{icon}] {detail}")

    total = sum(counts.values())
    print(f"\nTotal: {total} files")
    print(f"  [+] Current:   {counts['current']}")
    print(f"  [~] Outdated:  {counts['outdated']}")
    print(f"  [-] Missing:   {counts['missing']}")
    print(f"  [?] Scaffold:  {counts['scaffold']}")

    if counts["missing"] + counts["outdated"] + counts["scaffold"] > 0:
        print("\nTo translate, use Claude Code:")
        print('  "Translate docs/<file>.md to German following docs/glossary_terms.yml"')
        print("  Then run: python script/translate_docs.py --mark-current docs/<file>.de.md")
    return 0


def cmd_check(files: list[str] | None) -> int:
    """Check translation status. Returns 1 if any are outdated/missing."""
    all_files = get_target_files(files)
    issues: list[str] = []

    for en_path in all_files:
        status, detail = get_file_status(en_path)
        if status == "missing":
            issues.append(f"  MISSING:  {detail}")
        elif status == "outdated":
            issues.append(f"  OUTDATED: {detail}")
        elif status == "scaffold":
            issues.append(f"  SCAFFOLD: {detail}")

    if issues:
        print(f"Found {len(issues)} translation issue(s):\n")
        for issue in issues:
            print(issue)
        print("\nTranslate locally via Claude Code, then mark as current.")
        return 1

    print("All translations are up to date.")
    return 0


def cmd_scaffold(files: list[str] | None) -> int:
    """Create placeholder DE files for missing translations."""
    all_files = get_target_files(files)
    created = 0

    for en_path in all_files:
        status, _ = get_file_status(en_path)
        if status != "missing":
            continue

        rel = en_path.relative_to(DOCS_DIR)
        de_path = _en_to_de_path(en_path)
        de_rel = de_path.relative_to(DOCS_DIR)

        content = SCAFFOLD_CONTENT.format(
            rel_path=rel,
            de_path=f"docs/{de_rel}",
            en_name=en_path.name,
        )
        de_path.write_text(content, encoding="utf-8")
        print(f"  Created scaffold: docs/{de_rel}")
        created += 1

    print(f"\n{created} scaffold(s) created.")
    return 0


def cmd_mark_current(files: list[str]) -> int:
    """Update the source hash in a translated DE file to mark it as current."""
    if not files:
        print("ERROR: Specify DE file(s) to mark as current.")
        return 1

    updated = 0
    for f in files:
        de_path = Path(f)
        if not de_path.is_absolute():
            de_path = DOCS_DIR.parent / de_path if str(de_path).startswith("docs/") else DOCS_DIR / f

        if not de_path.exists():
            print(f"  ERROR: {de_path} does not exist")
            continue

        if not de_path.name.endswith(".de.md"):
            print(f"  ERROR: {de_path} is not a .de.md file")
            continue

        # Derive EN source path
        en_path = _de_to_en_path(de_path)
        if not en_path.exists():
            print(f"  ERROR: Source {en_path} does not exist")
            continue

        rel = en_path.relative_to(DOCS_DIR)
        source_hash = compute_hash(en_path)
        today = __import__("datetime").date.today().isoformat()

        de_content = de_path.read_text(encoding="utf-8")

        # Replace or add header
        new_header = f"---\ntranslation_source: docs/{rel}\ntranslation_date: {today}\ntranslation_source_hash: {source_hash}\n---\n"

        if de_content.startswith("---\n"):
            end = de_content.find("\n---\n", 4)
            de_content = new_header + de_content[end + 5 :] if end != -1 else new_header + "\n" + de_content
        else:
            de_content = new_header + "\n" + de_content

        de_path.write_text(de_content, encoding="utf-8")
        de_rel = de_path.relative_to(DOCS_DIR)
        print(f"  Marked current: docs/{de_rel} (hash: {source_hash})")
        updated += 1

    print(f"\n{updated} file(s) marked as current.")
    return 0


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Manage documentation translations (EN -> DE).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Check if translations are up to date (CI)")
    group.add_argument("--scaffold", action="store_true", help="Create placeholder files for missing translations")
    group.add_argument(
        "--mark-current", action="store_true", help="Mark DE file(s) as up-to-date with current EN source"
    )
    parser.add_argument("files", nargs="*", help="Specific files to process")
    args = parser.parse_args()

    if args.check:
        return cmd_check(args.files or None)
    if args.scaffold:
        return cmd_scaffold(args.files or None)
    if args.mark_current:
        return cmd_mark_current(args.files)
    return cmd_status(args.files or None)


if __name__ == "__main__":
    raise SystemExit(main())
