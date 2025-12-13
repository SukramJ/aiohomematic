"""
Metadata handler.

Handles metadata, renaming, rooms, functions, install mode, inbox devices,
and service messages operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final, cast

from aiohomematic import i18n
from aiohomematic.client.handlers.base import BaseHandler
from aiohomematic.const import InboxDeviceData, Interface, ServiceMessageData, ServiceMessageType, SystemUpdateData
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import BaseHomematicException, ClientException
from aiohomematic.interfaces.client import MetadataOperations
from aiohomematic.support import extract_exc_args

if TYPE_CHECKING:
    from aiohomematic.client import AioJsonRpcAioHttpClient
    from aiohomematic.client.rpc_proxy import BaseRpcProxy
    from aiohomematic.interfaces.client import ClientDependencies

_LOGGER: Final = logging.getLogger(__name__)


class MetadataHandler(BaseHandler, MetadataOperations):
    """
    Handler for metadata and system information operations.

    Implements MetadataOperations protocol for ISP-compliant client operations.

    Handles:
    - Metadata read/write operations
    - Device and channel renaming
    - Room and function queries
    - Install mode operations
    - Inbox device management
    - Service message queries
    - System update information
    - ReGa ID lookups
    """

    __slots__ = (
        "_supports_functions",
        "_supports_inbox_devices",
        "_supports_install_mode",
        "_supports_metadata",
        "_supports_rega_id_lookup",
        "_supports_rename",
        "_supports_rooms",
        "_supports_service_messages",
        "_supports_system_update_info",
    )

    def __init__(
        self,
        *,
        central: ClientDependencies,
        interface: Interface,
        interface_id: str,
        json_rpc_client: AioJsonRpcAioHttpClient,
        proxy: BaseRpcProxy,
        proxy_read: BaseRpcProxy,
        supports_functions: bool,
        supports_inbox_devices: bool,
        supports_install_mode: bool,
        supports_metadata: bool,
        supports_rega_id_lookup: bool,
        supports_rename: bool,
        supports_rooms: bool,
        supports_service_messages: bool,
        supports_system_update_info: bool,
    ) -> None:
        """Initialize the metadata handler."""
        super().__init__(
            central=central,
            interface=interface,
            interface_id=interface_id,
            json_rpc_client=json_rpc_client,
            proxy=proxy,
            proxy_read=proxy_read,
        )
        self._supports_functions: Final = supports_functions
        self._supports_inbox_devices: Final = supports_inbox_devices
        self._supports_install_mode: Final = supports_install_mode
        self._supports_metadata: Final = supports_metadata
        self._supports_rega_id_lookup: Final = supports_rega_id_lookup
        self._supports_rename: Final = supports_rename
        self._supports_rooms: Final = supports_rooms
        self._supports_service_messages: Final = supports_service_messages
        self._supports_system_update_info: Final = supports_system_update_info

    @inspector(re_raise=False)
    async def accept_device_in_inbox(self, *, device_address: str) -> bool:
        """
        Accept a device from the CCU inbox, completing its pairing process.

        The inbox contains newly paired devices waiting for user confirmation.
        Accepting moves the device to the active device list.

        Args:
            device_address: SGTIN or address of the inbox device.

        Returns:
            True if accepted successfully, False if not supported or failed.

        """
        if not self._supports_inbox_devices:
            _LOGGER.debug("ACCEPT_DEVICE_IN_INBOX: Not supported by client for %s", self._interface_id)
            return False

        return await self._json_rpc_client.accept_device_in_inbox(device_address=device_address)

    @inspector(re_raise=False, no_raise_return={})
    async def get_all_functions(self) -> dict[str, set[str]]:
        """
        Return function assignments for all channels.

        Functions are user-defined groupings in the CCU (e.g., "Lighting", "Heating").
        Maps each channel's ReGa ID to its assigned functions.

        Returns:
            Dict mapping channel address to set of function names.

        """
        if not self._supports_functions:
            _LOGGER.debug("GET_ALL_FUNCTIONS: Not supported by client for %s", self._interface_id)
            return {}

        functions: dict[str, set[str]] = {}
        rega_ids_function = await self._json_rpc_client.get_all_channel_rega_ids_function()
        for address, rega_id in self._central.cache_coordinator.device_details.device_channel_rega_ids.items():
            if sections := rega_ids_function.get(rega_id):
                if address not in functions:
                    functions[address] = set()
                functions[address].update(sections)
        return functions

    @inspector(re_raise=False, no_raise_return={})
    async def get_all_rooms(self) -> dict[str, set[str]]:
        """
        Return room assignments for all channels.

        Rooms are user-defined location groupings in the CCU. Maps each
        channel's ReGa ID to its assigned rooms.

        Returns:
            Dict mapping channel address to set of room names.

        """
        if not self._supports_rooms:
            _LOGGER.debug("GET_ALL_ROOMS: Not supported by client for %s", self._interface_id)
            return {}

        rooms: dict[str, set[str]] = {}
        rega_ids_room = await self._json_rpc_client.get_all_channel_rega_ids_room()
        for address, rega_id in self._central.cache_coordinator.device_details.device_channel_rega_ids.items():
            if names := rega_ids_room.get(rega_id):
                if address not in rooms:
                    rooms[address] = set()
                rooms[address].update(names)
        return rooms

    @inspector(re_raise=False, no_raise_return=())
    async def get_inbox_devices(self) -> tuple[InboxDeviceData, ...]:
        """
        Return devices awaiting user acceptance in the CCU inbox.

        After pairing, HmIP devices appear in the inbox until explicitly
        accepted. Each entry contains device type, address, and SGTIN.

        Returns:
            Tuple of InboxDeviceData dicts for pending devices.

        """
        if not self._supports_inbox_devices:
            _LOGGER.debug("GET_INBOX_DEVICES: Not supported by client for %s", self._interface_id)
            return ()

        return await self._json_rpc_client.get_inbox_devices()

    @inspector
    async def get_install_mode(self) -> int:
        """
        Return remaining seconds in pairing/install mode.

        Install mode allows new devices to be paired with the CCU. Uses JSON-RPC
        for HmIP-RF interface and XML-RPC for BidCos interfaces.

        Returns:
            Remaining seconds, or 0 if install mode is off or unsupported.

        Raises:
            ClientException: If the RPC call fails.

        """
        if not self._supports_install_mode:
            _LOGGER.debug("GET_INSTALL_MODE: Not supported by client for %s", self._interface_id)
            return 0

        try:
            # HmIP-RF uses JSON-RPC, BidCos-RF uses XML-RPC
            if self._interface == Interface.HMIP_RF:
                return await self._json_rpc_client.get_install_mode(interface=self._interface)

            if (remaining_time := await self._proxy.getInstallMode()) is not None:
                return int(remaining_time)
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.get_install_mode.failed",
                    interface_id=self._interface_id,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc
        return 0

    @inspector
    async def get_metadata(self, *, address: str, data_id: str) -> dict[str, Any]:
        """
        Return backend metadata for a device or channel.

        Metadata is key-value storage attached to Homematic objects, used by
        some backends for configuration data.

        Args:
            address: Device or channel address.
            data_id: Metadata key identifier.

        Returns:
            Metadata value dict, or empty dict if unsupported.

        Raises:
            ClientException: If the RPC call fails.

        """
        if not self._supports_metadata:
            _LOGGER.debug("GET_METADATA: Not supported by client for %s", self._interface_id)
            return {}

        try:
            return cast(dict[str, Any], await self._proxy.getMetadata(address, data_id))
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.get_metadata.failed",
                    address=address,
                    data_id=data_id,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    @inspector(re_raise=False)
    async def get_rega_id_by_address(self, *, address: str) -> int | None:
        """
        Return the ReGaHSS internal ID for an address.

        ReGa IDs are used by the CCU's scripting engine (ReGaHSS) to identify
        devices and channels. Required for rename operations and room/function
        lookups.

        Args:
            address: Device or channel address.

        Returns:
            ReGa ID integer, or None if not found or unsupported.

        """
        if not self._supports_rega_id_lookup:
            _LOGGER.debug("GET_REGA_ID_BY_ADDRESS: Not supported by client for %s", self._interface_id)
            return None

        return await self._json_rpc_client.get_rega_id_by_address(address=address)

    @inspector(re_raise=False, no_raise_return=())
    async def get_service_messages(
        self,
        *,
        message_type: ServiceMessageType | None = None,
    ) -> tuple[ServiceMessageData, ...]:
        """
        Get all active service messages from the backend.

        Args:
            message_type: Filter by message type. If None, return all messages.

        """
        if not self._supports_service_messages:
            _LOGGER.debug("GET_SERVICE_MESSAGES: Not supported by client for %s", self._interface_id)
            return ()

        return await self._json_rpc_client.get_service_messages(message_type=message_type)

    @inspector(re_raise=False)
    async def get_system_update_info(self) -> SystemUpdateData | None:
        """
        Return CCU firmware update availability status.

        Checks if a newer CCU firmware version is available for download.

        Returns:
            SystemUpdateData with version info, or None if unsupported/unavailable.

        """
        if not self._supports_system_update_info:
            _LOGGER.debug("GET_SYSTEM_UPDATE_INFO: Not supported by client for %s", self._interface_id)
            return None

        return await self._json_rpc_client.get_system_update_info()

    @inspector(re_raise=False)
    async def rename_channel(self, *, rega_id: int, new_name: str) -> bool:
        """
        Rename a channel in the CCU's ReGaHSS database.

        Args:
            rega_id: ReGaHSS internal ID of the channel.
            new_name: New display name for the channel.

        Returns:
            True if renamed successfully, False if unsupported or failed.

        """
        if not self._supports_rename:
            _LOGGER.debug("RENAME_CHANNEL: Not supported by client for %s", self._interface_id)
            return False

        return await self._json_rpc_client.rename_channel(rega_id=rega_id, new_name=new_name)

    @inspector(re_raise=False)
    async def rename_device(self, *, rega_id: int, new_name: str) -> bool:
        """
        Rename a device in the CCU's ReGaHSS database.

        Args:
            rega_id: ReGaHSS internal ID of the device.
            new_name: New display name for the device.

        Returns:
            True if renamed successfully, False if unsupported or failed.

        """
        if not self._supports_rename:
            _LOGGER.debug("RENAME_DEVICE: Not supported by client for %s", self._interface_id)
            return False

        return await self._json_rpc_client.rename_device(rega_id=rega_id, new_name=new_name)

    @inspector
    async def set_install_mode(
        self,
        *,
        on: bool = True,
        time: int = 60,
        mode: int = 1,
        device_address: str | None = None,
    ) -> bool:
        """
        Set the install mode on the backend.

        Args:
            on: Enable or disable install mode.
            time: Duration in seconds (default 60).
            mode: Mode 1=normal, 2=set all ROAMING devices into install mode.
            device_address: Optional device address/SGTIN to limit pairing.

        Returns:
            True if successful.

        """
        if not self._supports_install_mode:
            _LOGGER.debug("SET_INSTALL_MODE: Not supported by client for %s", self._interface_id)
            return False

        try:
            # HmIP-RF uses JSON-RPC setInstallModeHmIP, BidCos-RF uses XML-RPC
            if self._interface == Interface.HMIP_RF:
                return await self._json_rpc_client.set_install_mode_hmip(
                    interface=self._interface,
                    on=on,
                    time=time,
                    device_address=device_address,
                )

            if device_address:
                await self._proxy.setInstallMode(on, time, device_address)
            else:
                await self._proxy.setInstallMode(on, time, mode)
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.set_install_mode.failed",
                    interface_id=self._interface_id,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc
        else:
            return True

    @inspector
    async def set_metadata(self, *, address: str, data_id: str, value: dict[str, Any]) -> dict[str, Any]:
        """
        Write metadata for a device or channel.

        Args:
            address: Device or channel address.
            data_id: Metadata key identifier.
            value: Metadata value dict to store.

        Returns:
            Result dict from the backend, or empty dict if unsupported.

        Raises:
            ClientException: If the RPC call fails.

        """
        if not self._supports_metadata:
            _LOGGER.debug("SET_METADATA: Not supported by client for %s", self._interface_id)
            return {}

        try:
            return cast(dict[str, Any], await self._proxy.setMetadata(address, data_id, value))
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.set_metadata.failed",
                    address=address,
                    data_id=data_id,
                    value=value,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc
