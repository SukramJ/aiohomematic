# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
File system operations for aiohomematic.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import asyncio
import glob
import os

from aiohomematic import i18n
from aiohomematic.exceptions import AioHomematicException

__all__ = [
    "check_or_create_directory",
    "cleanup_script_for_session_recorder",
    "delete_file",
]


def delete_file(directory: str, file_name: str) -> None:  # kwonly: disable
    """Delete the file. File can contain a wildcard."""
    if os.path.exists(directory):
        for file_path in glob.glob(os.path.join(directory, file_name)):
            if os.path.isfile(file_path):
                os.remove(file_path)


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
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
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
