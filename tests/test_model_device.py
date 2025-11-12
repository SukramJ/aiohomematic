"""Tests for aiohomematic.model.device.Device and Channel."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from aiohomematic.const import (
    CLICK_EVENTS,
    DEVICE_DESCRIPTIONS_DIR,
    PARAMSET_DESCRIPTIONS_DIR,
    REPORT_VALUE_USAGE_VALUE_ID,
    VIRTUAL_REMOTE_MODELS,
    EventType,
    ForcedDeviceAvailability,
    ParamsetKey,
)
from aiohomematic.exceptions import AioHomematicException, BaseHomematicException
from aiohomematic_test_support import const

# Reuse existing test devices and fixtures from conftest and support

TEST_DEVICES: set[str] = {"VCU2128127", "VCU6354483"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, None, None),
    ],
)
async def test_device_general(
    central_client_factory_with_homegear_client,
) -> None:
    """Test device availability."""
    central, _, _ = central_client_factory_with_homegear_client
    device = central.get_device(address="VCU2128127")
    assert device.address == "VCU2128127"
    assert device.name == "HmIP-BSM VCU2128127"
    assert (
        str(device) == "address: VCU2128127, "
        "model: HmIP-BSM, "
        "name: HmIP-BSM VCU2128127, "
        "generic dps: 27, "
        "calculated dps: 0, "
        "custom dps: 3, "
        "events: 6"
    )
    assert device.model == "HmIP-BSM"
    assert device.interface == "BidCos-RF"
    assert device.interface_id == const.INTERFACE_ID
    assert device.has_custom_data_point_definition is True
    assert len(device.custom_data_points) == 3
    assert len(device.channels) == 11


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, None, None),
    ],
)
async def test_device_availability(
    central_client_factory_with_homegear_client,
) -> None:
    """Test device availability."""
    central, _, _ = central_client_factory_with_homegear_client
    device = central.get_device(address="VCU6354483")
    assert device.available is True
    for gdp in device.generic_data_points:
        assert gdp.available is True
    for cdp in device.custom_data_points:
        assert cdp.available is True

    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU6354483:0", parameter="UNREACH", value=1
    )
    assert device.available is False
    for gdp in device.generic_data_points:
        assert gdp.available is False
    for cdp in device.custom_data_points:
        assert cdp.available is False

    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU6354483:0", parameter="UNREACH", value=0
    )
    assert device.available is True
    for gdp in device.generic_data_points:
        assert gdp.available is True
    for cdp in device.custom_data_points:
        assert cdp.available is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, None, None),
    ],
)
async def test_device_config_pending(
    central_client_factory_with_homegear_client,
) -> None:
    """Test device availability."""
    central, _, _ = central_client_factory_with_homegear_client
    device = central.get_device(address="VCU2128127")
    assert device._dp_config_pending.value is False
    cache_hash = central.paramset_descriptions.content_hash
    last_save_triggered = central.paramset_descriptions.last_save_triggered
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU2128127:0", parameter="CONFIG_PENDING", value=True
    )
    assert device._dp_config_pending.value is True
    assert cache_hash == central.paramset_descriptions.content_hash
    assert last_save_triggered == central.paramset_descriptions.last_save_triggered
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU2128127:0", parameter="CONFIG_PENDING", value=False
    )
    assert device._dp_config_pending.value is False
    await asyncio.sleep(2)
    # Save triggered, but data not changed
    assert cache_hash == central.paramset_descriptions.content_hash
    assert last_save_triggered != central.paramset_descriptions.last_save_triggered


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [(TEST_DEVICES, True, None, None)],
)
async def test_forced_availability_and_callbacks(central_client_factory_with_homegear_client, monkeypatch) -> None:
    """
    Device.set_forced_availability toggles availability and emits dp callbacks once.

    Also covers available() branches including UNREACH and STICKY_UNREACH precedence.
    """
    central, _, _ = central_client_factory_with_homegear_client
    device = central.get_device(address="VCU6354483")

    # Ensure base availability is True
    assert device.available is True

    # Register a no-op device-updated callback to exercise registration/removal
    remove = device.register_device_updated_callback(cb=lambda: None)
    assert callable(remove)

    # set forced availability toggles and should not crash
    device.set_forced_availability(forced_availability=ForcedDeviceAvailability.FORCE_TRUE)
    device.set_forced_availability(forced_availability=ForcedDeviceAvailability.FORCE_FALSE)
    assert device.available is False

    # Reset forced availability -> availability falls back to UNREACH flags
    device.set_forced_availability(forced_availability=ForcedDeviceAvailability.NOT_SET)
    # Simulate UNREACH via event
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address=f"{device.address}:0", parameter="UNREACH", value=1
    )
    assert device.available is False
    # Clear UNREACH; stick to STICKY_UNREACH when present
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address=f"{device.address}:0", parameter="UNREACH", value=0
    )
    # STICKY_UNREACH is ignored if UNREACH datapoint exists; availability is True again
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address=f"{device.address}:0", parameter="STICKY_UNREACH", value=1
    )
    assert device.available is True

    # Clear STICKY_UNREACH
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address=f"{device.address}:0", parameter="STICKY_UNREACH", value=0
    )
    assert device.available is True

    # Unregister callback via returned remover and ensure no error
    remover = remove
    remover()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [({"VCU2128127"}, True, None, None)],
)
async def test_firmware_properties_and_refresh_callbacks(
    central_client_factory_with_homegear_client, monkeypatch
) -> None:
    """Exercise firmware properties and refresh_firmware_data triggering callbacks only on change."""
    central, _, _ = central_client_factory_with_homegear_client
    device = central.get_device(address="VCU2128127")

    # Register firmware callback
    emitted: list[int] = []

    def fw_cb() -> None:
        emitted.append(1)

    remove_fw = device.register_firmware_update_callback(cb=fw_cb)
    assert callable(remove_fw)

    # First refresh with unchanged data -> no callback
    orig_desc = dict(device._description)

    # Provide a mutable current_desc and patch method on the class to return it
    current_desc = dict(orig_desc)

    from aiohomematic.store.persistent import DeviceDescriptionCache

    def _patched_get_device_description(self, *, interface_id: str, address: str) -> dict[str, Any]:  # noqa: D401
        return dict(current_desc)

    monkeypatch.setattr(DeviceDescriptionCache, "get_device_description", _patched_get_device_description, raising=True)

    device.refresh_firmware_data()
    assert not emitted

    # Now change available firmware and state to trigger callback
    current_desc["AVAILABLE_FIRMWARE"] = "99.99"
    current_desc["FIRMWARE_UPDATE_STATE"] = 1  # any int that maps differently

    device.refresh_firmware_data()
    assert emitted

    # Duplicate registration returns None
    assert device.register_firmware_update_callback(cb=fw_cb) is None
    remove_fw()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [({"VCU2128127"}, True, None, None)],
)
async def test_create_and_remove_central_links(central_client_factory_with_homegear_client, monkeypatch) -> None:
    """Device.create/remove_central_links invoke channel logic and metadata cleanup branches."""
    central, client, _ = central_client_factory_with_homegear_client
    device = central.get_device(address="VCU2128127")

    # pick a channel that has KEYPRESS events
    ch = next(
        ch for ch in device.channels.values() if any(e.event_type is EventType.KEYPRESS for e in ch.generic_events)
    )

    # Spy for report_value_usage
    reported: list[tuple[str, int]] = []

    async def report_value_usage(*, address: str, value_id: str, ref_counter: int) -> None:
        reported.append((address, ref_counter))

    monkeypatch.setattr(client, "report_value_usage", report_value_usage)

    # 1) create_central_link should call client when no existing central link
    async def get_metadata_none(*, address: str, data_id: str):  # noqa: D401
        return {"something": 0}

    monkeypatch.setattr(client, "get_metadata", get_metadata_none)
    await ch.create_central_link()
    assert (ch.address, 1) in reported

    # 2) _has_central_link returns True if metadata says so
    async def get_metadata_true(*, address: str, data_id: str):  # noqa: D401
        return {REPORT_VALUE_USAGE_VALUE_ID: 1}

    monkeypatch.setattr(client, "get_metadata", get_metadata_true)
    assert await ch._has_central_link() is True

    # 3) remove_central_link removes only if has central link and no program ids
    async def has_program_ids_false(*, channel_hmid: str):  # noqa: D401
        return False

    monkeypatch.setattr(client, "has_program_ids", has_program_ids_false)
    await ch.remove_central_link()
    assert (ch.address, 0) in reported

    # 4) _has_central_link handles backend exception gracefully
    async def get_metadata_raises(*, address: str, data_id: str):  # noqa: D401
        raise BaseHomematicException("fail")

    monkeypatch.setattr(client, "get_metadata", get_metadata_raises)
    assert await ch._has_central_link() is False

    # 5) _has_program_ids truthy path
    async def has_program_ids_true(*, channel_hmid: str):  # noqa: D401
        return ["1"]

    monkeypatch.setattr(client, "has_program_ids", has_program_ids_true)
    assert await ch._has_program_ids() is True

    # 6) cleanup_central_link_metadata filters non-click keys
    called_set: dict[str, Any] = {"value": None}

    async def get_metadata_with_noise(*, address: str, data_id: str):  # noqa: D401
        noisy = {"noise": 123, REPORT_VALUE_USAGE_VALUE_ID: 2}
        # add one valid click event key
        if CLICK_EVENTS:
            first = next(iter(CLICK_EVENTS), None)
            if first is not None:
                noisy[first] = 1
        return noisy

    async def set_metadata(*, address: str, data_id: str, value: dict[str, Any]):  # noqa: D401
        called_set["value"] = value

    monkeypatch.setattr(client, "get_metadata", get_metadata_with_noise)
    monkeypatch.setattr(client, "set_metadata", set_metadata)
    await ch.cleanup_central_link_metadata()
    assert called_set["value"] is not None
    assert all(k in CLICK_EVENTS for k in called_set["value"])  # SIM118-compliant

    # Final: device-level iterators call channel paths
    reported.clear()
    await device.create_central_links()
    await device.remove_central_links()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [({"VCU2128127"}, True, None, None)],
)
async def test_identify_channel_and_grouping(central_client_factory_with_homegear_client) -> None:
    """Exercise identify_channel variants and grouping helpers."""
    central, _, _ = central_client_factory_with_homegear_client
    device = central.get_device(address="VCU2128127")

    # Take a non-base channel
    ch = next(ch for addr, ch in device.channels.items() if addr.endswith(":1"))

    # Identify by suffixing address
    assert device.identify_channel(text=f"foo {ch.address}") is ch
    # Identify by channel id in text - ensure a channel is returned and belongs to same device
    ch_by_id = device.identify_channel(text=f"id={ch.id}")
    assert ch_by_id is not None and ch_by_id.device is device
    # Identify by device id in text - first channel of device is a valid match
    ch_by_dev_id = device.identify_channel(text=f"device={ch.device.id}")
    assert ch_by_dev_id is not None and ch_by_dev_id.device is device
    # No match
    assert device.identify_channel(text="no-match") is None

    # Grouping helpers
    device.add_channel_to_group(group_no=1, channel_no=1)
    device.add_channel_to_group(group_no=1, channel_no=2)
    device.add_channel_to_group(group_no=2, channel_no=3)
    assert device.get_channel_group_no(channel_no=1) == 1
    assert device.is_in_multi_channel_group(channel_no=1) is True
    assert device.is_in_multi_channel_group(channel_no=None) is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [({"VCU2128127"}, True, None, None)],
)
async def test_getters_filters_and_reload(central_client_factory_with_homegear_client, monkeypatch) -> None:
    """Cover getters with filters, not-found lookups, load_value_cache and reload_paramset_descriptions."""
    central, client, _ = central_client_factory_with_homegear_client
    device = central.get_device(address="VCU2128127")

    # Not found lookups
    assert device.get_generic_event(channel_address=f"{device.address}:99", parameter="X") is None
    assert (
        device.get_generic_data_point(channel_address=f"{device.address}:99", parameter="Y", paramset_key=None) is None
    )

    # Readable dps and filters
    readable = device.get_readable_data_points(paramset_key=ParamsetKey.MASTER)
    assert isinstance(readable, tuple)

    # get_data_points/get_events via channel delegation (just ensure it does not crash)
    all_dps = device.get_data_points()
    all_events = device.get_events(event_type=EventType.KEYPRESS)
    assert isinstance(all_dps, tuple)
    assert isinstance(all_events, dict)

    # load value cache initializes lazily
    await device.load_value_cache()

    # reload paramset descriptions triggers client/central calls and dp updates
    called: dict[str, int] = {"fetch": 0, "save": 0}

    async def fake_fetch_paramset_description(*, channel_address: str, paramset_key: ParamsetKey) -> None:
        called["fetch"] += 1

    async def fake_save_files(*, save_paramset_descriptions: bool) -> None:
        called["save"] += 1

    monkeypatch.setattr(client, "fetch_paramset_description", fake_fetch_paramset_description)
    monkeypatch.setattr(central, "save_files", fake_save_files)
    await device.on_config_changed()
    assert called["fetch"] > 0 and called["save"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [({"VCU2128127"}, True, None, None)],
)
async def test_update_firmware_scheduling_and_return(central_client_factory_with_homegear_client, monkeypatch) -> None:
    """update_firmware returns client result and schedules refresh task when intervals provided."""
    central, client, _ = central_client_factory_with_homegear_client
    device = central.get_device(address="VCU2128127")

    async def upd(*, device_address: str) -> bool:  # noqa: D401
        return True

    monkeypatch.setattr(client, "update_device_firmware", upd)

    created: list[str] = []

    def create_task(*, target: Any, name: str) -> None:  # noqa: D401
        created.append(name)

    monkeypatch.setattr(central.looper, "create_task", create_task)

    ok = await device.update_firmware(refresh_after_update_intervals=(0,))
    assert ok is True and created == ["refresh_firmware_data"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [({"VCU2128127"}, True, None, None)],
)
async def test_export_device_definition_and_str(
    central_client_factory_with_homegear_client, tmp_path, monkeypatch
) -> None:
    """export_device_definition writes files; __str__ returns info string; exceptions are wrapped."""
    central, _, _ = central_client_factory_with_homegear_client
    device = central.get_device(address="VCU2128127")

    # Ensure export goes to temp storage by patching central.config.storage_directory
    monkeypatch.setattr(device.client.central.config, "storage_directory", str(tmp_path))

    await device.export_device_definition()

    # Expect the two export directories to exist and contain at least one file
    dev_dir = tmp_path / DEVICE_DESCRIPTIONS_DIR
    par_dir = tmp_path / PARAMSET_DESCRIPTIONS_DIR
    assert dev_dir.exists() and par_dir.exists()
    assert any(dev_dir.iterdir()) and any(par_dir.iterdir())

    # Force an exception path by patching exporter to raise inside export
    from aiohomematic.model import device as device_module

    class Boom(Exception):
        pass

    class ExplodingExporter(device_module._DefinitionExporter):  # type: ignore[attr-defined]
        async def export_data(self) -> None:  # type: ignore[override]
            raise Boom("boom")

    monkeypatch.setattr(device_module, "_DefinitionExporter", ExplodingExporter)
    with pytest.raises(AioHomematicException):
        await device.export_device_definition()

    # __str__ contains counts
    s = str(device)
    assert "address:" in s and "generic dps:" in s and "events:" in s


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [({"VCU2128127"}, True, None, None)],
)
async def test_misc_properties_and_caching(central_client_factory_with_homegear_client, monkeypatch) -> None:
    """Cover various Device/Channel simple properties and error paths to increase coverage."""
    central, _, _ = central_client_factory_with_homegear_client
    device = central.get_device(address="VCU2128127")

    # Simple info properties
    assert device.identifier.endswith(device.interface_id)
    assert device.ignore_on_initial_load in (True, False)
    assert str(device.interface)
    assert device.available_firmware is not None
    assert isinstance(device.firmware_updatable, bool)

    # has_sub_devices: create two groups with >1 members to become True
    device.add_channel_to_group(group_no=10, channel_no=1)
    device.add_channel_to_group(group_no=10, channel_no=2)
    device.add_channel_to_group(group_no=11, channel_no=3)
    device.add_channel_to_group(group_no=11, channel_no=4)
    assert device.has_sub_devices is True

    # relevant_for_central_link_management false path by forcing virtual model
    # Use the same device to avoid relying on an unavailable second device in this parametrization
    target = device
    if VIRTUAL_REMOTE_MODELS:
        monkeypatch.setattr(target, "_model", next(iter(VIRTUAL_REMOTE_MODELS)))
    assert target.relevant_for_central_link_management is False
    await target.create_central_links()
    await target.remove_central_links()

    # get_custom_data_point for an existing custom channel, if present
    if device.custom_data_points:
        ch_no = next(int(addr.split(":")[1]) for addr, ch in device.channels.items() if ch.custom_data_point)
        assert device.get_custom_data_point(channel_no=ch_no) is not None

    # emit_device_updated_callback handles exception in handler
    def exploding() -> None:
        raise RuntimeError("boom")

    device.register_device_updated_callback(cb=exploding)
    device.emit_device_updated_callback()

    # Channel operation_mode when dp present vs None
    ch = next(iter(device.channels.values()))

    # Patch get_generic_data_point to simulate a value
    class _X:
        value = "AUTO"

    from aiohomematic.const import Parameter
    from aiohomematic.model.device import Channel

    orig = Channel.get_generic_data_point

    def fake_get(self, *, parameter: str, paramset_key=None):  # type: ignore[no-untyped-def]
        if self is ch and parameter == Parameter.CHANNEL_OPERATION_MODE:
            return _X()
        return orig(self, parameter=parameter, paramset_key=paramset_key)

    monkeypatch.setattr(Channel, "get_generic_data_point", fake_get)
    assert ch.operation_mode == "AUTO"

    # access paramset descriptions mapping and unique id
    _ = ch.paramset_descriptions
    _ = ch.unique_id

    # _DefinitionExporter._anonymize_address
    from aiohomematic.model.device import _DefinitionExporter as Exporter  # type: ignore[attr-defined]

    exp = Exporter(device=device)
    anon = exp._anonymize_address(address=f"{device.address}:1")  # type: ignore[attr-defined]
    assert anon.split(":")[0] != device.address.split(":")[0]
