"""Test for aiohomematic.support."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from aiohomematic.exceptions import AioHomematicException
from aiohomematic.support import cleanup_text_from_html_tags, delete_file, extract_exc_args, log_boundary_error


@pytest.mark.asyncio
async def test_extract_exc_args_variants() -> None:
    """extract_exc_args returns the first arg, a tuple for multiple args, or the exception if no args are set."""
    # One arg -> returns the single arg
    e1 = Exception("only")
    assert extract_exc_args(exc=e1) == "only"

    # Multiple args -> returns the tuple
    e2 = Exception("a", 2)
    assert extract_exc_args(exc=e2) == ("a", 2)

    # No args -> returns the exception itself
    e3 = Exception()
    assert extract_exc_args(exc=e3) is e3


@pytest.mark.asyncio
async def test_cleanup_text_from_html_tags() -> None:
    """cleanup_text_from_html_tags removes HTML tags and entities while keeping inner text intact."""
    text = "<div>Hello <b>World</b> &amp; everyone!</div>"
    # Pattern also removes html entities like &amp;
    assert cleanup_text_from_html_tags(text=text) == "Hello World  everyone!"


@pytest.mark.asyncio
async def test_log_boundary_error_levels_and_context(caplog: pytest.LogCaptureFixture) -> None:
    """log_boundary_error chooses level (WARNING for domain errors, ERROR otherwise) and redacts sensitive context."""
    logger = logging.getLogger("aiohomematic.test.logging")

    # WARNING for domain/BaseHomematicException
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        log_boundary_error(
            logger,
            boundary="client",
            action="connect",
            err=AioHomematicException("oops"),
            log_context={"password": "secret", "token": "tok", "info": 42},
            message="while trying to connect",
        )
    assert any(rec.levelno == logging.WARNING for rec in caplog.records)
    # Validate redacted context and message parts present
    msg = caplog.records[-1].getMessage()
    assert "[boundary=client action=connect err=AioHomematicException: oops]" in msg
    assert "while trying to connect" in msg
    assert "ctx={" in msg
    assert '"password":"***"' in msg
    assert '"token":"***"' in msg
    assert '"info":42' in msg

    # ERROR for non-domain exception
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        log_boundary_error(
            logger,
            boundary="client",
            action="connect",
            err=ValueError("bad"),
        )
    assert any(rec.levelno == logging.ERROR for rec in caplog.records)
    assert "err=ValueError: bad" in caplog.records[-1].getMessage()


@pytest.mark.asyncio
async def test_delete_file_behaviour(tmp_path: Path) -> None:
    """delete_file removes regular files and symlinks but leaves directories and missing files untouched."""
    # Create regular file
    f = tmp_path / "a_file.txt"
    f.write_text("x")
    assert f.exists()

    # Create a symlink to the file
    s = tmp_path / "alink"
    os.symlink(f, s)
    assert s.exists()

    # Create a directory (should not be removed)
    d = tmp_path / "adir"
    d.mkdir()

    # delete regular file
    delete_file(folder=str(tmp_path), file_name=f.name)
    assert not f.exists()

    # delete symlink
    delete_file(folder=str(tmp_path), file_name=s.name)
    assert not s.exists()

    # attempt to delete directory by name -> function should no-op
    delete_file(folder=str(tmp_path), file_name=d.name)
    assert d.exists()

    # nonexistent file -> should not raise
    delete_file(folder=str(tmp_path), file_name="does_not_exist")
