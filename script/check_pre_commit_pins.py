#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Pin-drift guard for ``.pre-commit-config.yaml``.

Every remote hook repository in ``.pre-commit-config.yaml`` pins a tool version in its
``rev:``, and ``requirements_test_pre_commit.txt`` pins the very same tools for the test
environment. Nothing links the two files, so they are kept in sync by hand and drift
apart silently — a hook then runs a different version than the test environment installs.

This guard makes the link explicit and machine-checked. The mapping is **declared in the
files themselves** and never inferred from repository or package names:

* every pin in ``requirements_test_pre_commit.txt`` carries a trailing
  ``# pre-commit: <repo-url>`` comment naming the hook repo it mirrors, or
  ``# pre-commit: local`` when it backs a ``repo: local`` hook that has no ``rev:``;
* every remote repo in ``.pre-commit-config.yaml`` that intentionally has no pin carries
  a ``# no-pin: <reason>`` comment on the line directly above its ``- repo:`` line. That
  marker has to sit on its own line: prettier rewrites a YAML trailing comment down to a
  single leading space, which yamllint then rejects, so no trailing form passes both.

Checked:

1. **Version drift** — a declared pair whose two versions differ.
2. **Unmapped hook repo** — a remote repo with a ``rev:`` that no pin maps to and that is
   not marked ``# no-pin:``.
3. **Orphaned mapping** — a pin naming a repo that the config does not contain (any more).
4. **Undeclared pin** — a requirement line without a ``# pre-commit:`` comment.
5. **Contradiction** — a repo that is both mapped by a pin and marked ``# no-pin:``.

Versions are compared after stripping one leading ``v``: git tags carry it
(``rev: v0.16.5``) and PEP 440 accepts it as an optional release-segment prefix, so
``v0.16.5`` and ``0.16.5`` denote the same release. No other normalisation is applied —
anything else (a commit hash in ``rev:``, a differing patch level) is reported as drift.

Exits with code ``1`` if any issue is found, otherwise ``0``.

Run manually::

    python script/check_pre_commit_pins.py

Or wire into prek (see ``.pre-commit-config.yaml``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / ".pre-commit-config.yaml"
REQUIREMENTS_PATH = REPO_ROOT / "requirements_test_pre_commit.txt"

# Marker used in requirements comments for tools backing a `repo: local` hook.
LOCAL_TARGET = "local"

# A trailing comment is tolerated so the block is still recognised, but it is never read as a
# marker: only a comment on its own line above the repo declares "# no-pin:".
_REPO_LINE = re.compile(r"^\s*-\s+repo:\s+(?P<url>\S+)\s*(?:#.*)?$")
_COMMENT_LINE = re.compile(r"^\s*#\s*(?P<comment>.+?)\s*$")
_REV_LINE = re.compile(r"^\s{2,}rev:\s+(?P<rev>\S+)\s*(?:#.*)?$")
_PIN_LINE = re.compile(r"^(?P<package>[A-Za-z0-9._-]+)\s*==\s*(?P<version>[^\s#]+)\s*(?:#\s*(?P<comment>.*?))?\s*$")
_NO_PIN_COMMENT = re.compile(r"^no-pin:\s*(?P<reason>.+)$")
_PRE_COMMIT_COMMENT = re.compile(r"^pre-commit:\s*(?P<target>\S+)\s*$")


@dataclass(frozen=True, kw_only=True, slots=True)
class HookRepo:
    """Represent one remote ``- repo:`` block of the prek config."""

    url: str
    rev: str | None
    line_no: int
    no_pin_reason: str | None


@dataclass(frozen=True, kw_only=True, slots=True)
class Pin:
    """Represent one ``package==version`` line of the requirements file."""

    package: str
    version: str
    target: str | None
    line_no: int


def normalise_version(version: str) -> str:
    """Return the version without a single leading ``v`` (an optional PEP 440 prefix)."""
    return version.removeprefix("v")


def parse_hook_repos(*, text: str) -> list[HookRepo]:
    """Return the remote hook repos declared in the prek config, in file order."""
    repos: list[HookRepo] = []
    url: str | None = None
    line_no = 0
    comment: str | None = None
    rev: str | None = None
    pending_comment: str | None = None

    def flush() -> None:
        if url is None or url == LOCAL_TARGET:
            return
        reason = None
        if comment and (match := _NO_PIN_COMMENT.match(comment)):
            reason = match.group("reason").strip()
        repos.append(HookRepo(url=url, rev=rev, line_no=line_no, no_pin_reason=reason))

    for number, line in enumerate(text.splitlines(), start=1):
        if comment_match := _COMMENT_LINE.match(line):
            pending_comment = comment_match.group("comment")
            continue
        if repo_match := _REPO_LINE.match(line):
            flush()
            url = repo_match.group("url")
            comment = pending_comment
            line_no = number
            rev = None
        elif url is not None and (rev_match := _REV_LINE.match(line)):
            rev = rev_match.group("rev")
        pending_comment = None
    flush()
    return repos


def parse_pins(*, text: str) -> list[Pin]:
    """Return the version pins declared in the requirements file, in file order."""
    pins: list[Pin] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "-r ")):
            continue
        if not (match := _PIN_LINE.match(stripped)):
            continue
        target = None
        if (comment := match.group("comment")) and (target_match := _PRE_COMMIT_COMMENT.match(comment.strip())):
            target = target_match.group("target")
        pins.append(
            Pin(
                package=match.group("package"),
                version=match.group("version"),
                target=target,
                line_no=number,
            )
        )
    return pins


def check(*, config_path: Path, requirements_path: Path) -> list[str]:
    """Return one error message per pin-drift issue found between the two files."""
    config_name = config_path.name
    requirements_name = requirements_path.name
    repos = parse_hook_repos(text=config_path.read_text(encoding="utf-8"))
    pins = parse_pins(text=requirements_path.read_text(encoding="utf-8"))
    repos_by_url = {repo.url: repo for repo in repos}
    errors: list[str] = []
    mapped_urls: set[str] = set()

    for pin in pins:
        location = f"{requirements_name}:{pin.line_no}"
        if pin.target is None:
            errors.append(
                f"{location}: '{pin.package}' has no '# pre-commit: <repo-url>' comment. "
                f"Add the hook repo it mirrors, or '# pre-commit: {LOCAL_TARGET}' for a local hook."
            )
            continue
        if pin.target == LOCAL_TARGET:
            continue
        if (repo := repos_by_url.get(pin.target)) is None:
            errors.append(f"{location}: '{pin.package}' maps to '{pin.target}', which is not a repo in {config_name}.")
            continue
        mapped_urls.add(repo.url)
        if repo.no_pin_reason is not None:
            errors.append(
                f"{location}: '{pin.package}' maps to '{repo.url}', but {config_name}:{repo.line_no - 1} "
                f"marks that repo '# no-pin:'. Remove one of the two declarations."
            )
            continue
        if repo.rev is None:
            errors.append(f"{location}: '{pin.package}' maps to '{repo.url}', which has no 'rev:' in {config_name}.")
            continue
        if normalise_version(repo.rev) != normalise_version(pin.version):
            errors.append(
                f"{location}: '{pin.package}=={pin.version}' drifted from "
                f"{config_name}:{repo.line_no} 'rev: {repo.rev}' ({repo.url})."
            )

    for repo in repos:
        if repo.rev is None or repo.url in mapped_urls or repo.no_pin_reason is not None:
            continue
        errors.append(
            f"{config_name}:{repo.line_no}: '{repo.url}' pins 'rev: {repo.rev}' but nothing in "
            f"{requirements_name} mirrors it. Add a pin with '# pre-commit: {repo.url}', "
            "or mark the repo '# no-pin: <reason>'."
        )

    return errors


def main() -> int:
    """Run the pin-drift check and return a non-zero exit code when any issue is found."""
    errors = check(config_path=CONFIG_PATH, requirements_path=REQUIREMENTS_PATH)
    if errors:
        print("pre-commit pin drift detected:\n")
        for err in errors:
            print(f"  - {err}")
        print(f"\n{len(errors)} issue(s) found. See script/check_pre_commit_pins.py for details.")
        return 1
    print("pre-commit pins: no drift detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
