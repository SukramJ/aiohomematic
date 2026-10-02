# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for the godevccu subprocess helper."""

from pathlib import Path
import sys

import pytest

from tests.helpers.godevccu_process import GODEVCCU_BIN_ENV, GodevccuProcess, find_godevccu_binary

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="uses POSIX shebang scripts")


def _write_script(*, path: Path, body: str) -> str:
    path.write_text(f"#!{sys.executable}\n{body}")
    path.chmod(0o755)
    return str(path)


class TestGodevccuProcess:
    """Test GodevccuProcess against fake binaries."""

    def test_start_raises_with_log_when_process_exits(self, tmp_path: Path) -> None:
        binary = _write_script(path=tmp_path / "fake_fail", body="import sys\nprint('boom')\nsys.exit(3)\n")
        process = GodevccuProcess(binary=binary, args=[], work_dir=tmp_path)
        with pytest.raises(RuntimeError, match=r"exited with 3: boom"):
            process.start()

    def test_start_reads_ports_and_stop_terminates(self, tmp_path: Path) -> None:
        binary = _write_script(
            path=tmp_path / "fake_ok",
            body=(
                "import json, sys, time\n"
                "target = sys.argv[sys.argv.index('-ports-json') + 1]\n"
                "open(target, 'w').write(json.dumps({'xmlrpc': 4711}))\n"
                "time.sleep(60)\n"
            ),
        )
        process = GodevccuProcess(binary=binary, args=[], work_dir=tmp_path)
        process.start()
        assert process.ports == {"xmlrpc": 4711}
        assert process.is_running
        process.stop()
        assert not process.is_running


class TestFindGodevccuBinary:
    """Test where the godevccu binary is looked up."""

    def test_binary_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(GODEVCCU_BIN_ENV, "/opt/godevccu")
        assert find_godevccu_binary() == "/opt/godevccu"

    def test_binary_from_repo_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        repo_binary = tmp_path / "godevccu"
        repo_binary.touch()
        monkeypatch.delenv(GODEVCCU_BIN_ENV, raising=False)
        monkeypatch.setattr("tests.helpers.godevccu_process._REPO_BINARY", repo_binary)
        assert find_godevccu_binary() == str(repo_binary)

    def test_binary_missing_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv(GODEVCCU_BIN_ENV, raising=False)
        monkeypatch.setattr("tests.helpers.godevccu_process._REPO_BINARY", tmp_path / "missing")
        monkeypatch.setenv("PATH", "")
        with pytest.raises(RuntimeError, match="install_godevccu.sh"):
            find_godevccu_binary()
