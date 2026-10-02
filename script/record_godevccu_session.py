#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Record the godevccu session used by the homegear session-playback tests.

Starts the godevccu binary in homegear mode with every embedded device type,
runs a central against it with the session recorder recording the system init,
and copies the resulting ZIP to aiohomematic_test_support/data/.

Usage:
    script/install_godevccu.sh
    PYTHONPATH=. python script/record_godevccu_session.py

The recording keeps the device addresses as godevccu reports them
(SR_DISABLE_RANDOMIZE_OUTPUT): the playback tests reference devices by address.
"""

import asyncio
import contextlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from aiohomematic_test_support import const

from aiohomematic.central import CentralConfig
from aiohomematic.client import InterfaceConfig
from aiohomematic.const import (
    DEFAULT_SESSION_RECORDER_START_FOR_SECONDS,
    SUB_DIRECTORY_SESSION,
    Interface,
    OptionalSettings,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "aiohomematic_test_support" / "data" / const.FULL_SESSION_GODEVCCU
START_TIMEOUT = 15.0
# The recorder saves itself after DEFAULT_SESSION_RECORDER_START_FOR_SECONDS; allow time to write the ZIP.
SAVE_GRACE = 30.0


def _binary() -> str:
    """Return the godevccu binary."""
    if path := os.environ.get("GODEVCCU_BIN"):
        return path
    if (repo_binary := REPO_ROOT / ".godevccu" / "godevccu").exists():
        return str(repo_binary)
    sys.exit("godevccu binary not found: run script/install_godevccu.sh or set GODEVCCU_BIN")


def _start_godevccu(*, work_dir: Path) -> tuple[subprocess.Popen[bytes], int]:
    """Start godevccu and return the process and its XML-RPC port."""
    ports_file = work_dir / "ports.json"
    with (work_dir / "godevccu.log").open("wb") as log:
        process = subprocess.Popen(
            [
                _binary(),
                "-mode",
                "homegear",
                "-host",
                const.CCU_HOST,
                "-xml-rpc-port",
                "0",
                "-json-rpc-port",
                "0",
                "-ports-json",
                str(ports_file),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        if process.poll() is not None:
            sys.exit(f"godevccu exited with {process.returncode}")
        if ports_file.exists():
            return process, int(json.loads(ports_file.read_text())["xmlrpc"])
        time.sleep(0.05)
    process.terminate()
    sys.exit("godevccu did not report its ports")


async def _record(*, port: int, storage_dir: Path) -> Path:
    """Run a central against godevccu until the recorder has saved, return the ZIP."""
    central = await CentralConfig(
        name=const.CENTRAL_NAME,
        host=const.CCU_HOST,
        username=const.CCU_USERNAME,
        password=const.CCU_PASSWORD,
        central_id="test1234",
        interface_configs=frozenset(
            {InterfaceConfig(central_name=const.CENTRAL_NAME, interface=Interface.BIDCOS_RF, port=port)}
        ),
        storage_directory=str(storage_dir),
        program_markers=(),
        sysvar_markers=(),
        # start_direct: the central fetches listDevices itself. With a callback server the
        # devices arrive via newDevices instead, which the recorder (outgoing calls) misses.
        start_direct=True,
        optional_settings=(OptionalSettings.SR_RECORD_SYSTEM_INIT, OptionalSettings.SR_DISABLE_RANDOMIZE_OUTPUT),
    ).create_central()
    await central.start()
    print(f"Recording for {DEFAULT_SESSION_RECORDER_START_FOR_SECONDS} s ...")
    await asyncio.sleep(DEFAULT_SESSION_RECORDER_START_FOR_SECONDS + SAVE_GRACE)
    await central.stop()
    if not (zips := sorted((storage_dir / SUB_DIRECTORY_SESSION).rglob("*.zip"))):
        sys.exit(f"no session ZIP written below {storage_dir / SUB_DIRECTORY_SESSION}")
    if len(zips) != 1:
        sys.exit(f"expected one session ZIP, found {[str(z) for z in zips]}")
    return zips[0]


def main() -> None:
    """Record the session and copy it into the test-support data directory."""
    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)
        process, port = _start_godevccu(work_dir=work_dir)
        try:
            recorded = asyncio.run(_record(port=port, storage_dir=work_dir / "storage"))
            shutil.copyfile(recorded, TARGET)
        finally:
            process.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=5)
    print(f"Session written to {TARGET}")


if __name__ == "__main__":
    main()
