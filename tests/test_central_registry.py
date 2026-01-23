# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for the CentralRegistry thread-safe registry."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from aiohomematic.central import CENTRAL_REGISTRY
from aiohomematic.central.registry import CentralRegistry


class TestCentralRegistry:
    """Test CentralRegistry operations."""

    def test_contains(self) -> None:
        """Test __contains__ for checking registration."""
        registry = CentralRegistry()
        mock = MagicMock(spec=["name"])

        assert "test" not in registry
        registry.register(name="test", central=mock)
        assert "test" in registry

    def test_get_nonexistent_returns_none(self) -> None:
        """Test getting a non-existent central returns None."""
        registry = CentralRegistry()

        result = registry.get(name="nonexistent")
        assert result is None

    def test_iter_returns_names(self) -> None:
        """Test __iter__ returns registered names."""
        registry = CentralRegistry()
        registry.register(name="alpha", central=MagicMock())
        registry.register(name="beta", central=MagicMock())

        names = list(registry)
        assert "alpha" in names
        assert "beta" in names
        assert len(names) == 2

    def test_iter_returns_snapshot(self) -> None:
        """Test __iter__ returns a snapshot, safe for modification during iteration."""
        registry = CentralRegistry()
        registry.register(name="a", central=MagicMock())
        registry.register(name="b", central=MagicMock())

        # Get iterator
        names_iter = iter(registry)

        # Modify during iteration (should not affect the iterator)
        registry.register(name="c", central=MagicMock())

        # Original iterator should not see 'c'
        names = list(names_iter)
        assert "c" not in names
        assert len(names) == 2

    def test_len(self) -> None:
        """Test __len__ for counting registered centrals."""
        registry = CentralRegistry()

        assert len(registry) == 0

        registry.register(name="c1", central=MagicMock())
        assert len(registry) == 1

        registry.register(name="c2", central=MagicMock())
        assert len(registry) == 2

        registry.unregister(name="c1")
        assert len(registry) == 1

    def test_overwrite_existing(self) -> None:
        """Test registering with existing name overwrites."""
        registry = CentralRegistry()
        mock1 = MagicMock(spec=["name"])
        mock2 = MagicMock(spec=["name"])

        registry.register(name="test", central=mock1)
        assert registry.get(name="test") is mock1

        registry.register(name="test", central=mock2)
        assert registry.get(name="test") is mock2
        assert len(registry) == 1

    def test_register_and_get(self) -> None:
        """Test registering and retrieving a central."""
        registry = CentralRegistry()
        mock_central = MagicMock(spec=["name"])
        mock_central.name = "test-central"

        registry.register(name="test-central", central=mock_central)

        result = registry.get(name="test-central")
        assert result is mock_central

    def test_unregister_existing(self) -> None:
        """Test unregistering an existing central."""
        registry = CentralRegistry()
        mock_central = MagicMock(spec=["name"])

        registry.register(name="test", central=mock_central)
        assert registry.get(name="test") is mock_central

        result = registry.unregister(name="test")
        assert result is True
        assert registry.get(name="test") is None

    def test_unregister_nonexistent(self) -> None:
        """Test unregistering a non-existent central returns False."""
        registry = CentralRegistry()

        result = registry.unregister(name="nonexistent")
        assert result is False

    def test_values_is_copy(self) -> None:
        """Test values() returns a copy, not the internal dict."""
        registry = CentralRegistry()
        mock = MagicMock(spec=["name"])
        registry.register(name="test", central=mock)

        values1 = registry.values()
        values2 = registry.values()

        # Should be different list objects
        assert values1 is not values2
        # But contain the same centrals
        assert values1 == values2

    def test_values_returns_snapshot(self) -> None:
        """Test values() returns a list snapshot."""
        registry = CentralRegistry()
        mock1 = MagicMock(spec=["name"])
        mock2 = MagicMock(spec=["name"])

        registry.register(name="central1", central=mock1)
        registry.register(name="central2", central=mock2)

        values = registry.values()
        assert isinstance(values, list)
        assert len(values) == 2
        assert mock1 in values
        assert mock2 in values


class TestCentralRegistryThreadSafety:
    """Test thread-safety of CentralRegistry."""

    def test_concurrent_register_unregister(self) -> None:
        """Test concurrent registration and unregistration."""
        registry = CentralRegistry()
        num_threads = 10
        iterations = 100
        errors: list[Exception] = []

        def worker(thread_id: int) -> None:
            try:
                for i in range(iterations):
                    name = f"central-{thread_id}-{i}"
                    mock = MagicMock(spec=["name"])
                    registry.register(name=name, central=mock)
                    # Verify it's registered
                    assert name in registry
                    # Get it
                    assert registry.get(name=name) is mock
                    # Unregister
                    registry.unregister(name=name)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert len(registry) == 0  # All should be unregistered

    def test_concurrent_values_during_modification(self) -> None:
        """Test calling values() concurrently with modifications."""
        registry = CentralRegistry()
        num_threads = 5
        iterations = 50
        errors: list[Exception] = []

        def modifier() -> None:
            try:
                for i in range(iterations):
                    name = f"mod-{i}"
                    registry.register(name=name, central=MagicMock())
                    registry.unregister(name=name)
            except Exception as e:
                errors.append(e)

        def reader() -> None:
            try:
                for _ in range(iterations):
                    # values() should always return a consistent list
                    values = registry.values()
                    assert isinstance(values, list)
                    # Iterate the list (should be safe)
                    for _ in values:
                        pass
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(num_threads):
            threads.append(threading.Thread(target=modifier))
            threads.append(threading.Thread(target=reader))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"


class TestGlobalCentralRegistry:
    """Test the global CENTRAL_REGISTRY singleton."""

    def test_global_registry_is_central_registry(self) -> None:
        """Test that CENTRAL_REGISTRY is a CentralRegistry instance."""
        assert isinstance(CENTRAL_REGISTRY, CentralRegistry)

    def test_global_registry_operations(self) -> None:
        """Test basic operations on the global registry."""
        # Save initial state
        initial_len = len(CENTRAL_REGISTRY)

        mock = MagicMock(spec=["name"])
        test_name = "__test_global_registry__"

        try:
            # Register
            CENTRAL_REGISTRY.register(name=test_name, central=mock)
            assert test_name in CENTRAL_REGISTRY
            assert CENTRAL_REGISTRY.get(name=test_name) is mock

            # Values should include our mock
            values = CENTRAL_REGISTRY.values()
            assert mock in values

        finally:
            # Cleanup
            CENTRAL_REGISTRY.unregister(name=test_name)

        assert len(CENTRAL_REGISTRY) == initial_len
