# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for aiohomematic.model.calculated.derived_binary_sensor."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aiohomematic.const import CalculatedParameter, DataPointCategory, Parameter, ParameterType, ParamsetKey
from aiohomematic.model.calculated import DerivedBinarySensor, DerivedBinarySensorMapping, DerivedBinarySensorRegistry

# Shared fake helpers ---------------------------------------------------------


class _FakeCentral:
    def __init__(self) -> None:
        self.name = "CentralTest"
        self.config = type("Cfg", (), {"central_id": "CentralTest"})()
        self.paramset_descriptions = type("PS", (), {"is_in_multiple_channels": lambda *_args, **_kw: False})()
        self.device_details = type("DD", (), {"get_name": lambda *_args, **_kw: None})()

        class _PV:
            def parameter_is_hidden(self, *, channel, paramset_key, parameter) -> bool:
                return False

            def parameter_is_un_ignored(self, *, channel, paramset_key, parameter, custom_only: bool) -> bool:
                return False

        self.parameter_visibility = _PV()

        class _EventBus:
            def __init__(self, *, task_scheduler: Any = None) -> None:
                pass

            def subscribe(
                self, *, event_type: Any, event_key: Any, handler: Callable[[Any], None]
            ) -> Callable[[], None]:
                return lambda: None

        self.event_bus = _EventBus()


class _FakeDevice:
    def __init__(self, model: str = "HmIP-XYZ", address: str = "ADDR1") -> None:
        self.interface_id = "ifid"
        self.address = address
        self.central = _FakeCentral()
        self.model = model
        self.name = "DeviceName"
        self.client = type("Client", (), {"interface": None})()
        self._store: dict[tuple[str, ParamsetKey | None], _FakeGenericDP] = {}
        self.config_provider = type("ConfigProviderProtocol", (), {"config": self.central.config})()
        self.central_info = type("CentralInfoProtocol", (), {"name": "CentralTest", "available": True})()
        self.event_bus_provider = type("EventBusProviderProtocol", (), {"event_bus": self.central.event_bus})()
        self.event_publisher = type("EventPublisher", (), {})()
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

    def get_generic_data_point(self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey | None):
        key = (parameter, paramset_key)
        return self._store.get(key)


class _FakeGenericDP:
    def __init__(self, *, parameter: str, value: Any = None) -> None:
        self.parameter = parameter
        self._value = value
        self.is_readable = True
        self.paramset_key = ParamsetKey.VALUES

    @property
    def value(self) -> Any:
        return self._value

    @value.setter
    def value(self, val: Any) -> None:
        self._value = val

    def subscribe_to_internal_data_point_updated(self, handler: Callable[[], None]) -> Callable[[], None]:
        return lambda: None


class _FakeChannel:
    def __init__(self, device: _FakeDevice, no: int = 1) -> None:
        self.device = device
        self.no = no
        self.address = f"{device.address}:{no}"
        self._store: dict[tuple[str, ParamsetKey | None], _FakeGenericDP] = {}

    def get_generic_data_point(self, *, parameter: str, paramset_key: ParamsetKey | None):
        key = (parameter, paramset_key)
        return self._store.get(key)


# Tests -----------------------------------------------------------------------


def test_derived_binary_sensor_mapping_creation() -> None:
    """Test DerivedBinarySensorMapping dataclass creation."""
    mapping = DerivedBinarySensorMapping(
        model="HmIP-TEST",
        source_parameter=Parameter.STATE,
        source_channel_no=1,
        on_values=frozenset({"ON", "ACTIVE"}),
        off_values=frozenset({"OFF"}),
        calculated_parameter=CalculatedParameter.WINDOW_OPEN,
    )

    assert mapping.model == "HmIP-TEST"
    assert mapping.source_parameter == Parameter.STATE
    assert mapping.source_channel_no == 1
    assert mapping.on_values == frozenset({"ON", "ACTIVE"})
    assert mapping.off_values == frozenset({"OFF"})
    assert mapping.calculated_parameter == CalculatedParameter.WINDOW_OPEN


def test_registry_get_mappings_exact_match() -> None:
    """Test registry returns mappings for exact model match."""
    mappings = DerivedBinarySensorRegistry.get_mappings_for_model(model="HmIP-SRH")
    assert len(mappings) == 1
    assert mappings[0].calculated_parameter == CalculatedParameter.WINDOW_OPEN
    assert mappings[0].source_parameter == Parameter.STATE


def test_registry_get_mappings_prefix_match() -> None:
    """Test registry returns mappings for prefix model match."""
    mappings = DerivedBinarySensorRegistry.get_mappings_for_model(model="HmIP-SRH-123")
    assert len(mappings) == 1
    assert mappings[0].calculated_parameter == CalculatedParameter.WINDOW_OPEN


def test_registry_get_mappings_no_match() -> None:
    """Test registry returns empty tuple for unknown model."""
    mappings = DerivedBinarySensorRegistry.get_mappings_for_model(model="HmIP-UNKNOWN")
    assert len(mappings) == 0


def test_registry_get_mapping_by_parameter() -> None:
    """Test registry returns specific mapping by calculated parameter."""
    mapping = DerivedBinarySensorRegistry.get_mapping(calculated_parameter=CalculatedParameter.WINDOW_OPEN)
    assert mapping is not None
    assert mapping.model == ("HmIP-SRH", "HM-Sec-RHS")
    assert mapping.source_parameter == Parameter.STATE


def test_is_relevant_for_mapping_correct_model_and_channel() -> None:
    """Test is_relevant_for_mapping returns True for matching model and channel."""
    device = _FakeDevice(model="HM-Sec-RHS")
    channel = _FakeChannel(device=device, no=1)

    # Add source data point
    dp = _FakeGenericDP(parameter=Parameter.STATE)
    channel._store[(Parameter.STATE, ParamsetKey.VALUES)] = dp

    mapping = DerivedBinarySensorRegistry.get_mapping(calculated_parameter=CalculatedParameter.WINDOW_OPEN)
    assert mapping is not None

    assert DerivedBinarySensor.is_relevant_for_mapping(channel=channel, mapping=mapping) is True


def test_is_relevant_for_mapping_wrong_channel() -> None:
    """Test is_relevant_for_mapping returns False for wrong channel."""
    device = _FakeDevice(model="HmIP-SRH")
    channel = _FakeChannel(device=device, no=2)  # Wrong channel

    # Add source data point
    dp = _FakeGenericDP(parameter=Parameter.STATE)
    channel._store[(Parameter.STATE, ParamsetKey.VALUES)] = dp

    mapping = DerivedBinarySensorRegistry.get_mapping(calculated_parameter=CalculatedParameter.WINDOW_OPEN)
    assert mapping is not None

    assert DerivedBinarySensor.is_relevant_for_mapping(channel=channel, mapping=mapping) is False


def test_is_relevant_for_mapping_missing_parameter() -> None:
    """Test is_relevant_for_mapping returns False if source parameter missing."""
    device = _FakeDevice(model="HmIP-SRH")
    channel = _FakeChannel(device=device, no=1)

    # No source data point added

    mapping = DerivedBinarySensorRegistry.get_mapping(calculated_parameter=CalculatedParameter.WINDOW_OPEN)
    assert mapping is not None

    assert DerivedBinarySensor.is_relevant_for_mapping(channel=channel, mapping=mapping) is False


def test_derived_binary_sensor_value_on() -> None:
    """Test derived binary sensor returns True for ON values."""
    device = _FakeDevice(model="HmIP-SRH")
    channel = _FakeChannel(device=device, no=1)

    # Add source data point with OPEN value
    dp = _FakeGenericDP(parameter=Parameter.STATE, value="OPEN")
    channel._store[(Parameter.STATE, ParamsetKey.VALUES)] = dp

    mapping = DerivedBinarySensorRegistry.get_mapping(calculated_parameter=CalculatedParameter.WINDOW_OPEN)
    assert mapping is not None

    sensor = DerivedBinarySensor(channel=channel, mapping=mapping)

    assert sensor.value is True


def test_derived_binary_sensor_value_off() -> None:
    """Test derived binary sensor returns False for OFF values."""
    device = _FakeDevice(model="HmIP-SRH")
    channel = _FakeChannel(device=device, no=1)

    # Add source data point with CLOSED value
    dp = _FakeGenericDP(parameter=Parameter.STATE, value="CLOSED")
    channel._store[(Parameter.STATE, ParamsetKey.VALUES)] = dp

    mapping = DerivedBinarySensorRegistry.get_mapping(calculated_parameter=CalculatedParameter.WINDOW_OPEN)
    assert mapping is not None

    sensor = DerivedBinarySensor(channel=channel, mapping=mapping)

    assert sensor.value is False


def test_derived_binary_sensor_value_none() -> None:
    """Test derived binary sensor returns None if source value is None."""
    device = _FakeDevice(model="HmIP-SRH")
    channel = _FakeChannel(device=device, no=1)

    # Add source data point with None value
    dp = _FakeGenericDP(parameter=Parameter.STATE, value=None)
    channel._store[(Parameter.STATE, ParamsetKey.VALUES)] = dp

    mapping = DerivedBinarySensorRegistry.get_mapping(calculated_parameter=CalculatedParameter.WINDOW_OPEN)
    assert mapping is not None

    sensor = DerivedBinarySensor(channel=channel, mapping=mapping)

    assert sensor.value is None


def test_derived_binary_sensor_category() -> None:
    """Test derived binary sensor has correct category."""
    device = _FakeDevice(model="HmIP-SRH")
    channel = _FakeChannel(device=device, no=1)

    dp = _FakeGenericDP(parameter=Parameter.STATE)
    channel._store[(Parameter.STATE, ParamsetKey.VALUES)] = dp

    mapping = DerivedBinarySensorRegistry.get_mapping(calculated_parameter=CalculatedParameter.WINDOW_OPEN)
    assert mapping is not None

    sensor = DerivedBinarySensor(channel=channel, mapping=mapping)

    assert sensor.category == DataPointCategory.BINARY_SENSOR


def test_derived_binary_sensor_type() -> None:
    """Test derived binary sensor has correct type."""
    device = _FakeDevice(model="HmIP-SRH")
    channel = _FakeChannel(device=device, no=1)

    dp = _FakeGenericDP(parameter=Parameter.STATE)
    channel._store[(Parameter.STATE, ParamsetKey.VALUES)] = dp

    mapping = DerivedBinarySensorRegistry.get_mapping(calculated_parameter=CalculatedParameter.WINDOW_OPEN)
    assert mapping is not None

    sensor = DerivedBinarySensor(channel=channel, mapping=mapping)

    assert sensor.hmtype == ParameterType.BOOL


def test_smoke_alarm_mapping() -> None:
    """Test smoke alarm derived binary sensor mapping."""
    device = _FakeDevice(model="HmIP-SWSD")
    channel = _FakeChannel(device=device, no=1)

    # Add source data point with IDLE_OFF value
    dp = _FakeGenericDP(parameter=Parameter.SMOKE_DETECTOR_ALARM_STATUS, value="IDLE_OFF")
    channel._store[(Parameter.SMOKE_DETECTOR_ALARM_STATUS, ParamsetKey.VALUES)] = dp

    mapping = DerivedBinarySensorRegistry.get_mapping(calculated_parameter=CalculatedParameter.SMOKE_ALARM)
    assert mapping is not None

    sensor = DerivedBinarySensor(channel=channel, mapping=mapping)

    # IDLE_OFF should map to OFF (False)
    assert sensor.value is False

    # Change to PRIMARY_ALARM
    dp.value = "PRIMARY_ALARM"
    assert sensor.value is True


def test_window_open_multiple_on_values() -> None:
    """Test window open sensor with multiple ON values."""
    device = _FakeDevice(model="HmIP-SRH")
    channel = _FakeChannel(device=device, no=1)

    dp = _FakeGenericDP(parameter=Parameter.STATE)
    channel._store[(Parameter.STATE, ParamsetKey.VALUES)] = dp

    mapping = DerivedBinarySensorRegistry.get_mapping(calculated_parameter=CalculatedParameter.WINDOW_OPEN)
    assert mapping is not None

    sensor = DerivedBinarySensor(channel=channel, mapping=mapping)

    # Test TILTED -> ON
    dp.value = "TILTED"
    assert sensor.value is True

    # Test OPEN -> ON
    dp.value = "OPEN"
    assert sensor.value is True

    # Test CLOSED -> OFF
    dp.value = "CLOSED"
    assert sensor.value is False
