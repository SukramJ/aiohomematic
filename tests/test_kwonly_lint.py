"""Tests for keyword-only method linter (script.lint_kwonly)."""

from __future__ import annotations

from pathlib import Path

import script.lint_kwonly as kwlint


class TestKwonlyLint:
    """Test keyword-only method linter."""

    def test_kwonly_lint_detects_simple_init(self, tmp_path: Path) -> None:
        """The linter must detect missing '*' for __init__ beyond the first param."""
        code = "class Foo:\n    def __init__(self, x):\n        pass\n"
        p = tmp_path / "sample.py"
        p.write_text(code, encoding="utf-8")

        violations = kwlint.check_file(str(p))
        assert violations, "Expected at least one violation to be reported"
        msgs = "\n".join(str(v) for v in violations)
        assert "method '__init__'" in msgs

    def test_kwonly_lint_ignores_varargs(self, tmp_path: Path) -> None:
        """If *args is in the method signature, the linter must not flag it."""
        code = "class Foo:\n    def bar(self, x, *args):\n        pass\n"
        p = tmp_path / "sample_varargs.py"
        p.write_text(code, encoding="utf-8")

        violations = kwlint.check_file(str(p))
        assert not violations, f"Did not expect violations, got: {[str(v) for v in violations]}"
