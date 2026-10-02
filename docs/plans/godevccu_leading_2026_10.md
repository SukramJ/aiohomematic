# Plan: godevccu becomes the leading simulator, pydevccu is retired

Status: done (2026-10-02) — godevccu v0.8.0 (Go 1.27.1), aiohomematic 2026.10.1/2026.10.2, homematicip_local on aiohomematic 2026.10.2, openccu-loom on godevccu (REST API 13.4.0), pydevccu archived
Repos: `../godevccu` (Phase 1), `aiohomematic` (Phase 2), `../homematicip_local` (Phase 3),
`../openccu-loom` (Phase 4), `SukramJ/pydevccu` archive (Phase 5).
Predecessor: `docs/plans/godevccu_test_backend_2026_10.md` (Phases A–C done).

## 1. Decisions (made by the maintainer, 2026-10-02)

| #   | Decision                                                                                                                                                 |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | `Backend.PYDEVCCU = "PyDevCCU"` is renamed to `Backend.GODEVCCU = "GoDevCCU"`. No alias. Breaking change with migration guide.                           |
| D2  | godevccu reports `getVersion` = `"godevccu-<hmconst.Version>"` in homegear mode. `PydevccuVersion` is removed. aiohomematic detects only `"godevccu"`.   |
| D3  | The pydevccu session file is replaced by a new recording against godevccu.                                                                               |
| D4  | The godevccu version is pinned in one file; CI and `script/install_godevccu.sh` read it; a missing binary fails the fixtures with install instructions.  |
| D5  | godevccu is the leading system; no data is taken from pydevccu any more. All pydevccu references in aiohomematic (code, tests, docs) change to godevccu. |

Derived decisions (stated here so nobody has to guess):

- **Session file name:** `full_session_godevccu.zip`, constant `FULL_SESSION_GODEVCCU`.
  Not "randomized": the recording must use `randomize_output=False` (see 2.6), so the
  old name would be wrong.
- **History stays history:** past `changelog.md` entries and
  `docs/plans/godevccu_test_backend_2026_10.md` are not rewritten. The old plan gets a
  one-line "superseded by" note.
- **godevccu keeps its attribution:** `NOTICE` and the README acknowledgment of pydevccu
  stay (MIT license attribution for code and data that were ported). Code comments in
  godevccu that name pydevccu as the origin of a behaviour stay. Removed: the data-import
  tooling and every instruction to compare against or copy from pydevccu.
- **`init` with callback port 0 under `start_direct`:** no production change. It only
  happens when a `start_direct=True` central is _started_; the HA integration uses
  `start_direct=True` only for `validate_config_and_get_system_information`, which never
  sends `init` (`homematicip_local/.../control_unit.py:257-259,1513-1522,1785-1792`;
  `aiohomematic/client/__init__.py:152` → `interface_client.py:713-724`; `init` is sent only
  from `init_proxy` via `central/coordinators/client.py:577`).

## 2. Facts this plan rests on (measured 2026-10-02)

| Fact                                                                                                                                                                                                              | Source                                                                                                                                                         |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 238 pydevccu references in aiohomematic outside `changelog.md` history and the data dir                                                                                                                           | `grep -rn -i "pydevccu\|pydev_ccu\|pydev_openccu\|PyDev"`                                                                                                      |
| `Backend.PYDEVCCU = "PyDevCCU"`                                                                                                                                                                                   | `aiohomematic/const.py:374`                                                                                                                                    |
| Detection by substring `"pydevccu"`                                                                                                                                                                               | `aiohomematic/backend_detection.py:251-252`, `client/backends/factory.py:78`, `client/backends/homegear.py:86-87`                                              |
| godevccu homegear `getVersion` = `"pydevccu-" + PydevccuVersion`                                                                                                                                                  | `godevccu/internal/ccu/rpcfunctions.go:216-222`, `internal/hmconst/hmconst.go:18`                                                                              |
| Tests on `PydevccuVersion`                                                                                                                                                                                        | `godevccu/internal/hmconst/hmconst_test.go:53`, `internal/virtualccu/virtualccu_test.go:146`, `internal/ccu/extra_test.go:278`                                 |
| godevccu data import from pydevccu                                                                                                                                                                                | `godevccu/Makefile:23,36-37`, `script/copy_data.sh`, `.gitignore:39`, `README.md:14,110,119-125`, `internal/embed/embed.go:5,8`, `CLAUDE.md:5-6,51,63,148-155` |
| ~40 test files use the pydevccu session via `factory_with_homegear_client` / `central_client_factory_with_homegear_client`                                                                                        | `grep -rln "factory_with_homegear_client\|central_client_factory_with_homegear_client" tests`                                                                  |
| Old session: 395 root devices, 2881 addresses; recorded with a real callback server (`init` → `http://127.0.0.1:34461`)                                                                                           | `full_session_randomized_pydevccu.json` (unzipped)                                                                                                             |
| godevccu full catalogue: 399 root devices, 2924 addresses; 394 root addresses shared with the old session, **all 394 with the same TYPE**                                                                         | `listDevices` on godevccu 0.7.0 homegear vs. old session                                                                                                       |
| Old-only device: `VCU1851882` (`HmIP-FWI`), referenced by no test; new-only roots: `VCU2098109`, `VCU4820995`, `VCU6562990`, `VCU8166343`, `VCU9979350`                                                           | same comparison; `grep -rn VCU1851882 tests`                                                                                                                   |
| `randomize_output=True` shuffles the device addresses (`shuffle` of the address list)                                                                                                                             | `aiohomematic/store/persistent/session.py:486-488`                                                                                                             |
| `load_device_description` reads from the installed pydevccu package (`anchor="pydevccu"`); used once                                                                                                              | `aiohomematic_test_support/helper.py:42-46`, `tests/test_central.py:653`                                                                                       |
| `aiohomematic_test_support` ships `data/` (`graft data`)                                                                                                                                                          | `aiohomematic_test_support/MANIFEST.in`                                                                                                                        |
| homematicip_local imports `FULL_SESSION_RANDOMIZED_PYDEVCCU`                                                                                                                                                      | `homematicip_local/tests/conftest.py:15,278`                                                                                                                   |
| Required status checks on `main`: `Run pre-commit hooks`, `Python 3.14`, `Python 3.14t`, `Analyze (Python)`, `Python 3.14 (godevccu)`                                                                             | `gh api repos/SukramJ/aiohomematic/branches/main/protection/required_status_checks`                                                                            |
| openccu-loom uses pydevccu in `snapshot-py` (`script/aiohomematic_snapshot.py:180-181`), `datasource-diff` (`Makefile:357-358`, `script/datasource_diff.py`) and `.github/workflows/cross-stack-parity.yml:44-49` | grep                                                                                                                                                           |
| pydevccu repo: `SukramJ/pydevccu`, not archived, not a fork; PyPI `pydevccu` 0.2.6                                                                                                                                | `gh repo view`, `pip index versions`                                                                                                                           |
| Top `changelog.md` entry `2026.9.5` is untagged (last tag `2026.9.4`)                                                                                                                                             | `git tag --list '2026.*'`, `head -1 changelog.md`                                                                                                              |

## 3. Phase 1 — godevccu (release v0.8.0)

Branch `feat/godevccu-leading`.

1. `internal/hmconst/hmconst.go`: delete `PydevccuVersion` and its comment block (lines 13-18).
2. `internal/ccu/rpcfunctions.go`:
   - Options comment (around line 173-176): "When empty, it defaults to `godevccu-<Version>` (Homegear mode). CCU/OpenCCU callers override this with the real CCU firmware version."
   - default (around line 216-222): `version = "godevccu-" + hmconst.Version`, comment: "Homegear mode identifies the simulator by name so clients can detect it."
3. Tests: `internal/virtualccu/virtualccu_test.go:146` and `internal/ccu/extra_test.go:278` → `want := "godevccu-" + hmconst.Version`; delete the `PydevccuVersion` assertion in `internal/hmconst/hmconst_test.go:53-55`.
4. Remove the data import: delete `script/copy_data.sh`; in `Makefile` delete `PYDEVCCU ?= ../pydevccu` and the `data` target; delete the `.gitignore` block starting at line 39 (comment + its pattern lines).
5. `internal/embed/embed.go:5-8`: "The device and paramset descriptions are maintained in this repository. Add or update a device by placing `device_descriptions/<TYPE>.json` and `paramset_descriptions/<TYPE>.json` under `internal/embed/data/` — the format of the ZIP that Homematic(IP) Local's `export_device_definition` action writes — and rebuild."
6. `README.md`: line 3 → "a virtual HomeMatic CCU … written in Go." (drop "standalone port of pydevccu"); line 14 → "**399 device types** embedded via `//go:embed`"; replace the paragraph at line 110 and the `make data` lines 119-125 with the text of step 5; keep the acknowledgment at line 161.
7. `CLAUDE.md`: replace the pydevccu-as-reference framing (lines 5-6, 12-30, 51, 63, 112, 119, 148-155, 166) with: godevccu is the reference implementation; behaviour changes are decided here; pydevccu is archived and only explains the origin of existing behaviour. Keep the module table (lines 75-91) under the heading "Origin of the packages (pydevccu, archived)".
8. `CHANGELOG.md` `[Unreleased]`: `### Changed` — "**BREAKING:** homegear-mode `getVersion` reports `godevccu-<version>` instead of `pydevccu-0.2.0`; `hmconst.PydevccuVersion` is removed. Clients that detect the simulator by the `pydevccu` substring must look for `godevccu`." `### Removed` — "`make data` and `script/copy_data.sh`: device data is maintained in this repository."
9. Verify: `make build test lint`; `./bin/godevccu -mode homegear -xml-rpc-port 2141 -json-rpc-port 0 &` then `python3 -c "import xmlrpc.client as x; print(x.ServerProxy('http://127.0.0.1:2141').getVersion())"` → `godevccu-<Version>`.
10. PR (`git commit -s`, no co-author trailer) → merge → release PR `release: 0.8.0` (bump `hmconst.Version`, date the section, compare links) → annotated tag `v0.8.0` → wait for the release workflow.

## 4. Phase 2 — aiohomematic

Branch `feat/godevccu-leading`. Do not merge before Phase 1 is released.

### 2.1 Production code (D1, D2)

| File                                             | Change                                                                                      |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| `aiohomematic/const.py:374`                      | `GODEVCCU = "GoDevCCU"` replaces `PYDEVCCU = "PyDevCCU"` (keep enum member order otherwise) |
| `aiohomematic/backend_detection.py:6,88`         | docstrings "Homegear/godevccu"                                                              |
| `aiohomematic/backend_detection.py:202-203`      | `Backend.GODEVCCU`; comment "Homegear/godevccu only supports BidCos-RF"                     |
| `aiohomematic/backend_detection.py:251-252`      | `if "godevccu" in version_lower: return Backend.GODEVCCU`                                   |
| `aiohomematic/client/backends/factory.py:77-78`  | comment "Homegear/godevccu"; condition `("Homegear" in version or "godevccu" in version)`   |
| `aiohomematic/client/backends/homegear.py:10,46` | docstrings "Homegear and godevccu systems"                                                  |
| `aiohomematic/client/backends/homegear.py:86-87` | `Backend.GODEVCCU.lower()` / `return Backend.GODEVCCU`                                      |
| `aiohomematic/client/backends/protocol.py:86`    | "(CCU, Homegear, godevccu)"                                                                 |
| `aiohomematic/model/device.py:2138`              | "(list format of godevccu's device_descriptions files)"                                     |

Tests for 2.1:

- `tests/contract/test_enum_constants_contract.py:105-108` → `test_backend_has_godevccu`, asserting `Backend.GODEVCCU.value == "GoDevCCU"` and `not hasattr(Backend, "PYDEVCCU")`.
- `tests/test_backend_detection.py:39-43,490-548,663-669,716`: version strings `"godevccu-0.8.0"`, `"GoDevCCU 0.8.0"`, `"GODEVCCU"`; expected `Backend.GODEVCCU`; test names/docstrings `godevccu`. Add one case asserting `_determine_backend(version="pydevccu-0.2.6") == Backend.CCU` (old string no longer special).

### 2.2 Pinned version, install script, binary lookup (D4)

1. New file `.godevccu-version`, one line: `v0.8.0`.
2. New file `script/install_godevccu.sh` (executable, `set -euo pipefail`):
   - `version=$(tr -d '[:space:]' < .godevccu-version)`; `os` from `uname -s` (`Darwin`→`darwin`, `Linux`→`linux`, else exit 1 with message); `arch` from `uname -m` (`x86_64`→`amd64`, `arm64|aarch64`→`arm64`, else exit 1).
   - `asset="godevccu-${version}-${os}-${arch}"`, `base="https://github.com/SukramJ/godevccu/releases/download/${version}"`.
   - `mkdir -p .godevccu`; `curl -fsSL -o ".godevccu/${asset}" "${base}/${asset}"` and the same for `${asset}.sha256`.
   - Verify inside `.godevccu`: `sha256sum -c` if available, else `shasum -a 256 -c`.
   - `chmod +x`; `ln -sf "${asset}" .godevccu/godevccu`; print the path.
3. `.gitignore`: add `.godevccu/`.
4. `tests/helpers/godevccu_process.py`:
   - delete `SIMULATOR_ENV`, `SIMULATOR_GODEVCCU`, `SIMULATOR_PYDEVCCU`, `use_godevccu()`.
   - new module constant `_REPO_BINARY = Path(__file__).resolve().parents[2] / ".godevccu" / "godevccu"`.
   - `find_godevccu_binary()` order: `GODEVCCU_BIN` → `_REPO_BINARY` if it exists → `shutil.which("godevccu")`; error text: `"godevccu binary not found: run script/install_godevccu.sh, set GODEVCCU_BIN or put godevccu on PATH"`.
5. `tests/test_godevccu_process.py`: delete `test_default_is_pydevccu` and `test_godevccu_selected`; keep the rest. `test_binary_missing_raises`: unset `GODEVCCU_BIN`, set `PATH=""`, `monkeypatch.setattr("tests.helpers.godevccu_process._REPO_BINARY", tmp_path / "missing")` (CI installs the real binary there), assert the message contains `install_godevccu.sh`. New `test_binary_from_repo_dir`: create an empty file, point `_REPO_BINARY` at it, unset `GODEVCCU_BIN`, assert it is returned.

### 2.3 Fixtures and test files (D5)

`tests/conftest.py`:

- Delete `import pydevccu`, the `PYDEVCCU_HAS_OPENCCU_SUPPORT` / `BackendMode` / `VirtualCCU` try-block (lines 15-27), `requires_openccu` (lines 332-336) and every `if use_godevccu():` branch condition — the godevccu path becomes the only path; delete the pydevccu code paths entirely (including `contextlib`/`asyncio` stop fallbacks and all `remotes.clear()` teardown code).
- Rename: `pydevccu_mini`→`godevccu_mini`, `pydevccu_full`→`godevccu_full`, `pydevccu_openccu`→`godevccu_openccu`, `central_unit_pydevccu_mini`→`central_unit_godevccu_mini`, `central_unit_pydevccu_full`→`central_unit_godevccu_full`, `session_player_pydevccu`→`session_player_godevccu`; return types `GodevccuProcess`.
- Section comments: "godevccu mini fixtures", "godevccu full fixtures", "OpenCCU fixtures (godevccu in openccu mode)"; `# Homegear/godevccu client fixtures`.
- `session_player_godevccu` loads `const.FULL_SESSION_GODEVCCU`; docstring "godevccu session file".

Test files:

- `git mv tests/test_central_pydevccu.py tests/test_central_godevccu.py`; class `TestCentralGoDevCCU`; fixtures renamed; `central.model == "GoDevCCU"` (3×2 places); `xdist_group("godevccu")`.
- `git mv tests/test_central_pydev_openccu.py tests/test_central_godevccu_openccu.py`; class `TestCentralGoDevCCUOpenCCU`, docstring "godevccu in OpenCCU mode"; drop `requires_openccu`; `xdist_group("godevccu_openccu")`.
- `tests/test_backend_openccu.py`: drop the import of `PYDEVCCU_HAS_OPENCCU_SUPPORT, requires_openccu`, the `requires_openccu` marks, and the placeholder class at lines 144-160 (the only skipped test); fixture `godevccu_openccu`; module docstring "virtual OpenCCU (godevccu)".
- `tests/test_model_climate.py:1639-1655,1954-1967`, `tests/test_error_paths.py:368-411`, `tests/test_model_access_permission.py:100-109`: fixture renames, `xdist_group("godevccu")`, "GoDevCCU" in docstrings.
- `tests/test_model_sound_player.py:16`: "(from godevccu session data)".
- `tests/test_central_full_session.py:37-39`, `tests/test_central.py:107`: values follow the new session (2.6).
- Delete `tests/test_warning_filters.py` and the `filterwarnings` entry in `pyproject.toml:433-438` (both exist only for pydevccu's `_ask_devices` thread). If `filterwarnings` becomes empty, delete the key.
- `requirements_test.txt:11`: delete `pydevccu==0.2.6`.

### 2.4 aiohomematic_test_support (public package — breaking for consumers)

- `const.py:22-25`: comment "OpenCCU ports for godevccu in openccu mode".
- `const.py:71,75`: `FULL_SESSION_GODEVCCU = "full_session_godevccu.zip"` replaces `FULL_SESSION_RANDOMIZED_PYDEVCCU` (also in the tuple at line 75).
- `factory.py:289`: `get_godevccu_central_unit_full` replaces `get_pydev_ccu_central_unit_full`; update the import in `tests/conftest.py`.
- `helper.py:42-46`: `load_device_description` reads `aiohomematic_test_support/data/device_descriptions/<file>`: `_load_json_file(anchor="aiohomematic_test_support", resource=os.path.join("data", "device_descriptions"), file_name=file_name)`.
- Copy `../godevccu/internal/embed/data/device_descriptions/HmIP-BSM.json` to `aiohomematic_test_support/data/device_descriptions/HmIP-BSM.json` (godevccu is the source).

### 2.5 CI

`.github/workflows/test-run.yaml`:

- In job `test` add before "Run tests with coverage": step `Install godevccu` → `run: script/install_godevccu.sh`. The repo-local `.godevccu/godevccu` is found by `find_godevccu_binary()`; no env needed. Both matrix entries (`3.14`, `3.14t`) get it.
- Delete job `test-godevccu` completely.

Branch protection (do this **immediately before merging** the Phase 2 PR, otherwise every PR waits for a check that no longer runs): `PATCH .../branches/main/protection/required_status_checks` with `strict: true` and the four checks `Run pre-commit hooks`, `Python 3.14`, `Python 3.14t`, `Analyze (Python)` (all `app_id` 15368). Read back and compare.

### 2.6 Re-record the session (D3)

New script `script/record_godevccu_session.py` (kept in the repo for future re-recordings).
**As executed** (the first draft of this step — callback server, `OptionalSettings.SESSION_RECORDER` —
did not work: that option does not exist, and with a running callback server the central never
calls `listDevices`; godevccu pushes `newDevices` instead, which the recorder does not capture):

1. Start `.godevccu/godevccu -mode homegear -host 127.0.0.1 -xml-rpc-port 0 -json-rpc-port 0 -ports-json <tmp>/ports.json`; wait for the ports file.
2. `CentralConfig(name=const.CENTRAL_NAME, …, central_id="test1234", storage_directory=<tmp>, program_markers=(), sysvar_markers=(), start_direct=True, optional_settings=(OptionalSettings.SR_RECORD_SYSTEM_INIT, OptionalSettings.SR_DISABLE_RANDOMIZE_OUTPUT))`.
3. `await central.start()`, sleep `DEFAULT_SESSION_RECORDER_START_FOR_SECONDS` + 30 s (the recorder saves itself), stop.
4. Copy the single ZIP below `<tmp>/storage/session/` to `aiohomematic_test_support/data/full_session_godevccu.zip`; `git rm` the pydevccu ZIP.
5. Run: `PYTHONPATH=. python script/record_godevccu_session.py`.

Verify the recording before touching tests:

- unzip, count `listDevices` roots = 399 and addresses = 2924; `getVersion` = `godevccu-0.8.0`; the 394 shared root addresses keep their TYPE (rerun the comparison from section 2).

Then run `pytest tests/`. Expected, explainable differences: device/data-point/description counts (+5 devices, −1 `HmIP-FWI`) and `central.version` / `central.model` strings. Update an assertion only when the difference is fully explained by these; for every other failure stop and report it with the test id and diff (do not adapt the assertion).

### 2.7 Documentation

| File                                                                                     | Change                                                                                                                                                                                                                                                                                                                                                                                                   |
| ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `README.md:15,171,189`                                                                   | godevccu, link `https://github.com/SukramJ/godevccu`                                                                                                                                                                                                                                                                                                                                                     |
| `CLAUDE.md:349-350`                                                                      | `session_player_godevccu`; `central_unit_godevccu_mini`, `central_unit_godevccu_full`                                                                                                                                                                                                                                                                                                                    |
| `docs/developer/backend_detection.md:7,21,47,109`                                        | GoDevCCU / "Version contains `godevccu`" / `GODEVCCU`                                                                                                                                                                                                                                                                                                                                                    |
| `docs/architecture/sequence_diagrams.md:708`                                             | `"godevccu" in version`                                                                                                                                                                                                                                                                                                                                                                                  |
| `docs/architecture.md:80`                                                                | check the sentence and replace pydevccu with godevccu if present                                                                                                                                                                                                                                                                                                                                         |
| `docs/glossary_terms.yml:24`                                                             | `godevccu: ""` replaces `pydevccu: ""`                                                                                                                                                                                                                                                                                                                                                                   |
| `docs/user/features/homeassistant_actions.md:518`, `.de.md:524`                          | "Upload to [godevccu](https://github.com/SukramJ/godevccu) …" / German equivalent                                                                                                                                                                                                                                                                                                                        |
| `docs/contributor/contributing.md:171`                                                   | "**Add to godevccu** (`internal/embed/data/`)"                                                                                                                                                                                                                                                                                                                                                           |
| `docs/contributor/testing/session_playback.md:221` and "Creating new session files"      | `full_session_godevccu.zip`, source "godevccu (homegear mode)"; reference `script/record_godevccu_session.py`; note `randomize_output=False`                                                                                                                                                                                                                                                             |
| `docs/contributor/dev-environment.md` section "Running simulator tests against godevccu" | rewrite: simulator tests always use godevccu; `script/install_godevccu.sh`; `GODEVCCU_BIN` override; version pinned in `.godevccu-version`                                                                                                                                                                                                                                                               |
| `docs/plans/godevccu_test_backend_2026_10.md`                                            | line 3: append "Superseded by `godevccu_leading_2026_10.md`."                                                                                                                                                                                                                                                                                                                                            |
| `docs/migrations/godevccu_migration_2026_10.md`                                          | new, template sections: Overview · Breaking Changes (`Backend.PYDEVCCU`→`Backend.GODEVCCU`, `"PyDevCCU"`→`"GoDevCCU"`; test support: `FULL_SESSION_RANDOMIZED_PYDEVCCU`→`FULL_SESSION_GODEVCCU`, `get_pydev_ccu_central_unit_full`→`get_godevccu_central_unit_full`, `load_device_description` source) · Migration Steps · Search-and-Replace Patterns · Compatibility Notes (godevccu ≥ 0.8.0 required) |
| `docs/migrations/index.md`                                                               | add the new guide                                                                                                                                                                                                                                                                                                                                                                                        |

Afterwards `grep -rn -i "pydevccu\|pydev_ccu\|PyDev"` over the repo must only hit `changelog.md` history entries, the two plan files, the migration guide and godevccu attribution links. List every remaining hit in the PR description.

### 2.8 Changelog and checks

- `changelog.md`, top untagged entry (`2026.9.5` unless a tag appeared — check with `git tag --list '2026.9.*' '2026.10.*'` first): `### Breaking Changes` with the enum and test-support renames and a link to the migration guide; `### Changed` — tests use godevccu only (pinned in `.godevccu-version`), pydevccu removed.
- `aiohomematic/const.py:VERSION` stays in sync with the top entry.
- `pytest tests/`, `prek run --all-files` (with `venv/bin` on `PATH`), `python script/check_docs_references.py`, contract tests.

## 5. Phase 3 — homematicip_local

After the aiohomematic release from Phase 2: `tests/conftest.py:15,278` → `FULL_SESSION_GODEVCCU`; bump the aiohomematic requirement; run its tests. Any `"PyDevCCU"` assertion found by `grep -rn "PyDevCCU" tests` → `"GoDevCCU"`.

## 6. Phase 4 — openccu-loom

- **Must land before loom bumps godevccu to ≥ v0.8.0** (gomod Dependabot is weekly):
  `tests/integration/xmlrpc_test.go:93` asserts `pydevccu` in `getVersion`, and
  `internal/client/backends/homegear.go:20` (`HomegearModelPyDevCCU = "pydevccu"`, tests in
  `homegear_model_test.go:24-26`) mirrors aiohomematic's detection. Rename to `godevccu`
  the same way as aiohomematic 2.1.
- `script/aiohomematic_snapshot.py`: start the godevccu binary instead of `pydevccu.Server` (same 4 devices via `-devices`); drop the pydevccu import/bootstrap.
- Delete `datasource-diff` (`Makefile:357-358`, `script/datasource_diff.py`) — there is no second data source any more.
- `.github/workflows/cross-stack-parity.yml:44-49`: provision aiohomematic + openccu-data + godevccu binary, no pydevccu.
- Docs: `README.md`, `CLAUDE.md`, `tests/CLAUDE.md`, `SPECIFICATION.md`, `THIRD-PARTY-NOTICES.md` (attribution stays).

## 7. Phase 5 — archive pydevccu

Only after Phases 1–4 are merged: final commit to `SukramJ/pydevccu` README ("Archived — succeeded by godevccu: https://github.com/SukramJ/godevccu"), then `gh repo archive SukramJ/pydevccu --yes`. The PyPI package stays published (no yank).

## 8. Order and gates

1 → (release v0.8.0) → 2 (branch protection change right before merge) → aiohomematic release → 3 → 4 → 5.
Each phase: own PR, `git commit -s`, no co-author trailer, maintainer merges.
