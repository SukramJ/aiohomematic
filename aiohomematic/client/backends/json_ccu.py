# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
JSON-RPC CCU backend implementation (CCU-Jack).

Uses JSON-RPC exclusively for all operations.

Public API
----------
- JsonCcuBackend: Backend for CCU-Jack using JSON-RPC exclusively
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final, cast

from aiohomematic import i18n
from aiohomematic.client.backends.base import BaseBackend
from aiohomematic.client.backends.capabilities import JSON_CCU_CAPABILITIES
from aiohomematic.client.circuit_breaker import CircuitBreaker
from aiohomematic.const import (
    DUMMY_SERIAL,
    Backend,
    CircuitState,
    CommandRxMode,
    DeviceDescription,
    DeviceDetail,
    Interface,
    ParameterData,
    ParameterType,
    ParamsetKey,
    SystemInformation,
)
from aiohomematic.exceptions import BaseHomematicException, ClientException
from aiohomematic.schemas import normalize_device_description
from aiohomematic.support import extract_exc_args

if TYPE_CHECKING:
    from aiohomematic.client.json_rpc import AioJsonRpcAioHttpClient
    from aiohomematic.interfaces import ParamsetDescriptionProviderProtocol

__all__ = ["JsonCcuBackend"]

_LOGGER: Final = logging.getLogger(__name__)

_CCU_JSON_VALUE_TYPE: Final = {
    "ACTION": "bool",
    "BOOL": "bool",
    "ENUM": "list",
    "FLOAT": "double",
    "INTEGER": "int",
    "STRING": "string",
}


class JsonCcuBackend(BaseBackend):
    """
    Backend for CCU-Jack using JSON-RPC exclusively.

    CCU-Jack provides a JSON-RPC interface that exposes Homematic device
    operations without requiring the full CCU infrastructure.
    """

    __slots__ = ("_json_rpc", "_paramset_provider")

    def __init__(
        self,
        *,
        interface: Interface,
        interface_id: str,
        json_rpc: AioJsonRpcAioHttpClient,
        paramset_provider: ParamsetDescriptionProviderProtocol,
        has_push_updates: bool,
    ) -> None:
        """Initialize the JSON CCU backend."""
        # Build capabilities based on config
        capabilities = JSON_CCU_CAPABILITIES.model_copy(update={"push_updates": has_push_updates})
        super().__init__(
            interface=interface,
            interface_id=interface_id,
            capabilities=capabilities,
        )
        self._json_rpc: Final = json_rpc
        self._paramset_provider: Final = paramset_provider

    @property
    def all_circuit_breakers_closed(self) -> bool:
        """Return True if all circuit breakers are in closed state."""
        return self._json_rpc.circuit_breaker.state == CircuitState.CLOSED

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Return the primary circuit breaker for metrics access."""
        return self._json_rpc.circuit_breaker

    @property
    def model(self) -> str:
        """Return the backend model name."""
        return Backend.CCU

    async def check_connection(self, *, handle_ping_pong: bool, caller_id: str | None = None) -> bool:
        """Check connection via JSON-RPC isPresent."""
        # JSON-RPC backend doesn't support ping-pong, uses isPresent instead
        return await self._json_rpc.is_present(interface=self._interface)

    async def deinit_proxy(self, *, init_url: str) -> None:
        """No proxy de-initialization needed."""

    async def get_all_device_data(self, *, interface: Interface) -> dict[str, Any] | None:
        """Return all device data via JSON-RPC."""
        return dict(await self._json_rpc.get_all_device_data(interface=interface))

    async def get_device_description(self, *, address: str) -> DeviceDescription | None:
        """Return device description via JSON-RPC."""
        try:
            return await self._json_rpc.get_device_description(interface=self._interface, address=address)
        except BaseHomematicException as bhexc:
            _LOGGER.warning(  # i18n-log: ignore
                "GET_DEVICE_DESCRIPTION failed: %s [%s]",
                bhexc.name,
                extract_exc_args(exc=bhexc),
            )
            return None

    async def get_device_details(self, *, addresses: tuple[str, ...] | None = None) -> list[DeviceDetail] | None:
        """
        Return device names, interfaces, and rega IDs via JSON-RPC.

        Note: The addresses parameter is ignored as JSON-RPC returns all device
        details in a single call via Device.listAllDetail.
        """
        return list(await self._json_rpc.get_device_details())

    async def get_paramset(self, *, channel_address: str, paramset_key: ParamsetKey | str) -> dict[str, Any]:
        """Return a paramset via JSON-RPC."""
        return (
            await self._json_rpc.get_paramset(
                interface=self._interface,
                address=channel_address,
                paramset_key=paramset_key,
            )
            or {}
        )

    async def get_paramset_description(
        self, *, channel_address: str, paramset_key: ParamsetKey
    ) -> dict[str, ParameterData] | None:
        """Return paramset description via JSON-RPC."""
        try:
            return cast(
                dict[str, ParameterData],
                await self._json_rpc.get_paramset_description(
                    interface=self._interface,
                    address=channel_address,
                    paramset_key=paramset_key,
                ),
            )
        except BaseHomematicException as bhexc:
            _LOGGER.debug(
                "GET_PARAMSET_DESCRIPTION failed: %s [%s] for %s/%s",
                bhexc.name,
                extract_exc_args(exc=bhexc),
                channel_address,
                paramset_key,
            )
            return None

    async def get_value(self, *, channel_address: str, parameter: str) -> Any:
        """Return a parameter value via JSON-RPC."""
        return await self._json_rpc.get_value(
            interface=self._interface,
            address=channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter=parameter,
        )

    async def init_proxy(self, *, init_url: str, interface_id: str) -> None:
        """No proxy initialization needed for JSON-RPC only backend."""

    async def initialize(self) -> None:
        """Initialize the backend."""
        self._system_information = SystemInformation(
            available_interfaces=(self._interface,),
            serial=f"{self._interface}_{DUMMY_SERIAL}",
        )

    async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
        """Return all device descriptions via JSON-RPC (normalized)."""
        try:
            raw_descriptions = await self._json_rpc.list_devices(interface=self._interface)
            return tuple(normalize_device_description(device_description=desc) for desc in raw_descriptions)
        except BaseHomematicException as bhexc:
            _LOGGER.debug(
                "LIST_DEVICES failed: %s [%s]",
                bhexc.name,
                extract_exc_args(exc=bhexc),
            )
            return None

    async def put_paramset(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey | str,
        values: dict[str, Any],
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Set paramset values via JSON-RPC (one value at a time)."""
        for parameter, value in values.items():
            await self.set_value(
                channel_address=channel_address,
                parameter=parameter,
                value=value,
                rx_mode=rx_mode,
            )

    def reset_circuit_breakers(self) -> None:
        """Reset all circuit breakers to closed state."""
        self._json_rpc.circuit_breaker.reset()

    async def set_value(
        self,
        *,
        channel_address: str,
        parameter: str,
        value: Any,
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Set a parameter value via JSON-RPC."""
        if (value_type := self._get_parameter_type(address=channel_address, parameter=parameter)) is None:
            raise ClientException(
                i18n.tr(
                    key="exception.client.json_ccu.set_value.unknown_type",
                    channel_address=channel_address,
                    paramset_key=ParamsetKey.VALUES,
                    parameter=parameter,
                )
            )

        json_type = _CCU_JSON_VALUE_TYPE.get(value_type, "string")
        await self._json_rpc.set_value(
            interface=self._interface,
            address=channel_address,
            parameter=parameter,
            value_type=json_type,
            value=value,
        )

    async def stop(self) -> None:
        """Stop the backend (no resources to release)."""

    def _get_parameter_type(self, *, address: str, parameter: str) -> ParameterType | None:
        """Return the parameter's TYPE from its description."""
        if parameter_data := self._paramset_provider.get_parameter_data(
            interface_id=self._interface_id,
            channel_address=address,
            paramset_key=ParamsetKey.VALUES,
            parameter=parameter,
        ):
            return parameter_data["TYPE"]
        return None
