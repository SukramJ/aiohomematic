Dependency Injection Architecture
==================================

aiohomematic uses protocol-based dependency injection to reduce coupling and improve testability.

Overview
--------

The architecture follows a three-tier dependency injection pattern:

- **Tier 1 (Infrastructure)**: Full DI with protocol interfaces only
- **Tier 2 (Coordinators)**: Full protocol-based DI
- **Tier 3 (Model)**: Full DI through protocol interfaces

Protocol Interfaces
-------------------

All protocol interfaces are defined in ``aiohomematic/interfaces.py`` using Python's ``@runtime_checkable`` Protocol:

.. code-block:: python

    from typing import Protocol, runtime_checkable

    @runtime_checkable
    class CentralInfo(Protocol):
        """Protocol for central system information."""
        @property
        def name(self) -> str: ...

        @property
        def model(self) -> str: ...

Benefits
~~~~~~~~

1. **Reduced Coupling**: Components depend only on what they need
2. **Better Testability**: Easy to mock protocol interfaces
3. **Clear Dependencies**: Explicit interface contracts
4. **Maintainability**: Easier to understand and modify

Tier 1: Infrastructure Layer
-----------------------------

Components receive only protocol interfaces:

.. code-block:: python

    class CacheCoordinator:
        def __init__(
            self,
            *,
            central_info: CentralInfo,
            device_provider: DeviceProvider,
            client_provider: ClientProvider,
            # ... more protocol interfaces
        ) -> None:
            self._central_info: Final = central_info
            self._device_provider: Final = device_provider
            # Zero references to CentralUnit

Tier 2: Coordinator Layer
--------------------------

Coordinators use protocol interfaces exclusively (as of 2025-11-23):

Client Coordinator
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    class ClientCoordinator:
        def __init__(
            self,
            *,
            client_factory: ClientFactoryProtocol,  # Factory protocol
            central_info: CentralInfo,
            config_provider: ConfigProvider,
            # ... other protocol interfaces
        ) -> None:
            self._client_factory: Final = client_factory
            # All operations use protocol interfaces

Hub Coordinator
~~~~~~~~~~~~~~~

.. code-block:: python

    class HubCoordinator:
        def __init__(
            self,
            *,
            central_info: CentralInfo,
            channel_lookup: ChannelLookup,
            config_provider: ConfigProvider,
            event_bus_provider: EventBusProvider,
            # ... other protocol interfaces
        ) -> None:
            # Creates Hub using protocol interfaces
            self._hub: Final = Hub(
                central_info=central_info,
                config_provider=config_provider,
                # ... protocol interfaces only
            )

Tier 3: Model Layer
-------------------

Model classes receive protocol interfaces through their constructors:

Device
~~~~~~

.. code-block:: python

    class Device:
        def __init__(
            self,
            *,
            interface_id: str,
            device_address: str,
            device_details_provider: DeviceDetailsProviderProtocol,
            device_description_provider: DeviceDescriptionProviderProtocol,
            paramset_description_provider: ParamsetDescriptionProviderProtocol,
            # ... 13 more protocol interfaces
        ) -> None:
            self._device_details_provider: Final = device_details_provider
            # Stores all protocol interfaces

Channel
~~~~~~~

Channels access protocol interfaces through their parent Device:

.. code-block:: python

    class Channel:
        def __init__(self, *, device: Device, channel_address: str) -> None:
            self._device: Final = device
            # Accesses interfaces via self._device._xxx_provider

DataPoint
~~~~~~~~~

DataPoints receive protocol interfaces from channel.device:

.. code-block:: python

    class BaseDataPoint:
        def __init__(
            self,
            *,
            channel: Channel,
            unique_id: str,
            is_in_multiple_channels: bool,
        ) -> None:
            # Extracts protocol interfaces from channel.device
            super().__init__(
                unique_id=unique_id,
                central_info=channel.device._central_info,
                event_bus_provider=channel.device._event_bus_provider,
                # ... other protocol interfaces
            )

Testing with DI
---------------

Protocol interfaces make testing easy:

Mock Implementation
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    class MockCentralInfo(CentralInfo):
        """Mock implementation for testing."""
        def __init__(self, name: str = "test"):
            self._name = name

        @property
        def name(self) -> str:
            return self._name

        @property
        def model(self) -> str:
            return "TestModel"

Using in Tests
~~~~~~~~~~~~~~

.. code-block:: python

    @pytest.mark.asyncio
    async def test_coordinator():
        """Test coordinator with mocks."""
        mock_info = MockCentralInfo(name="test-central")
        mock_provider = MockDeviceProvider()

        coordinator = MyCoordinator(
            central_info=mock_info,
            device_provider=mock_provider,
        )

        # Test coordinator functionality
        assert coordinator.name == "test-central"

Available Protocols
-------------------

See :doc:`../api/interfaces` for complete list of protocol interfaces.

Key protocols include:

- **CentralInfo**: System identification
- **ClientFactoryProtocol**: Client instance creation (introduced 2025-11-23)
- **ClientProvider**: Client lookup
- **DeviceProvider**: Device registry access
- **EventBusProvider**: Event system access
- **TaskScheduler**: Background task scheduling

Historical Note
---------------

Prior to 2025-11-23, Tier 2 coordinators used a "hybrid DI" pattern where they kept a CentralUnit reference for factory operations. This was refactored to use pure protocol-based DI:

- **ClientCoordinator**: Now uses ``ClientFactoryProtocol`` protocol
- **HubCoordinator**: Now constructs Hub with protocol interfaces only
- **Hub**: Removed unused CentralUnit dependency

See Also
--------

- :doc:`../docs/di_refactor_summary` - Complete refactoring details
- :doc:`contributing` - Contributing guidelines
- :doc:`testing` - Testing guide
