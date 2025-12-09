"""Tests for the ReGa script linter."""

from __future__ import annotations

from pathlib import Path

# Import from script directory
import sys
import tempfile

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "script"))
from lint_rega_scripts import (
    PARAM_DECL_PATTERN,
    PARAM_PATTERN,
    _check_header_order,
    check_script,
    find_used_parameters,
    generate_fixed_content,
    parse_script,
)


class TestParamPattern:
    """Tests for parameter pattern matching."""

    def test_find_multiple_params(self) -> None:
        """Test finding multiple parameters."""
        content = """
        string sId = "##id##";
        integer sState = ##state##;
        """
        params = find_used_parameters(content)
        assert params == {"id", "state"}

    def test_find_param_with_underscore(self) -> None:
        """Test finding parameter with underscore."""
        content = 'string sAddr = "##device_address##";'
        params = find_used_parameters(content)
        assert params == {"device_address"}

    def test_find_simple_param(self) -> None:
        """Test finding a simple parameter."""
        content = 'string sInterface = "##interface##";'
        params = find_used_parameters(content)
        assert params == {"interface"}

    def test_no_params(self) -> None:
        """Test content without parameters."""
        content = 'Write("Hello World");'
        params = find_used_parameters(content)
        assert params == set()

    def test_param_pattern_regex(self) -> None:
        """Test the PARAM_PATTERN regex directly."""
        assert PARAM_PATTERN.findall("##test##") == ["test"]
        assert PARAM_PATTERN.findall("##Test123##") == ["Test123"]
        assert PARAM_PATTERN.findall("##_private##") == ["_private"]
        assert PARAM_PATTERN.findall("####") == []  # Empty param name
        assert PARAM_PATTERN.findall("##123##") == []  # Starts with number


class TestParamDeclPattern:
    """Tests for parameter declaration pattern matching."""

    def test_invalid_param_decl_no_quotes(self) -> None:
        """Test invalid parameter declaration without quotes."""
        match = PARAM_DECL_PATTERN.match("!# param: ##interface##")
        assert match is None

    def test_invalid_param_decl_wrong_prefix(self) -> None:
        """Test invalid parameter declaration with wrong prefix."""
        match = PARAM_DECL_PATTERN.match('# param: "##interface##"')
        assert match is None

    def test_param_decl_with_underscore(self) -> None:
        """Test parameter declaration with underscore."""
        match = PARAM_DECL_PATTERN.match('!# param: "##device_address##"')
        assert match is not None
        assert match.group(1) == "device_address"

    def test_valid_param_decl(self) -> None:
        """Test valid parameter declaration."""
        match = PARAM_DECL_PATTERN.match('!# param: "##interface##"')
        assert match is not None
        assert match.group(1) == "interface"


class TestParseScript:
    """Tests for script parsing."""

    def test_parse_script_multiple_params(self) -> None:
        """Test parsing script with multiple parameters."""
        content = """!# name: multi.fn
!# param: "##id##"
!# param: "##state##"
code here
"""
        name, params, other = parse_script(content)
        assert name == "multi.fn"
        assert params == {"id", "state"}
        assert other == ["code here"]

    def test_parse_script_no_params(self) -> None:
        """Test parsing script without parameters."""
        content = """!# name: simple.fn
Write("Hello");
"""
        name, params, other = parse_script(content)
        assert name == "simple.fn"
        assert params == set()
        assert other == ['Write("Hello");']

    def test_parse_script_with_comments(self) -> None:
        """Test parsing script with comment lines."""
        content = """!# name: commented.fn
!# param: "##value##"
!#
!# This is a comment
!#
code here
"""
        name, params, other = parse_script(content)
        assert name == "commented.fn"
        assert params == {"value"}
        assert "!#" in other
        assert "!# This is a comment" in other

    def test_parse_simple_script(self) -> None:
        """Test parsing a simple script."""
        content = """!# name: test.fn
!# param: "##value##"
string sValue = "##value##";
"""
        name, params, other = parse_script(content)
        assert name == "test.fn"
        assert params == {"value"}
        assert other == ['string sValue = "##value##";']


class TestCheckHeaderOrder:
    """Tests for header order checking."""

    def test_correct_order_multiple_params(self) -> None:
        """Test correct order with multiple parameters."""
        content = """!# name: test.fn
!# param: "##id##"
!# param: "##state##"
code
"""
        assert _check_header_order(content, {"id", "state"}) is True

    def test_correct_order_no_params(self) -> None:
        """Test correct order with no parameters."""
        content = """!# name: test.fn
code
"""
        assert _check_header_order(content, set()) is True

    def test_correct_order_single_param(self) -> None:
        """Test correct order with single parameter."""
        content = """!# name: test.fn
!# param: "##value##"
code
"""
        assert _check_header_order(content, {"value"}) is True

    def test_empty_content(self) -> None:
        """Test empty content."""
        assert _check_header_order("", set()) is False

    def test_missing_name_line(self) -> None:
        """Test missing name line."""
        content = """!# param: "##value##"
code
"""
        assert _check_header_order(content, {"value"}) is False

    def test_wrong_order_param_at_end(self) -> None:
        """Test wrong order where param is at end of file."""
        content = """!# name: test.fn
code
!# param: "##value##"
"""
        assert _check_header_order(content, {"value"}) is False

    def test_wrong_order_param_not_after_name(self) -> None:
        """Test wrong order where param is not directly after name."""
        content = """!# name: test.fn
!# comment
!# param: "##value##"
code
"""
        assert _check_header_order(content, {"value"}) is False


class TestGenerateFixedContent:
    """Tests for content generation."""

    def test_generate_multiple_params_sorted(self) -> None:
        """Test that parameters are sorted alphabetically."""
        result = generate_fixed_content("test.fn", {"zebra", "alpha", "middle"}, ["code"])
        lines = result.splitlines()
        assert lines[0] == "!# name: test.fn"
        assert lines[1] == '!# param: "##alpha##"'
        assert lines[2] == '!# param: "##middle##"'
        assert lines[3] == '!# param: "##zebra##"'

    def test_generate_no_params(self) -> None:
        """Test generating content without parameters."""
        result = generate_fixed_content("test.fn", set(), ["code"])
        expected = """!# name: test.fn

code
"""
        assert result == expected

    def test_generate_preserves_comment_headers(self) -> None:
        """Test that !# comment lines are preserved after params."""
        other_lines = ["!#", "!# This is a comment", "code"]
        result = generate_fixed_content("test.fn", {"value"}, other_lines)
        lines = result.splitlines()
        assert lines[0] == "!# name: test.fn"
        assert lines[1] == '!# param: "##value##"'
        assert lines[2] == "!#"
        assert lines[3] == "!# This is a comment"

    def test_generate_removes_leading_empty_lines(self) -> None:
        """Test that leading empty lines are removed."""
        other_lines = ["", "", "code"]
        result = generate_fixed_content("test.fn", set(), other_lines)
        lines = result.splitlines()
        assert lines[0] == "!# name: test.fn"
        assert lines[1] == ""
        assert lines[2] == "code"

    def test_generate_simple(self) -> None:
        """Test generating simple fixed content."""
        result = generate_fixed_content("test.fn", {"value"}, ['code = "##value##";'])
        expected = """!# name: test.fn
!# param: "##value##"

code = "##value##";
"""
        assert result == expected


class TestCheckScript:
    """Tests for full script checking."""

    def test_fix_creates_correct_output(self) -> None:
        """Test that fix mode creates correct output."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fn", delete=False) as f:
            f.write("""!# name: test_fix.fn
!# comment line
!# param: "##value##"
string s = "##value##";
""")
            f.flush()
            filepath = Path(f.name)
            filepath = filepath.rename(filepath.parent / "test_fix.fn")

        try:
            errors = check_script(filepath, fix=True)
            assert errors == []

            # Read fixed content
            content = filepath.read_text()
            lines = content.splitlines()
            assert lines[0] == "!# name: test_fix.fn"
            assert lines[1] == '!# param: "##value##"'
            assert "!# comment line" in lines
        finally:
            filepath.unlink()

    def test_missing_name_line(self) -> None:
        """Test script without name line."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fn", delete=False) as f:
            f.write('string s = "test";')
            f.flush()
            filepath = Path(f.name)

        try:
            errors = check_script(filepath)
            assert len(errors) >= 1
            assert any("!# name:" in e for e in errors)
        finally:
            filepath.unlink()

    def test_missing_param_declaration(self) -> None:
        """Test script with undeclared parameter."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fn", delete=False) as f:
            f.write("""!# name: test_missing.fn
string s = "##missing_param##";
""")
            f.flush()
            filepath = Path(f.name)
            filepath = filepath.rename(filepath.parent / "test_missing.fn")

        try:
            errors = check_script(filepath)
            assert len(errors) >= 1
            assert any("missing_param" in e for e in errors)
        finally:
            filepath.unlink()

    def test_param_wrong_position(self) -> None:
        """Test script with param declaration in wrong position."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fn", delete=False) as f:
            f.write("""!# name: test_pos.fn
!# comment
!# param: "##value##"
string s = "##value##";
""")
            f.flush()
            filepath = Path(f.name)
            filepath = filepath.rename(filepath.parent / "test_pos.fn")

        try:
            errors = check_script(filepath)
            assert len(errors) >= 1
            assert any("directly after" in e for e in errors)
        finally:
            filepath.unlink()

    def test_unused_param_declaration(self) -> None:
        """Test script with unused parameter declaration."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fn", delete=False) as f:
            f.write("""!# name: test_unused.fn
!# param: "##unused##"
code without param
""")
            f.flush()
            filepath = Path(f.name)
            filepath = filepath.rename(filepath.parent / "test_unused.fn")

        try:
            errors = check_script(filepath)
            assert len(errors) >= 1
            assert any("unused" in e.lower() for e in errors)
        finally:
            filepath.unlink()

    def test_valid_script(self) -> None:
        """Test a valid script returns no errors."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fn", delete=False) as f:
            f.write("""!# name: test_valid.fn
!# param: "##value##"
string s = "##value##";
""")
            f.flush()
            filepath = Path(f.name)
            filepath = filepath.rename(filepath.parent / "test_valid.fn")

        try:
            errors = check_script(filepath)
            assert errors == []
        finally:
            filepath.unlink()

    def test_wrong_name(self) -> None:
        """Test script with wrong name in header."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fn", delete=False) as f:
            f.write("""!# name: wrong_name.fn
code
""")
            f.flush()
            filepath = Path(f.name)

        try:
            errors = check_script(filepath)
            assert len(errors) >= 1
            assert any("wrong_name.fn" in e for e in errors)
        finally:
            filepath.unlink()


class TestIntegration:
    """Integration tests with actual rega_scripts files."""

    def test_all_rega_scripts_valid(self) -> None:
        """Test that all rega_scripts pass validation."""
        rega_dir = Path(__file__).parent.parent / "aiohomematic" / "rega_scripts"
        if not rega_dir.exists():
            pytest.skip("rega_scripts directory not found")

        all_errors = []
        for filepath in rega_dir.glob("*.fn"):
            errors = check_script(filepath)
            all_errors.extend(errors)

        assert all_errors == [], f"Errors found: {all_errors}"
