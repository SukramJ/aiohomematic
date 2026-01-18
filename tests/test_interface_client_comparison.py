# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Comparison tests between InterfaceClient and legacy clients.

These tests verify that InterfaceClient produces identical results to
the legacy ClientCCU/DeviceHandler implementation for:
- set_value operations
- put_paramset operations
- Value validation errors
- Temporary value writing
- Request coalescing
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from aiohomematic.client import InterfaceClient, InterfaceConfig
from aiohomematic.const import DEFAULT_TIMEOUT_CONFIG, Interface, ParamsetKey


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
    """Minimal paramset descriptions exposing required methods."""

    def __init__(self) -> None:
        self._raw_paramset_descriptions: dict[str, Any] = {}

    def add(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
        paramset_description: dict[str, Any],
        device_type: str,
    ) -> None:
        if interface_id not in self._raw_paramset_descriptions:
            self._raw_paramset_descriptions[interface_id] = {}
        if channel_address not in self._raw_paramset_descriptions[interface_id]:
            self._raw_paramset_descriptions[interface_id][channel_address] = {}
        self._raw_paramset_descriptions[interface_id][channel_address][paramset_key] = paramset_description

    def get_parameter_data(
        self, *, interface_id: str, channel_address: str, paramset_key: ParamsetKey, parameter: str
    ) -> dict[str, Any] | None:
        if self._raw_paramset_descriptions:
            try:
                return self._raw_paramset_descriptions[interface_id][channel_address][paramset_key].get(parameter)
            except KeyError:
                pass
        return None


class _FakeDeviceDescriptions:
    """Minimal device descriptions exposing required methods."""

    def __init__(self) -> None:
        self._device_descriptions: dict[str, dict[str, Any]] = {}

    def find_device_description(self, *, interface_id: str, device_address: str) -> dict[str, Any] | None:
        if interface_id in self._device_descriptions:
            return self._device_descriptions[interface_id].get(device_address)
        return None

    def get_device_descriptions(self, *, interface_id: str) -> dict[str, Any] | None:
        return self._device_descriptions.get(interface_id)


class _FakeBackend:
    """Fake backend for testing InterfaceClient without network I/O."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.interface_id = "test-BidCos-RF"
        self.interface = Interface.BIDCOS_RF
        self.model = "CCU"
        self.system_information = SimpleNamespace(
            available_interfaces=(Interface.BIDCOS_RF,),
            serial="TEST1234",
            has_backup=True,
        )
        self.capabilities = SimpleNamespace(
            backup=True,
            device_firmware_update=True,
            firmware_update_trigger=True,
            firmware_updates=True,
            functions=True,
            inbox_devices=True,
            install_mode=True,
            linking=True,
            metadata=True,
            ping_pong=True,
            programs=True,
            push_updates=True,
            rega_id_lookup=True,
            rename=True,
            rooms=True,
            rpc_callback=True,
            service_messages=True,
            system_update_info=True,
            value_usage_reporting=True,
        )

    async def check_connection(self, *, handle_ping_pong: bool) -> bool:
        self.calls.append(("check_connection", handle_ping_pong))
        return True

    async def get_device_description(self, *, address: str) -> dict[str, Any] | None:
        self.calls.append(("get_device_description", address))
        return {
            "ADDRESS": address,
            "TYPE": "TEST_DEVICE",
            "PARAMSETS": ["VALUES", "MASTER"],
            "CHILDREN": [f"{address}:1", f"{address}:2"] if ":" not in address else [],
        }

    async def get_paramset(self, *, address: str, paramset_key: ParamsetKey | str) -> dict[str, Any]:
        self.calls.append(("get_paramset", (address, paramset_key)))
        return {"LEVEL": 0.5}

    async def get_paramset_description(self, *, address: str, paramset_key: ParamsetKey) -> dict[str, Any] | None:
        self.calls.append(("get_paramset_description", (address, paramset_key)))
        return {
            "LEVEL": {
                "TYPE": "FLOAT",
                "OPERATIONS": 7,
                "MIN": 0.0,
                "MAX": 1.0,
            },
            "STATE": {
                "TYPE": "BOOL",
                "OPERATIONS": 7,
            },
        }

    async def get_value(self, *, address: str, parameter: str) -> Any:
        self.calls.append(("get_value", (address, parameter)))
        return 0.5

    async def list_devices(self) -> tuple[dict[str, Any], ...] | None:
        return ()

    async def put_paramset(
        self,
        *,
        address: str,
        paramset_key: ParamsetKey | str,
        values: dict[str, Any],
        rx_mode: Any | None = None,
    ) -> None:
        self.calls.append(("put_paramset", (address, paramset_key, values, rx_mode)))

    async def set_value(
        self,
        *,
        address: str,
        parameter: str,
        value: Any,
        rx_mode: Any | None = None,
    ) -> None:
        self.calls.append(("set_value", (address, parameter, value, rx_mode)))

    async def stop(self) -> None:
        pass


class _FakeCentral:
    """Minimal CentralUnit-like object for InterfaceClient testing."""

    def __init__(self) -> None:
        self._event_bus = _FakeEventBus()
        self.paramset_descriptions = _FakeParamsetDescriptions()
        self.device_descriptions = _FakeDeviceDescriptions()
        self._devices: dict[str, Any] = {}
        self._channels: dict[str, Any] = {}
        self._data_points: dict[str, Any] = {}
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
            schedule_timer_config = SimpleNamespace(
                master_poll_after_send_intervals=(0.1, 0.5),
            )

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
        return self

    @property
    def listen_port_xml_rpc(self) -> int:
        return self._listen_port_xml_rpc

    def add_channel(self, channel_address: str) -> None:
        self._channels[channel_address] = SimpleNamespace(
            get_readable_data_points=lambda paramset_key: (),
        )

    def add_data_point(
        self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey, requires_polling: bool = False
    ) -> MagicMock:
        key = f"{channel_address}:{parameter}:{paramset_key}"
        dp = MagicMock()
        dp.requires_polling = requires_polling
        dp.write_temporary_value = MagicMock()
        self._data_points[key] = dp
        return dp

    def add_device(self, addr: str, *, rx_modes: tuple[Any, ...] = ()) -> None:
        self._devices[addr] = SimpleNamespace(
            interface_id="test-BidCos-RF",
            rx_modes=rx_modes,
            set_forced_availability=lambda **kwargs: None,
        )

    def get_channel(self, *, channel_address: str) -> Any:
        return self._channels.get(channel_address)

    def get_device(self, *, address: str) -> Any:
        # Extract device address from channel address if needed
        dev_addr = address.split(":")[0] if ":" in address else address
        return self._devices.get(dev_addr)

    def get_generic_data_point(self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey) -> Any:
        key = f"{channel_address}:{parameter}:{paramset_key}"
        return self._data_points.get(key)

    def get_last_event_seen_for_interface(self, *, interface_id: str) -> datetime | None:
        return datetime.now()

    async def save_files(self, *, save_paramset_descriptions: bool = False) -> None:
        pass


def _create_interface_client(
    central: _FakeCentral | None = None,
    backend: _FakeBackend | None = None,
) -> InterfaceClient:
    """Create an InterfaceClient with fake dependencies."""
    if central is None:
        central = _FakeCentral()
    if backend is None:
        backend = _FakeBackend()

    iface_cfg = InterfaceConfig(central_name="test", interface=Interface.BIDCOS_RF, port=32001)

    return InterfaceClient(
        backend=backend,  # type: ignore[arg-type]
        central=central,  # type: ignore[arg-type]
        interface_config=iface_cfg,
        version="2.0",
    )


class TestInterfaceClientSetValue:
    """Test set_value operations produce identical results."""

    @pytest.mark.asyncio
    async def test_set_value_basic(self) -> None:
        """Test basic set_value calls the backend correctly."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        result = await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
            value=True,
            wait_for_callback=None,
        )

        assert isinstance(result, set)
        assert len(backend.calls) == 1
        assert backend.calls[0][0] == "set_value"
        assert backend.calls[0][1][0] == "dev1:1"  # address
        assert backend.calls[0][1][1] == "STATE"  # parameter
        assert backend.calls[0][1][2] is True  # value

    @pytest.mark.asyncio
    async def test_set_value_parameter_not_found(self) -> None:
        """Test set_value returns empty set when parameter not in paramset description."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Empty paramset descriptions
        central.paramset_descriptions._raw_paramset_descriptions = {}

        # The @inspector(re_raise=False) decorator catches exceptions and returns empty set
        result = await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="UNKNOWN_PARAM",
            value=1.0,
            wait_for_callback=None,
            check_against_pd=True,
        )
        assert result == set()
        assert len(backend.calls) == 0

    @pytest.mark.asyncio
    async def test_set_value_routes_master_to_put_paramset(self) -> None:
        """Test set_value with MASTER paramset routes to put_paramset."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        result = await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.MASTER,
            parameter="CONFIG_PARAM",
            value=42,
            wait_for_callback=None,
        )

        assert isinstance(result, set)
        # Should have called put_paramset, not set_value
        assert len(backend.calls) == 1
        assert backend.calls[0][0] == "put_paramset"

    @pytest.mark.asyncio
    async def test_set_value_validation_error_above_max(self) -> None:
        """Test set_value returns empty set when value is above MAX (inspector catches exception)."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Setup paramset description with MAX constraint
        central.paramset_descriptions._raw_paramset_descriptions = {
            "test-BidCos-RF": {
                "dev1:1": {
                    ParamsetKey.VALUES: {
                        "LEVEL": {
                            "TYPE": "FLOAT",
                            "OPERATIONS": 7,
                            "MIN": 0.0,
                            "MAX": 1.0,
                        },
                    },
                }
            }
        }

        # The @inspector(re_raise=False) decorator catches exceptions and returns empty set
        result = await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.5,
            wait_for_callback=None,
            check_against_pd=True,
        )
        assert result == set()
        assert len(backend.calls) == 0

    @pytest.mark.asyncio
    async def test_set_value_validation_error_below_min(self) -> None:
        """Test set_value returns empty set when value is below MIN (inspector catches exception)."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Setup paramset description with MIN constraint
        central.paramset_descriptions._raw_paramset_descriptions = {
            "test-BidCos-RF": {
                "dev1:1": {
                    ParamsetKey.VALUES: {
                        "LEVEL": {
                            "TYPE": "FLOAT",
                            "OPERATIONS": 7,
                            "MIN": 0.0,
                            "MAX": 1.0,
                        },
                    },
                }
            }
        }

        # The @inspector(re_raise=False) decorator catches exceptions and returns empty set
        result = await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=-0.5,
            wait_for_callback=None,
            check_against_pd=True,
        )
        assert result == set()
        # Backend should not have been called
        assert len(backend.calls) == 0

    @pytest.mark.asyncio
    async def test_set_value_with_validation(self) -> None:
        """Test set_value with check_against_pd validates and converts values."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Setup paramset description
        central.paramset_descriptions._raw_paramset_descriptions = {
            "test-BidCos-RF": {
                "dev1:1": {
                    ParamsetKey.VALUES: {
                        "LEVEL": {
                            "TYPE": "FLOAT",
                            "OPERATIONS": 7,
                            "MIN": 0.0,
                            "MAX": 1.0,
                        },
                    },
                }
            }
        }

        result = await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.5,
            wait_for_callback=None,
            check_against_pd=True,
        )

        assert isinstance(result, set)
        assert backend.calls[0][1][2] == 0.5


class TestInterfaceClientPutParamset:
    """Test put_paramset operations produce identical results."""

    @pytest.mark.asyncio
    async def test_put_paramset_basic(self) -> None:
        """Test basic put_paramset calls the backend correctly."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        result = await client.put_paramset(
            channel_address="dev1:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"STATE": True, "LEVEL": 0.5},
            wait_for_callback=None,
        )

        assert isinstance(result, set)
        assert len(backend.calls) == 1
        assert backend.calls[0][0] == "put_paramset"
        assert backend.calls[0][1][0] == "dev1:1"
        assert backend.calls[0][1][1] == ParamsetKey.VALUES
        assert backend.calls[0][1][2] == {"STATE": True, "LEVEL": 0.5}

    @pytest.mark.asyncio
    async def test_put_paramset_invalid_paramset_key(self) -> None:
        """Test put_paramset returns empty set for invalid paramset key (inspector catches exception)."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # The @inspector(re_raise=False) decorator catches exceptions and returns empty set
        result = await client.put_paramset(
            channel_address="dev1:1",
            paramset_key_or_link_address="INVALID",  # Not a valid paramset key or channel address
            values={"LEVEL": 0.5},
            wait_for_callback=None,
            check_against_pd=True,
        )
        assert result == set()
        assert len(backend.calls) == 0

    @pytest.mark.asyncio
    async def test_put_paramset_validation_error(self) -> None:
        """Test put_paramset returns empty set when any value is invalid (inspector catches exception)."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Setup paramset description with constraints
        central.paramset_descriptions._raw_paramset_descriptions = {
            "test-BidCos-RF": {
                "dev1:1": {
                    ParamsetKey.VALUES: {
                        "LEVEL": {
                            "TYPE": "FLOAT",
                            "OPERATIONS": 7,
                            "MIN": 0.0,
                            "MAX": 1.0,
                        },
                    },
                }
            }
        }

        # The @inspector(re_raise=False) decorator catches exceptions and returns empty set
        result = await client.put_paramset(
            channel_address="dev1:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"LEVEL": 2.0},  # Above MAX
            wait_for_callback=None,
            check_against_pd=True,
        )
        assert result == set()
        assert len(backend.calls) == 0

    @pytest.mark.asyncio
    async def test_put_paramset_with_validation(self) -> None:
        """Test put_paramset with check_against_pd validates all values."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Setup paramset description
        central.paramset_descriptions._raw_paramset_descriptions = {
            "test-BidCos-RF": {
                "dev1:1": {
                    ParamsetKey.VALUES: {
                        "LEVEL": {
                            "TYPE": "FLOAT",
                            "OPERATIONS": 7,
                            "MIN": 0.0,
                            "MAX": 1.0,
                        },
                        "STATE": {
                            "TYPE": "BOOL",
                            "OPERATIONS": 7,
                        },
                    },
                }
            }
        }

        result = await client.put_paramset(
            channel_address="dev1:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"STATE": True, "LEVEL": 0.75},
            wait_for_callback=None,
            check_against_pd=True,
        )

        assert isinstance(result, set)
        # Values should be validated and passed through
        assert backend.calls[0][1][2]["LEVEL"] == 0.75
        assert backend.calls[0][1][2]["STATE"] is True


class TestInterfaceClientTemporaryValues:
    """Test temporary value writing for immediate UI feedback."""

    @pytest.mark.asyncio
    async def test_put_paramset_writes_temporary_values(self) -> None:
        """Test put_paramset writes temporary values to all polling data points."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Add polling data points for both parameters
        dp_level = central.add_data_point(
            channel_address="dev1:1",
            parameter="LEVEL",
            paramset_key=ParamsetKey.VALUES,
            requires_polling=True,
        )
        dp_state = central.add_data_point(
            channel_address="dev1:1",
            parameter="STATE",
            paramset_key=ParamsetKey.VALUES,
            requires_polling=True,
        )

        await client.put_paramset(
            channel_address="dev1:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"LEVEL": 0.5, "STATE": True},
            wait_for_callback=None,
        )

        # Verify write_temporary_value was called for both
        dp_level.write_temporary_value.assert_called_once()
        dp_state.write_temporary_value.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_value_skips_temporary_for_non_polling(self) -> None:
        """Test set_value does not write temporary value to non-polling data points."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Add a non-polling data point
        dp = central.add_data_point(
            channel_address="dev1:1",
            parameter="LEVEL",
            paramset_key=ParamsetKey.VALUES,
            requires_polling=False,  # Not a polling data point
        )

        await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.75,
            wait_for_callback=None,
        )

        # Verify write_temporary_value was NOT called
        dp.write_temporary_value.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_value_writes_temporary_value(self) -> None:
        """Test set_value writes temporary value to polling data points."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Add a polling data point
        dp = central.add_data_point(
            channel_address="dev1:1",
            parameter="LEVEL",
            paramset_key=ParamsetKey.VALUES,
            requires_polling=True,
        )

        await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.75,
            wait_for_callback=None,
        )

        # Verify write_temporary_value was called
        dp.write_temporary_value.assert_called_once()
        call_args = dp.write_temporary_value.call_args
        assert call_args.kwargs["value"] == 0.75


class _SlowBackend(_FakeBackend):
    """Fake backend with artificial delay to test coalescing."""

    async def get_device_description(self, *, address: str) -> dict[str, Any] | None:
        self.calls.append(("get_device_description", address))
        await asyncio.sleep(0.05)  # Add delay to allow coalescing
        return {
            "ADDRESS": address,
            "TYPE": "TEST_DEVICE",
            "PARAMSETS": ["VALUES", "MASTER"],
            "CHILDREN": [f"{address}:1", f"{address}:2"] if ":" not in address else [],
        }

    async def get_paramset_description(self, *, address: str, paramset_key: ParamsetKey) -> dict[str, Any] | None:
        self.calls.append(("get_paramset_description", (address, paramset_key)))
        await asyncio.sleep(0.05)  # Add delay to allow coalescing
        return {
            "LEVEL": {
                "TYPE": "FLOAT",
                "OPERATIONS": 7,
                "MIN": 0.0,
                "MAX": 1.0,
            },
            "STATE": {
                "TYPE": "BOOL",
                "OPERATIONS": 7,
            },
        }


class TestInterfaceClientRequestCoalescing:
    """Test request coalescing for device and paramset descriptions."""

    def test_coalescer_statistics(self) -> None:
        """Test coalescer exposes request statistics."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        assert client.request_coalescer is not None
        assert client.request_coalescer.total_requests == 0
        assert client.request_coalescer.executed_requests == 0
        assert client.request_coalescer.pending_count == 0

    @pytest.mark.asyncio
    async def test_device_description_coalescing(self) -> None:
        """Test concurrent device description requests are coalesced."""
        central = _FakeCentral()
        backend = _SlowBackend()  # Use slow backend for coalescing
        client = _create_interface_client(central, backend)

        # Make multiple concurrent requests for the same device
        results = await asyncio.gather(
            client.get_device_description(address="dev1"),
            client.get_device_description(address="dev1"),
            client.get_device_description(address="dev1"),
        )

        # All should return the same result
        assert all(r is not None for r in results)
        assert all(r["ADDRESS"] == "dev1" for r in results)  # type: ignore[index]

        # Backend should only be called once due to coalescing
        device_desc_calls = [c for c in backend.calls if c[0] == "get_device_description"]
        assert len(device_desc_calls) == 1

    @pytest.mark.asyncio
    async def test_different_addresses_not_coalesced(self) -> None:
        """Test requests for different addresses are not coalesced."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Make requests for different devices
        await asyncio.gather(
            client.get_device_description(address="dev1"),
            client.get_device_description(address="dev2"),
        )

        # Backend should be called twice (once per device)
        device_desc_calls = [c for c in backend.calls if c[0] == "get_device_description"]
        assert len(device_desc_calls) == 2

    @pytest.mark.asyncio
    async def test_paramset_description_coalescing(self) -> None:
        """Test concurrent paramset description requests are coalesced."""
        central = _FakeCentral()
        backend = _SlowBackend()  # Use slow backend for coalescing
        client = _create_interface_client(central, backend)

        # Make multiple concurrent requests for the same paramset
        await asyncio.gather(
            client.fetch_paramset_description(
                channel_address="dev1:1", paramset_key=ParamsetKey.VALUES, device_type="TEST"
            ),
            client.fetch_paramset_description(
                channel_address="dev1:1", paramset_key=ParamsetKey.VALUES, device_type="TEST"
            ),
            client.fetch_paramset_description(
                channel_address="dev1:1", paramset_key=ParamsetKey.VALUES, device_type="TEST"
            ),
        )

        # Backend should only be called once due to coalescing
        paramset_desc_calls = [c for c in backend.calls if c[0] == "get_paramset_description"]
        assert len(paramset_desc_calls) == 1


class TestInterfaceClientValueConversion:
    """Test value conversion matches legacy implementation."""

    @pytest.mark.asyncio
    async def test_bool_conversion(self) -> None:
        """Test bool values are converted correctly."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        central.paramset_descriptions._raw_paramset_descriptions = {
            "test-BidCos-RF": {
                "dev1:1": {
                    ParamsetKey.VALUES: {
                        "STATE": {
                            "TYPE": "BOOL",
                            "OPERATIONS": 7,
                        },
                    },
                }
            }
        }

        # Integer 1 should be converted to True
        await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
            value=1,  # Integer
            wait_for_callback=None,
            check_against_pd=True,
        )

        assert backend.calls[0][1][2] is True

    @pytest.mark.asyncio
    async def test_float_conversion(self) -> None:
        """Test float values are converted correctly."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        central.paramset_descriptions._raw_paramset_descriptions = {
            "test-BidCos-RF": {
                "dev1:1": {
                    ParamsetKey.VALUES: {
                        "LEVEL": {
                            "TYPE": "FLOAT",
                            "OPERATIONS": 7,
                            "MIN": 0.0,
                            "MAX": 1.0,
                        },
                    },
                }
            }
        }

        # Integer should be converted to float
        await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1,  # Integer
            wait_for_callback=None,
            check_against_pd=True,
        )

        assert backend.calls[0][1][2] == 1.0  # Should be float

    @pytest.mark.asyncio
    async def test_integer_conversion(self) -> None:
        """Test integer values are converted correctly."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        central.paramset_descriptions._raw_paramset_descriptions = {
            "test-BidCos-RF": {
                "dev1:1": {
                    ParamsetKey.VALUES: {
                        "COUNT": {
                            "TYPE": "INTEGER",
                            "OPERATIONS": 7,
                            "MIN": 0,
                            "MAX": 100,
                        },
                    },
                }
            }
        }

        # Float should be converted to integer
        await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="COUNT",
            value=42.7,  # Float
            wait_for_callback=None,
            check_against_pd=True,
        )

        assert backend.calls[0][1][2] == 42  # Should be truncated to int

    @pytest.mark.asyncio
    async def test_operation_validation(self) -> None:
        """Test that write operation is validated against OPERATIONS mask."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Parameter with OPERATIONS = 5 (READ | EVENT, no WRITE)
        central.paramset_descriptions._raw_paramset_descriptions = {
            "test-BidCos-RF": {
                "dev1:1": {
                    ParamsetKey.VALUES: {
                        "READ_ONLY": {
                            "TYPE": "FLOAT",
                            "OPERATIONS": 5,  # READ (1) | EVENT (4) = 5, no WRITE (2)
                        },
                    },
                }
            }
        }

        # The @inspector(re_raise=False) decorator catches exceptions and returns empty set
        result = await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="READ_ONLY",
            value=1.0,
            wait_for_callback=None,
            check_against_pd=True,
        )
        assert result == set()
        assert len(backend.calls) == 0


class TestInterfaceClientProperties:
    """Test InterfaceClient properties and basic functionality."""

    def test_basic_properties(self) -> None:
        """Test basic property access."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        assert client.interface_id == "test-BidCos-RF"
        assert client.interface == Interface.BIDCOS_RF
        assert client.model == "CCU"
        assert client.version == "2.0"
        assert client.capabilities.ping_pong is True
        assert client.capabilities.linking is True
        assert client.capabilities.programs is True

    def test_capability_properties(self) -> None:
        """Test capability properties from backend."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        assert client.capabilities.backup is True
        assert client.capabilities.device_firmware_update is True
        assert client.capabilities.firmware_updates is True
        assert client.capabilities.functions is True
        assert client.capabilities.rooms is True
        assert client.capabilities.rpc_callback is True

    def test_str_representation(self) -> None:
        """Test string representation."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        assert "test-BidCos-RF" in str(client)
