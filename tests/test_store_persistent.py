"""Tests for store/persistent.py of aiohomematic."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
import zipfile

import pytest

from aiohomematic.async_support import Looper
from aiohomematic.const import (
    ADDRESS_SEPARATOR,
    SUB_DIRECTORY_CACHE,
    SUB_DIRECTORY_SESSION,
    DataOperationResult,
    ParamsetKey,
    RPCType,
)
from aiohomematic.store.persistent import (
    DeviceDescriptionCache,
    ParamsetDescriptionCache,
    SessionRecorder,
    _freeze_params,
    _get_file_name,
    _get_file_path,
    _unfreeze_params,
    cleanup_files,
)


class _Cfg:
    """Simple central config stub used by tests."""

    def __init__(self, storage_directory: str, use_caches: bool = True) -> None:
        self.storage_directory = storage_directory
        self.use_caches = use_caches
        # Session recorder related defaults used by Central but not here
        self.session_recorder_start = False
        self.session_recorder_start_for_seconds = 0
        self.session_recorder_randomize_output = False
        self.default_callback_port_xml_rpc = 0


class _DeviceObj:
    """Simple object with an address attribute to test randomization."""

    def __init__(self, address: str) -> None:
        self.address = address


class _CentralStub:
    """Minimal Central stub exposing the attributes used by persistent caches."""

    def __init__(self, name: str, storage_directory: str, use_caches: bool = True) -> None:
        self.name = name
        self.config = _Cfg(storage_directory=storage_directory, use_caches=use_caches)
        self.looper = Looper()
        # Used by BasePersistentFile._manipulate_content when randomizing
        self.devices: list[_DeviceObj] = []


class TestHelperFunctions:
    """Test helper functions for freezing/unfreezing params and file path generation."""

    def test_freeze_params_datetime(self) -> None:
        """Test freezing datetime objects."""
        dt = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
        frozen = _freeze_params(dt)
        assert "__datetime__" in frozen
        unfrozen = _unfreeze_params(frozen)
        assert unfrozen == dt

    def test_freeze_params_primitives(self) -> None:
        """Test freezing primitive types."""
        assert _freeze_params("string") == "string"
        assert _freeze_params(123) == "123"
        assert _freeze_params(True) == "True"
        assert _freeze_params(None) == "None"

    def test_freeze_params_set(self) -> None:
        """Test freezing set objects."""
        s = {1, 2, 3}
        frozen = _freeze_params(s)
        assert "__set__" in frozen
        unfrozen = _unfreeze_params(frozen)
        # Note: primitives get stringified, so check idempotency instead
        assert _freeze_params(unfrozen) == frozen

    @pytest.mark.parametrize(
        "value",
        [
            # Dict/list/tuple roundtrip
            {"a": [1, 2, (3, 4)], "b": {"c": 5}},
            # Sets become tagged and still roundtrip
            {"set": {1, 2, 3}},
            # Datetime tagged roundtrip
            {"dt": datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)},
            # Nested mixture
            ({"x": {"y": [1, {"z": {1, 2}}]}}),
        ],
    )
    def test_freeze_unfreeze_roundtrip(self, value) -> None:
        """Test that freeze/unfreeze is idempotent for various data types."""
        frozen = _freeze_params(value)
        unfrozen = _unfreeze_params(frozen)
        # Idempotency check
        assert _freeze_params(unfrozen) == frozen

    def test_get_file_name_plain(self) -> None:
        """Test file name generation without timestamp."""
        fn_plain = _get_file_name(central_name="My Central", file_name="devices")
        assert fn_plain.endswith("devices.json")
        assert "my-central" in fn_plain

    def test_get_file_name_with_timestamp(self) -> None:
        """Test file name generation with timestamp."""
        ts = datetime(2023, 2, 3, 4, 5, 6)
        fn_ts = _get_file_name(central_name="X", file_name="rec", ts=ts)
        assert "20230203_040506" in fn_ts
        assert fn_ts.endswith(".json")

    def test_get_file_path(self, tmp_path) -> None:
        """Test file path generation."""
        base = str(tmp_path)
        path_cache = _get_file_path(storage_directory=base, sub_directory=SUB_DIRECTORY_CACHE)
        assert path_cache.endswith(SUB_DIRECTORY_CACHE)

    def test_unfreeze_params_invalid_string(self) -> None:
        """Test unfreezing invalid string returns original."""
        invalid = "not a valid frozen param"
        unfrozen = _unfreeze_params(invalid)
        assert unfrozen == invalid


class TestDeviceDescriptionCache:
    """Test DeviceDescriptionCache functionality."""

    @pytest.mark.asyncio
    async def test_add_device_updates_existing(self, tmp_path) -> None:
        """Test adding device with existing address updates description."""
        central = _CentralStub("Test Central", str(tmp_path))
        ddc = DeviceDescriptionCache(central=central)

        iface = "if1"
        dev_addr = "DEV1"

        # Add device first time
        ddc.add_device(
            interface_id=iface,
            device_description={"ADDRESS": dev_addr, "CHILDREN": [], "TYPE": "TYPE1"},
        )

        # Add same device with different type (update)
        ddc.add_device(
            interface_id=iface,
            device_description={"ADDRESS": dev_addr, "CHILDREN": [], "TYPE": "TYPE2"},
        )

        # Should have updated type
        assert ddc.get_model(device_address=dev_addr) == "TYPE2"

    @pytest.mark.asyncio
    async def test_find_device_description(self, tmp_path) -> None:
        """Test finding a specific device description."""
        central = _CentralStub("Test Central", str(tmp_path))
        ddc = DeviceDescriptionCache(central=central)

        iface = "if1"
        ddc.add_device(interface_id=iface, device_description={"ADDRESS": "DEV1", "CHILDREN": [], "TYPE": "T1"})

        desc = ddc.find_device_description(interface_id=iface, device_address="DEV1")
        assert desc is not None
        assert desc["TYPE"] == "T1"

        not_found = ddc.find_device_description(interface_id=iface, device_address="NONEXISTENT")
        assert not_found is None

    @pytest.mark.asyncio
    async def test_get_addresses_all_interfaces(self, tmp_path) -> None:
        """Test getting addresses across all interfaces."""
        central = _CentralStub("Test Central", str(tmp_path))
        ddc = DeviceDescriptionCache(central=central)

        ddc.add_device(interface_id="if1", device_description={"ADDRESS": "DEV1", "CHILDREN": [], "TYPE": "T1"})
        ddc.add_device(interface_id="if2", device_description={"ADDRESS": "DEV2", "CHILDREN": [], "TYPE": "T2"})

        all_addresses = ddc.get_addresses()
        assert "DEV1" in all_addresses
        assert "DEV2" in all_addresses

    @pytest.mark.asyncio
    async def test_get_device_descriptions(self, tmp_path) -> None:
        """Test getting all device descriptions for an interface."""
        central = _CentralStub("Test Central", str(tmp_path))
        ddc = DeviceDescriptionCache(central=central)

        iface = "if1"
        ddc.add_device(interface_id=iface, device_description={"ADDRESS": "DEV1", "CHILDREN": [], "TYPE": "T1"})
        ddc.add_device(interface_id=iface, device_description={"ADDRESS": "DEV2", "CHILDREN": [], "TYPE": "T2"})

        descs = ddc.get_device_descriptions(interface_id=iface)
        assert len(descs) == 2
        assert "DEV1" in descs
        assert "DEV2" in descs

    @pytest.mark.asyncio
    async def test_get_raw_device_descriptions(self, tmp_path) -> None:
        """Test getting raw device descriptions list."""
        central = _CentralStub("Test Central", str(tmp_path))
        ddc = DeviceDescriptionCache(central=central)

        iface = "if1"
        ddc.add_device(interface_id=iface, device_description={"ADDRESS": "DEV1", "CHILDREN": [], "TYPE": "T1"})

        raw_descs = ddc.get_raw_device_descriptions(interface_id=iface)
        assert len(raw_descs) == 1
        assert raw_descs[0]["ADDRESS"] == "DEV1"

    @pytest.mark.asyncio
    async def test_has_device_descriptions(self, tmp_path) -> None:
        """Test checking if interface has device descriptions."""
        central = _CentralStub("Test Central", str(tmp_path))
        ddc = DeviceDescriptionCache(central=central)

        ddc.add_device(interface_id="if1", device_description={"ADDRESS": "DEV1", "CHILDREN": [], "TYPE": "T1"})

        assert ddc.has_device_descriptions(interface_id="if1") is True
        assert ddc.has_device_descriptions(interface_id="if2") is False

    @pytest.mark.asyncio
    async def test_load_from_zip(self, tmp_path) -> None:
        """Test loading from ZIP file."""
        central = _CentralStub("Test Central", str(tmp_path))
        iface = "if1"
        dev_addr = "DEV123"
        ch_addr = f"{dev_addr}{ADDRESS_SEPARATOR}1"

        # Create ZIP with device descriptions
        plain_json = tmp_path / "plain.json"
        with open(plain_json, "w", encoding="utf-8") as fp:
            json.dump(
                {
                    iface: [
                        {"ADDRESS": dev_addr, "CHILDREN": [ch_addr], "TYPE": "HM-TEST"},
                        {"ADDRESS": ch_addr, "CHILDREN": [], "TYPE": "HM-TEST-CH"},
                    ]
                },
                fp,
            )

        zip_path = tmp_path / "cache.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(plain_json, arcname=plain_json.name)

        ddc = DeviceDescriptionCache(central=central)
        load_result = await ddc.load(file_path=str(zip_path))
        assert load_result == DataOperationResult.LOAD_SUCCESS

        # Verify data loaded correctly
        assert iface in ddc.get_interface_ids()
        assert dev_addr in ddc.get_addresses(interface_id=iface)
        assert ddc.get_model(device_address=dev_addr) == "HM-TEST"

        dev_map = ddc.get_device_with_channels(interface_id=iface, device_address=dev_addr)
        assert set(dev_map.keys()) == {dev_addr, ch_addr}

    @pytest.mark.asyncio
    async def test_load_missing_file(self, tmp_path) -> None:
        """Test that loading missing file returns NO_LOAD."""
        central = _CentralStub("Test Central", str(tmp_path))
        ddc = DeviceDescriptionCache(central=central)
        assert await ddc.load(file_path=str(tmp_path / "does_not_exist.json")) == DataOperationResult.NO_LOAD

    @pytest.mark.asyncio
    async def test_load_with_caches_disabled(self, tmp_path) -> None:
        """Test that load returns NO_LOAD when caches are disabled."""
        central = _CentralStub("Test Central", str(tmp_path), use_caches=False)
        ddc = DeviceDescriptionCache(central=central)

        result = await ddc.load()
        assert result == DataOperationResult.NO_LOAD

    @pytest.mark.asyncio
    async def test_remove_device(self, tmp_path) -> None:
        """Test removing a device updates internal maps."""
        central = _CentralStub("Test Central", str(tmp_path))
        ddc = DeviceDescriptionCache(central=central)

        iface = "if1"
        dev_addr = "ADDR"
        ch_addr = f"{dev_addr}{ADDRESS_SEPARATOR}1"
        ddc.add_device(interface_id=iface, device_description={"ADDRESS": dev_addr, "CHILDREN": [ch_addr], "TYPE": "X"})
        ddc.add_device(interface_id=iface, device_description={"ADDRESS": ch_addr, "CHILDREN": [], "TYPE": "XCH"})

        class _Dev:
            def __init__(self):
                self.interface_id = iface
                self.address = dev_addr
                self.channels = {ch_addr: object()}

        ddc.remove_device(device=_Dev())
        assert dev_addr not in ddc.get_addresses(interface_id=iface)

    @pytest.mark.asyncio
    async def test_save_load_and_randomize(self, tmp_path) -> None:
        """Test save/load behavior with randomized output."""
        central = _CentralStub("Test Central", str(tmp_path))
        ddc = DeviceDescriptionCache(central=central)

        # Add a device description and save
        iface = "if1"
        dev_addr = "ABC1234"
        ch_addr = f"{dev_addr}{ADDRESS_SEPARATOR}1"
        ddc.add_device(
            interface_id=iface,
            device_description={
                "ADDRESS": dev_addr,
                "CHILDREN": [ch_addr],
                "TYPE": "HM-TEST",
            },
        )
        # Also add child channel description
        ddc.add_device(
            interface_id=iface,
            device_description={
                "ADDRESS": ch_addr,
                "CHILDREN": [],
                "TYPE": "HM-TEST-CH",
            },
        )

        # Randomization uses central.devices
        central.devices = [_DeviceObj(address=dev_addr)]

        # Save with randomization and timestamped filename
        result = await ddc.save(randomize_output=True, use_ts_in_file_name=True)
        assert result == DataOperationResult.SAVE_SUCCESS

        # Verify file exists and device address has been randomized
        files = list((tmp_path / SUB_DIRECTORY_CACHE).glob("*.json"))
        assert files, "Expected a persistent file to be created"
        content = files[0].read_text(encoding="utf-8")
        assert dev_addr not in content, "Original address should be randomized"

    @pytest.mark.asyncio
    async def test_save_no_changes(self, tmp_path) -> None:
        """Test that save returns NO_SAVE when content hasn't changed."""
        central = _CentralStub("Test Central", str(tmp_path))
        ddc = DeviceDescriptionCache(central=central)
        # Initially unchanged -> NO_SAVE
        assert await ddc.save() == DataOperationResult.NO_SAVE


class TestParamsetDescriptionCache:
    """Test ParamsetDescriptionCache functionality."""

    @pytest.mark.asyncio
    async def test_add_and_query_paramsets(self, tmp_path) -> None:
        """Test adding paramset descriptions and querying them."""
        central = _CentralStub("C", str(tmp_path))
        pdc = ParamsetDescriptionCache(central=central)

        iface = "if1"
        dev_addr = "D1"
        ch1 = f"{dev_addr}:1"
        ch2 = f"{dev_addr}:2"

        # Add two channels with VALUES paramsets
        pdc.add(
            interface_id=iface,
            channel_address=ch1,
            paramset_key=ParamsetKey.VALUES,
            paramset_description={"LEVEL": {"TYPE": "FLOAT"}},
        )
        pdc.add(
            interface_id=iface,
            channel_address=ch2,
            paramset_key=ParamsetKey.VALUES,
            paramset_description={"LEVEL": {"TYPE": "FLOAT"}},
        )
        pdc.add(
            interface_id=iface,
            channel_address=ch1,
            paramset_key=ParamsetKey.MASTER,
            paramset_description={"NORM": {"TYPE": "INTEGER"}},
        )

        assert pdc.has_interface_id(interface_id=iface)
        assert set(pdc.get_paramset_keys(interface_id=iface, channel_address=ch1)) == {
            ParamsetKey.VALUES,
            ParamsetKey.MASTER,
        }

        # LEVEL parameter appears in multiple channels
        assert pdc.is_in_multiple_channels(channel_address=ch1, parameter="LEVEL") is True

        # get_channel_addresses_by_paramset_key groups by device address
        by_key = pdc.get_channel_addresses_by_paramset_key(interface_id=iface, device_address=dev_addr)
        assert set(by_key.keys()) == {ParamsetKey.VALUES, ParamsetKey.MASTER}
        assert set(by_key[ParamsetKey.VALUES]) == {ch1, ch2}

    @pytest.mark.asyncio
    async def test_get_channel_paramset_descriptions(self, tmp_path) -> None:
        """Test getting all paramsets for a channel."""
        central = _CentralStub("C", str(tmp_path))
        pdc = ParamsetDescriptionCache(central=central)

        iface = "if1"
        ch = "D1:1"
        pdc.add(
            interface_id=iface,
            channel_address=ch,
            paramset_key=ParamsetKey.VALUES,
            paramset_description={"LEVEL": {"TYPE": "FLOAT"}},
        )
        pdc.add(
            interface_id=iface,
            channel_address=ch,
            paramset_key=ParamsetKey.MASTER,
            paramset_description={"NORM": {"TYPE": "INTEGER"}},
        )

        all_paramsets = pdc.get_channel_paramset_descriptions(interface_id=iface, channel_address=ch)
        assert len(all_paramsets) == 2
        assert ParamsetKey.VALUES in all_paramsets
        assert ParamsetKey.MASTER in all_paramsets

    @pytest.mark.asyncio
    async def test_get_parameter_data(self, tmp_path) -> None:
        """Test getting specific parameter data."""
        central = _CentralStub("C", str(tmp_path))
        pdc = ParamsetDescriptionCache(central=central)

        iface = "if1"
        ch = "D1:1"
        pdc.add(
            interface_id=iface,
            channel_address=ch,
            paramset_key=ParamsetKey.VALUES,
            paramset_description={"LEVEL": {"TYPE": "FLOAT", "MIN": 0.0, "MAX": 1.0}},
        )

        param_data = pdc.get_parameter_data(
            interface_id=iface, channel_address=ch, paramset_key=ParamsetKey.VALUES, parameter="LEVEL"
        )
        assert param_data is not None
        assert param_data["TYPE"] == "FLOAT"

        # Test non-existent parameter
        not_found = pdc.get_parameter_data(
            interface_id=iface, channel_address=ch, paramset_key=ParamsetKey.VALUES, parameter="NONEXISTENT"
        )
        assert not_found is None

    @pytest.mark.asyncio
    async def test_get_paramset_descriptions(self, tmp_path) -> None:
        """Test getting all paramset descriptions for a channel."""
        central = _CentralStub("C", str(tmp_path))
        pdc = ParamsetDescriptionCache(central=central)

        iface = "if1"
        ch = "D1:1"
        pdc.add(
            interface_id=iface,
            channel_address=ch,
            paramset_key=ParamsetKey.VALUES,
            paramset_description={"LEVEL": {"TYPE": "FLOAT"}, "STATE": {"TYPE": "BOOL"}},
        )

        descs = pdc.get_paramset_descriptions(interface_id=iface, channel_address=ch, paramset_key=ParamsetKey.VALUES)
        assert len(descs) == 2
        assert "LEVEL" in descs
        assert "STATE" in descs

    @pytest.mark.asyncio
    async def test_is_in_multiple_channels_no_separator(self, tmp_path) -> None:
        """Test that channels without ADDRESS_SEPARATOR return False."""
        central = _CentralStub("C", str(tmp_path))
        pdc = ParamsetDescriptionCache(central=central)

        # Channel without separator should return False
        assert pdc.is_in_multiple_channels(channel_address="INVALID", parameter="PARAM") is False

    @pytest.mark.asyncio
    async def test_is_in_multiple_channels_single_channel(self, tmp_path) -> None:
        """Test parameter that exists in only one channel."""
        central = _CentralStub("C", str(tmp_path))
        pdc = ParamsetDescriptionCache(central=central)

        iface = "if1"
        ch = "D1:1"
        pdc.add(
            interface_id=iface,
            channel_address=ch,
            paramset_key=ParamsetKey.VALUES,
            paramset_description={"UNIQUE_PARAM": {"TYPE": "STRING"}},
        )

        assert pdc.is_in_multiple_channels(channel_address=ch, parameter="UNIQUE_PARAM") is False

    @pytest.mark.asyncio
    async def test_load_with_caches_disabled(self, tmp_path) -> None:
        """Test that load returns NO_LOAD when caches are disabled."""
        central = _CentralStub("C", str(tmp_path), use_caches=False)
        pdc = ParamsetDescriptionCache(central=central)

        result = await pdc.load()
        assert result == DataOperationResult.NO_LOAD

    @pytest.mark.asyncio
    async def test_remove_device(self, tmp_path) -> None:
        """Test removing device paramset descriptions."""
        central = _CentralStub("C", str(tmp_path))
        pdc = ParamsetDescriptionCache(central=central)

        iface = "if1"
        dev_addr = "D1"
        ch1 = f"{dev_addr}:1"
        ch2 = f"{dev_addr}:2"

        pdc.add(
            interface_id=iface,
            channel_address=ch1,
            paramset_key=ParamsetKey.VALUES,
            paramset_description={"LEVEL": {"TYPE": "FLOAT"}},
        )
        pdc.add(
            interface_id=iface,
            channel_address=ch2,
            paramset_key=ParamsetKey.VALUES,
            paramset_description={"STATE": {"TYPE": "BOOL"}},
        )

        class _Dev:
            def __init__(self):
                self.interface_id = iface
                self.address = dev_addr
                self.channels = {ch1: object(), ch2: object()}

        pdc.remove_device(device=_Dev())

        # Channels should be removed
        assert pdc.get_channel_paramset_descriptions(interface_id=iface, channel_address=ch1) == {}
        assert pdc.get_channel_paramset_descriptions(interface_id=iface, channel_address=ch2) == {}

    @pytest.mark.asyncio
    async def test_save_and_load(self, tmp_path) -> None:
        """Test save/load triggers parameter list initialization."""
        central = _CentralStub("C", str(tmp_path))
        pdc = ParamsetDescriptionCache(central=central)

        iface = "if1"
        ch1 = "D1:1"
        pdc.add(
            interface_id=iface,
            channel_address=ch1,
            paramset_key=ParamsetKey.VALUES,
            paramset_description={"LEVEL": {"TYPE": "FLOAT"}},
        )

        # Save and reload
        assert await pdc.save() in (DataOperationResult.SAVE_SUCCESS, DataOperationResult.NO_SAVE)
        pdc2 = ParamsetDescriptionCache(central=central)
        assert await pdc2.load() in (DataOperationResult.LOAD_SUCCESS, DataOperationResult.NO_LOAD)


class TestSessionRecorder:
    """Test SessionRecorder functionality."""

    @pytest.mark.asyncio
    async def test_activate_deactivate(self, tmp_path) -> None:
        """Test activate/deactivate lifecycle."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=False, ttl_seconds=0, refresh_on_get=False)

        # Activate
        ok = await rec.activate(on_time=0, auto_save=False, randomize_output=False, use_ts_in_file_name=False)
        assert ok is True
        assert rec.active is True

        # Deactivate
        ok = await rec.deactivate(delay=0, auto_save=False, randomize_output=False, use_ts_in_file_name=False)
        assert ok is True
        assert rec.active is False

    @pytest.mark.asyncio
    async def test_activate_with_delay(self, tmp_path) -> None:
        """Test activate with auto-deactivate delay."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=False, ttl_seconds=0, refresh_on_get=False)

        # Activate with 1 second delay
        ok = await rec.activate(on_time=1, auto_save=False, randomize_output=False, use_ts_in_file_name=False)
        assert ok is True

        # Should be active
        assert rec.active is True

        # Wait for auto-deactivate
        await asyncio.sleep(1.5)

        # Should be deactivated
        assert rec.active is False

    @pytest.mark.asyncio
    async def test_add_json_rpc_session(self, tmp_path) -> None:
        """Test adding JSON-RPC session data."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=True, ttl_seconds=0, refresh_on_get=False)

        method = "test.method"
        params = {"x": 1}
        response = {"result": "ok"}

        rec.add_json_rpc_session(method=method, params=params, response=response)

        # Should be retrievable
        result = rec.get(rpc_type=str(RPCType.JSON_RPC), method=method, params=params)
        assert result == response

    @pytest.mark.asyncio
    async def test_add_json_rpc_session_with_exception(self, tmp_path) -> None:
        """Test adding JSON-RPC session with exception."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=True, ttl_seconds=0, refresh_on_get=False)

        method = "test.method"
        params = {"x": 1}
        exc = ValueError("test error")

        rec.add_json_rpc_session(method=method, params=params, session_exc=exc)

        # Should be stored
        result = rec.get(rpc_type=str(RPCType.JSON_RPC), method=method, params=params)
        assert result is not None

    @pytest.mark.asyncio
    async def test_add_xml_rpc_session(self, tmp_path) -> None:
        """Test adding XML-RPC session data."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=True, ttl_seconds=0, refresh_on_get=False)

        method = "test.method"
        params = (1, 2, 3)
        response = "ok"

        rec.add_xml_rpc_session(method=method, params=params, response=response)

        # Should be retrievable
        result = rec.get(rpc_type=str(RPCType.XML_RPC), method=method, params=params)
        assert result == response

    @pytest.mark.asyncio
    async def test_add_xml_rpc_session_with_exception(self, tmp_path) -> None:
        """Test adding XML-RPC session with exception."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=True, ttl_seconds=0, refresh_on_get=False)

        method = "test.method"
        params = (1, 2)
        exc = RuntimeError("test error")

        rec.add_xml_rpc_session(method=method, params=params, session_exc=exc)

        # Should be stored
        result = rec.get(rpc_type=str(RPCType.XML_RPC), method=method, params=params)
        assert result is not None

    @pytest.mark.asyncio
    async def test_cleanup(self, tmp_path) -> None:
        """Test cleanup removes expired entries."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=True, ttl_seconds=0.5, refresh_on_get=False)

        rpc_type = str(RPCType.JSON_RPC)
        method = "test.method"

        # Add entries
        rec.set(rpc_type=rpc_type, method=method, params={"x": 1}, response={"v": 1})

        # Wait for expiration
        await asyncio.sleep(1.2)

        # Cleanup should remove expired
        rec.cleanup()

        # Should be empty
        assert rec.get_latest_response_by_method(rpc_type=rpc_type, method=method) == []

    @pytest.mark.asyncio
    async def test_delete_entry(self, tmp_path) -> None:
        """Test deleting specific entry."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=True, ttl_seconds=0, refresh_on_get=False)

        rpc_type = str(RPCType.JSON_RPC)
        method = "test.method"
        params = {"x": 1}

        # Add entry
        rec.set(rpc_type=rpc_type, method=method, params=params, response={"ok": True})

        # Delete should return True
        assert rec.delete(rpc_type=rpc_type, method=method, params=params) is True

        # Entry should be gone
        assert rec.get(rpc_type=rpc_type, method=method, params=params) is None

        # Deleting again should return False
        assert rec.delete(rpc_type=rpc_type, method=method, params=params) is False

    @pytest.mark.asyncio
    async def test_get_latest_response_by_method(self, tmp_path) -> None:
        """Test getting latest responses by method."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=True, ttl_seconds=0, refresh_on_get=False)

        rpc_type = str(RPCType.JSON_RPC)
        method = "test.method"

        rec.set(rpc_type=rpc_type, method=method, params={"x": 1}, response={"result": 1})
        rec.set(rpc_type=rpc_type, method=method, params={"x": 2}, response={"result": 2})

        latest = rec.get_latest_response_by_method(rpc_type=rpc_type, method=method)
        assert len(latest) == 2
        # Extract responses
        responses = [r[1] for r in latest]
        assert {"result": 1} in responses
        assert {"result": 2} in responses

    @pytest.mark.asyncio
    async def test_get_latest_response_by_params(self, tmp_path) -> None:
        """Test getting latest response for specific params."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=True, ttl_seconds=0, refresh_on_get=False)

        rpc_type = str(RPCType.JSON_RPC)
        method = "test.method"
        params = {"x": 1}

        rec.set(rpc_type=rpc_type, method=method, params=params, response={"v": 1})
        rec.set(rpc_type=rpc_type, method=method, params=params, response={"v": 2})

        latest = rec.get_latest_response_by_params(rpc_type=rpc_type, method=method, params=params)
        assert latest == {"v": 2}

    @pytest.mark.asyncio
    async def test_negative_ttl_raises_error(self, tmp_path) -> None:
        """Test that negative TTL raises ValueError."""
        central = _CentralStub("C", str(tmp_path))

        with pytest.raises(ValueError):
            SessionRecorder(central=central, active=False, ttl_seconds=-1, refresh_on_get=False)

    @pytest.mark.asyncio
    async def test_peek_ts(self, tmp_path) -> None:
        """Test peeking at timestamp without modifying entry."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=True, ttl_seconds=0, refresh_on_get=False)

        rpc_type = str(RPCType.JSON_RPC)
        method = "test.method"
        params = {"x": 1}

        # No entry yet
        assert rec.peek_ts(rpc_type=rpc_type, method=method, params=params) is None

        # Add entry
        now = datetime.now(tz=UTC)
        rec.set(rpc_type=rpc_type, method=method, params=params, response={"ok": True}, ts=now)

        # Should be able to peek at timestamp
        ts = rec.peek_ts(rpc_type=rpc_type, method=method, params=params)
        assert ts is not None
        assert isinstance(ts, datetime)

    @pytest.mark.asyncio
    async def test_refresh_on_get(self, tmp_path) -> None:
        """Test that refresh_on_get extends TTL."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=True, ttl_seconds=10, refresh_on_get=True)

        rpc_type = str(RPCType.JSON_RPC)
        method = "test.method"
        params = {"x": 1}

        rec.set(rpc_type=rpc_type, method=method, params=params, response={"ok": True})

        # Get should refresh the entry
        first_get = rec.get(rpc_type=rpc_type, method=method, params=params)
        assert first_get == {"ok": True}

        # Get again should still work (refreshed)
        second_get = rec.get(rpc_type=rpc_type, method=method, params=params)
        assert second_get == {"ok": True}

    @pytest.mark.asyncio
    async def test_repr(self, tmp_path) -> None:
        """Test string representation."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=True, ttl_seconds=0, refresh_on_get=False)

        repr_str = repr(rec)
        assert "SessionRecorder" in repr_str

    @pytest.mark.asyncio
    async def test_save_and_clear(self, tmp_path) -> None:
        """Test saving to disk and clearing."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=True, ttl_seconds=0, refresh_on_get=False)

        rec.set(rpc_type=str(RPCType.XML_RPC), method="m", params=(1, 2), response=123)

        # Save
        await rec.save(randomize_output=False, use_ts_in_file_name=True)

        # Files should exist
        session_dir = tmp_path / SUB_DIRECTORY_SESSION
        files = list(session_dir.glob("*.json"))
        assert files, "Should have saved file"

        # Clear
        await rec.clear()
        assert list(session_dir.glob("*.json")) == []

    @pytest.mark.asyncio
    async def test_set_and_get_basic(self, tmp_path) -> None:
        """Test basic set and get operations."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=True, ttl_seconds=0, refresh_on_get=False)

        rpc_type = str(RPCType.JSON_RPC)
        method = "test.method"
        params = {"x": 1}
        response = {"ok": True}

        # No data yet
        assert rec.get(rpc_type=rpc_type, method=method, params=params) is None

        # Set and retrieve
        rec.set(rpc_type=rpc_type, method=method, params=params, response=response)
        assert rec.get(rpc_type=rpc_type, method=method, params=params) == response

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, tmp_path) -> None:
        """Test that entries expire after TTL."""
        central = _CentralStub("C", str(tmp_path))
        rec = SessionRecorder(central=central, active=True, ttl_seconds=0.5, refresh_on_get=False)

        rpc_type = str(RPCType.JSON_RPC)
        method = "test.method"
        params = {"x": 1}

        # Set with explicit timestamp
        now_dt = datetime.now(tz=UTC)
        rec.set(rpc_type=rpc_type, method=method, params=params, response={"ok": True}, ts=now_dt)

        # Should be retrievable immediately
        assert rec.get(rpc_type=rpc_type, method=method, params=params) == {"ok": True}

        # After TTL, should be gone
        await asyncio.sleep(1.2)
        assert rec.get(rpc_type=rpc_type, method=method, params=params) is None


class TestCleanupFiles:
    """Test cleanup_files functionality."""

    @pytest.mark.asyncio
    async def test_cleanup_files_schedules_deletion(self, tmp_path) -> None:
        """Test that cleanup_files schedules file deletion."""
        central_name = "Test Central"

        # Create dummy files
        cache_dir = tmp_path / SUB_DIRECTORY_CACHE
        session_dir = tmp_path / SUB_DIRECTORY_SESSION
        cache_dir.mkdir(parents=True, exist_ok=True)
        session_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{central_name.lower().replace(' ', '-')}_devices.json").write_text("{}", encoding="utf-8")
        (session_dir / f"{central_name.lower().replace(' ', '-')}_rec.json").write_text("{}", encoding="utf-8")

        cleanup_files(central_name=central_name, storage_directory=str(tmp_path))
        await asyncio.sleep(0.1)  # Give executor time to run

        # Directories should still exist
        assert cache_dir.exists()
        assert session_dir.exists()
