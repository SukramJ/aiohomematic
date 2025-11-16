"""Tests for package import side effects and signal handling in aiohomematic."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def reload_pkg(monkeypatch):
    """Reload the top-level package with patched environment and validator."""

    def _reload(stdout_isatty: bool = True, validate_raises: Exception | None = None):
        # Patch sys.stdout.isatty for import behavior
        monkeypatch.setattr(sys, "stdout", SimpleNamespace(isatty=lambda: stdout_isatty))
        # Prepare: import real validator and patch its validate_startup behavior
        import aiohomematic.validator as validator  # type: ignore[import-not-found]

        if validate_raises is None:
            monkeypatch.setattr(validator, "validate_startup", lambda: None)
        else:

            def _raise():
                raise validate_raises

            monkeypatch.setattr(validator, "validate_startup", _raise)
        # Import or reload top-level package which executes startup validation and signal setup
        if "aiohomematic" in sys.modules:
            pkg = importlib.reload(sys.modules["aiohomematic"])  # type: ignore[arg-type]
        else:
            pkg = importlib.import_module("aiohomematic")
        return pkg

    return _reload


class TestPackageImport:
    """Test package import side effects and signal handling."""

    def test_import_raises_clear_error(self, monkeypatch):
        """Importing __init__ should raise clear RuntimeError when validation fails."""
        # Import once to ensure environment is stable
        import aiohomematic.validator as validator  # type: ignore[import-not-found]

        # Patch validator to raise and execute module code in isolated namespace
        def _raise():
            raise ValueError("boom")

        monkeypatch.setattr(validator, "validate_startup", _raise)

        import runpy

        with pytest.raises(RuntimeError) as err:
            # Execute package __init__ in a fresh namespace to avoid polluting global state
            runpy.run_module("aiohomematic.__init__", init_globals={}, run_name="__init__")

        assert "startup validation failed" in str(err.value).lower()

    def test_init_sets_version_and_allows_non_tty_import(self, reload_pkg):
        """Import on non-TTY should still set __version__ and __all__."""
        pkg = reload_pkg(stdout_isatty=False)
        assert hasattr(pkg, "__version__")
        assert "__version__" in pkg.__all__

    def test_signal_handler_triggers_stop(self, monkeypatch, reload_pkg):
        """Signal handler should schedule stop() on all central instances."""

        # Prepare a minimal fake central with stop coroutine
        class FakeCentral:
            def __init__(self):
                self.stopped = False

            async def stop(self):
                self.stopped = True
                return

        # Need an event loop to be running to schedule stop; patch asyncio.get_running_loop
        import asyncio

        loop = asyncio.new_event_loop()
        monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop)

        # Patch central instances mapping
        import aiohomematic.central as hmcu

        fake = FakeCentral()
        monkeypatch.setattr(hmcu, "CENTRAL_INSTANCES", {"c1": fake})

        pkg = reload_pkg(stdout_isatty=True)

        # Call the signal handler and ensure it schedules stop
        pkg.signal_handler(sig=2, frame=None)
        # Execute scheduled task
        loop.run_until_complete(asyncio.sleep(0))
        # Allow the thread-safe future to complete
        loop.run_until_complete(asyncio.sleep(0))
        assert fake.stopped is True

        loop.close()
