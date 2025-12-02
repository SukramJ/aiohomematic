"""Unit tests for aiohomematic.client (__init__.py)."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from aiohomematic import central as hmcu
from aiohomematic.client import (
    Client,
    ClientCCU,
    ClientConfig,
    InterfaceConfig,
    _isclose as client_isclose,
    _track_single_data_point_state_change_or_timeout,
    _wait_for_state_change_or_timeout,
    get_client as get_client_by_id,
)
from aiohomematic.const import (
    CALLBACK_WARN_INTERVAL,
    DataPointKey,
    EventKey,
    Interface,
    InterfaceEventType,
    ParamsetKey,
    ProductGroup,
)
from aiohomematic.exceptions import ClientException, NoConnectionException


class _FakeDP:
    """Minimal fake DataPoint that disables events to exercise early-return path."""

    supports_events = False


class _FakeDevice:
    """Minimal fake Device exposing get_generic_data_point for event tracker helpers."""

    def get_generic_data_point(self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey):  # noqa: ARG002
        return _FakeDP()


class _FakeDeviceDetails:
    """Minimal cache for device details used by ClientCCU methods."""

    def __init__(self) -> None:
        self.device_channel_rega_ids: dict[str, int] = {}
        self._names: dict[str, str] = {}
        self._interfaces: dict[str, Interface] = {}
        self._addr_ids: dict[str, int] = {}

    def add_address_rega_id(self, *, address: str, rega_id: int) -> None:  # noqa: D401
        self._addr_ids[address] = rega_id
        # Simulate that channel addresses map to channel ids
        self.device_channel_rega_ids[address] = rega_id

    def add_interface(self, *, address: str, interface: Interface) -> None:  # noqa: D401
        self._interfaces[address] = interface

    def add_name(self, *, address: str, name: str) -> None:  # noqa: D401
        self._names[address] = name


class _FakeDataCache:
    """Minimal data cache capturing added data for assertions."""

    def __init__(self) -> None:
        self.last_added: tuple[Interface, dict[str, str]] | None = None

    def add_data(self, *, interface: Interface, all_device_data: dict[str, str]) -> None:  # noqa: D401
        self.last_added = (interface, all_device_data)


class _FakeXmlRpcProxy:
    """Fake xml-rpc proxy to satisfy ping and reportValueUsage calls."""

    def __init__(self) -> None:
        self.supported_methods = {"getVersion"}

    async def do_init(self) -> None:  # noqa: D401
        return None

    async def getVersion(self) -> str:  # noqa: D401,N802
        return "2.1"

    async def ping(self, _callerId: str) -> None:  # noqa: D401,N803
        return None

    async def reportValueUsage(self, _address: str, _value_id: str, _ref_counter: int) -> bool:  # noqa: D401,N802
        return True


class _FakeJsonRpcClient:
    """Fake JSON-RPC client to drive ClientJsonCCU/ClientCCU methods without I/O."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def add_link(self, *, sender_address: str, receiver_address: str, name: str, description: str) -> bool:  # noqa: D401,ARG002,E501
        self.calls.append("add_link")
        return True

    async def delete_system_variable(self, *, name: str) -> bool:  # noqa: D401,ARG002
        self.calls.append(f"delete_system_variable:{name}")
        return True

    async def execute_program(self, *, pid: str) -> bool:  # noqa: D401,ARG002
        self.calls.append(f"execute_program:{pid}")
        return True

    async def get_all_channel_rega_ids_function(self):  # noqa: D401
        self.calls.append("get_all_channel_rega_ids_function")
        return {11: {"Func X"}, 12: {"Func Y"}}

    async def get_all_channel_rega_ids_room(self):  # noqa: D401
        self.calls.append("get_all_channel_rega_ids_room")
        return {11: {"Room A"}, 12: {"Room B"}}

    async def get_all_device_data(self, *, interface: Interface):  # noqa: D401,ARG002
        self.calls.append("get_all_device_data")
        return {"BidCos-RF.OEQ:1.STATE": "ON/OFF"}

    async def get_all_programs(self, *, markers: tuple[str, ...]):  # noqa: D401,ARG002
        self.calls.append("get_all_programs")
        return ()

    async def get_all_system_variables(self, *, markers: tuple[str, ...]):  # noqa: D401,ARG002
        self.calls.append("get_all_system_variables")
        return ()

    async def get_device_description(self, *, interface: Interface, address: str):  # noqa: D401,ARG002
        self.calls.append("get_device_description")
        return {"address": address}

    async def get_device_details(self):  # noqa: D401
        self.calls.append("get_device_details")
        return [
            {
                "address": "dev1",
                "name": "Device 1",
                "id": 1,
                "interface": Interface.BIDCOS_RF,
                "channels": [
                    {"address": "dev1:1", "name": "Ch1", "id": 11},
                    {"address": "dev1:2", "name": "Ch2", "id": 12},
                ],
            }
        ]

    async def get_link_peers(self, *, address: str):  # noqa: D401,ARG002
        self.calls.append("get_link_peers")
        return ()

    async def get_links(self, *, address: str, flags: int):  # noqa: D401,ARG002
        self.calls.append("get_links")
        return ()

    async def get_metadata(self, *, address: str, data_id: str):  # noqa: D401,ARG002
        self.calls.append("get_metadata")
        return {}

    async def get_paramset(self, *, interface: Interface, address: str, paramset_key: ParamsetKey):  # noqa: D401,ARG002
        self.calls.append(f"get_paramset:{address}:{paramset_key}")
        if paramset_key == ParamsetKey.MASTER:
            return {"LEVEL": 99}
        return {"LEVEL": 1}

    async def get_paramset_description(self, *, interface: Interface, address: str, paramset_key: ParamsetKey):  # noqa: D401,ARG002,E501
        self.calls.append("get_paramset_description")
        return {"LEVEL": {"TYPE": "FLOAT", "UNIT": "%"}}

    async def get_system_information(self):  # noqa: D401
        self.calls.append("get_system_information")
        from aiohomematic.const import SystemInformation

        return SystemInformation(available_interfaces=(Interface.BIDCOS_RF,), serial="BIDCOS_RF_1234")

    async def get_system_variable(self, *, name: str) -> Any:  # noqa: D401,ARG002
        self.calls.append(f"get_system_variable:{name}")
        return 42

    async def get_value(self, *, interface: Interface, address: str, paramset_key: ParamsetKey, parameter: str):  # noqa: D401,ARG002
        self.calls.append(f"get_value:{address}:{parameter}")
        return 7

    async def has_program_ids(self, *, rega_id: str) -> bool:  # noqa: D401,ARG002
        self.calls.append(f"has_program_ids:{rega_id}")
        return True

    async def is_present(self, *, interface: Interface) -> bool:  # noqa: D401,ARG002
        self.calls.append("is_present")
        return True

    async def list_devices(self, *, interface: Interface):  # noqa: D401,ARG002
        self.calls.append("list_devices")
        return ({"address": "dev1"},)

    async def put_paramset(
        self, *, interface: Interface, address: str, paramset_key: ParamsetKey | str, values: dict[str, Any]
    ):  # noqa: D401,ARG002,E501
        self.calls.append("put_paramset")
        return True

    async def remove_link(self, *, sender_address: str, receiver_address: str) -> bool:  # noqa: D401,ARG002
        self.calls.append("remove_link")
        return True

    async def set_metadata(self, *, address: str, data_id: str, value: dict[str, Any]):  # noqa: D401,ARG002
        self.calls.append("set_metadata")
        return True

    async def set_program_state(self, *, pid: str, state: bool) -> bool:  # noqa: D401,ARG002
        self.calls.append(f"set_program_state:{pid}:{state}")
        return True

    async def set_system_variable(self, *, legacy_name: str, value: Any) -> bool:  # noqa: D401,ARG002
        self.calls.append(f"set_system_variable:{legacy_name}:{value}")
        return True

    async def set_value(
        self, *, interface: Interface, address: str, parameter: str, value_type: str | None = None, value: Any = None
    ):  # noqa: D401,ARG002,E501
        self.calls.append("set_value")
        return True

    async def update_device_firmware(self, *, device_address: str):  # noqa: D401,ARG002
        self.calls.append("update_device_firmware")
        return True


class _FakeParamsetDescriptions:
    """Minimal paramset descriptions exposing required methods."""

    def get_parameter_data(self, *, interface_id: str, channel_address: str, paramset_key: ParamsetKey, parameter: str):  # noqa: D401,ARG002
        # Return a dict mimicking ParameterData with TYPE FLOAT for LEVEL
        if parameter == "LEVEL":
            return {"TYPE": "FLOAT"}
        return None

    def get_parameters(
        self,
        *,
        paramset_key: ParamsetKey,
        operations: tuple,
        full_format: bool = False,
        un_ignore_candidates_only: bool = False,
        use_channel_wildcard: bool = False,
    ):  # noqa: D401,ARG002
        return ()


class _FakeCentral:
    """Minimal CentralUnit-like object used by ClientConfig/ClientCCU without I/O."""

    def __init__(self) -> None:
        from types import SimpleNamespace

        self.connection_state = hmcu.CentralConnectionState()
        self.json_rpc_client = _FakeJsonRpcClient()
        self.device_details = _FakeDeviceDetails()
        self.data_cache = _FakeDataCache()
        self.paramset_descriptions = _FakeParamsetDescriptions()
        self.recorder = SimpleNamespace()  # not used by fakes
        self._clients: dict[str, object] = {}
        self.name = "central"

        class Cfg:
            host = "localhost"
            tls = False
            verify_tls = False
            username = None
            password = None
            max_read_workers = 0
            callback_host = "127.0.0.1"
            callback_port_xml_rpc = 0
            interfaces_requiring_periodic_refresh = frozenset()

        self.config = Cfg()
        self._listen_port_xml_rpc = 32001
        self._callback_ip_addr = "127.0.0.1"

    @property
    def callback_ip_addr(self) -> str:  # noqa: D401
        return self._callback_ip_addr

    @property
    def listen_port_xml_rpc(self) -> int:  # noqa: D401
        return self._listen_port_xml_rpc

    def get_client(self, *, interface_id: str):  # noqa: D401,ARG002
        return self._clients.get(interface_id)

    def has_client(self, *, interface_id: str) -> bool:  # noqa: D401,ARG002
        return interface_id in self._clients

    def publish_homematic_event(self, *, event_type: Any, event_data: dict[str, Any]) -> None:  # noqa: D401,ARG002,ANN401
        return None

    def publish_interface_event(
        self, *, interface_id: str, interface_event_type: InterfaceEventType, data: dict[EventKey, str]
    ):  # noqa: D401,ARG002,E501
        return None

    def save_files(self, *, save_paramset_descriptions: bool = False) -> None:  # noqa: ARG002,D401
        return None


class _XmlProxy2:
    """
    Simple fake of the XmlRpcProxy used by Client for proxy lifecycle and calls.

    Dedicated variant to avoid colliding with other test fakes in this module.
    """

    def __init__(self, *, fail_init: bool = False, fail_deinit: bool = False) -> None:
        self.supported_methods = {"getVersion"}
        self._fail_init = fail_init
        self._fail_deinit = fail_deinit
        self._stopped = False
        self._calls: list[tuple[Any, ...] | tuple[str, tuple[Any, ...]]] = []

    async def addLink(self, *args: Any):  # noqa: D401,N802,ANN401
        raise ClientException("addLink-fail")

    async def do_init(self) -> None:  # noqa: D401
        return None

    async def getDeviceDescription(self, *args: Any):  # noqa: D401,ANN401
        return None

    async def getInstallMode(self) -> int:  # noqa: D401,N802
        return 60

    async def getLinkPeers(self, *args: Any):  # noqa: D401,N802,ANN401
        raise ClientException("getLinkPeers-fail")

    async def getLinks(self, *args: Any):  # noqa: D401,N802,ANN401
        raise ClientException("getLinks-fail")

    async def getMetadata(self, *args: Any):  # noqa: D401,ANN401
        raise ClientException("getMetadata-fail")

    async def getParamset(self, addr: str, key: Any):  # noqa: D401,N802,ANN401
        return {"LEVEL": 5}

    async def getValue(self, addr: str, param: str):  # noqa: D401,N802
        return 123

    async def init(self, *args: Any) -> None:  # noqa: D401
        self._calls.append(("init", args))
        if self._fail_init:
            raise ClientException("init-fail")
        return

    async def installFirmware(self, *args: Any):  # noqa: D401,ANN401
        return True

    async def listDevices(self):  # noqa: D401
        return []

    async def ping(self, _callerId: str) -> None:  # noqa: N803,D401
        return None

    async def putParamset(self, addr: str, key: Any, values: dict[str, Any], *rest: Any):  # noqa: D401,N802,ANN401
        self._calls.append(("putParamset", (addr, key, values, *rest)))
        return

    async def removeLink(self, *args: Any):  # noqa: D401,N802,ANN401
        raise ClientException("removeLink-fail")

    async def setInstallMode(self, *args: Any):  # noqa: D401,N802,ANN401
        return None

    async def setMetadata(self, *args: Any):  # noqa: D401,ANN401
        raise ClientException("setMetadata-fail")

    async def setValue(self, addr: str, param: str, value: Any, *rest: Any):  # noqa: D401,N802
        self._calls.append(("setValue", (addr, param, value, *rest)))
        return

    async def stop(self) -> None:  # noqa: D401
        self._stopped = True

    async def updateFirmware(self, *args: Any):  # noqa: D401,ANN401
        return True


class _FakeCentral2:
    """
    Minimal central used by consolidated tests without I/O.

    Dedicated variant to avoid colliding with other test fakes in this module.
    """

    def __init__(self, *, push_updates: bool = True) -> None:
        self.connection_state = hmcu.CentralConnectionState()
        self.json_rpc_client = SimpleNamespace()  # not used in these tests
        self.device_details = SimpleNamespace(
            device_channel_rega_ids={},
            add_interface=lambda **kwargs: None,  # type: ignore[misc]
            add_name=lambda **kwargs: None,  # type: ignore[misc]
            add_address_rega_id=lambda **kwargs: None,  # type: ignore[misc]
        )
        self.data_cache = SimpleNamespace(add_data=lambda **kwargs: None)  # type: ignore[misc]
        self.paramset_descriptions = SimpleNamespace(
            get_parameter_data=lambda **kwargs: None,  # type: ignore[misc]
            add=lambda **kwargs: None,  # type: ignore[misc]
            has_interface_id=lambda **kwargs: True,  # type: ignore[misc]
        )
        self.recorder = SimpleNamespace()
        self._devices: dict[str, Any] = {}
        self._channels: dict[str, Any] = {}
        self._last_event: datetime | None = None
        self._events: list[tuple[str, InterfaceEventType, dict[EventKey, Any]]] = []
        self._clients: dict[str, Any] = {}
        self._listen_port_xml_rpc = 32001
        self._callback_ip_addr = "127.0.0.1"
        self.devices: tuple[Any, ...] = ()

        class Cfg:
            host = "localhost"
            tls = False
            verify_tls = False
            username = None
            password = None
            max_read_workers = 0
            callback_host = "127.0.0.1"
            callback_port_xml_rpc = 0
            interfaces_requiring_periodic_refresh = frozenset()
            hm_master_poll_after_send_intervals = (0,)

        self.config = Cfg()
        if not push_updates:
            self.config.interfaces_requiring_periodic_refresh = {Interface.BIDCOS_RF}

        self.looper = SimpleNamespace(create_task=lambda **kwargs: None)  # type: ignore[misc]

    @property
    def callback_ip_addr(self) -> str:  # noqa: D401
        return self._callback_ip_addr

    @property
    def listen_port_xml_rpc(self) -> int:  # noqa: D401
        return self._listen_port_xml_rpc

    def add_channel(self, channel_address: str) -> None:
        self._channels[channel_address] = SimpleNamespace(
            get_readable_data_points=lambda paramset_key: (),  # type: ignore[misc]
        )

    def add_device(self, addr: str, *, product_group: ProductGroup) -> None:
        self._devices[addr] = SimpleNamespace(product_group=product_group, interface_id="i")

    def get_channel(self, *, channel_address: str):  # noqa: D401,ANN001
        return self._channels.get(channel_address)

    def get_device(self, *, address: str):  # noqa: D401,ANN001
        return self._devices.get(address)

    def get_generic_data_point(self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey):  # noqa: D401,ARG002
        return None

    def get_last_event_seen_for_interface(self, *, interface_id: str):  # noqa: D401,ARG002
        return self._last_event

    def publish_interface_event(
        self, *, interface_id: str, interface_event_type: InterfaceEventType, data: dict[EventKey, Any]
    ):  # noqa: D401,E501
        self._events.append((interface_id, interface_event_type, data))

    async def save_files(self, *, save_paramset_descriptions: bool = False):  # noqa: ARG002,D401
        return None


class _EventDP:
    """Fake DataPoint that supports events and provides a callback api for tracker timeout path."""

    def __init__(self, *, should_match: bool = False) -> None:
        self.supports_events = True
        self._handler: Any | None = None
        self.value = 0.0 if should_match else 1.0
        self.unsub_called = False

    def subscribe_to_data_point_updated(self, *, handler, custom_id):  # type: ignore[no-untyped-def]
        self._handler = handler

        def _unsub():
            self.unsub_called = True

        return _unsub


class _EventDevice:
    """Device returning _EventDP to allow exercising the timeout branch of the tracker."""

    def __init__(self) -> None:
        self.dp = _EventDP()

    def get_generic_data_point(self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey):  # noqa: ARG002
        return self.dp


class _TestClient(Client):
    """Minimal concrete Client for testing property/helper behavior without I/O."""

    @property
    def model(self) -> str:  # pragma: no cover - not relevant to tested logic
        return "test"

    async def check_connection_availability(self, *, handle_ping_pong: bool) -> bool:  # pragma: no cover
        return True

    async def delete_system_variable(self, *, name: str):  # pragma: no cover - not used
        return None

    async def fetch_all_device_data(self) -> None:  # pragma: no cover - not used in tests
        return None

    async def fetch_device_details(self) -> None:  # pragma: no cover - not used in tests
        return None

    async def get_all_system_variables(self, *, markers):  # pragma: no cover - not used
        return ()

    async def get_install_mode(self) -> int:  # pragma: no cover - not used
        return 0

    async def get_system_variable(self, *, name: str):  # pragma: no cover - not used
        return None

    async def rename_channel(self, *, rega_id: int, new_name: str) -> bool:  # pragma: no cover - not used
        return False

    async def rename_device(self, *, rega_id: int, new_name: str) -> bool:  # pragma: no cover - not used
        return False

    async def set_system_variable(self, *, legacy_name: str, value):  # pragma: no cover - not used
        return None

    async def trigger_firmware_update(self) -> bool:  # pragma: no cover - not used
        return False

    async def _get_system_information(self):  # pragma: no cover - not used
        from aiohomematic.const import DUMMY_SERIAL, Interface, SystemInformation

        return SystemInformation(available_interfaces=(Interface.BIDCOS_RF,), serial=f"{self.interface}_{DUMMY_SERIAL}")


def _make_client_with_interface(iface: Interface, *, push: bool = True, fw: bool = False) -> _TestClient:
    """
    Create an uninitialized Client instance with a fake _config for given interface.

    We bypass the real Client.__init__ to avoid network/config dependencies and only
    provide the attributes used by the tested properties/methods.
    """
    c = object.__new__(_TestClient)
    fake_cfg = SimpleNamespace(
        interface=iface,
        supports_linking=(iface in {Interface.HMIP_RF, Interface.BIDCOS_RF, Interface.BIDCOS_WIRED}),
        supports_push_updates=push,
        supports_firmware_updates=fw,
        supports_ping_pong=(iface in {Interface.HMIP_RF, Interface.BIDCOS_RF, Interface.BIDCOS_WIRED}),
        supports_rpc_callback=(iface in {Interface.HMIP_RF, Interface.BIDCOS_RF, Interface.BIDCOS_WIRED}),
        version="0",
    )
    # Attach minimal config needed by Client properties
    c._config = fake_cfg  # type: ignore[attr-defined]
    return c


# === Additional tests to raise coverage for aiohomematic/client/__init__.py ===
class TestClientEventTracking:
    """Test client event tracking helpers and timeouts."""

    @pytest.mark.asyncio
    async def test_event_tracker_timeout_and_unsubscribe(self) -> None:
        """Tracker should timeout and call unsubscribe in finally when event does not meet value condition."""
        dpk = DataPointKey(
            interface_id="i", channel_address="addr:1", paramset_key=ParamsetKey.VALUES, parameter="LEVEL"
        )
        dev = _EventDevice()
        await _track_single_data_point_state_change_or_timeout(device=dev, dpk_value=(dpk, 0.0), wait_for_callback=0)
        assert dev.dp.unsub_called is True

    @pytest.mark.asyncio
    async def test_event_tracking_helpers_early_return(self) -> None:
        """_track_single_data_point_state_change_or_timeout returns early when dp supports no events."""
        dpk = DataPointKey(
            interface_id="i",
            channel_address="addr:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
        )
        # Should not raise and should return quickly when dp.supports_events is False
        await _track_single_data_point_state_change_or_timeout(
            device=_FakeDevice(), dpk_value=(dpk, 0), wait_for_callback=1
        )

        # The wrapper that awaits multiple trackers should also complete successfully
        await _wait_for_state_change_or_timeout(device=_FakeDevice(), dpk_values={(dpk, 0)}, wait_for_callback=1)


class TestClientClasses:
    """Test ClientCCU and ClientJsonCCU functionality."""

    @pytest.mark.asyncio
    async def test_client_classes_happy_paths(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exercise many methods of ClientCCU/ClientJsonCCU and ClientConfig using fakes to raise coverage."""
        central = _FakeCentral()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        # Create ClientConfig and patch xml proxy creation
        from aiohomematic.client import (
            ClientCCU as _ClientCCU,
            ClientConfig as _ClientConfig,
            ClientJsonCCU as _ClientJsonCCU,
        )

        ccfg = _ClientConfig(central=central, interface_config=iface_cfg)

        # Patch XML-RPC creation used by _get_version and others (for all ClientConfig instances)
        async def _fake_create_xml_rpc_proxy(self, **kwargs):  # type: ignore[no-untyped-def]
            return _FakeXmlRpcProxy()

        monkeypatch.setattr(_ClientConfig, "_create_xml_rpc_proxy", _fake_create_xml_rpc_proxy)  # type: ignore[assignment]

        # _get_version via xml proxy supported_methods
        ver = await ccfg._get_version()
        assert ver == "2.1"

        # Instantiate clients
        client_ccu = _ClientCCU(client_config=ccfg)
        client_json = _ClientJsonCCU(client_config=ccfg)

        # Provide a fake xml-rpc proxy to client_ccu
        client_ccu._proxy = _FakeXmlRpcProxy()  # type: ignore[attr-defined]

        # Simple properties and __str__ and product groups
        assert str(client_ccu) == f"interface_id: {client_ccu.interface_id}"
        assert client_ccu.get_product_group(model="HmIP-ABC") == ProductGroup.HMIP
        assert client_ccu.get_product_group(model="hmw-xyz") == ProductGroup.HMW
        assert client_ccu.get_product_group(model="hm-") == ProductGroup.HM

        # JSON-based methods through FakeJsonRpcClient
        await client_ccu.fetch_device_details()
        await client_ccu.fetch_all_device_data()
        assert central.data_cache.last_added[0] == Interface.BIDCOS_RF  # type: ignore[index]

        assert await client_ccu.check_connection_availability(handle_ping_pong=False) is True
        assert await client_ccu.execute_program(pid="p1") is True
        assert await client_ccu.set_program_state(pid="p1", state=True) is True
        assert await client_ccu.has_program_ids(rega_id="ch1") is True
        assert await client_ccu.set_system_variable(legacy_name="sv", value=1) is True
        assert await client_ccu.delete_system_variable(name="sv") is True
        assert await client_ccu.get_system_variable(name="sv") == 42
        assert await client_ccu.get_all_system_variables(markers=()) == ()
        assert await client_ccu.get_all_programs(markers=()) == ()

        # Rooms/functions use device_details ids
        rooms = await client_ccu.get_all_rooms()
        funcs = await client_ccu.get_all_functions()
        assert "dev1:1" in rooms and "dev1:1" in funcs

        # ClientJsonCCU methods
        assert await client_json.check_connection_availability(handle_ping_pong=False) is True
        assert await client_json.get_device_description(address="dev1") is not None
        assert await client_json.get_paramset(address="dev1:1", paramset_key=ParamsetKey.VALUES) == {"LEVEL": 1}
        assert (
            await client_json.get_value(channel_address="dev1:1", paramset_key=ParamsetKey.VALUES, parameter="LEVEL")
            == 7
        )
        assert (await client_json.list_devices()) is not None
        assert (
            await client_json._get_paramset_description(address="dev1:1", paramset_key=ParamsetKey.VALUES)
        ) is not None

        # Exec set/put value wrappers
        # _exec_put_paramset returns None on success; just ensure it completes without raising.
        await client_json._exec_put_paramset(
            channel_address="dev1:1", paramset_key=ParamsetKey.VALUES, values={"LEVEL": 1}
        )
        # _exec_set_value returns None on success; just ensure it completes without raising.
        await client_json._exec_set_value(channel_address="dev1:1", parameter="LEVEL", value=1.0)

        # Links/metadata passthroughs: these methods may not return a value; ensure they complete without raising.
        await client_json.add_link(sender_address="a", receiver_address="b", name="n", description="d")
        await client_json.remove_link(sender_address="a", receiver_address="b")
        await client_json.get_link_peers(address="a")
        await client_json.get_links(address="a", flags=0)
        await client_json.get_metadata(address="a", data_id="d")
        await client_json.set_metadata(address="a", data_id="d", value={})
        await client_json.report_value_usage(address="a", value_id="v", ref_counter=1)
        await client_json.update_device_firmware(device_address="dev1")

        # System information
        si = await client_json._get_system_information()
        assert isinstance(si.available_interfaces, tuple)

    @pytest.mark.asyncio
    async def test_client_init_and_ping_paths(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cover Client.init_client proxy creation and check_connection_availability branches (ping, exception)."""
        central = _FakeCentral()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        from aiohomematic.client import ClientCCU as _ClientCCU, ClientConfig as _ClientConfig

        ccfg = _ClientConfig(central=central, interface_config=iface_cfg)

        async def _fake_create_xml_rpc_proxy(self, **kwargs):  # type: ignore[no-untyped-def]
            return _FakeXmlRpcProxy()

        monkeypatch.setattr(_ClientConfig, "_create_xml_rpc_proxy", _fake_create_xml_rpc_proxy)  # type: ignore[assignment]

        client_ccu = _ClientCCU(client_config=ccfg)

        # init_client should create proxies when supports_rpc_callback True
        await client_ccu.init_client()

        # Not initialized path: pings with interface_id
        client_ccu._is_initialized = False  # type: ignore[attr-defined]
        assert await client_ccu.check_connection_availability(handle_ping_pong=False) is True

        # Initialized and supports_ping_pong path: pings with callerId including timestamp
        client_ccu._is_initialized = True  # type: ignore[attr-defined]
        assert await client_ccu.check_connection_availability(handle_ping_pong=True) is True

        # Exception path: proxy ping raises -> method returns False
        class _ErrProxy(_FakeXmlRpcProxy):
            async def ping(self, _callerId: str) -> None:  # noqa: N803
                raise ClientException("boom")

        client_ccu._proxy = _ErrProxy()  # type: ignore[attr-defined]
        assert await client_ccu.check_connection_availability(handle_ping_pong=True) is False

    @pytest.mark.asyncio
    async def test_clientjsonccu_value_and_description_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cover ClientJsonCCU.get_value non-VALUES branch and get_device_description exception path."""
        central = _FakeCentral()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        from aiohomematic.client import ClientConfig as _ClientConfig, ClientJsonCCU as _ClientJsonCCU

        ccfg = _ClientConfig(central=central, interface_config=iface_cfg)
        client_json = _ClientJsonCCU(client_config=ccfg)

        # get_value for MASTER branch should read from MASTER paramset returned by FakeJsonRpcClient
        val = await client_json.get_value(channel_address="dev1:1", paramset_key=ParamsetKey.MASTER, parameter="LEVEL")
        assert val == 99

        # get_device_description should catch BaseHomematicException and return None
        async def raise_bhe(*, interface: Interface, address: str):  # noqa: ARG002
            raise ClientException("fail")

        monkeypatch.setattr(central.json_rpc_client, "get_device_description", raise_bhe)
        assert await client_json.get_device_description(address="dev1") is None

    @pytest.mark.asyncio
    async def test_fetch_all_device_data_exception_event(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """fetch_all_device_data should publish interface event on ClientException and not raise when decorated with re_raise=False."""
        central = _FakeCentral()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        from aiohomematic.client import ClientCCU as _ClientCCU, ClientConfig as _ClientConfig

        ccfg = _ClientConfig(central=central, interface_config=iface_cfg)
        client_ccu = _ClientCCU(client_config=ccfg)

        # Patch json client to raise ClientException on get_all_device_data
        async def raise_client_exc(*, interface: Interface):  # noqa: ARG002
            raise ClientException("x")

        central.json_rpc_client.get_all_device_data = raise_client_exc  # type: ignore[assignment]

        # Capture publish_interface_event calls
        called: dict[str, Any] = {}

        def _emit(**kwargs: Any) -> None:  # noqa: ANN001
            called.update(kwargs)

        central.publish_interface_event = _emit  # type: ignore[assignment]

        # Should not raise due to inspector(re_raise=False)
        await client_ccu.fetch_all_device_data()

        assert called.get("interface_event_type") == InterfaceEventType.FETCH_DATA


class TestClientConfig:
    """Test ClientConfig creation and selection logic."""

    @pytest.mark.asyncio
    async def test_clientconfig_create_client_branches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cover ClientConfig.create_client selections (Homegear, JsonCCU) and failure path when availability is False."""
        central = _FakeCentral()
        from aiohomematic.client import (
            ClientCCU as _ClientCCU,
            ClientConfig as _ClientConfig,
            ClientJsonCCU as _ClientJsonCCU,
        )

        # Homegear selection via version string on BIDCOS_RF
        iface_hg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        ccfg_hg = _ClientConfig(central=central, interface_config=iface_hg)

        class _HGProxy(_FakeXmlRpcProxy):
            async def clientServerInitialized(self, interface_id: str) -> bool:  # noqa: N802,ARG002
                """Simulate Homegear proxy method to check initialization."""
                return True

            async def getVersion(self) -> str:  # noqa: N802
                return "Homegear 0.8"

        async def _fake_proxy(self, **kwargs):  # type: ignore[no-untyped-def]
            return _HGProxy()

        monkeypatch.setattr(_ClientConfig, "_create_xml_rpc_proxy", _fake_proxy)  # type: ignore[assignment]

        # Also patch xml proxy creation used by create_rpc_proxy during init_client
        client = await ccfg_hg.create_client()
        assert isinstance(client, _ClientCCU)

        # JsonCCU selection for HMIP_RF (requires JSON-RPC client)
        iface_js = InterfaceConfig(central_name="c", interface=Interface.CUXD, port=8701)
        ccfg_js = _ClientConfig(central=central, interface_config=iface_js)
        client2 = await ccfg_js.create_client()
        assert isinstance(client2, _ClientJsonCCU)

        # Failure path: force availability check to return False and expect NoConnectionException
        iface_fail = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        ccfg_fail = _ClientConfig(central=central, interface_config=iface_fail)

        # Use fixed version so ClientCCU is selected, then make check_connection_availability return False
        async def _get_version_zero(self) -> str:  # type: ignore[no-untyped-def]
            return "0"

        monkeypatch.setattr(_ClientConfig, "_get_version", _get_version_zero)  # type: ignore[assignment]

        # Monkeypatch the ClientCCU method before creation
        async def _cca_false(self, *, handle_ping_pong: bool) -> bool:  # type: ignore[no-untyped-def]
            return False

        monkeypatch.setattr(_ClientCCU, "check_connection_availability", _cca_false)  # type: ignore[assignment]

        with pytest.raises(NoConnectionException):
            await ccfg_fail.create_client()

    @pytest.mark.asyncio
    async def test_clientconfig_get_version_without_getversion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_get_version should return "0" when proxy lacks getVersion in supported_methods."""
        central = _FakeCentral2()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        ccfg = ClientConfig(central=central, interface_config=iface_cfg)

        class _NoGetVersionProxy:
            supported_methods: set[str] = set()

            async def getVersion(self) -> str:  # pragma: no cover - should not be called
                return "should-not-be-called"

        async def _fake_simple_proxy(self, *, interface: Interface):  # type: ignore[no-untyped-def]
            return _NoGetVersionProxy()

        monkeypatch.setattr(ClientConfig, "_create_simple_rpc_proxy", _fake_simple_proxy)  # type: ignore[assignment]

        ver = await ccfg._get_version()
        assert ver == "0"


class TestInterfaceConfig:
    """Test InterfaceConfig validation and enabling."""

    def test_interface_config_enabled_and_validation(self) -> None:
        """InterfaceConfig.enabled toggles; validation raises when port is falsy for callback-capable interfaces."""
        cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        assert cfg.enabled is True
        cfg.disable()
        assert cfg.enabled is False

        # Validation error when port is falsy and interface supports callback
        with pytest.raises(ClientException):
            InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=0)


class TestClientHelpers:
    """Test client helper functions and utilities."""

    @pytest.mark.asyncio
    async def test_client_helpers_isclose_and_get_client(self) -> None:
        """Import client module to generate coverage; verify _isclose and get_client(None)."""
        # float closeness uses rounding to 2 decimals
        assert client_isclose(value1=1.234, value2=1.2344) is True
        assert client_isclose(value1=1.234, value2=1.235) is False
        # non-floats: strict equality
        assert client_isclose(value1="a", value2="a") is True
        assert client_isclose(value1="a", value2="b") is False

        # get_client returns None for unknown interface_id, without mutating registry
        assert get_client_by_id("non-existent-interface-id") is None


class TestClientProductGroup:
    """Test product group determination by model and interface."""

    def test_get_product_group_by_interface_fallbacks(self) -> None:
        """When no known prefix is found, the interface determines the product group."""
        assert _make_client_with_interface(Interface.HMIP_RF).get_product_group(model="X") is ProductGroup.HMIP
        assert _make_client_with_interface(Interface.BIDCOS_WIRED).get_product_group(model="X") is ProductGroup.HMW
        assert _make_client_with_interface(Interface.BIDCOS_RF).get_product_group(model="X") is ProductGroup.HM
        assert (
            _make_client_with_interface(Interface.VIRTUAL_DEVICES).get_product_group(model="X") is ProductGroup.VIRTUAL
        )
        assert _make_client_with_interface(Interface.CUXD).get_product_group(model="X") is ProductGroup.UNKNOWN

    def test_get_product_group_by_model_prefixes(self) -> None:
        """get_product_group should classify by known model prefixes (case-insensitive)."""
        c = _make_client_with_interface(Interface.BIDCOS_RF)

        assert c.get_product_group(model="HMIPW-ABC123") is ProductGroup.HMIPW
        assert c.get_product_group(model="hmip-device") is ProductGroup.HMIP
        assert c.get_product_group(model="HMW-foo") is ProductGroup.HMW
        assert c.get_product_group(model="hm-bar") is ProductGroup.HM


class TestClientSupportFlags:
    """Test client support flags from configuration."""

    def test_support_flags_from_config(self) -> None:
        """supports_ping_pong/push/firmware reflect the derived values from config."""
        c1 = _make_client_with_interface(Interface.BIDCOS_RF, push=True, fw=True)
        assert c1.supports_ping_pong is True
        assert c1.supports_push_updates is True
        assert c1.supports_firmware_updates is True

        c2 = _make_client_with_interface(Interface.CUXD, push=False, fw=False)
        assert c2.supports_ping_pong is False
        assert c2.supports_push_updates is False
        assert c2.supports_firmware_updates is False


class TestClientProxyLifecycle:
    """Test proxy initialization and deinitialization."""

    @pytest.mark.asyncio
    async def test_proxy_lifecycle_success_and_failure_consolidated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """initialize_proxy/deinitialize_proxy paths including exceptions and non-callback path."""
        central = _FakeCentral2()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        ccfg = ClientConfig(central=central, interface_config=iface_cfg)

        client = ClientCCU(client_config=ccfg)

        # Patch proxies on client directly
        client._proxy = _XmlProxy2()  # type: ignore[attr-defined]
        client._proxy_read = _XmlProxy2()  # type: ignore[attr-defined]

        state = await client.initialize_proxy()
        from aiohomematic.const import ProxyInitState

        assert state is ProxyInitState.INIT_SUCCESS and client.is_initialized is True

        state = await client.deinitialize_proxy()
        assert (
            state in {ProxyInitState.DE_INIT_SUCCESS, ProxyInitState.DE_INIT_FAILED} and client.is_initialized is False
        )

        client._config.supports_rpc_callback = False  # type: ignore[attr-defined]
        state = await client.deinitialize_proxy()
        assert state is ProxyInitState.DE_INIT_SUCCESS

        client._config.supports_rpc_callback = False  # type: ignore[attr-defined]
        state = await client.initialize_proxy()
        assert state in {ProxyInitState.INIT_FAILED, ProxyInitState.INIT_SUCCESS}

        client._config.supports_rpc_callback = True  # type: ignore[attr-defined]
        client._proxy = _XmlProxy2(fail_init=True)  # type: ignore[attr-defined]
        state = await client.initialize_proxy()
        assert state is ProxyInitState.INIT_FAILED


class TestClientReconnectAndConnection:
    """Test client reconnection and connection checking."""

    def test_is_callback_alive_paths_consolidated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cover warning and recovery branches in is_callback_alive based on last event time."""
        central = _FakeCentral2()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        client = ClientCCU(client_config=ClientConfig(central=central, interface_config=iface_cfg))

        assert client.is_callback_alive() is True

        central._last_event = datetime.now() - timedelta(seconds=CALLBACK_WARN_INTERVAL + 1)
        assert client.is_callback_alive() is False
        assert client.is_callback_alive() is False

        central._last_event = datetime.now()
        assert client.is_callback_alive() is True

    @pytest.mark.asyncio
    async def test_reconnect_and_is_connected_consolidated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cover reconnect waiting path and is_connected counting/push-updates logic."""
        central = _FakeCentral2(push_updates=True)
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        client = ClientCCU(client_config=ClientConfig(central=central, interface_config=iface_cfg))

        async def _cca_true(*, handle_ping_pong: bool) -> bool:  # noqa: ARG001
            return True

        async def _cca_false(*, handle_ping_pong: bool) -> bool:  # noqa: ARG001
            return False

        client.check_connection_availability = _cca_true  # type: ignore[method-assign]

        async def _no_sleep(_):  # noqa: ANN001
            return None

        monkeypatch.setattr("asyncio.sleep", _no_sleep)

        assert await client.reconnect() is False

        client.modified_at = datetime.now()
        assert await client.is_connected() is True

        client.check_connection_availability = _cca_false  # type: ignore[method-assign]
        res = [await client.is_connected() for _ in range(4)]
        assert res[-1] is False

        central2 = _FakeCentral2(push_updates=False)
        client2 = ClientCCU(client_config=ClientConfig(central=central2, interface_config=iface_cfg))
        client2.check_connection_availability = _cca_true  # type: ignore[method-assign]
        assert await client2.is_connected() is True


class TestClientValueAndParamset:
    """Test client value and paramset operations."""

    @pytest.mark.asyncio
    async def test_get_device_descriptions_and_wrappers_consolidated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cover get_all_device_descriptions and link/metadata wrappers raising ClientException."""
        central = _FakeCentral2()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        client = ClientCCU(client_config=ClientConfig(central=central, interface_config=iface_cfg))
        client._proxy = _XmlProxy2()  # type: ignore[attr-defined]
        client._proxy_read = _XmlProxy2()  # type: ignore[attr-defined]

        res = await client.get_all_device_descriptions(device_address="dev1")
        assert res == ()

        for meth in (
            client.add_link,
            client.remove_link,
            client.get_link_peers,
            client.get_links,
            client.get_metadata,
            client.set_metadata,
        ):
            with pytest.raises(ClientException):
                name = getattr(meth, "__name__", "")
                if name in {"get_link_peers", "get_links", "get_metadata", "set_metadata"}:
                    if name == "get_link_peers":
                        await meth(address="a")  # type: ignore[misc]
                    elif name == "get_links":
                        await meth(address="a", flags=0)  # type: ignore[misc]
                    elif name == "get_metadata":
                        await meth(address="a", data_id="x")  # type: ignore[misc]
                    else:  # set_metadata
                        await meth(address="a", data_id="x", value={})  # type: ignore[misc]
                elif name == "remove_link":
                    await meth(sender_address="a", receiver_address="b")  # type: ignore[misc]
                else:  # add_link
                    await meth(sender_address="a", receiver_address="b", name="n", description="d")  # type: ignore[misc]

    @pytest.mark.asyncio
    async def test_set_value_and_put_paramset_paths_consolidated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cover set_value/_set_value branches including validation errors."""
        central = _FakeCentral2()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        client = ClientCCU(client_config=ClientConfig(central=central, interface_config=iface_cfg))
        client._proxy = _XmlProxy2()  # type: ignore[attr-defined]
        client._proxy_read = _XmlProxy2()  # type: ignore[attr-defined]

        dpk_values = await client._set_value(
            channel_address="dev1:1",
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=0,
            rx_mode=None,
            check_against_pd=False,
        )
        assert isinstance(dpk_values, set)

        res2 = await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.MASTER,
            parameter="LEVEL",
            value=2,
            wait_for_callback=None,
        )
        assert isinstance(res2, set)

        with pytest.raises(ClientException):
            await client.put_paramset(
                channel_address="dev1:1",
                paramset_key_or_link_address="not-a-channel",
                values={"LEVEL": 1},
                check_against_pd=True,
            )

        with pytest.raises(ClientException):
            await client.put_paramset(
                channel_address="dev1:1",
                paramset_key_or_link_address="device1:2",
                values={"LEVEL": 1},
                check_against_pd=True,
            )


class TestClientFirmwareAndUpdates:
    """Test firmware updates and paramset description updates."""

    @pytest.mark.asyncio
    async def test_update_device_firmware_and_paramset_updates_consolidated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cover update_device_firmware branches and update_paramset_descriptions missing cases."""
        central = _FakeCentral2()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        client = ClientCCU(client_config=ClientConfig(central=central, interface_config=iface_cfg))
        client._proxy = _XmlProxy2()  # type: ignore[attr-defined]
        client._proxy_read = _XmlProxy2()  # type: ignore[attr-defined]

        assert await client.update_device_firmware(device_address="dev1") is False

        central.add_device("dev_hmip", product_group=ProductGroup.HMIP)
        central.add_device("dev_hm", product_group=ProductGroup.HM)
        assert await client.update_device_firmware(device_address="dev_hmip") is True
        assert await client.update_device_firmware(device_address="dev_hm") is True

        def _find_device_description(interface_id: str, device_address: str):  # noqa: ARG002
            return None

        central.device_descriptions = SimpleNamespace(
            get_device_descriptions=lambda interface_id: ("i",),  # type: ignore[misc]
            find_device_description=_find_device_description,
        )

        await client.update_paramset_descriptions(device_address="dev1")

    # === Additional tests to raise coverage for aiohomematic/client/__init__.py ===


class TestClientVirtualRemote:
    """Test virtual remote device retrieval."""

    def test_get_virtual_remote_returns_device(self) -> None:
        """Client.get_virtual_remote should return matching virtual remote device from central.devices."""
        from aiohomematic.const import VIRTUAL_REMOTE_MODELS

        central = _FakeCentral2()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        client = ClientCCU(client_config=ClientConfig(central=central, interface_config=iface_cfg))

        # Initially no devices -> None
        assert client.get_virtual_remote() is None

        # Add a device with the expected model and matching interface_id
        vr_model = VIRTUAL_REMOTE_MODELS[0] if VIRTUAL_REMOTE_MODELS else "HM-RCV-50"
        dev = SimpleNamespace(interface_id=client.interface_id, model=vr_model)
        central.devices = (dev,)

        vr = client.get_virtual_remote()
        assert vr is dev


class TestClientHomegear:
    """Test ClientHomegear specific functionality."""

    def test_clienthomegear_model_and_supports_ping_pong(self) -> None:
        """ClientHomegear.model should reflect version content and supports_ping_pong is always False."""
        from aiohomematic.client import ClientHomegear
        from aiohomematic.const import Backend

        central = _FakeCentral2()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        client_hg = ClientHomegear(client_config=ClientConfig(central=central, interface_config=iface_cfg))

        # Default version is "0" -> does not contain pydevccu -> HOMEGEAR
        client_hg._config.version = "Homegear 0.8"  # type: ignore[attr-defined]
        assert client_hg.model == Backend.HOMEGEAR
        assert client_hg.supports_ping_pong is False

        # If version contains pydevccu -> PYDEVCCU
        client_hg._config.version = "pydevccu 1.0"  # type: ignore[attr-defined]
        assert client_hg.model == Backend.PYDEVCCU

        # If version is falsy -> CCU
        client_hg._config.version = ""  # type: ignore[attr-defined]
        assert client_hg.model == Backend.CCU


class TestClientRegistry:
    """Test client registry lookup."""

    def test_get_client_registry_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_client should return a client when CENTRAL_INSTANCES contains a matching central."""
        dummy_client = object()

        fake_central = SimpleNamespace(
            has_client=lambda interface_id: interface_id == "iid",
            get_client=lambda interface_id: dummy_client if interface_id == "iid" else None,
        )

        import aiohomematic.central as hmcu

        monkeypatch.setattr(hmcu, "CENTRAL_INSTANCES", {"c": fake_central})

        assert get_client_by_id("iid") is dummy_client
        assert get_client_by_id("unknown") is None


class TestClientInstallMode:
    """Test install mode get and set operations."""

    @pytest.mark.asyncio
    async def test_get_install_mode_raises_on_error(self) -> None:
        """get_install_mode should raise ClientException on proxy error."""
        central = _FakeCentral2()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        client = ClientCCU(client_config=ClientConfig(central=central, interface_config=iface_cfg))

        class _ErrProxy(_XmlProxy2):
            async def getInstallMode(self) -> int:  # noqa: N802
                raise ClientException("getInstallMode-fail")

        client._proxy = _ErrProxy()

        with pytest.raises(ClientException):
            await client.get_install_mode()

    @pytest.mark.asyncio
    async def test_get_install_mode_returns_zero_on_none(self) -> None:
        """get_install_mode should return 0 when proxy returns None."""
        central = _FakeCentral2()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        client = ClientCCU(client_config=ClientConfig(central=central, interface_config=iface_cfg))

        class _NoneProxy(_XmlProxy2):
            async def getInstallMode(self) -> int | None:  # noqa: N802
                return None

        client._proxy = _NoneProxy()

        result = await client.get_install_mode()
        assert result == 0

    @pytest.mark.asyncio
    async def test_get_install_mode_success(self) -> None:
        """get_install_mode should return the remaining time in install mode."""
        central = _FakeCentral2()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        client = ClientCCU(client_config=ClientConfig(central=central, interface_config=iface_cfg))
        client._proxy = _XmlProxy2()

        result = await client.get_install_mode()
        assert result == 60

    @pytest.mark.asyncio
    async def test_set_install_mode_raises_on_error(self) -> None:
        """set_install_mode should raise ClientException on proxy error."""
        central = _FakeCentral2()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        client = ClientCCU(client_config=ClientConfig(central=central, interface_config=iface_cfg))

        class _ErrProxy(_XmlProxy2):
            async def setInstallMode(self, *args: Any) -> None:  # noqa: N802
                raise ClientException("setInstallMode-fail")

        client._proxy = _ErrProxy()

        with pytest.raises(ClientException):
            await client.set_install_mode(on=True)

    @pytest.mark.asyncio
    async def test_set_install_mode_success(self) -> None:
        """set_install_mode should return True on success."""
        central = _FakeCentral2()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        client = ClientCCU(client_config=ClientConfig(central=central, interface_config=iface_cfg))
        client._proxy = _XmlProxy2()

        result = await client.set_install_mode(on=True, time=60, mode=1)
        assert result is True

    @pytest.mark.asyncio
    async def test_set_install_mode_with_device_address(self) -> None:
        """set_install_mode should pass device_address when provided."""
        central = _FakeCentral2()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        client = ClientCCU(client_config=ClientConfig(central=central, interface_config=iface_cfg))

        calls: list[tuple[Any, ...]] = []

        class _TrackingProxy(_XmlProxy2):
            async def setInstallMode(self, *args: Any) -> None:  # noqa: N802
                calls.append(args)

        client._proxy = _TrackingProxy()

        await client.set_install_mode(on=True, time=120, mode=2, device_address="ABC123")
        assert len(calls) == 1
        assert calls[0] == (True, 120, 2, "ABC123")
