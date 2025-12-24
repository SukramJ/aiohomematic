# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Tests for aiohomematic.model.update.DpUpdate behavior using fakes.

Covers properties, latest_firmware selection, in_progress state, register/unregister
of handlers, and refresh/update methods.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aiohomematic.const import HMIP_FIRMWARE_UPDATE_IN_PROGRESS_STATES, HMIP_FIRMWARE_UPDATE_READY_STATES, Interface
from aiohomematic.model.update import DpUpdate
from aiohomematic.type_aliases import FirmwareUpdateHandler, UnsubscribeCallback


class _FakeCentral:
    def __init__(self) -> None:
        self.config = type("Cfg", (), {"central_id": "CentralTest"})()
        self._refreshed: list[str] = []
        self.name = "CentralTest"
        self.available = True

    async def refresh_firmware_data(self, *, device_address: str) -> None:  # noqa: D401
        """Record that refresh was invoked."""
        self._refreshed.append(device_address)


class _FakeConfigProvider:
    def __init__(self, *, central: _FakeCentral) -> None:
        self.config = central.config


class _FakeCentralInfo:
    def __init__(self, *, central: _FakeCentral) -> None:
        self.name = central.name
        self.available = central.available


class _FakeEventBus:
    """Minimal fake EventBus for testing."""

    async def publish(self, *, event: Any) -> None:  # noqa: ARG002
        """Do nothing for publish in tests."""

    def subscribe(self, *, event_type: type, event_key: Any, handler: Callable[..., Any]) -> Callable[[], None]:  # noqa: ARG002
        """Return a no-op unsubscribe function."""
        return lambda: None


class _FakeEventBusProvider:
    def __init__(self) -> None:
        self.event_bus = _FakeEventBus()


class _FakeTaskScheduler:
    pass


class _FakeParamsetDescriptionProvider:
    pass


class _FakeParameterVisibilityProvider:
    pass


class _FakeDeviceDataRefresher:
    def __init__(self, *, central: _FakeCentral) -> None:
        self._central = central

    async def refresh_firmware_data(self, *, device_address: str) -> None:
        await self._central.refresh_firmware_data(device_address=device_address)


class _FakeDevice:
    def __init__(self) -> None:
        self.central = _FakeCentral()
        self.address = "ADDR1"
        self.model = "HmIP-XYZ"
        self.name = "My Device"
        self.available = True
        self.firmware: str | None = "1.0.0"
        self.firmware_update_state: str | None = None
        self.available_firmware: str | None = None
        self.interface = Interface.BIDCOS_RF
        self._handlers: list[FirmwareUpdateHandler] = []
        # Add protocol interface attributes for DI
        self.config_provider = _FakeConfigProvider(central=self.central)
        self.central_info = _FakeCentralInfo(central=self.central)
        self.event_bus_provider = _FakeEventBusProvider()
        self.event_publisher = type("EventEmitter", (), {})()
        self.task_scheduler = _FakeTaskScheduler()
        self.paramset_description_provider = _FakeParamsetDescriptionProvider()
        self.parameter_visibility_provider = _FakeParameterVisibilityProvider()
        self.device_data_refresher = _FakeDeviceDataRefresher(central=self.central)

    def subscribe_to_firmware_updated(self, *, handler: FirmwareUpdateHandler) -> UnsubscribeCallback:
        self._handlers.append(handler)

        def _unsubscribe() -> None:
            self._handlers.remove(handler)

        return _unsubscribe

    def unsubscribe_from_firmware_update_handler(self, *, handler: FirmwareUpdateHandler) -> None:
        if handler in self._handlers:
            self._handlers.remove(handler)

    async def update_firmware(self, *, refresh_after_update_intervals: tuple[int, ...]) -> bool:  # noqa: D401
        """Pretend to start an update and return success."""
        return True


class TestUpdateDataPoint:
    """Tests for DpUpdate data points."""

    async def test_update_properties_and_latest_firmware_and_in_progress(self) -> None:
        """Test DpUpdate device properties and latest firmware computation."""
        dev = _FakeDevice()
        dp = DpUpdate(device=dev)  # type: ignore[arg-type]

        # Basic properties
        assert dp.available is True
        assert dp.firmware == "1.0.0"
        assert dp.firmware_update_state is None

        # latest_firmware for BidCos returns available_firmware if set
        dev.available_firmware = "1.1.0"
        assert dp.latest_firmware == "1.1.0"

        # HMIP: in_progress depends on state, latest depends on READY states
        dev.interface = Interface.HMIP_RF
        dev.firmware_update_state = next(iter(HMIP_FIRMWARE_UPDATE_IN_PROGRESS_STATES))
        assert dp.in_progress is True
        dev.firmware_update_state = next(iter(HMIP_FIRMWARE_UPDATE_READY_STATES))
        dev.available_firmware = "2.0.0"
        assert dp.latest_firmware == "2.0.0"

    async def test_update_register_unsubscribe_and_actions(self, monkeypatch: Any) -> None:
        """Test DpUpdate callback registration and firmware update actions."""
        dev = _FakeDevice()
        dp = DpUpdate(device=dev)  # type: ignore[arg-type]

        called: dict[str, Any] = {"count": 0}

        def cb(**kwargs: Any) -> None:  # noqa: D401
            """Execute dummy callback."""
            called["count"] += 1

        # Test subscription using EventBus architecture
        unregister = dp.subscribe_to_data_point_updated(handler=cb, custom_id="CID")
        assert callable(unregister)
        # With EventBus, subscriptions are managed by the event bus, not device callbacks
        # Just verify that unregister works without error
        unregister()

        # refresh_firmware_data should forward to central and update modified_at
        before = dp.modified_at
        await dp.refresh_firmware_data()
        assert dev.address in dev.central._refreshed
        assert dp.modified_at >= before

        # update_firmware forwards to device
        assert await dp.update_firmware(refresh_after_update_intervals=(1, 2)) is True
