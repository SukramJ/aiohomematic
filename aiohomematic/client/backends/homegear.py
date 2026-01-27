# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Homegear backend implementation.

Uses XML-RPC exclusively with Homegear-specific extensions.

Public API
----------
- HomegearBackend: Backend for Homegear and pydevccu systems
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final, cast

from aiohomematic.client.backends.base import BaseBackend
from aiohomematic.client.backends.capabilities import HOMEGEAR_CAPABILITIES
from aiohomematic.client.circuit_breaker import CircuitBreaker
from aiohomematic.const import (
    DUMMY_SERIAL,
    Backend,
    CircuitState,
    CommandRxMode,
    DescriptionMarker,
    DeviceDescription,
    DeviceDetail,
    Interface,
    ParameterData,
    ParamsetKey,
    SystemInformation,
    SystemVariableData,
)
from aiohomematic.exceptions import BaseHomematicException
from aiohomematic.schemas import normalize_device_description
from aiohomematic.support import extract_exc_args

if TYPE_CHECKING:
    from aiohomematic.client.rpc_proxy import BaseRpcProxy

__all__ = ["HomegearBackend"]

_LOGGER: Final = logging.getLogger(__name__)
_NAME: Final = "NAME"


class HomegearBackend(BaseBackend):
    """
    Backend for Homegear and pydevccu systems.

    Communication:
    - XML-RPC exclusively with Homegear-specific methods
    - System variables via getSystemVariable/setSystemVariable (not JSON-RPC)
    - Device names via getMetadata (not JSON-RPC)
    """

    __slots__ = ("_proxy", "_proxy_read", "_version")

    def __init__(
        self,
        *,
        interface: Interface,
        interface_id: str,
        proxy: BaseRpcProxy,
        proxy_read: BaseRpcProxy,
        version: str,
        has_push_updates: bool,
    ) -> None:
        """Initialize the Homegear backend."""
        # Build capabilities based on config
        capabilities = HOMEGEAR_CAPABILITIES.model_copy(update={"push_updates": has_push_updates})
        super().__init__(
            interface=interface,
            interface_id=interface_id,
            capabilities=capabilities,
        )
        self._proxy: Final = proxy
        self._proxy_read: Final = proxy_read
        self._version: Final = version

    @property
    def all_circuit_breakers_closed(self) -> bool:
        """Return True if all circuit breakers are in closed state."""
        if self._proxy.circuit_breaker.state != CircuitState.CLOSED:
            return False
        # Check proxy_read only if it's a different object
        if self._proxy_read is not self._proxy:
            return self._proxy_read.circuit_breaker.state == CircuitState.CLOSED
        return True

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Return the primary circuit breaker for metrics access."""
        return self._proxy.circuit_breaker

    @property
    def model(self) -> str:
        """Return the backend model name."""
        if Backend.PYDEVCCU.lower() in self._version.lower():
            return Backend.PYDEVCCU
        return Backend.HOMEGEAR

    async def check_connection(self, *, handle_ping_pong: bool, caller_id: str | None = None) -> bool:
        """Check connection via clientServerInitialized."""
        try:
            # Homegear uses clientServerInitialized instead of ping
            await self._proxy.clientServerInitialized(self._interface_id)
        except BaseHomematicException:
            return False
        return True

    async def deinit_proxy(self, *, init_url: str) -> None:
        """De-initialize the proxy."""
        await self._proxy.init(init_url)

    async def delete_system_variable(self, *, name: str) -> bool:
        """Delete system variable via Homegear's deleteSystemVariable."""
        await self._proxy.deleteSystemVariable(name)
        return True

    async def get_all_system_variables(
        self, *, markers: tuple[DescriptionMarker | str, ...]
    ) -> tuple[SystemVariableData, ...] | None:
        """Return all system variables via Homegear's getAllSystemVariables."""
        variables: list[SystemVariableData] = []
        if hg_variables := await self._proxy.getAllSystemVariables():
            for name, value in hg_variables.items():
                variables.append(SystemVariableData(vid=name, legacy_name=name, value=value))
        return tuple(variables)

    async def get_device_description(self, *, address: str) -> DeviceDescription | None:
        """Return device description."""
        try:
            return cast(
                DeviceDescription | None,
                await self._proxy_read.getDeviceDescription(address),
            )
        except BaseHomematicException as bhexc:
            _LOGGER.warning(  # i18n-log: ignore
                "GET_DEVICE_DESCRIPTION failed: %s [%s]",
                bhexc.name,
                extract_exc_args(exc=bhexc),
            )
            return None

    async def get_device_details(self, *, addresses: tuple[str, ...] | None = None) -> list[DeviceDetail] | None:
        """
        Return device names from metadata (Homegear-specific).

        Homegear stores device names in metadata under the "NAME" key.
        This fetches names for all provided addresses.
        """
        if not addresses:
            return None

        _LOGGER.debug("GET_DEVICE_DETAILS: Fetching names via Metadata for %d addresses", len(addresses))
        details: list[DeviceDetail] = []
        for address in addresses:
            try:
                name = await self._proxy_read.getMetadata(address, _NAME)
                # Homegear doesn't have rega IDs or channels in the same way as CCU
                # Create a minimal DeviceDetail with just the name
                details.append(
                    DeviceDetail(
                        address=address,
                        name=name if isinstance(name, str) else str(name) if name else "",
                        id=0,  # Homegear doesn't use rega IDs
                        interface=self._interface_id,
                        channels=[],  # Homegear doesn't provide channel details this way
                    )
                )
            except BaseHomematicException as bhexc:
                _LOGGER.warning(  # i18n-log: ignore
                    "GET_DEVICE_DETAILS: %s [%s] Failed to fetch name for %s",
                    bhexc.name,
                    extract_exc_args(exc=bhexc),
                    address,
                )
        return details if details else None

    async def get_metadata(self, *, address: str, data_id: str) -> dict[str, Any]:
        """Return metadata (Homegear stores device names here)."""
        return cast(
            dict[str, Any],
            await self._proxy_read.getMetadata(address, data_id),
        )

    async def get_paramset(self, *, channel_address: str, paramset_key: ParamsetKey | str) -> dict[str, Any]:
        """Return a paramset."""
        return cast(
            dict[str, Any],
            await self._proxy_read.getParamset(channel_address, paramset_key),
        )

    async def get_paramset_description(
        self, *, channel_address: str, paramset_key: ParamsetKey
    ) -> dict[str, ParameterData] | None:
        """Return paramset description."""
        try:
            return cast(
                dict[str, ParameterData],
                await self._proxy_read.getParamsetDescription(channel_address, paramset_key),
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

    async def get_system_variable(self, *, name: str) -> Any:
        """Return system variable via Homegear's getSystemVariable."""
        return await self._proxy.getSystemVariable(name)

    async def get_value(self, *, channel_address: str, parameter: str) -> Any:
        """Return a parameter value."""
        return await self._proxy_read.getValue(channel_address, parameter)

    async def init_proxy(self, *, init_url: str, interface_id: str) -> None:
        """Initialize the proxy."""
        await self._proxy.init(init_url, interface_id)

    async def initialize(self) -> None:
        """Initialize the backend."""
        self._system_information = SystemInformation(
            available_interfaces=(Interface.BIDCOS_RF,),
            serial=f"{self._interface}_{DUMMY_SERIAL}",
        )

    async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
        """Return all device descriptions (normalized)."""
        try:
            raw_descriptions = await self._proxy_read.listDevices()
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
        """Set paramset values."""
        if rx_mode:
            await self._proxy.putParamset(channel_address, paramset_key, values, rx_mode)
        else:
            await self._proxy.putParamset(channel_address, paramset_key, values)

    def reset_circuit_breakers(self) -> None:
        """Reset all circuit breakers to closed state."""
        self._proxy.circuit_breaker.reset()
        # Reset proxy_read only if it's a different object
        if self._proxy_read is not self._proxy:
            self._proxy_read.circuit_breaker.reset()

    async def set_system_variable(self, *, name: str, value: Any) -> bool:
        """Set system variable via Homegear's setSystemVariable."""
        await self._proxy.setSystemVariable(name, value)
        return True

    async def set_value(
        self,
        *,
        channel_address: str,
        parameter: str,
        value: Any,
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Set a parameter value."""
        if rx_mode:
            await self._proxy.setValue(channel_address, parameter, value, rx_mode)
        else:
            await self._proxy.setValue(channel_address, parameter, value)

    async def stop(self) -> None:
        """Stop the backend."""
        await self._proxy.stop()
        await self._proxy_read.stop()
