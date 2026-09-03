# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for the pre-commit pin-drift guard."""

from __future__ import annotations

from pathlib import Path

# Import from script directory
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "script"))
from check_pre_commit_pins import CONFIG_PATH, REQUIREMENTS_PATH, check, normalise_version, parse_hook_repos, parse_pins

CONFIG = """\
repos:
  - repo: local
    hooks:
      - id: mypy
        name: mypy
  - repo: https://github.com/example/ruff-pre-commit
    rev: v1.2.3
    hooks:
      - id: ruff
  # no-pin: hook-only repo
  - repo: https://github.com/example/hooks
    rev: v6.0.0
    hooks:
      - id: check-json
"""

REQUIREMENTS = """\
# A leading comment.
-r requirements.txt
ruff==1.2.3  # pre-commit: https://github.com/example/ruff-pre-commit
mypy==2.3.1  # pre-commit: local
"""


def _write(tmp_path: Path, *, config: str = CONFIG, requirements: str = REQUIREMENTS) -> tuple[Path, Path]:
    """Write both source files into tmp_path and return their paths."""
    config_path = tmp_path / ".pre-commit-config.yaml"
    requirements_path = tmp_path / "requirements_test_pre_commit.txt"
    config_path.write_text(config, encoding="utf-8")
    requirements_path.write_text(requirements, encoding="utf-8")
    return config_path, requirements_path


def _check(tmp_path: Path, *, config: str = CONFIG, requirements: str = REQUIREMENTS) -> list[str]:
    """Run the guard against files written into tmp_path."""
    config_path, requirements_path = _write(tmp_path, config=config, requirements=requirements)
    return check(config_path=config_path, requirements_path=requirements_path)


class TestParsing:
    """Tests for the two file parsers."""

    def test_normalise_version_strips_single_leading_v(self) -> None:
        """Test that only one leading `v` is stripped."""
        assert normalise_version("v1.2.3") == "1.2.3"
        assert normalise_version("1.2.3") == "1.2.3"
        assert normalise_version("vv1.2.3") == "v1.2.3"

    def test_parse_hook_repos_reads_no_pin_comment(self) -> None:
        """Test that a `# no-pin:` comment on the preceding line is picked up."""
        repo = parse_hook_repos(text=CONFIG)[1]
        assert repo.no_pin_reason == "hook-only repo"

    def test_parse_hook_repos_reads_rev_and_line(self) -> None:
        """Test that rev and line number are read from the block."""
        repo = parse_hook_repos(text=CONFIG)[0]
        assert repo.rev == "v1.2.3"
        assert repo.line_no == 6
        assert repo.no_pin_reason is None

    def test_parse_hook_repos_skips_local(self) -> None:
        """Test that a `repo: local` block is not treated as a pinned hook repo."""
        urls = [repo.url for repo in parse_hook_repos(text=CONFIG)]
        assert urls == ["https://github.com/example/ruff-pre-commit", "https://github.com/example/hooks"]

    def test_parse_pins_ignores_includes_and_comments(self) -> None:
        """Test that `-r` includes and comment lines are not parsed as pins."""
        assert len(parse_pins(text=REQUIREMENTS)) == 2

    def test_parse_pins_reads_target(self) -> None:
        """Test that the `# pre-commit:` comment is read as the mapping target."""
        pins = parse_pins(text=REQUIREMENTS)
        assert [(pin.package, pin.version, pin.target) for pin in pins] == [
            ("ruff", "1.2.3", "https://github.com/example/ruff-pre-commit"),
            ("mypy", "2.3.1", "local"),
        ]

    def test_parse_pins_records_missing_target(self) -> None:
        """Test that a pin without a `# pre-commit:` comment has no target."""
        assert parse_pins(text="ruff==1.2.3\n")[0].target is None


class TestCheck:
    """Tests for the drift checks."""

    def test_commit_hash_rev_is_drift(self, tmp_path: Path) -> None:
        """Test that a rev that is not the pinned version is reported, hash or not."""
        errors = _check(tmp_path, config=CONFIG.replace("rev: v1.2.3", "rev: 0f1e2d3"))
        assert len(errors) == 1
        assert "drifted from" in errors[0]

    def test_contradiction_between_no_pin_and_mapping(self, tmp_path: Path) -> None:
        """Test that a repo both mapped and marked `# no-pin:` is reported."""
        requirements = REQUIREMENTS + "hooks==6.0.0  # pre-commit: https://github.com/example/hooks\n"
        errors = _check(tmp_path, requirements=requirements)
        assert len(errors) == 1
        assert "marks that repo '# no-pin:'" in errors[0]

    def test_local_target_needs_no_repo(self, tmp_path: Path) -> None:
        """Test that a `# pre-commit: local` pin is accepted without a matching repo."""
        requirements = "mypy==2.3.1  # pre-commit: local\n"
        config = CONFIG.replace("  - repo: https://github.com/example/ruff-pre-commit\n    rev: v1.2.3\n", "")
        errors = _check(tmp_path, config=config, requirements=requirements)
        assert errors == []

    def test_mapped_repo_without_rev(self, tmp_path: Path) -> None:
        """Test that a mapping to a repo that carries no rev is reported."""
        config = CONFIG.replace("    rev: v1.2.3\n", "")
        errors = _check(tmp_path, config=config)
        assert len(errors) == 1
        assert "has no 'rev:'" in errors[0]

    def test_no_drift(self, tmp_path: Path) -> None:
        """Test that consistent files produce no errors."""
        assert _check(tmp_path) == []

    def test_no_pin_marker_must_directly_precede_the_repo(self, tmp_path: Path) -> None:
        """Test that a marker separated from its repo line by content does not apply."""
        config = CONFIG.replace(
            "  # no-pin: hook-only repo\n  - repo: https://github.com/example/hooks",
            "  # no-pin: hook-only repo\n  - repo: https://github.com/example/other\n"
            "    rev: v9.9.9\n    hooks:\n      - id: other\n  - repo: https://github.com/example/hooks",
        )
        errors = _check(tmp_path, config=config)
        assert len(errors) == 1
        assert "https://github.com/example/hooks" in errors[0]

    def test_orphaned_mapping(self, tmp_path: Path) -> None:
        """Test that a pin naming an absent repo is reported."""
        requirements = REQUIREMENTS.replace("example/ruff-pre-commit", "example/gone")
        errors = _check(tmp_path, requirements=requirements)
        assert len(errors) == 2
        assert any("is not a repo in .pre-commit-config.yaml" in err for err in errors)
        assert any("nothing in requirements_test_pre_commit.txt mirrors it" in err for err in errors)

    def test_trailing_no_pin_marker_is_not_honoured(self, tmp_path: Path) -> None:
        """Test that a `# no-pin:` written as a trailing comment fails loudly, not silently."""
        config = CONFIG.replace(
            "  # no-pin: hook-only repo\n  - repo: https://github.com/example/hooks",
            "  - repo: https://github.com/example/hooks  # no-pin: hook-only repo",
        )
        errors = _check(tmp_path, config=config)
        assert len(errors) == 1
        assert "nothing in requirements_test_pre_commit.txt mirrors it" in errors[0]

    def test_undeclared_pin(self, tmp_path: Path) -> None:
        """Test that a pin without a mapping comment is reported."""
        requirements = REQUIREMENTS.replace("  # pre-commit: https://github.com/example/ruff-pre-commit", "")
        errors = _check(tmp_path, requirements=requirements)
        assert len(errors) == 2
        assert any("has no '# pre-commit: <repo-url>' comment" in err for err in errors)

    def test_unmapped_hook_repo(self, tmp_path: Path) -> None:
        """Test that a pinned repo nothing mirrors is reported."""
        config = CONFIG.replace("  # no-pin: hook-only repo\n", "")
        errors = _check(tmp_path, config=config)
        assert len(errors) == 1
        assert "nothing in requirements_test_pre_commit.txt mirrors it" in errors[0]

    def test_v_prefix_is_not_drift(self, tmp_path: Path) -> None:
        """Test that a `v` prefix on the pin matches an unprefixed rev and vice versa."""
        config = CONFIG.replace("rev: v1.2.3", "rev: 1.2.3")
        assert _check(tmp_path, config=config, requirements=REQUIREMENTS.replace("ruff==1.2.3", "ruff==v1.2.3")) == []

    def test_version_drift(self, tmp_path: Path) -> None:
        """Test that a differing version is reported."""
        errors = _check(tmp_path, requirements=REQUIREMENTS.replace("ruff==1.2.3", "ruff==1.2.4"))
        assert len(errors) == 1
        assert "drifted from" in errors[0]
        assert "rev: v1.2.3" in errors[0]


def test_repository_is_free_of_pin_drift() -> None:
    """Test that the repository's own two files are in sync."""
    assert check(config_path=CONFIG_PATH, requirements_path=REQUIREMENTS_PATH) == []
