Testing Guide
=============

This guide covers testing in aiohomematic.

Running Tests
-------------

Run all tests:

.. code-block:: bash

    pytest tests/

Run with coverage:

.. code-block:: bash

    pytest --cov=aiohomematic tests/

Run specific test file:

.. code-block:: bash

    pytest tests/test_central.py

Run with verbose output:

.. code-block:: bash

    pytest -v tests/

Test Organization
-----------------

Tests are organized in ``/tests/``:

.. code-block:: text

    tests/
    ├── conftest.py              # Shared fixtures
    ├── helpers/                 # Test helpers
    │   ├── mock_json_rpc.py
    │   └── mock_xml_rpc.py
    ├── test_central.py          # Central unit tests
    ├── test_client.py           # Client tests
    ├── test_model_*.py          # Model tests by entity type
    └── fixtures/                # Test data

Available Fixtures
------------------

Key fixtures from ``conftest.py``:

.. code-block:: python

    # Factory fixtures
    factory_with_ccu_client
    factory_with_homegear_client

    # Full central unit with client
    central_client_factory_with_ccu_client
    central_client_factory_with_homegear_client

    # Session playback
    session_player_ccu
    session_player_pydevccu

    # Virtual CCU instances
    central_unit_pydevccu_mini
    central_unit_pydevccu_full

    # HTTP session
    aiohttp_session

Writing Tests
-------------

Basic Test Structure
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    """Test for feature."""

    from __future__ import annotations

    import pytest

    from aiohomematic.central import CentralUnit
    from aiohomematic.const import Interface


    @pytest.mark.asyncio
    async def test_device_discovery(
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test device discovery."""
        central, _ = await central_client_factory_with_ccu_client()

        await central.start()

        # Assertions
        assert len(central.devices) > 0
        assert central.is_connected is True

        await central.stop()

Testing with Mocks
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from unittest.mock import Mock, AsyncMock

    @pytest.mark.asyncio
    async def test_with_mock():
        """Test with mocked dependencies."""
        mock_client = AsyncMock()
        mock_client.get_value.return_value = 42

        # Use mock in test
        result = await mock_client.get_value("parameter")
        assert result == 42

Testing Protocol Interfaces
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from aiohomematic.interfaces import CentralInfo

    class MockCentralInfo(CentralInfo):
        """Mock implementation."""
        @property
        def name(self) -> str:
            return "test"

        @property
        def model(self) -> str:
            return "TestModel"

    def test_with_protocol():
        """Test with protocol interface."""
        mock_info = MockCentralInfo()
        assert mock_info.name == "test"

Test Coverage
-------------

Target Coverage
~~~~~~~~~~~~~~~

- **Core Logic**: 90%+ coverage
- **Overall**: 85%+ coverage

Excluded Files
~~~~~~~~~~~~~~

Some files are excluded from coverage:

- ``aiohomematic/validator.py``
- ``aiohomematic/exceptions.py``
- ``aiohomematic/central/rpc_server.py``

Generate Coverage Report
~~~~~~~~~~~~~~~~~~~~~~~~

HTML report:

.. code-block:: bash

    pytest --cov=aiohomematic --cov-report=html tests/
    open htmlcov/index.html

Terminal report:

.. code-block:: bash

    pytest --cov=aiohomematic --cov-report=term-missing tests/

Best Practices
--------------

1. **Use Type Annotations**

   .. code-block:: python

       def test_function() -> None:
           """Test with type annotations."""
           result: int = some_function()
           assert result == 42

2. **Descriptive Test Names**

   .. code-block:: python

       def test_device_discovery_returns_all_devices() -> None:
           """Test that device discovery returns all devices."""

3. **One Assert Per Test**

   Prefer focused tests with single assertions:

   .. code-block:: python

       def test_device_count() -> None:
           """Test device count."""
           assert len(central.devices) == 5

       def test_device_names() -> None:
           """Test device names."""
           assert all(d.name for d in central.devices)

4. **Async Tests**

   Use ``@pytest.mark.asyncio`` for async tests:

   .. code-block:: python

       @pytest.mark.asyncio
       async def test_async_operation() -> None:
           """Test async operation."""
           result = await async_function()
           assert result is not None

5. **Cleanup**

   Always cleanup resources:

   .. code-block:: python

       @pytest.mark.asyncio
       async def test_with_cleanup() -> None:
           """Test with cleanup."""
           central = await create_central()
           try:
               await central.start()
               # Test code
           finally:
               await central.stop()

Running CI Tests
----------------

Tests run automatically on GitHub Actions for:

- Pull requests
- Pushes to ``master`` and ``devel``

CI runs:

- All tests
- Coverage checks
- Linting (ruff, mypy, pylint)
- Security checks (bandit)

Troubleshooting
---------------

Import Errors
~~~~~~~~~~~~~

If tests can't import modules:

1. Ensure you're in the project root
2. Install package in development mode: ``pip install -e .``
3. Check Python path

Async Warnings
~~~~~~~~~~~~~~

If you see warnings about unclosed resources:

.. code-block:: python

    # Add cleanup
    @pytest.fixture
    async def resource():
        r = await create_resource()
        yield r
        await r.close()

See Also
--------

- :doc:`contributing` - Contributing guide
- :doc:`di_architecture` - DI architecture
- pytest documentation: https://docs.pytest.org/
