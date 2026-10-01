# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Run the godevccu simulator as a subprocess for tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import time

GODEVCCU_BIN_ENV = "GODEVCCU_BIN"
SIMULATOR_ENV = "AIOHM_TEST_SIMULATOR"
SIMULATOR_GODEVCCU = "godevccu"
SIMULATOR_PYDEVCCU = "pydevccu"

_START_TIMEOUT = 15.0
_STOP_TIMEOUT = 5.0
_POLL_INTERVAL = 0.05


def use_godevccu() -> bool:
    """Return True if the tests should run against godevccu."""
    return os.environ.get(SIMULATOR_ENV, SIMULATOR_PYDEVCCU) == SIMULATOR_GODEVCCU


def find_godevccu_binary() -> str:
    """Return the godevccu binary from GODEVCCU_BIN or PATH."""
    if path := os.environ.get(GODEVCCU_BIN_ENV):
        return path
    if path := shutil.which("godevccu"):
        return path
    raise RuntimeError(f"godevccu binary not found: set {GODEVCCU_BIN_ENV} or put godevccu on PATH")


class GodevccuProcess:
    """Represent a godevccu subprocess with its bound ports."""

    def __init__(self, *, binary: str, args: list[str], work_dir: Path) -> None:
        """Initialize the process wrapper."""
        self._binary = binary
        self._args = args
        self._ports_file = work_dir / "ports.json"
        self._log_file = work_dir / "godevccu.log"
        self._process: subprocess.Popen[bytes] | None = None
        self.ports: dict[str, int] = {}

    @property
    def is_running(self) -> bool:
        """Return True if the subprocess is alive."""
        return self._process is not None and self._process.poll() is None

    def start(self) -> None:
        """Start godevccu and wait until it reports its ports."""
        cmd = [self._binary, *self._args, "-ports-json", str(self._ports_file)]
        with self._log_file.open("wb") as log:
            self._process = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)  # noqa: S603
        deadline = time.monotonic() + _START_TIMEOUT
        while time.monotonic() < deadline:
            if (returncode := self._process.poll()) is not None:
                raise RuntimeError(f"godevccu exited with {returncode}: {self._log_tail()}")
            if self._ports_file.exists():
                self.ports = json.loads(self._ports_file.read_text())
                return
            time.sleep(_POLL_INTERVAL)
        self.stop()
        raise RuntimeError(f"godevccu did not report its ports within {_START_TIMEOUT}s: {self._log_tail()}")

    def stop(self) -> None:
        """Terminate godevccu, kill it if it does not exit in time."""
        if self._process is None or self._process.poll() is not None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=_STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()

    def _log_tail(self, *, lines: int = 20) -> str:
        """Return the last lines of the godevccu log."""
        if not self._log_file.exists():
            return ""
        return "\n".join(self._log_file.read_text(errors="replace").splitlines()[-lines:])
