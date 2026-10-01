# Plan: godevccu as an alternative test simulator to pydevccu

Status: Phases A–C done (2026-10-01): godevccu v0.6.0 released, fixtures switchable, CI job blocking after 3 identical runs. Phase D open.
Scope: test infrastructure only — no change to `aiohomematic/` production code.
Repos touched: `../godevccu` (Phase A), `aiohomematic` (Phases B–C).
Out of scope: removing pydevccu (Phase D, separate decision after Phase C).

## 1. Goal

Run the simulator-backed tests against `godevccu` (Go binary, subprocess) as an
alternative to `pydevccu` (in-process Python library), selected by an environment
variable. `pydevccu` stays the default until Phase C shows equal results.

## 2. Facts this plan rests on (measured, with source)

| Fact                                                                                                                                                                                                       | Source                                                                                                                                                                        |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| pydevccu is a test-only dependency, pinned `pydevccu==0.2.6`                                                                                                                                               | `requirements_test.txt:11`                                                                                                                                                    |
| Three session fixtures start the simulator: `pydevccu_mini` (devices `HmIP-BWTH`, `HmIP-eTRV-2`), `pydevccu_full`, `pydevccu_openccu` (`VirtualCCU`, `BackendMode.OPENCCU`, auth, `setup_default_state()`) | `tests/conftest.py:170`, `:213`, `:284`                                                                                                                                       |
| Teardown reaches into pydevccu internals: `_rpcfunctions.remotes.clear()`                                                                                                                                  | `tests/conftest.py:205`, `:262`, `:430-431`                                                                                                                                   |
| The openccu teardown is already guarded by `hasattr(..., "_xml_rpc_server")`                                                                                                                               | `tests/conftest.py:430`                                                                                                                                                       |
| Fixture consumers: `test_central_pydevccu.py`, `test_central_pydev_openccu.py`, `test_backend_openccu.py`, `test_model_climate.py`, `test_model_access_permission.py`, `test_error_paths.py`               | `grep -rlE "central_unit_pydevccu\|central_unit_openccu\|pydevccu_(full\|mini\|openccu)" tests`                                                                               |
| Ports are fixed per xdist worker (`base + 2*worker_no`)                                                                                                                                                    | `aiohomematic_test_support/const.py:18-55`                                                                                                                                    |
| aiohomematic picks `HomegearBackend` when the version string contains `pydevccu`                                                                                                                           | `aiohomematic/client/backends/factory.py:78`, `aiohomematic/backend_detection.py:251`                                                                                         |
| godevccu in homegear mode answers `getVersion` with `"pydevccu-" + PydevccuVersion` (`"pydevccu-0.2.0"`)                                                                                                   | `../godevccu/internal/ccu/rpcfunctions.go:213-219`, `internal/hmconst/hmconst.go:18`                                                                                          |
| godevccu in ccu/openccu mode answers with the CCU firmware version                                                                                                                                         | `../godevccu/internal/virtualccu/virtualccu.go:288-291`                                                                                                                       |
| godevccu CLI default mode is `openccu`                                                                                                                                                                     | `../godevccu/cmd/godevccu/main.go:39`                                                                                                                                         |
| godevccu CLI has **no** device filter outside lite mode; `Config.Devices` exists in the library                                                                                                            | `main.go:53` (`-lite-devices` only), `main.go:83-106`; `internal/virtualccu/virtualccu.go:61`                                                                                 |
| Device filter in godevccu matches the file-derived type name, case-insensitive                                                                                                                             | `../godevccu/internal/ccu/loader.go:43-64`                                                                                                                                    |
| `-ports-json FILE` writes the bound ports atomically once every server listens; keys `xmlrpc`, `jsonrpc`, …                                                                                                | `main.go:59`, `main.go:185-205`, `internal/virtualccu/scenario.go:257-276`                                                                                                    |
| Port `0` on the CLI = system-picked port                                                                                                                                                                   | `main.go:85-88`, `main.go:158-164`                                                                                                                                            |
| BIN-RPC, ReGa script port and SSDP are off by default (no fixed extra ports)                                                                                                                               | `internal/virtualccu/virtualccu.go:53-57`, `:85-93`, `:433`                                                                                                                   |
| `-defaults` seeds programs, sysvars, rooms, functions (same fixture set as pydevccu)                                                                                                                       | `main.go:47`, `internal/state/defaults.go:8-47`                                                                                                                               |
| `init(url, "")` unregisters a remote in godevccu                                                                                                                                                           | `internal/ccu/rpcfunctions.go:1125-1141`                                                                                                                                      |
| Device catalogue of godevccu is byte-identical to `../pydevccu` 0.2.6 (399 device + 399 paramset files, `diff -rq` empty)                                                                                  | `diff -rq ../pydevccu/pydevccu/device_descriptions ../godevccu/internal/embed/data/device_descriptions` (same for `paramset_descriptions`), `../pydevccu/pydevccu/const.py:7` |
| godevccu releases ship `godevccu-<tag>-<os>-<arch>` plus `.sha256` (file name only inside)                                                                                                                 | `../godevccu/.github/workflows/release.yml:93-102`, `gh release view v0.5.0 -R SukramJ/godevccu`                                                                              |
| ruff reports `S603` for `subprocess.Popen(cmd)` under `tests/helpers/`                                                                                                                                     | probe run with `venv/bin/ruff check` on a scratch file                                                                                                                        |

Not verified (to be measured in Phase C): whether every test produces the same
result on godevccu; whether godevccu in homegear mode behaves like `pydevccu.Server`
in event timing, logic devices and persistence.

## 3. Phase A — godevccu: add `-devices` flag

Repo: `../godevccu`. Branch: `feature/cli-devices-flag`.

### A1. `cmd/godevccu/main.go`

After the line

```go
	portsJSON := flag.String("ports-json", "", "once every server listens, write the bound ports as JSON to this file, or as one line to stdout with \"-\"")
```

insert

```go
	devices := flag.String("devices", "", "comma-separated device types to load (empty: every embedded type); lite mode uses -lite-devices")
```

After the line

```go
	cfg.EnableLogic = *logic
```

insert

```go
	if *devices != "" {
		cfg.Devices = splitList(*devices)
	}
```

### A2. `README.md`

In the CLI example block under `### As a CLI`, add the line

```bash
./bin/godevccu -mode homegear -xml-rpc-port 2001 -devices HmIP-BWTH,HmIP-eTRV-2
```

### A3. `CHANGELOG.md`

Under `## [Unreleased]` add:

```markdown
### Added

- CLI: `-devices` restricts the loaded device types outside lite mode
  (the library already had `Config.Devices`).
```

### A4. Verify

```bash
cd ../godevccu
make build && make test && make lint
./bin/godevccu -mode homegear -host 127.0.0.1 -xml-rpc-port 2101 -json-rpc-port 0 \
  -devices HmIP-BWTH,HmIP-eTRV-2 -ports-json /tmp/gd_ports.json &
sleep 1; cat /tmp/gd_ports.json
python3 -c "import xmlrpc.client as x; p=x.ServerProxy('http://127.0.0.1:2101'); print(p.getVersion(), len(p.listDevices()))"
kill %1
```

Compare the `listDevices` length with pydevccu (run from the aiohomematic venv):

```bash
python -c "import os,time,xmlrpc.client as x,pydevccu; s=pydevccu.Server(addr=('127.0.0.1',2102),devices=['HmIP-BWTH','HmIP-eTRV-2']); s.start(); time.sleep(1); p=x.ServerProxy('http://127.0.0.1:2102'); print(p.getVersion(), len(p.listDevices())); os._exit(0)"
```

Expected: godevccu prints `pydevccu-0.2.0 <N>`, pydevccu prints `pydevccu <version> <N>`
with the **same N**. If N differs, stop and report — do not continue to Phase B.

### A5. Release

1. `git tag | sort -V | tail -1` — take the next minor version (after `v0.5.0` that is `v0.6.0`; use whatever is next if a newer tag exists).
2. Rename `## [Unreleased]` content into `## [<version>] — <date>`, keep an empty `## [Unreleased]`.
3. PR → merge → tag `v<version>`. The release workflow builds the binaries.

## 4. Phase B — aiohomematic: switchable simulator

Branch: `feature/godevccu-test-backend`.

### B1. New file `tests/helpers/godevccu_process.py`

```python
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
```

### B2. `tests/conftest.py`

1. Imports: below `from tests.helpers.mock_xml_rpc import MockXmlRpcServer` add

   ```python
   from tests.helpers.godevccu_process import GodevccuProcess, find_godevccu_binary, use_godevccu
   ```

2. Replace

   ```python
   requires_openccu = pytest.mark.skipif(
       not PYDEVCCU_HAS_OPENCCU_SUPPORT,
   ```

   with

   ```python
   requires_openccu = pytest.mark.skipif(
       not (PYDEVCCU_HAS_OPENCCU_SUPPORT or use_godevccu()),
   ```

3. Add this helper directly above the `# homegear mini fixtures` comment:

   ```python
   def _start_godevccu(*, args: list[str], tmp_path_factory: pytest.TempPathFactory) -> GodevccuProcess:
       """Start a godevccu subprocess in its own temp directory."""
       process = GodevccuProcess(
           binary=find_godevccu_binary(),
           args=args,
           work_dir=tmp_path_factory.mktemp("godevccu"),
       )
       process.start()
       return process
   ```

4. `pydevccu_mini`: change the signature to

   ```python
   def pydevccu_mini(tmp_path_factory: pytest.TempPathFactory) -> pydevccu.Server | GodevccuProcess:
   ```

   and insert as the first statements after the docstring:

   ```python
       if use_godevccu():
           process = _start_godevccu(
               args=[
                   "-mode", "homegear",
                   "-host", const.CCU_HOST,
                   "-xml-rpc-port", str(const.get_ccu_mini_port()),
                   "-json-rpc-port", "0",
                   "-devices", "HmIP-BWTH,HmIP-eTRV-2",
               ],
               tmp_path_factory=tmp_path_factory,
           )
           try:
               yield process
           finally:
               process.stop()
           return
   ```

5. `pydevccu_full`: same pattern, signature
   `def pydevccu_full(tmp_path_factory: pytest.TempPathFactory) -> pydevccu.Server | GodevccuProcess:`,
   args identical to B2.4 **without** the `"-devices", …` pair and with
   `const.get_ccu_port()` instead of `const.get_ccu_mini_port()`.

6. `pydevccu_openccu`: change the signature to

   ```python
   def pydevccu_openccu(tmp_path_factory: pytest.TempPathFactory) -> VirtualCCU | GodevccuProcess | None:  # type: ignore[name-defined]
   ```

   and insert directly after the docstring (before the `if not PYDEVCCU_HAS_OPENCCU_SUPPORT:` check):

   ```python
       if use_godevccu():
           process = _start_godevccu(
               args=[
                   "-mode", "openccu",
                   "-host", const.CCU_HOST,
                   "-xml-rpc-port", str(const.get_openccu_xml_rpc_port()),
                   "-json-rpc-port", str(const.get_openccu_json_rpc_port()),
                   "-username", const.CCU_USERNAME,
                   "-password", const.CCU_PASSWORD,
                   "-auth=true",
                   "-defaults",
               ],
               tmp_path_factory=tmp_path_factory,
           )
           try:
               yield process
           finally:
               process.stop()
           return
   ```

7. `central_unit_pydevccu_mini` teardown: replace

   ```python
           pydevccu_mini._rpcfunctions.remotes.clear()
   ```

   with

   ```python
           if isinstance(pydevccu_mini, pydevccu.Server):
               pydevccu_mini._rpcfunctions.remotes.clear()
   ```

   and change the parameter annotation to `pydevccu_mini: pydevccu.Server | GodevccuProcess`.

8. `central_unit_pydevccu_full`: same as B2.7 with `pydevccu_full`.

9. `central_unit_openccu`: no change — the teardown is already guarded by
   `hasattr(pydevccu_openccu, "_xml_rpc_server")` (`tests/conftest.py:430`); a
   `GodevccuProcess` has no such attribute. Its `if not PYDEVCCU_HAS_OPENCCU_SUPPORT:`
   skip must become `if not (PYDEVCCU_HAS_OPENCCU_SUPPORT or use_godevccu()):`.

Rationale for dropping `remotes.clear()` with godevccu: the clear exists to stop
pydevccu's `_askDevices` Python thread from raising into pytest
(`pyproject.toml:433-437`). godevccu runs in another process; a failing callback
there only lands in `godevccu.log`. Phase C checks that log for errors after stop.

### B3. New file `tests/test_godevccu_process.py`

```python
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for the godevccu subprocess helper."""

from pathlib import Path
import sys

import pytest

from tests.helpers.godevccu_process import (
    GODEVCCU_BIN_ENV,
    SIMULATOR_ENV,
    GodevccuProcess,
    find_godevccu_binary,
    use_godevccu,
)

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="uses POSIX shebang scripts")


def _write_script(*, path: Path, body: str) -> str:
    path.write_text(f"#!{sys.executable}\n{body}")
    path.chmod(0o755)
    return str(path)


class TestGodevccuProcess:
    """Test GodevccuProcess against fake binaries."""

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

    def test_start_raises_with_log_when_process_exits(self, tmp_path: Path) -> None:
        binary = _write_script(path=tmp_path / "fake_fail", body="import sys\nprint('boom')\nsys.exit(3)\n")
        process = GodevccuProcess(binary=binary, args=[], work_dir=tmp_path)
        with pytest.raises(RuntimeError, match=r"exited with 3: boom"):
            process.start()


class TestSimulatorSelection:
    """Test environment-based simulator selection."""

    def test_default_is_pydevccu(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(SIMULATOR_ENV, raising=False)
        assert use_godevccu() is False

    def test_godevccu_selected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(SIMULATOR_ENV, "godevccu")
        assert use_godevccu() is True

    def test_binary_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(GODEVCCU_BIN_ENV, "/opt/godevccu")
        assert find_godevccu_binary() == "/opt/godevccu"

    def test_binary_missing_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(GODEVCCU_BIN_ENV, raising=False)
        monkeypatch.setenv("PATH", "")
        with pytest.raises(RuntimeError, match="godevccu binary not found"):
            find_godevccu_binary()
```

### B4. `.github/workflows/test-run.yaml`

Append a second job under `jobs:` (same indentation as `test:`). Set
`GODEVCCU_VERSION` to the tag released in A5.

```yaml
test-godevccu:
  runs-on: ubuntu-latest
  name: Python 3.14 (godevccu)
  # Informational until Phase C shows parity with pydevccu.
  continue-on-error: true
  env:
    GODEVCCU_VERSION: v0.6.0
    AIOHM_TEST_SIMULATOR: godevccu
  steps:
    - uses: actions/checkout@v7
    - name: Set up Python
      uses: actions/setup-python@v7.0.0
      with:
        python-version: "3.14"
        cache: "pip"
        cache-dependency-path: |
          requirements.txt
          requirements_test.txt
          requirements_test_pre_commit.txt
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements_test.txt
    - name: Download godevccu
      env:
        GH_TOKEN: ${{ github.token }}
      run: |
        mkdir -p "$RUNNER_TEMP/godevccu"
        cd "$RUNNER_TEMP/godevccu"
        asset="godevccu-${GODEVCCU_VERSION}-linux-amd64"
        gh release download "$GODEVCCU_VERSION" -R SukramJ/godevccu -p "$asset" -p "$asset.sha256"
        sha256sum -c "$asset.sha256"
        chmod +x "$asset"
        echo "GODEVCCU_BIN=$RUNNER_TEMP/godevccu/$asset" >> "$GITHUB_ENV"
    - name: Run simulator-backed tests
      run: |
        pytest tests/test_central_pydevccu.py tests/test_central_pydev_openccu.py \
          tests/test_backend_openccu.py tests/test_model_climate.py \
          tests/test_model_access_permission.py tests/test_error_paths.py \
          tests/test_godevccu_process.py \
          -n auto --dist loadscope --asyncio-mode=legacy
```

### B5. Docs: `docs/contributor/dev-environment.md`

Append a section:

````markdown
## Running simulator tests against godevccu

The simulator-backed tests use pydevccu by default. To run them against
[godevccu](https://github.com/SukramJ/godevccu) instead:

```bash
export AIOHM_TEST_SIMULATOR=godevccu
export GODEVCCU_BIN=/path/to/godevccu   # or put godevccu on PATH
pytest tests/test_central_pydevccu.py tests/test_central_pydev_openccu.py \
  tests/test_backend_openccu.py tests/test_model_climate.py \
  tests/test_model_access_permission.py tests/test_error_paths.py
```

The binary is built with `make build` in a godevccu checkout or downloaded from
its GitHub releases. godevccu needs version 0.6.0 or later (`-devices` flag).
````

(Replace `0.6.0` with the version actually released in A5.)

### B6. Changelog / version

1. `git tag --list '2026.10.*' | sort -V | tail -3` and `head -1 changelog.md`.
2. If the top `changelog.md` version is **not** tagged: add the bullet to that entry.
   Otherwise: create `# Version 2026.10.<next NN> (<date>)` and set
   `aiohomematic/const.py:VERSION` to the same value.
3. Bullet (under the existing `## What's Changed` heading of that entry):
   `- Tests: simulator-backed tests can run against godevccu (AIOHM_TEST_SIMULATOR=godevccu); pydevccu stays the default`

### B7. Verify

```bash
pytest tests/test_godevccu_process.py -v
pytest tests/                                   # default = pydevccu, must stay green
AIOHM_TEST_SIMULATOR=godevccu GODEVCCU_BIN=../godevccu/bin/godevccu \
  pytest tests/test_central_pydevccu.py tests/test_central_pydev_openccu.py \
    tests/test_backend_openccu.py tests/test_model_climate.py \
    tests/test_model_access_permission.py tests/test_error_paths.py -v
prek run --all-files
```

## 5. Phase C — parity evaluation

1. Run the six fixture-consuming test files twice (default, then godevccu, commands in B7)
   with `--override-ini="addopts="` (serial run, no xdist) so ordering is identical.
2. Record per test id: pass/fail/skip on each simulator. Put the table in the PR description.
3. For every difference: find the root cause in godevccu or the fixture. **Do not**
   change assertions in aiohomematic to match godevccu without a root cause; a
   godevccu deviation from pydevccu is fixed in godevccu.
4. After the godevccu run, grep every `godevccu.log` under the pytest temp root
   (`pytest --basetemp=<dir>` makes it findable) for `level=ERROR` and list the hits.
5. Exit criterion: identical results in 3 consecutive CI runs of `test-godevccu`.
   Then remove `continue-on-error: true` from B4.

## 6. Phase D — removing pydevccu (not part of this plan)

Only after Phase C, and only on an explicit decision. Would touch
`requirements_test.txt`, the pydevccu branches and imports in `tests/conftest.py`,
the `filterwarnings` entry in `pyproject.toml:433-437`, and docs mentioning
pydevccu as the test simulator. The string `pydevccu` in
`aiohomematic/backend_detection.py` / `client/backends/factory.py` stays, because
godevccu reports itself as `pydevccu-<version>` in homegear mode.

## 7. Risks

- Behavioural drift beyond device data (event timing, logic simulators, persistence)
  is unmeasured — Phase C exists for exactly this.
- godevccu reports `pydevccu-0.2.0`, pydevccu `pydevccu-0.2.6` (both measured via `getVersion`, 2026-10-01); no test asserts the
  exact string (checked with `grep -rnE "pydevccu[ -]0\.|\.version ==|Backend.PYDEVCCU"`
  over the six files).
- Adds a network download to CI (pinned tag, checksum verified).

## 8. Follow-up test ideas

- Contract-style test that `getVersion` of the selected simulator in homegear mode
  contains `pydevccu`, so the backend factory keeps choosing `HomegearBackend`.
- A test that a failing godevccu start surfaces the log tail in the fixture error.
