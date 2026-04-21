#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Doc-drift linter for aiohomematic.

Checks ``docs/`` for three classes of drift:

1. **Broken relative links** — every ``[text](path.md)`` / ``[text](path.md#anchor)``
   relative link in a markdown file must resolve to an existing file.
2. **Stale class names** — known-renamed classes must not appear as bare names any more.
   The renames are hard-coded below; extend ``STALE_PATTERNS`` when the codebase is
   refactored.
3. **Missing event types** — every concrete ``Event`` subclass exported from
   ``aiohomematic.central.events`` (i.e. listed in its ``__all__``) must appear at least
   once in ``docs/architecture/events/event_reference.md``. This catches drift when new
   events are added but the hand-written reference is not updated.

Exits with code ``1`` if any issue is found, otherwise ``0``.

Run manually::

    python script/check_docs_references.py

Or wire into prek (see ``.pre-commit-config.yaml``).
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"
EVENT_REFERENCE = DOCS / "architecture" / "events" / "event_reference.md"
EVENTS_INIT = REPO_ROOT / "aiohomematic" / "central" / "events" / "__init__.py"

# Known-renamed identifiers that must not appear as bare words in docs.
# Pattern → explanation (shown in the error message).
STALE_PATTERNS: dict[str, str] = {
    r"\bXmlRpcProxy\b": "renamed to AioXmlRpcProxy",
    r"\bxml_rpc_server\.py\b": "renamed to rpc_server.py",
    r"\baiohomematic/caches/\b": "moved to aiohomematic/store/",
    r"\b0018_contract_tests\.md\b": "renamed to 0018-contract-tests.md",
    r"\b0013-implementation-status\.md\b": "renamed to 0013a-implementation-status.md",
}

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`]*`")


def _strip_code(text: str) -> str:
    """Remove fenced and inline code blocks so regexes don't match Python snippets."""
    text = FENCED_CODE_RE.sub("", text)
    return INLINE_CODE_RE.sub("", text)


def _load_exported_event_classes() -> list[str]:
    """Read ``__all__`` from the events package and return concrete Event class names."""
    text = EVENTS_INIT.read_text(encoding="utf-8")
    match = re.search(r"__all__\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if not match:
        return []
    names = re.findall(r'"([A-Z][A-Za-z0-9_]*)"', match.group(1))
    # We only track public Event classes in the reference; skip helpers/enums/protocols.
    skip = {
        "EventBus",
        "EventBatch",
        "HandlerStats",
        "SubscriptionGroup",
        "Event",
        "EventPriority",
        "DataFetchOperation",
        "DeviceLifecycleEventType",
        "IntegrationIssue",
    }
    return [n for n in names if n.endswith("Event") and n not in skip]


def _check_broken_links() -> list[str]:
    """Return error messages for broken relative markdown links."""
    errors: list[str] = []
    for md in DOCS.rglob("*.md"):
        if "_build" in md.parts:
            continue
        text = _strip_code(md.read_text(encoding="utf-8"))
        for target in LINK_RE.findall(text):
            # Skip external URLs, anchors-only, mailto and auto-link placeholders.
            if target.startswith(("http://", "https://", "mailto:", "#", "<")):
                continue
            path_part = target.split("#", 1)[0].split("?", 1)[0].strip()
            if not path_part:
                continue
            resolved = (md.parent / path_part).resolve()
            if not resolved.exists():
                rel = md.relative_to(REPO_ROOT)
                errors.append(f"{rel}: broken link → {target}")
    return errors


def _check_stale_patterns() -> list[str]:
    """Return error messages for stale identifiers in docs."""
    errors: list[str] = []
    for md in DOCS.rglob("*.md"):
        if "_build" in md.parts:
            continue
        # Skip changelog — historical entries legitimately reference old names.
        if md.name == "changelog.md":
            continue
        raw = md.read_text(encoding="utf-8")
        stripped = _strip_code(raw)
        for pattern, explanation in STALE_PATTERNS.items():
            for match in re.finditer(pattern, stripped):
                line_no = stripped[: match.start()].count("\n") + 1
                rel = md.relative_to(REPO_ROOT)
                errors.append(f"{rel}:{line_no}: stale reference '{match.group()}' ({explanation})")
    return errors


def _check_event_reference_coverage() -> list[str]:
    """Return error messages for Event classes missing from event_reference.md."""
    if not EVENT_REFERENCE.exists():
        return [f"{EVENT_REFERENCE.relative_to(REPO_ROOT)}: file missing"]
    reference = EVENT_REFERENCE.read_text(encoding="utf-8")
    missing = [cls for cls in _load_exported_event_classes() if cls not in reference]
    if missing:
        rel = EVENT_REFERENCE.relative_to(REPO_ROOT)
        return [f"{rel}: missing Event class(es): {', '.join(sorted(missing))}"]
    return []


def main() -> int:
    """Run all drift checks and return a non-zero exit code when any issue is found."""
    errors: list[str] = []
    errors.extend(_check_broken_links())
    errors.extend(_check_stale_patterns())
    errors.extend(_check_event_reference_coverage())
    if errors:
        print("Documentation drift detected:\n")
        for err in errors:
            print(f"  - {err}")
        print(f"\n{len(errors)} issue(s) found. See script/check_docs_references.py for details.")
        return 1
    print("docs/: no drift detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
