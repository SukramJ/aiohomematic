#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Lint script to enforce event tier boundaries.

Internal events (defined in ``aiohomematic.central.events.internal``) must not
be imported by external consumer code. This script scans Python files in the
given directories and flags any import of an internal event type.

The canonical internal event module is::

    aiohomematic.central.events.internal

Internal event names are auto-discovered from that module's ``__all__``.

Usage::

    python script/lint_event_tiers.py ../homematicip_local ../aiohomematic2mqtt

Exit codes:
    0 - No violations found
    1 - Violations detected
"""

import ast
from pathlib import Path
import sys

# Internal event names from aiohomematic.central.events.internal.__all__
INTERNAL_EVENTS: frozenset[str] = frozenset(
    {
        # Re-exported from types.py
        "CircuitBreakerStateChangedEvent",
        "CircuitBreakerTrippedEvent",
        "DataFetchCompletedEvent",
        "DataFetchOperation",
        "HealthRecordedEvent",
        # Data point value routing
        "DataPointStatusReceivedEvent",
        "DataPointValueReceivedEvent",
        # Device/channel state
        "DeviceStateChangedEvent",
        "FirmwareStateChangedEvent",
        "LinkPeerChangedEvent",
        # Connection health
        "ConnectionHealthChangedEvent",
        "ConnectionLostEvent",
        "ConnectionStageChangedEvent",
        # Cache
        "CacheInvalidatedEvent",
        # Data refresh
        "DataRefreshCompletedEvent",
        "DataRefreshTriggeredEvent",
        # Program execution
        "ProgramExecutedEvent",
        # Request coalescing
        "RequestCoalescedEvent",
        # Recovery (internal-only)
        "HeartbeatTimerFiredEvent",
        "RecoveryAttemptedEvent",
    }
)


def check_file(path: Path) -> list[str]:
    """Return violations found in a single Python file."""
    violations: list[str] = []
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError, UnicodeDecodeError:
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module is None:
            continue
        # Check imports from aiohomematic.central.events (any sub-path)
        if not node.module.startswith("aiohomematic.central.events"):
            continue
        for alias in node.names:
            name = alias.name
            if name in INTERNAL_EVENTS:
                violations.append(f"{path}:{node.lineno}: imports internal event '{name}' from '{node.module}'")
    return violations


def main() -> int:
    """Scan directories for internal event imports."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <directory> [directory ...]")
        return 1

    skip_dirs = {"venv", ".venv", "node_modules", "__pycache__", ".git", "site-packages"}

    all_violations: list[str] = []
    for dir_arg in sys.argv[1:]:
        scan_dir = Path(dir_arg)
        if not scan_dir.is_dir():
            print(f"Warning: {scan_dir} is not a directory, skipping.")
            continue
        for py_file in sorted(scan_dir.rglob("*.py")):
            if skip_dirs.intersection(py_file.parts):
                continue
            all_violations.extend(check_file(py_file))

    if all_violations:
        print(f"Found {len(all_violations)} internal event import violation(s):\n")
        for v in all_violations:
            print(f"  {v}")
        print(
            "\nInternal events should not be imported by external consumers."
            "\nUse public events from aiohomematic.central.events instead."
        )
        return 1

    print("No internal event tier violations found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
