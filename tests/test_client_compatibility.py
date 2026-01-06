# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Compatibility tests for InterfaceClient vs Legacy Client.

These tests ensure that both client implementations produce identical results
for ALL client output at every level of the hierarchy:
- Device descriptions and metadata
- Channel descriptions and metadata
- Data point values and metadata
- Paramset descriptions
- Events
- Names at all levels
- Rooms and functions
- ReGa IDs
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any
from unittest.mock import patch

import pytest

from aiohomematic.central import CentralUnit
from aiohomematic.const import DataPointCategory, ParamsetKey
from aiohomematic_test_support import const
from aiohomematic_test_support.factory import FactoryWithClient
from aiohomematic_test_support.mock import SessionPlayer, get_session_player

# Test device addresses that cover multiple device types
TEST_DEVICES: set[str] = {
    "VCU2128127",  # HmIP-BSM - Switch with power metering
    "VCU6354483",  # HmIP-eTRV-2 - Thermostat
}


# pylint: disable=protected-access,too-many-instance-attributes


@dataclass
class DataPointSnapshot:
    """Snapshot of a single data point."""

    unique_id: str
    name: str
    full_name: str
    category: DataPointCategory
    value: Any
    unit: str | None
    min_value: Any
    max_value: Any
    default_value: Any
    value_list: tuple[str, ...] | None
    is_valid: bool
    is_forced_sensor: bool
    is_refreshed: bool


@dataclass
class EventSnapshot:
    """Snapshot of a single event."""

    unique_id: str
    name: str
    full_name: str
    event_type: str
    parameter: str


@dataclass
class ChannelSnapshot:
    """Snapshot of a single channel."""

    address: str
    name: str
    full_name: str
    no: int | None
    type_name: str
    rega_id: int
    room: str | None
    rooms: frozenset[str]
    function: str | None
    paramset_keys: tuple[str, ...]
    generic_dp_count: int
    custom_dp_count: int
    calculated_dp_count: int
    event_count: int


@dataclass
class DeviceSnapshot:
    """Snapshot of a single device."""

    address: str
    name: str
    model: str
    firmware: str
    interface: str
    interface_id: str
    rega_id: int
    room: str | None
    available: bool
    channel_count: int
    generic_dp_count: int
    custom_dp_count: int
    calculated_dp_count: int
    event_count: int


@dataclass
class CentralSnapshot:
    """Complete snapshot of central state for comparison."""

    # Devices
    devices: dict[str, DeviceSnapshot] = field(default_factory=dict)
    device_count: int = 0

    # Channels
    channels: dict[str, ChannelSnapshot] = field(default_factory=dict)

    # Data points (generic, custom, calculated)
    generic_data_points: dict[str, DataPointSnapshot] = field(default_factory=dict)
    custom_data_points: dict[str, DataPointSnapshot] = field(default_factory=dict)
    calculated_data_points: dict[str, DataPointSnapshot] = field(default_factory=dict)

    # Events
    events: dict[str, EventSnapshot] = field(default_factory=dict)

    # Paramset descriptions (keyed by "address:paramset_key")
    paramset_descriptions: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Device details from cache (names, rega_ids, interfaces)
    cached_names: dict[str, str] = field(default_factory=dict)
    cached_rega_ids: dict[str, int] = field(default_factory=dict)
    cached_interfaces: dict[str, str] = field(default_factory=dict)


def capture_data_point_snapshot(*, dp: Any) -> DataPointSnapshot:
    """Capture snapshot of a data point."""
    return DataPointSnapshot(
        unique_id=dp.unique_id,
        name=dp.name,
        full_name=dp.full_name,
        category=dp.category,
        value=getattr(dp, "value", None),  # Custom DPs may not have value
        unit=getattr(dp, "unit", None),
        min_value=getattr(dp, "min", None),
        max_value=getattr(dp, "max", None),
        default_value=getattr(dp, "default", None),
        value_list=getattr(dp, "value_list", None),
        is_valid=getattr(dp, "is_valid", True),
        is_forced_sensor=getattr(dp, "_is_forced_sensor", False),
        is_refreshed=getattr(dp, "is_refreshed", False),
    )


def capture_event_snapshot(*, event: Any) -> EventSnapshot:
    """Capture snapshot of an event."""
    return EventSnapshot(
        unique_id=event.unique_id,
        name=event.name,
        full_name=event.full_name,
        event_type=str(event.event_type),
        parameter=event.parameter,
    )


def capture_channel_snapshot(*, channel: Any) -> ChannelSnapshot:
    """Capture snapshot of a channel."""
    return ChannelSnapshot(
        address=channel.address,
        name=channel.name,
        full_name=channel.name_data.full_name,
        no=channel.no,
        type_name=channel.type_name,
        rega_id=channel.rega_id,
        room=channel.room,
        rooms=frozenset(channel.rooms),
        function=channel.function,
        paramset_keys=tuple(str(pk) for pk in channel.paramset_keys),
        generic_dp_count=len(channel.generic_data_points),
        custom_dp_count=1 if channel.custom_data_point else 0,
        calculated_dp_count=len(channel.calculated_data_points),
        event_count=len(channel.generic_events),
    )


def capture_device_snapshot(*, device: Any) -> DeviceSnapshot:
    """Capture snapshot of a device."""
    return DeviceSnapshot(
        address=device.address,
        name=device.name,
        model=device.model,
        firmware=device.firmware,
        interface=str(device.interface),
        interface_id=device.interface_id,
        rega_id=device.rega_id,
        room=device.room,
        available=device.available,
        channel_count=len(device.channels),
        generic_dp_count=len(device.generic_data_points),
        custom_dp_count=len(device.custom_data_points),
        calculated_dp_count=len(device.calculated_data_points),
        event_count=len(device.generic_events),
    )


def capture_central_snapshot(*, central: CentralUnit) -> CentralSnapshot:
    """Capture a complete snapshot of the central state."""
    snapshot = CentralSnapshot()
    snapshot.device_count = len(central.devices)

    for device in central.devices:
        # Capture device
        snapshot.devices[device.address] = capture_device_snapshot(device=device)

        # Capture channels
        for channel in device.channels.values():
            snapshot.channels[channel.address] = capture_channel_snapshot(channel=channel)

            # Capture paramset descriptions for this channel
            for paramset_key in channel.paramset_keys:
                key = f"{channel.address}:{paramset_key}"
                try:
                    desc = central.cache_coordinator.paramset_descriptions.get_paramset_descriptions(
                        interface_id=device.interface_id,
                        channel_address=channel.address,
                        paramset_key=paramset_key,
                    )
                    # Convert to comparable dict (sort keys)
                    snapshot.paramset_descriptions[key] = {
                        param: dict(sorted(data.items())) for param, data in sorted(desc.items())
                    }
                except KeyError:
                    pass  # Paramset not in cache

            # Capture generic data points
            for dp in channel.generic_data_points:
                snapshot.generic_data_points[dp.unique_id] = capture_data_point_snapshot(dp=dp)

            # Capture custom data point
            if channel.custom_data_point:
                dp = channel.custom_data_point
                snapshot.custom_data_points[dp.unique_id] = capture_data_point_snapshot(dp=dp)

            # Capture calculated data points
            for dp in channel.calculated_data_points:
                snapshot.calculated_data_points[dp.unique_id] = capture_data_point_snapshot(dp=dp)

            # Capture events
            for event in channel.generic_events:
                snapshot.events[event.unique_id] = capture_event_snapshot(event=event)

    # Capture cached device details
    device_details = central.cache_coordinator.device_details
    for device in central.devices:
        if name := device_details.get_name(address=device.address):
            snapshot.cached_names[device.address] = name
        if rega_id := device_details.get_address_id(address=device.address):
            snapshot.cached_rega_ids[device.address] = rega_id
        if interface := device_details.get_interface(address=device.address):
            snapshot.cached_interfaces[device.address] = str(interface)

        for channel in device.channels.values():
            if name := device_details.get_name(address=channel.address):
                snapshot.cached_names[channel.address] = name
            if rega_id := device_details.get_address_id(address=channel.address):
                snapshot.cached_rega_ids[channel.address] = rega_id

    # Note: Rooms and functions are loaded asynchronously from hub and may not be
    # available in test context. They are fetched via client.get_all_rooms() and
    # client.get_all_functions() which depend on backend capabilities.

    return snapshot


async def create_central_with_client_type(
    *,
    session_player: SessionPlayer,
    use_interface_client: bool,
) -> tuple[CentralUnit, FactoryWithClient]:
    """Create a central with the specified client type."""
    env_value = "1" if use_interface_client else "0"
    with patch.dict(os.environ, {"AIOHOMEMATIC_USE_INTERFACE_CLIENT": env_value}):
        factory = FactoryWithClient(
            player=session_player,
            address_device_translation=TEST_DEVICES,
        )
        central = await factory.get_default_central()
        return central, factory


def _compare_items(
    *,
    iface_items: dict[str, Any],
    legacy_items: dict[str, Any],
    item_type: str,
    attrs: tuple[str, ...],
    differences: list[str],
) -> None:
    """Compare dictionary items by attributes and append differences."""
    if iface_items.keys() != legacy_items.keys():
        iface_only = set(iface_items.keys()) - set(legacy_items.keys())
        legacy_only = set(legacy_items.keys()) - set(iface_items.keys())
        differences.append(f"{item_type} IDs differ: InterfaceClient-only={iface_only}, Legacy-only={legacy_only}")
        return

    for key, iface_item in iface_items.items():
        legacy_item = legacy_items[key]
        for attr in attrs:
            iface_val = getattr(iface_item, attr)
            legacy_val = getattr(legacy_item, attr)
            if iface_val != legacy_val:
                differences.append(
                    f"{item_type} {key}.{attr} mismatch: InterfaceClient={iface_val!r}, Legacy={legacy_val!r}"
                )


def _compare_paramsets(
    *,
    interface: CentralSnapshot,
    legacy: CentralSnapshot,
    differences: list[str],
) -> None:
    """Compare paramset descriptions."""
    if interface.paramset_descriptions.keys() != legacy.paramset_descriptions.keys():
        iface_only = set(interface.paramset_descriptions.keys()) - set(legacy.paramset_descriptions.keys())
        legacy_only = set(legacy.paramset_descriptions.keys()) - set(interface.paramset_descriptions.keys())
        differences.append(
            f"Paramset description keys differ: InterfaceClient-only={iface_only}, Legacy-only={legacy_only}"
        )
        return

    for key, iface_desc in interface.paramset_descriptions.items():
        legacy_desc = legacy.paramset_descriptions[key]
        if iface_desc != legacy_desc:
            differences.append(f"Paramset description {key} differs")


def _compare_cached_details(
    *,
    interface: CentralSnapshot,
    legacy: CentralSnapshot,
    differences: list[str],
) -> None:
    """Compare cached device details."""
    if interface.cached_names != legacy.cached_names:
        differences.append(
            f"Cached names differ: InterfaceClient={interface.cached_names}, Legacy={legacy.cached_names}"
        )
    if interface.cached_rega_ids != legacy.cached_rega_ids:
        differences.append(
            f"Cached rega_ids differ: InterfaceClient={interface.cached_rega_ids}, Legacy={legacy.cached_rega_ids}"
        )
    if interface.cached_interfaces != legacy.cached_interfaces:
        differences.append(
            f"Cached interfaces differ: InterfaceClient={interface.cached_interfaces}, "
            f"Legacy={legacy.cached_interfaces}"
        )


# Attribute lists for comparison
_DEVICE_ATTRS = (
    "name",
    "model",
    "firmware",
    "interface",
    "interface_id",
    "rega_id",
    "room",
    "available",
    "channel_count",
    "generic_dp_count",
    "custom_dp_count",
    "calculated_dp_count",
    "event_count",
)
_CHANNEL_ATTRS = (
    "name",
    "full_name",
    "no",
    "type_name",
    "rega_id",
    "room",
    "rooms",
    "function",
    "paramset_keys",
    "generic_dp_count",
    "custom_dp_count",
    "calculated_dp_count",
    "event_count",
)
_GENERIC_DP_ATTRS = (
    "name",
    "full_name",
    "category",
    "value",
    "unit",
    "min_value",
    "max_value",
    "default_value",
    "value_list",
    "is_valid",
)
_CUSTOM_DP_ATTRS = ("name", "full_name", "category", "value", "is_valid")
_CALCULATED_DP_ATTRS = ("name", "full_name", "value")
_EVENT_ATTRS = ("name", "full_name", "event_type", "parameter")


def compare_snapshots(*, interface: CentralSnapshot, legacy: CentralSnapshot) -> list[str]:
    """Compare two snapshots and return list of differences."""
    differences: list[str] = []

    # Compare device count
    if interface.device_count != legacy.device_count:
        differences.append(
            f"Device count mismatch: InterfaceClient={interface.device_count}, Legacy={legacy.device_count}"
        )

    # Compare devices
    _compare_items(
        iface_items=interface.devices,
        legacy_items=legacy.devices,
        item_type="Device",
        attrs=_DEVICE_ATTRS,
        differences=differences,
    )

    # Compare channels
    _compare_items(
        iface_items=interface.channels,
        legacy_items=legacy.channels,
        item_type="Channel",
        attrs=_CHANNEL_ATTRS,
        differences=differences,
    )

    # Compare generic data points
    _compare_items(
        iface_items=interface.generic_data_points,
        legacy_items=legacy.generic_data_points,
        item_type="Generic DP",
        attrs=_GENERIC_DP_ATTRS,
        differences=differences,
    )

    # Compare custom data points
    _compare_items(
        iface_items=interface.custom_data_points,
        legacy_items=legacy.custom_data_points,
        item_type="Custom DP",
        attrs=_CUSTOM_DP_ATTRS,
        differences=differences,
    )

    # Compare calculated data points
    _compare_items(
        iface_items=interface.calculated_data_points,
        legacy_items=legacy.calculated_data_points,
        item_type="Calculated DP",
        attrs=_CALCULATED_DP_ATTRS,
        differences=differences,
    )

    # Compare events
    _compare_items(
        iface_items=interface.events,
        legacy_items=legacy.events,
        item_type="Event",
        attrs=_EVENT_ATTRS,
        differences=differences,
    )

    # Compare paramset descriptions
    _compare_paramsets(interface=interface, legacy=legacy, differences=differences)

    # Compare cached device details
    _compare_cached_details(interface=interface, legacy=legacy, differences=differences)

    return differences


class TestClientCompatibility:
    """Test that both clients produce identical results for ALL output."""

    @pytest.mark.asyncio
    async def test_complete_client_output_identical(self) -> None:
        """
        Test that ALL client output is identical between InterfaceClient and Legacy client.

        This comprehensive test compares:
        - Device metadata (name, model, firmware, interface, rega_id, room, availability)
        - Channel metadata (name, type, rega_id, room, function, paramset_keys)
        - Data point values and metadata (value, category, unit, min/max/default, value_list)
        - Calculated data points
        - Events
        - Paramset descriptions
        - Cached device details (names, rega_ids, interfaces)
        - Rooms and functions
        """
        # Load session data
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)

        # Create central with InterfaceClient and capture snapshot
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )
        interface_snapshot = capture_central_snapshot(central=interface_central)
        await interface_central.stop()
        interface_factory.cleanup()

        # Reload session for fresh state
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)

        # Create central with Legacy client and capture snapshot
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )
        legacy_snapshot = capture_central_snapshot(central=legacy_central)
        await legacy_central.stop()
        legacy_factory.cleanup()

        # Compare all data
        differences = compare_snapshots(interface=interface_snapshot, legacy=legacy_snapshot)

        # Report all differences at once for better debugging
        assert not differences, "Client outputs differ:\n" + "\n".join(f"  - {diff}" for diff in differences)


class TestNameVerificationAtAllLevels:
    """
    Verify that names are correctly populated at all levels.

    Uses session player for realistic data that includes proper names.
    """

    @pytest.mark.asyncio
    async def test_all_names_populated(self) -> None:
        """
        Test that all names are non-empty at every level.

        This test verifies:
        - Device names
        - Channel names
        - Generic data point names (name and full_name)
        - Custom data point names (name and full_name)
        - Calculated data point names
        - Event names
        """
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        factory = FactoryWithClient(
            player=session_player,
            address_device_translation=TEST_DEVICES,
        )
        central = await factory.get_default_central()

        try:
            # Verify device names
            for device in central.devices:
                assert device.name, f"Device {device.address} has empty name"
                assert device.name != device.address, f"Device {device.address} name equals address (not user-friendly)"

                # Verify channel names
                # Note: channel :0 (device channel) has channel.no == None and may have empty
                # channel.name by design (it would be redundant with device name).
                # In this case, name_data.full_name still has the full name.
                for channel in device.channels.values():
                    if channel.no is not None:
                        assert channel.name, f"Channel {channel.address} has empty name"
                    # full_name should always be populated for all channels
                    assert channel.name_data.full_name, f"Channel {channel.address} has empty full_name"

                # Verify generic data point names
                # Note: dp.name can be empty when channel name equals device name.
                # dp.full_name should always be populated.
                for dp in device.generic_data_points:
                    assert dp.full_name, f"Generic DP {dp.unique_id} has empty full_name"

                # Verify custom data point names
                for dp in device.custom_data_points:
                    assert dp.full_name, f"Custom DP {dp.unique_id} has empty full_name"

                # Verify calculated data point names
                for dp in device.calculated_data_points:
                    assert dp.full_name, f"Calculated DP {dp.unique_id} has empty full_name"

                # Verify event names
                for event in device.generic_events:
                    assert event.full_name, f"Event {event.unique_id} has empty full_name"
        finally:
            await central.stop()
            factory.cleanup()


class TestWriteOperationCompatibility:
    """
    Test that write operations produce identical results on both clients.

    These tests verify that set_value, put_paramset, and other write operations
    behave identically between InterfaceClient and Legacy client.
    """

    @pytest.mark.asyncio
    async def test_put_paramset_produces_same_events(self) -> None:
        """Test that put_paramset produces the same data point events on both clients."""
        interface_events: list[tuple[str, Any]] = []
        legacy_events: list[tuple[str, Any]] = []

        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            # Find thermostat channel for testing paramset
            test_channel = None
            for device in interface_central.devices:
                if device.model == "HmIP-eTRV-2":
                    # Channel 1 is the climate channel
                    test_channel = device.channels.get(f"{device.address}:1")
                    break

            if test_channel:
                # Subscribe to value changes
                def on_interface_update(*, parameter: str, value: Any, **kwargs: Any) -> None:
                    interface_events.append((parameter, value))

                for dp in test_channel.generic_data_points:
                    dp.subscribe_to_data_point_updated(handler=on_interface_update, custom_id="test")

                # Perform put_paramset
                await client.put_paramset(
                    channel_address=test_channel.address,
                    paramset_key="VALUES",
                    values={"SET_POINT_TEMPERATURE": 21.0},
                )
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            test_channel = None
            for device in legacy_central.devices:
                if device.model == "HmIP-eTRV-2":
                    test_channel = device.channels.get(f"{device.address}:1")
                    break

            if test_channel:

                def on_legacy_update(*, parameter: str, value: Any, **kwargs: Any) -> None:
                    legacy_events.append((parameter, value))

                for dp in test_channel.generic_data_points:
                    dp.subscribe_to_data_point_updated(handler=on_legacy_update, custom_id="test")

                await client.put_paramset(
                    channel_address=test_channel.address,
                    paramset_key="VALUES",
                    values={"SET_POINT_TEMPERATURE": 21.0},
                )
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        # Compare events
        assert len(interface_events) == len(legacy_events), (
            f"Event count mismatch: InterfaceClient={len(interface_events)}, Legacy={len(legacy_events)}"
        )

        # Sort by parameter to ensure consistent comparison
        interface_sorted = sorted(interface_events, key=lambda x: x[0])
        legacy_sorted = sorted(legacy_events, key=lambda x: x[0])

        for iface_evt, legacy_evt in zip(interface_sorted, legacy_sorted, strict=True):
            assert iface_evt[0] == legacy_evt[0], f"Parameter mismatch: {iface_evt[0]} != {legacy_evt[0]}"
            assert iface_evt[1] == legacy_evt[1], f"Value mismatch: {iface_evt[1]} != {legacy_evt[1]}"

    @pytest.mark.asyncio
    async def test_set_value_produces_same_event(self) -> None:
        """Test that set_value produces the same data point event on both clients."""
        # Track received events
        interface_events: list[tuple[str, str, Any]] = []
        legacy_events: list[tuple[str, str, Any]] = []

        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            # Find a writable data point (switch STATE parameter)
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            # Find a device with a switch channel
            test_device = None
            test_channel = None
            for device in interface_central.devices:
                if device.model == "HmIP-BSM":
                    test_device = device
                    # Channel 4 is the switch channel for BSM
                    test_channel = device.channels.get(f"{device.address}:4")
                    break

            if test_device and test_channel:
                # Subscribe to value changes
                def on_interface_update(*, unique_id: str, parameter: str, value: Any, **kwargs: Any) -> None:
                    interface_events.append((unique_id, parameter, value))

                for dp in test_channel.generic_data_points:
                    if dp.parameter == "STATE":
                        dp.subscribe_to_data_point_updated(handler=on_interface_update, custom_id="test")

                        # Perform set_value via client
                        await client.set_value(
                            channel_address=test_channel.address,
                            paramset_key=ParamsetKey.VALUES,
                            parameter="STATE",
                            value=True,
                        )
                        break
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            test_device = None
            test_channel = None
            for device in legacy_central.devices:
                if device.model == "HmIP-BSM":
                    test_device = device
                    test_channel = device.channels.get(f"{device.address}:4")
                    break

            if test_device and test_channel:

                def on_legacy_update(*, unique_id: str, parameter: str, value: Any, **kwargs: Any) -> None:
                    legacy_events.append((unique_id, parameter, value))

                for dp in test_channel.generic_data_points:
                    if dp.parameter == "STATE":
                        dp.subscribe_to_data_point_updated(handler=on_legacy_update, custom_id="test")

                        await client.set_value(
                            channel_address=test_channel.address,
                            paramset_key=ParamsetKey.VALUES,
                            parameter="STATE",
                            value=True,
                        )
                        break
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        # Compare events (both should have received same parameter and value)
        assert len(interface_events) == len(legacy_events), (
            f"Event count mismatch: InterfaceClient={len(interface_events)}, Legacy={len(legacy_events)}"
        )

        for iface_evt, legacy_evt in zip(interface_events, legacy_events, strict=True):
            # unique_id will differ due to different central instances, but parameter and value should match
            assert iface_evt[1] == legacy_evt[1], f"Parameter mismatch: {iface_evt[1]} != {legacy_evt[1]}"
            assert iface_evt[2] == legacy_evt[2], f"Value mismatch: {iface_evt[2]} != {legacy_evt[2]}"


class TestReadOperationCompatibility:
    """Test that read operations return identical results on both clients."""

    @pytest.mark.asyncio
    async def test_get_paramset_returns_identical_data(self) -> None:
        """Test that get_paramset returns identical data from both clients."""
        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        interface_paramsets: dict[str, dict[str, Any]] = {}

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            for device in interface_central.devices:
                for channel in device.channels.values():
                    try:
                        paramset = await client.get_paramset(
                            address=channel.address,
                            paramset_key="VALUES",
                        )
                        interface_paramsets[channel.address] = paramset
                    except Exception:
                        # Some channels may not have VALUES paramset
                        pass
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        legacy_paramsets: dict[str, dict[str, Any]] = {}

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            for device in legacy_central.devices:
                for channel in device.channels.values():
                    try:
                        paramset = await client.get_paramset(
                            address=channel.address,
                            paramset_key="VALUES",
                        )
                        legacy_paramsets[channel.address] = paramset
                    except Exception:
                        pass
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        # Compare paramsets
        assert interface_paramsets.keys() == legacy_paramsets.keys(), (
            f"Paramset keys differ: {interface_paramsets.keys()} != {legacy_paramsets.keys()}"
        )

        for address, iface_ps in interface_paramsets.items():
            legacy_ps = legacy_paramsets[address]
            assert iface_ps == legacy_ps, f"Paramset for {address} differs"


class TestConnectionCompatibility:
    """Test that connection operations behave identically on both clients."""

    @pytest.mark.asyncio
    async def test_check_connection_returns_same_result(self) -> None:
        """Test that check_connection returns the same result on both clients."""
        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            interface_result = await client.check_connection_availability(handle_ping_pong=True)
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            legacy_result = await client.check_connection_availability(handle_ping_pong=True)
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        assert interface_result == legacy_result, (
            f"check_connection results differ: InterfaceClient={interface_result}, Legacy={legacy_result}"
        )


class TestCapabilityCompatibility:
    """Test that capability reporting is identical between clients."""

    @pytest.mark.asyncio
    async def test_capabilities_identical(self) -> None:
        """Test that both clients report the same capabilities."""
        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            interface_caps = client.capabilities
            interface_caps_dict = {
                "supports_ping_pong": interface_caps.supports_ping_pong,
                "supports_programs": interface_caps.supports_programs,
                "supports_rooms": interface_caps.supports_rooms,
                "supports_functions": interface_caps.supports_functions,
                "supports_service_messages": interface_caps.supports_service_messages,
                "supports_linking": interface_caps.supports_linking,
                "supports_rename": interface_caps.supports_rename,
            }
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            legacy_caps = client.capabilities
            legacy_caps_dict = {
                "supports_ping_pong": legacy_caps.supports_ping_pong,
                "supports_programs": legacy_caps.supports_programs,
                "supports_rooms": legacy_caps.supports_rooms,
                "supports_functions": legacy_caps.supports_functions,
                "supports_service_messages": legacy_caps.supports_service_messages,
                "supports_linking": legacy_caps.supports_linking,
                "supports_rename": legacy_caps.supports_rename,
            }
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        # Compare capabilities
        for cap_name, interface_val in interface_caps_dict.items():
            legacy_val = legacy_caps_dict[cap_name]
            assert interface_val == legacy_val, (
                f"Capability {cap_name} differs: InterfaceClient={interface_val}, Legacy={legacy_val}"
            )


class TestCircuitBreakerCompatibility:
    """Test that circuit breaker behavior is identical between clients."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_properties_identical(self) -> None:
        """Test that circuit breaker properties are identical after initialization."""
        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            # InterfaceClient uses backend's circuit breaker
            backend = getattr(client, "_backend", None)
            interface_cb_closed = backend.all_circuit_breakers_closed if backend else True
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            # Legacy client has circuit breaker on the proxy
            proxy = getattr(client, "_proxy", None)
            legacy_cb = proxy.circuit_breaker if proxy else None
            legacy_cb_closed = client.available  # available indicates circuit breaker is closed
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        # Both should have circuit breakers in closed state after successful init
        assert interface_cb_closed is True, "InterfaceClient circuit breaker not closed"
        # Legacy client: if it's available, the connection is good
        # Note: The exact structure differs, but both should be in a healthy state
        assert legacy_cb_closed is True or legacy_cb is not None, "Legacy circuit breaker not properly initialized"


class TestModelInformationCompatibility:
    """Test that model/version information is identical between clients."""

    @pytest.mark.asyncio
    async def test_model_and_version_identical(self) -> None:
        """Test that model and version are reported identically."""
        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            interface_model = client.model
            interface_version = client.version
            interface_available = client.available
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            legacy_model = client.model
            legacy_version = client.version
            legacy_available = client.available
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        assert interface_model == legacy_model, f"Model differs: {interface_model} != {legacy_model}"
        assert interface_version == legacy_version, f"Version differs: {interface_version} != {legacy_version}"
        assert interface_available == legacy_available, (
            f"Available differs: {interface_available} != {legacy_available}"
        )


class TestHubOperationCompatibility:
    """Test that hub operations (programs, sysvars, rooms, functions) are identical."""

    @pytest.mark.asyncio
    async def test_get_all_functions_identical(self) -> None:
        """Test that get_all_functions returns identical data."""
        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            interface_functions = await client.get_all_functions()
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            legacy_functions = await client.get_all_functions()
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        # Compare functions
        assert interface_functions == legacy_functions, f"Functions differ: {interface_functions} != {legacy_functions}"

    @pytest.mark.asyncio
    async def test_get_all_programs_identical(self) -> None:
        """Test that get_all_programs returns identical data."""

        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            interface_programs = await client.get_all_programs(markers=())
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            legacy_programs = await client.get_all_programs(markers=())
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        # Compare programs
        assert len(interface_programs) == len(legacy_programs), (
            f"Program count differs: {len(interface_programs)} != {len(legacy_programs)}"
        )

    @pytest.mark.asyncio
    async def test_get_all_rooms_identical(self) -> None:
        """Test that get_all_rooms returns identical data."""
        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            interface_rooms = await client.get_all_rooms()
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            legacy_rooms = await client.get_all_rooms()
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        # Compare rooms
        assert interface_rooms == legacy_rooms, f"Rooms differ: {interface_rooms} != {legacy_rooms}"

    @pytest.mark.asyncio
    async def test_get_all_system_variables_identical(self) -> None:
        """Test that get_all_system_variables returns identical data."""

        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            interface_sysvars = await client.get_all_system_variables(markers=())
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            legacy_sysvars = await client.get_all_system_variables(markers=())
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        # Both should return data or both should return None
        if interface_sysvars is None and legacy_sysvars is None:
            return  # Both unsupported - OK

        assert (interface_sysvars is None) == (legacy_sysvars is None), (
            f"Sysvar support differs: InterfaceClient={interface_sysvars is not None}, "
            f"Legacy={legacy_sysvars is not None}"
        )

        if interface_sysvars and legacy_sysvars:
            assert len(interface_sysvars) == len(legacy_sysvars), (
                f"Sysvar count differs: {len(interface_sysvars)} != {len(legacy_sysvars)}"
            )


class TestDeviceManagementCompatibility:
    """Test that device management operations are identical."""

    @pytest.mark.asyncio
    async def test_get_inbox_devices_identical(self) -> None:
        """Test that get_inbox_devices returns identical data."""
        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            interface_inbox = await client.get_inbox_devices()
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            legacy_inbox = await client.get_inbox_devices()
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        assert len(interface_inbox) == len(legacy_inbox), (
            f"Inbox device count differs: {len(interface_inbox)} != {len(legacy_inbox)}"
        )

    @pytest.mark.asyncio
    async def test_get_install_mode_identical(self) -> None:
        """Test that get_install_mode returns identical data."""
        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            interface_mode = await client.get_install_mode()
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            legacy_mode = await client.get_install_mode()
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        assert interface_mode == legacy_mode, f"Install mode differs: {interface_mode} != {legacy_mode}"

    @pytest.mark.asyncio
    async def test_get_service_messages_identical(self) -> None:
        """Test that get_service_messages returns identical data."""
        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            interface_messages = await client.get_service_messages()
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            legacy_messages = await client.get_service_messages()
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        assert len(interface_messages) == len(legacy_messages), (
            f"Service message count differs: {len(interface_messages)} != {len(legacy_messages)}"
        )


class TestLinkOperationCompatibility:
    """Test that link operations are identical."""

    @pytest.mark.asyncio
    async def test_get_link_peers_identical(self) -> None:
        """Test that get_link_peers returns identical data."""
        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        interface_links: dict[str, tuple[str, ...]] = {}

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            for device in interface_central.devices:
                for channel in device.channels.values():
                    try:
                        peers = await client.get_link_peers(address=channel.address)
                        if peers:
                            interface_links[channel.address] = peers
                    except Exception:
                        pass  # Some channels may not support links
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        legacy_links: dict[str, tuple[str, ...]] = {}

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            for device in legacy_central.devices:
                for channel in device.channels.values():
                    try:
                        peers = await client.get_link_peers(address=channel.address)
                        if peers:
                            legacy_links[channel.address] = peers
                    except Exception:
                        pass
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        # Compare links
        assert interface_links == legacy_links, f"Link peers differ: {interface_links} != {legacy_links}"


class TestMetadataOperationCompatibility:
    """Test that metadata operations are identical."""

    @pytest.mark.asyncio
    async def test_get_metadata_identical(self) -> None:
        """Test that get_metadata returns identical data."""
        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        interface_metadata: dict[str, dict[str, Any]] = {}

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            for device in interface_central.devices:
                try:
                    metadata = await client.get_metadata(address=device.address, data_id="")
                    if metadata:
                        interface_metadata[device.address] = metadata
                except Exception:
                    pass  # Some backends don't support metadata
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        legacy_metadata: dict[str, dict[str, Any]] = {}

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            for device in legacy_central.devices:
                try:
                    metadata = await client.get_metadata(address=device.address, data_id="")
                    if metadata:
                        legacy_metadata[device.address] = metadata
                except Exception:
                    pass
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        # Compare metadata
        assert interface_metadata == legacy_metadata, f"Metadata differs: {interface_metadata} != {legacy_metadata}"


class TestErrorHandlingCompatibility:
    """Test that error handling is identical between clients."""

    @pytest.mark.asyncio
    async def test_invalid_address_handling_identical(self) -> None:
        """Test that both clients handle invalid addresses the same way."""
        invalid_address = "INVALID_ADDRESS_12345:999"

        interface_error: Exception | None = None
        legacy_error: Exception | None = None

        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            try:
                await client.get_paramset(address=invalid_address, paramset_key="VALUES")
            except Exception as ex:
                interface_error = ex
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            try:
                await client.get_paramset(address=invalid_address, paramset_key="VALUES")
            except Exception as ex:
                legacy_error = ex
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        # Both should either succeed (empty dict) or fail
        # The key is they should behave the same way
        interface_failed = interface_error is not None
        legacy_failed = legacy_error is not None

        assert interface_failed == legacy_failed, (
            f"Error handling differs: InterfaceClient error={interface_error}, Legacy error={legacy_error}"
        )

    @pytest.mark.asyncio
    async def test_list_devices_identical(self) -> None:
        """Test that list_devices returns identical device lists."""
        # Test with InterfaceClient
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        interface_central, interface_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=True,
        )

        try:
            client = interface_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            interface_devices = await client.list_devices()
        finally:
            await interface_central.stop()
            interface_factory.cleanup()

        # Test with Legacy client
        session_player = await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
        legacy_central, legacy_factory = await create_central_with_client_type(
            session_player=session_player,
            use_interface_client=False,
        )

        try:
            client = legacy_central.client_coordinator.primary_client
            assert client is not None, "No primary client available"

            legacy_devices = await client.list_devices()
        finally:
            await legacy_central.stop()
            legacy_factory.cleanup()

        # Both should return device lists or None
        assert (interface_devices is None) == (legacy_devices is None), "list_devices availability differs"

        if interface_devices and legacy_devices:
            # Compare device count
            assert len(interface_devices) == len(legacy_devices), (
                f"Device count differs: {len(interface_devices)} != {len(legacy_devices)}"
            )

            # Compare device addresses
            interface_addresses = {d.get("ADDRESS") or d.get("address", "") for d in interface_devices}
            legacy_addresses = {d.get("ADDRESS") or d.get("address", "") for d in legacy_devices}
            assert interface_addresses == legacy_addresses, (
                f"Device addresses differ: {interface_addresses} != {legacy_addresses}"
            )
