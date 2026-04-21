# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
File system operations for aiohomematic.

Public API of this module is defined by __all__.
"""

import asyncio
from pathlib import Path

from aiohomematic import i18n
from aiohomematic.exceptions import AioHomematicException

__all__ = [
    "check_or_create_directory",
    "cleanup_script_for_session_recorder",
    "delete_file",
]


def delete_file(directory: str, file_name: str) -> None:  # kwonly: disable
    """Delete the file. File can contain a wildcard."""
    dir_path = Path(directory)
    if dir_path.exists():
        real_directory = dir_path.resolve()
        for file_path in dir_path.glob(file_name):
            resolved = file_path.resolve()
            if resolved.is_relative_to(real_directory) and resolved.is_file():
                resolved.unlink()


def cleanup_script_for_session_recorder(*, script: str) -> str:
    """
    Cleanup the script for session recording.

    Keep only the first line (script name) and lines starting with '!# param:'.
    The first line contains the script identifier (e.g., '!# name: script.fn' or '!# script.fn').
    """

    if not (lines := script.splitlines()):
        return ""
    # Keep the first line (script name) and all param lines
    result = [lines[0]]
    result.extend(line for line in lines[1:] if line.startswith("!# param:"))
    return "\n".join(result)


def _check_or_create_directory_sync(*, directory: str) -> bool:
    """Check / create directory (internal sync implementation)."""
    if not directory:
        return False
    dir_path = Path(directory)
    if not dir_path.exists():
        try:
            dir_path.mkdir(mode=0o700, parents=True)
        except OSError as oserr:
            raise AioHomematicException(
                i18n.tr(
                    key="exception.support.check_or_create_directory.failed",
                    directory=directory,
                    reason=oserr.strerror,
                )
            ) from oserr
    return True


async def check_or_create_directory(*, directory: str) -> bool:
    """Check / create directory asynchronously."""
    return await asyncio.to_thread(_check_or_create_directory_sync, directory=directory)
