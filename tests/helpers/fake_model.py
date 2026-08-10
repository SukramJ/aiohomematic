# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Lightweight fake model objects for tests that construct data points directly.

These fakes provide the minimum surface a channel, device and generic data point need
so that model classes can be instantiated without a central unit or a backend.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from aiohomematic.const import INIT_DATETIME, ParamsetKey

__all__ = [
    "FakeCentral",
    "FakeChannel",
    "FakeDevice",
    "FakeGenericDP",
]


class FakeCentral:
    """Minimal stand-in for a central unit."""

    def __init__(self) -> None:
        """Initialize the fake central."""
        self.name = "CentralTest"
        self.config = type("Cfg", (), {"central_id": "CentralTest", "locale": "en"})()
        # Minimal helpers used by name generation (not used here)
        self.paramset_descriptions = type("PS", (), {"is_in_multiple_channels": lambda *_args, **_kw: False})()
        self.device_details = type("DD", (), {"get_name": lambda *_args, **_kw: None})()

        # Provide minimal parameter_visibility used by GenericDataPoint init
        class _PV:
            def parameter_is_hidden(self, *, channel, paramset_key, parameter) -> bool:
                """In tests, nothing is hidden by default."""
                return False

            def parameter_is_un_ignored(self, *, channel, paramset_key, parameter, custom_only: bool) -> bool:
                """In tests, default to False (not un-ignored)."""
                return False

        self.parameter_visibility = _PV()

        # Provide minimal event_bus for callback registration
        class _EventBus:
            def __init__(self, *, task_scheduler: Any = None) -> None:
                """Initialize fake event bus."""

            def subscribe(
                self, *, event_type: Any, event_key: Any, handler: Callable[[Any], None]
            ) -> Callable[[], None]:
                """Mock subscribe that returns a no-op unsubscribe."""
                return lambda: None

        self.event_bus = _EventBus()


class FakeDevice:
    """Minimal stand-in for a device."""

    def __init__(self, model: str = "HmIP-XYZ", address: str = "ADDR1") -> None:
        """Initialize the fake device."""
        self.interface_id = "ifid"
        self.address = address
        self.central = FakeCentral()
        self.model = model
        self.name = "DeviceName"
        self.client = type("Client", (), {"interface": None})()
        self._store: dict[tuple[str, ParamsetKey | None], FakeGenericDP] = {}
        # Add protocol interface attributes for DI
        self.config_provider = type("ConfigProviderProtocol", (), {"config": self.central.config})()
        self.central_info = type("CentralInfoProtocol", (), {"name": "CentralTest", "available": True})()
        self.event_bus_provider = type("EventBusProviderProtocol", (), {"event_bus": self.central.event_bus})()
        self.event_publisher = type("EventEmitter", (), {})()
        self.task_scheduler = type("TaskScheduler", (), {})()
        self.paramset_description_provider = type(
            "ParamsetDescriptionProviderProtocol",
            (),
            {"is_in_multiple_channels": lambda self, channel_address, parameter: False},
        )()
        self.parameter_visibility_provider = type(
            "ParameterVisibilityProviderProtocol",
            (),
            {
                "parameter_is_hidden": lambda self, channel, paramset_key, parameter: False,
                "parameter_is_un_ignored": lambda self, channel, paramset_key, parameter, custom_only=False: False,
            },
        )()
        self.device_data_refresher = type("DeviceDataRefresherProtocol", (), {})()
        self.device_details_provider = type(
            "DeviceDetailsProviderProtocol", (), {"get_name": lambda self, address: None}
        )()

    def add_dp(self, dp: FakeGenericDP) -> None:
        """Add a data point on device level."""
        self._store[(dp.parameter, dp.paramset_key)] = dp

    def get_generic_data_point(
        self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey | None
    ) -> FakeGenericDP | None:
        """Return a device level data point."""
        return self._store.get((parameter, paramset_key))


class FakeGenericDP:
    """Minimal stand-in for a generic data point."""

    _counter: int = 0

    def __init__(
        self,
        *,
        parameter: str,
        paramset_key: ParamsetKey,
        value: Any = None,
        default: Any = None,
        readable: bool = True,
    ) -> None:
        """Initialize the fake generic data point."""
        FakeGenericDP._counter += 1
        self.parameter = parameter
        self.paramset_key = paramset_key
        self.value = value
        self.default = default
        self._readable = readable
        self._modified_at = INIT_DATETIME
        self._refreshed_at = INIT_DATETIME
        self.is_refreshed = True
        self.is_status_valid = True
        self.state_uncertain = False
        self.published_event_recently = True
        # Mimics the extra type/range checks of GenericDataPoint.is_valid, which a
        # refreshed data point without a usable value fails.
        self.has_valid_value = True
        self._unsubscribed: list[bool] = []
        self.unique_id = f"fake_dp_{FakeGenericDP._counter}"

    @property
    def is_readable(self) -> bool:
        """Return if the data point is readable."""
        return self._readable

    @property
    def is_valid(self) -> bool:
        """Return if the data point carries a usable value."""
        return self.is_refreshed and self.is_status_valid and self.has_valid_value

    @property
    def modified_at(self) -> datetime:
        """Return the last modification timestamp."""
        return self._modified_at

    @property
    def refreshed_at(self) -> datetime:
        """Return the last refresh timestamp."""
        return self._refreshed_at

    def set_times(self, *, modified_delta: int, refreshed_delta: int) -> None:
        """Set modification and refresh timestamps relative to now."""
        base = datetime.now()
        self._modified_at = base + timedelta(seconds=modified_delta)
        self._refreshed_at = base + timedelta(seconds=refreshed_delta)


class FakeChannel:
    """Minimal stand-in for a channel."""

    def __init__(self, model: str = "HmIP-XYZ", address: str = "ADDR1:1") -> None:
        """Initialize the fake channel."""
        self.central = FakeCentral()
        self.device = FakeDevice(model=model, address=address.split(":")[0])
        self.address = address
        self.no = int(address.split(":")[-1]) if ":" in address else 1
        self.name = f"FakeChannel {address}"
        self.type_name = "FAKE_CHANNEL_TYPE"
        self._store: dict[tuple[str, ParamsetKey | None], FakeGenericDP] = {}

    def add_fake(self, dp: FakeGenericDP) -> None:
        """Add a data point on channel level."""
        self._store[(dp.parameter, dp.paramset_key)] = dp

    # Channel-level DP getter used by calculated DPs
    def get_generic_data_point(self, *, parameter: str, paramset_key: ParamsetKey | None) -> FakeGenericDP | None:
        """Return a channel level data point."""
        return self._store.get((parameter, paramset_key))
