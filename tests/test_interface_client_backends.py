# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Tests for InterfaceClient backend-specific behavior.

These tests verify that InterfaceClient correctly handles:
- Different backend capability configurations (CCU, Homegear, CCU-Jack)
- Capability-gated feature access
- Backend-specific behaviors
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from aiohomematic.client import InterfaceClient, InterfaceConfig
from aiohomematic.const import DEFAULT_TIMEOUT_CONFIG, Interface, ParamsetKey, ServiceMessageType


class _FakeEventBus:
    """Minimal fake EventBus for testing."""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, *, event: Any) -> None:
        self.published_events.append(event)

    def publish_sync(self, *, event: Any) -> None:
        self.published_events.append(event)

    def subscribe(self, *, event_type: Any, event_key: Any, handler: Any) -> Any:
        return lambda: None


class _FakeParamsetDescriptions:
    """Minimal paramset descriptions for testing."""

    def __init__(self) -> None:
        self._raw_paramset_descriptions: dict[str, Any] = {}

    def get_parameter_data(
        self, *, interface_id: str, channel_address: str, paramset_key: ParamsetKey, parameter: str
    ) -> dict[str, Any] | None:
        return None


class _FakeDeviceDescriptions:
    """Minimal device descriptions for testing."""

    def __init__(self) -> None:
        self._device_descriptions: dict[str, dict[str, Any]] = {}

    def get_device_descriptions(self, *, interface_id: str) -> dict[str, Any] | None:
        return self._device_descriptions.get(interface_id, {})


class _FakeCentral:
    """Minimal CentralUnit-like object for backend testing."""

    def __init__(self) -> None:
        self._event_bus = _FakeEventBus()
        self.paramset_descriptions = _FakeParamsetDescriptions()
        self.device_descriptions = _FakeDeviceDescriptions()
        self._devices: dict[str, Any] = {}
        self.name = "test-central"

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
            timeout_config = DEFAULT_TIMEOUT_CONFIG

        self.config = Cfg()
        self._listen_port_xml_rpc = 32001
        self._callback_ip_addr = "127.0.0.1"

        def _close_task(*, target: Any, name: str) -> None:
            target.close()

        self.looper = SimpleNamespace(create_task=_close_task)
        self.json_rpc_client = SimpleNamespace(
            clear_session=lambda: None,
            circuit_breaker=SimpleNamespace(reset=lambda: None),
        )

        class _ConnectionState:
            pass

        self.connection_state = _ConnectionState()

    @property
    def cache_coordinator(self) -> Any:
        return SimpleNamespace(
            device_details=SimpleNamespace(
                add_interface=lambda **kwargs: None,
                add_name=lambda **kwargs: None,
                add_address_rega_id=lambda **kwargs: None,
            ),
            paramset_descriptions=self.paramset_descriptions,
            data_cache=SimpleNamespace(add_data=lambda **kwargs: None),
            device_descriptions=self.device_descriptions,
            incident_store=None,
        )

    @property
    def callback_ip_addr(self) -> str:
        return self._callback_ip_addr

    @property
    def device_coordinator(self) -> Any:
        return self

    @property
    def device_registry(self) -> Any:
        return SimpleNamespace(devices=tuple(self._devices.values()))

    @property
    def event_bus(self) -> Any:
        return self._event_bus

    @property
    def event_coordinator(self) -> Any:
        return SimpleNamespace(
            get_last_event_seen_for_interface=lambda *, interface_id: datetime.now(),
        )

    @property
    def listen_port_xml_rpc(self) -> int:
        return self._listen_port_xml_rpc

    def add_device(self, addr: str) -> None:
        self._devices[addr] = SimpleNamespace(
            interface_id="test-BidCos-RF",
            rx_modes=(),
            set_forced_availability=lambda **kwargs: None,
        )


def _make_capabilities(
    *,
    backup: bool = True,
    device_firmware_update: bool = True,
    firmware_update_trigger: bool = True,
    firmware_updates: bool = True,
    functions: bool = True,
    inbox_devices: bool = True,
    install_mode: bool = True,
    linking: bool = True,
    metadata: bool = True,
    ping_pong: bool = True,
    programs: bool = True,
    push_updates: bool = True,
    rega_id_lookup: bool = True,
    rename: bool = True,
    rooms: bool = True,
    rpc_callback: bool = True,
    service_messages: bool = True,
    system_update_info: bool = True,
    value_usage_reporting: bool = True,
) -> SimpleNamespace:
    """Create a capabilities object with all fields."""
    return SimpleNamespace(
        backup=backup,
        device_firmware_update=device_firmware_update,
        firmware_update_trigger=firmware_update_trigger,
        firmware_updates=firmware_updates,
        functions=functions,
        inbox_devices=inbox_devices,
        install_mode=install_mode,
        linking=linking,
        metadata=metadata,
        ping_pong=ping_pong,
        programs=programs,
        push_updates=push_updates,
        rega_id_lookup=rega_id_lookup,
        rename=rename,
        rooms=rooms,
        rpc_callback=rpc_callback,
        service_messages=service_messages,
        system_update_info=system_update_info,
        value_usage_reporting=value_usage_reporting,
    )


# Standard capability configurations for different backends
CCU_CAPABILITIES = _make_capabilities(
    # CCU has all capabilities
)

HOMEGEAR_CAPABILITIES = _make_capabilities(
    backup=False,  # Homegear doesn't support backup
    device_firmware_update=False,  # No firmware updates
    firmware_update_trigger=False,
    firmware_updates=False,
    functions=False,  # No function/room metadata
    inbox_devices=False,  # No inbox
    programs=False,  # No programs
    rega_id_lookup=False,  # No ReGa
    rooms=False,
    service_messages=False,  # No service messages
    system_update_info=False,
)

JSON_CCU_CAPABILITIES = _make_capabilities(
    ping_pong=False,  # No ping/pong for CUxD/CCU-Jack
    rpc_callback=False,  # No XML-RPC callback
)


class _FakeBackend:
    """Configurable fake backend for testing capability gating."""

    def __init__(
        self,
        *,
        interface_id: str = "test-BidCos-RF",
        interface: Interface = Interface.BIDCOS_RF,
        model: str = "CCU",
        capabilities: SimpleNamespace | None = None,
    ) -> None:
        self.interface_id = interface_id
        self.interface = interface
        self.model = model
        self.capabilities = capabilities or CCU_CAPABILITIES
        self.system_information = SimpleNamespace(
            available_interfaces=(interface,),
            serial="TEST1234",
            has_backup=self.capabilities.backup,
        )
        self.all_circuit_breakers_closed = True
        self.circuit_breaker = MagicMock()
        self.calls: list[tuple[str, Any]] = []

        # Configurable return values
        self._rooms_result: dict[str, set[str]] = {}
        self._functions_result: dict[str, set[str]] = {}
        self._programs_result: tuple[Any, ...] = ()
        self._service_messages_result: tuple[Any, ...] = ()
        self._system_update_result: Any = None
        self._inbox_devices_result: tuple[Any, ...] = ()

    async def accept_device_in_inbox(self, *, device_address: str) -> bool:
        self.calls.append(("accept_device_in_inbox", device_address))
        return True

    async def add_link(self, *, sender_address: str, receiver_address: str, name: str, description: str) -> None:
        self.calls.append(("add_link", (sender_address, receiver_address, name, description)))

    async def check_connection(self, *, handle_ping_pong: bool, caller_id: str | None = None) -> bool:
        self.calls.append(("check_connection", (handle_ping_pong, caller_id)))
        return True

    async def create_backup_and_download(self, *, max_wait_time: float, poll_interval: float) -> Any:
        self.calls.append(("create_backup_and_download", (max_wait_time, poll_interval)))
        return None

    async def deinit_proxy(self, *, init_url: str) -> bool:
        self.calls.append(("deinit_proxy", init_url))
        return True

    async def execute_program(self, *, pid: str) -> bool:
        self.calls.append(("execute_program", pid))
        return True

    async def get_all_functions(self) -> dict[str, set[str]]:
        self.calls.append(("get_all_functions", None))
        return self._functions_result

    async def get_all_programs(self, *, markers: tuple[Any, ...]) -> tuple[Any, ...]:
        self.calls.append(("get_all_programs", markers))
        return self._programs_result

    async def get_all_rooms(self) -> dict[str, set[str]]:
        self.calls.append(("get_all_rooms", None))
        return self._rooms_result

    async def get_inbox_devices(self) -> tuple[Any, ...]:
        self.calls.append(("get_inbox_devices", None))
        return self._inbox_devices_result

    async def get_install_mode(self) -> int:
        self.calls.append(("get_install_mode", None))
        return 0

    async def get_link_peers(self, *, address: str) -> tuple[str, ...]:
        self.calls.append(("get_link_peers", address))
        return ()

    async def get_links(self, *, address: str, flags: int) -> dict[str, Any]:
        self.calls.append(("get_links", (address, flags)))
        return {}

    async def get_metadata(self, *, address: str, data_id: str) -> dict[str, Any]:
        self.calls.append(("get_metadata", (address, data_id)))
        return {}

    async def get_rega_id_by_address(self, *, address: str) -> int | None:
        self.calls.append(("get_rega_id_by_address", address))
        return None

    async def get_service_messages(self, *, message_type: ServiceMessageType | None) -> tuple[Any, ...]:
        self.calls.append(("get_service_messages", message_type))
        return self._service_messages_result

    async def get_system_update_info(self) -> Any:
        self.calls.append(("get_system_update_info", None))
        return self._system_update_result

    async def has_program_ids(self, *, rega_id: int) -> bool:
        self.calls.append(("has_program_ids", rega_id))
        return False

    async def init_proxy(self, *, init_url: str, interface_id: str) -> bool:
        self.calls.append(("init_proxy", (init_url, interface_id)))
        return True

    async def list_devices(self) -> tuple[dict[str, Any], ...] | None:
        self.calls.append(("list_devices", None))
        return ()

    async def stop(self) -> None:
        pass


def _create_client_with_capabilities(
    capabilities: SimpleNamespace,
    interface: Interface = Interface.BIDCOS_RF,
) -> tuple[InterfaceClient, _FakeBackend, _FakeCentral]:
    """Create an InterfaceClient with specific capabilities."""
    central = _FakeCentral()
    backend = _FakeBackend(capabilities=capabilities, interface=interface)

    iface_cfg = InterfaceConfig(central_name="test", interface=interface, port=32001)

    client = InterfaceClient(
        backend=backend,  # type: ignore[arg-type]
        central=central,  # type: ignore[arg-type]
        interface_config=iface_cfg,
        version="2.0",
    )

    return client, backend, central


class TestBackendCapabilityGating:
    """Test capability-gated feature access."""

    @pytest.mark.asyncio
    async def test_accept_device_in_inbox_capability_disabled(self) -> None:
        """accept_device_in_inbox should return False when capability disabled."""
        caps = _make_capabilities(inbox_devices=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        result = await client.accept_device_in_inbox(device_address="dev1")

        assert result is False
        assert not any(call[0] == "accept_device_in_inbox" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_add_link_capability_disabled(self) -> None:
        """add_link should return early when linking capability disabled."""
        caps = _make_capabilities(linking=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        await client.add_link(
            sender_address="dev1:1",
            receiver_address="dev2:1",
            name="Test Link",
            description="Test",
        )

        assert not any(call[0] == "add_link" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_create_backup_capability_disabled(self) -> None:
        """create_backup_and_download should return None when capability disabled."""
        caps = _make_capabilities(backup=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        result = await client.create_backup_and_download()

        assert result is None
        assert not any(call[0] == "create_backup_and_download" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_execute_program_capability_disabled(self) -> None:
        """execute_program should return False when programs capability disabled."""
        caps = _make_capabilities(programs=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        result = await client.execute_program(pid="prog123")

        assert result is False
        assert not any(call[0] == "execute_program" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_get_all_functions_capability_disabled(self) -> None:
        """get_all_functions should return empty when functions capability disabled."""
        caps = _make_capabilities(functions=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        result = await client.get_all_functions()

        assert result == {}
        assert not any(call[0] == "get_all_functions" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_get_all_functions_capability_enabled(self) -> None:
        """get_all_functions should call backend when capability enabled."""
        caps = _make_capabilities(functions=True)
        client, backend, _ = _create_client_with_capabilities(caps)
        backend._functions_result = {"Light": {"dev1:1"}}

        result = await client.get_all_functions()

        assert result == {"Light": {"dev1:1"}}
        assert any(call[0] == "get_all_functions" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_get_all_programs_capability_disabled(self) -> None:
        """get_all_programs should return empty when programs capability disabled."""
        caps = _make_capabilities(programs=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        result = await client.get_all_programs(markers=())

        assert result == ()
        assert not any(call[0] == "get_all_programs" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_get_all_rooms_capability_disabled(self) -> None:
        """get_all_rooms should return empty when rooms capability disabled."""
        caps = _make_capabilities(rooms=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        result = await client.get_all_rooms()

        assert result == {}
        # Backend should NOT have been called
        assert not any(call[0] == "get_all_rooms" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_get_all_rooms_capability_enabled(self) -> None:
        """get_all_rooms should call backend when capability enabled."""
        caps = _make_capabilities(rooms=True)
        client, backend, _ = _create_client_with_capabilities(caps)
        backend._rooms_result = {"Living Room": {"dev1:1", "dev2:1"}}

        result = await client.get_all_rooms()

        assert result == {"Living Room": {"dev1:1", "dev2:1"}}
        assert any(call[0] == "get_all_rooms" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_get_inbox_devices_capability_disabled(self) -> None:
        """get_inbox_devices should return empty when capability disabled."""
        caps = _make_capabilities(inbox_devices=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        result = await client.get_inbox_devices()

        assert result == ()
        assert not any(call[0] == "get_inbox_devices" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_get_install_mode_capability_disabled(self) -> None:
        """get_install_mode should return 0 when capability disabled."""
        caps = _make_capabilities(install_mode=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        result = await client.get_install_mode()

        assert result == 0
        assert not any(call[0] == "get_install_mode" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_get_link_peers_capability_disabled(self) -> None:
        """get_link_peers should return empty when linking capability disabled."""
        caps = _make_capabilities(linking=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        result = await client.get_link_peers(channel_address="dev1:1")

        assert result == ()
        assert not any(call[0] == "get_link_peers" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_get_metadata_capability_disabled(self) -> None:
        """get_metadata should return empty when capability disabled."""
        caps = _make_capabilities(metadata=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        result = await client.get_metadata(address="dev1", data_id="NAME")

        assert result == {}
        assert not any(call[0] == "get_metadata" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_get_rega_id_capability_disabled(self) -> None:
        """get_rega_id_by_address should return None when capability disabled."""
        caps = _make_capabilities(rega_id_lookup=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        result = await client.get_rega_id_by_address(address="dev1:1")

        assert result is None
        assert not any(call[0] == "get_rega_id_by_address" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_get_service_messages_capability_disabled(self) -> None:
        """get_service_messages should return empty when capability disabled."""
        caps = _make_capabilities(service_messages=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        result = await client.get_service_messages()

        assert result == ()
        assert not any(call[0] == "get_service_messages" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_get_system_update_info_capability_disabled(self) -> None:
        """get_system_update_info should return None when capability disabled."""
        caps = _make_capabilities(system_update_info=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        result = await client.get_system_update_info()

        assert result is None
        assert not any(call[0] == "get_system_update_info" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_has_program_ids_capability_disabled(self) -> None:
        """has_program_ids should return False when capability disabled."""
        caps = _make_capabilities(programs=False)
        client, backend, _ = _create_client_with_capabilities(caps)

        result = await client.has_program_ids(rega_id=12345)

        assert result is False
        assert not any(call[0] == "has_program_ids" for call in backend.calls)


class TestCCUBackendBehavior:
    """Test CCU-specific backend behavior."""

    def test_ccu_capabilities(self) -> None:
        """CCU should have all standard capabilities enabled."""
        client, backend, _ = _create_client_with_capabilities(CCU_CAPABILITIES)

        assert client.capabilities.backup is True
        assert client.capabilities.programs is True
        assert client.capabilities.rooms is True
        assert client.capabilities.functions is True
        assert client.capabilities.ping_pong is True
        assert client.capabilities.rpc_callback is True

    def test_ccu_model_property(self) -> None:
        """CCU model should be reported correctly."""
        client, backend, _ = _create_client_with_capabilities(CCU_CAPABILITIES)

        assert client.model == "CCU"


class TestHomegearBackendBehavior:
    """Test Homegear-specific backend behavior."""

    def test_homegear_capabilities(self) -> None:
        """Homegear should have limited capabilities."""
        client, backend, _ = _create_client_with_capabilities(HOMEGEAR_CAPABILITIES)

        assert client.capabilities.backup is False
        assert client.capabilities.programs is False
        assert client.capabilities.rooms is False
        assert client.capabilities.functions is False
        # But still has ping_pong and rpc_callback
        assert client.capabilities.ping_pong is True
        assert client.capabilities.rpc_callback is True

    @pytest.mark.asyncio
    async def test_homegear_skips_metadata_features(self) -> None:
        """Homegear should skip metadata features gracefully."""
        client, backend, _ = _create_client_with_capabilities(HOMEGEAR_CAPABILITIES)

        # These should all return empty/default without calling backend
        assert await client.get_all_rooms() == {}
        assert await client.get_all_functions() == {}
        assert await client.get_all_programs(markers=()) == ()

        # No backend calls for these features
        assert len(backend.calls) == 0


class TestJsonCCUBackendBehavior:
    """Test JSON CCU (CUxD/CCU-Jack) specific backend behavior."""

    def test_json_ccu_is_callback_alive_always_true(self) -> None:
        """JSON CCU is_callback_alive should always return True (no ping_pong)."""
        client, backend, _ = _create_client_with_capabilities(JSON_CCU_CAPABILITIES)

        # Without ping_pong, is_callback_alive always returns True
        assert client.is_callback_alive() is True

    def test_json_ccu_no_ping_pong(self) -> None:
        """JSON CCU should not support ping_pong."""
        client, backend, _ = _create_client_with_capabilities(JSON_CCU_CAPABILITIES)

        assert client.capabilities.ping_pong is False

    def test_json_ccu_no_rpc_callback(self) -> None:
        """JSON CCU should not support RPC callback."""
        client, backend, _ = _create_client_with_capabilities(JSON_CCU_CAPABILITIES)

        assert client.capabilities.rpc_callback is False


class TestProductGroupDetection:
    """Test product group detection based on model and interface."""

    def test_product_group_case_insensitive(self) -> None:
        """Product group detection should be case-insensitive."""
        client, backend, _ = _create_client_with_capabilities(CCU_CAPABILITIES)

        from aiohomematic.const import ProductGroup

        assert client.get_product_group(model="hmip-bwth") == ProductGroup.HMIP
        assert client.get_product_group(model="HMIP-BWTH") == ProductGroup.HMIP
        assert client.get_product_group(model="HmIP-BWTH") == ProductGroup.HMIP

    def test_product_group_from_interface_bidcos_wired(self) -> None:
        """Unknown model on BidCos-Wired should return HMW."""
        client, backend, _ = _create_client_with_capabilities(CCU_CAPABILITIES, interface=Interface.BIDCOS_WIRED)

        from aiohomematic.const import ProductGroup

        result = client.get_product_group(model="UNKNOWN-MODEL")
        assert result == ProductGroup.HMW

    def test_product_group_from_interface_hmip(self) -> None:
        """Unknown model on HMIP interface should return HMIP."""
        client, backend, _ = _create_client_with_capabilities(CCU_CAPABILITIES, interface=Interface.HMIP_RF)

        from aiohomematic.const import ProductGroup

        result = client.get_product_group(model="UNKNOWN-MODEL")
        assert result == ProductGroup.HMIP

    def test_product_group_hm(self) -> None:
        """HM model should return HM product group."""
        client, backend, _ = _create_client_with_capabilities(CCU_CAPABILITIES)

        from aiohomematic.const import ProductGroup

        result = client.get_product_group(model="HM-LC-Sw1-FM")
        assert result == ProductGroup.HM

    def test_product_group_hmip(self) -> None:
        """HmIP model should return HMIP product group."""
        client, backend, _ = _create_client_with_capabilities(CCU_CAPABILITIES)

        from aiohomematic.const import ProductGroup

        result = client.get_product_group(model="HmIP-BWTH")
        assert result == ProductGroup.HMIP

    def test_product_group_hmipw(self) -> None:
        """HmIPW model should return HMIPW product group."""
        client, backend, _ = _create_client_with_capabilities(CCU_CAPABILITIES)

        from aiohomematic.const import ProductGroup

        result = client.get_product_group(model="HmIPW-DRD3")
        assert result == ProductGroup.HMIPW

    def test_product_group_hmw(self) -> None:
        """HMW model should return HMW product group."""
        client, backend, _ = _create_client_with_capabilities(CCU_CAPABILITIES)

        from aiohomematic.const import ProductGroup

        result = client.get_product_group(model="HMW-IO-12-Sw7-DR")
        assert result == ProductGroup.HMW


class TestInterfaceClientSystemInformation:
    """Test system information access."""

    def test_interface_id_property(self) -> None:
        """interface_id should be derived from backend."""
        client, backend, _ = _create_client_with_capabilities(CCU_CAPABILITIES)

        assert client.interface_id == backend.interface_id

    def test_interface_property(self) -> None:
        """Interface property should return the correct interface type."""
        client, _, _ = _create_client_with_capabilities(CCU_CAPABILITIES, interface=Interface.HMIP_RF)

        assert client.interface == Interface.HMIP_RF

    def test_system_information_property(self) -> None:
        """system_information should return backend's system information."""
        client, backend, _ = _create_client_with_capabilities(CCU_CAPABILITIES)

        assert client.system_information.serial == "TEST1234"
        assert client.system_information.has_backup is True
        assert Interface.BIDCOS_RF in client.system_information.available_interfaces

    def test_version_property(self) -> None:
        """Version should return the configured version."""
        client, _, _ = _create_client_with_capabilities(CCU_CAPABILITIES)

        assert client.version == "2.0"
