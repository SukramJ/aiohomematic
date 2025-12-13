"""
Firmware handler.

Handles device and system firmware update operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from aiohomematic import i18n
from aiohomematic.client.handlers.base import BaseHandler
from aiohomematic.const import ProductGroup
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import BaseHomematicException, ClientException
from aiohomematic.interfaces.client import FirmwareOperations
from aiohomematic.support import extract_exc_args

if TYPE_CHECKING:
    from aiohomematic.client import AioJsonRpcAioHttpClient
    from aiohomematic.client.rpc_proxy import BaseRpcProxy
    from aiohomematic.const import Interface
    from aiohomematic.interfaces.client import ClientDependencies

_LOGGER: Final = logging.getLogger(__name__)


class FirmwareHandler(BaseHandler, FirmwareOperations):
    """
    Handler for firmware update operations.

    Implements FirmwareOperations protocol for ISP-compliant client operations.

    Handles:
    - Updating device firmware
    - Triggering system firmware updates
    """

    __slots__ = (
        "_supports_device_firmware_update",
        "_supports_firmware_update_trigger",
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
        supports_device_firmware_update: bool,
        supports_firmware_update_trigger: bool,
    ) -> None:
        """Initialize the firmware handler."""
        super().__init__(
            central=central,
            interface=interface,
            interface_id=interface_id,
            json_rpc_client=json_rpc_client,
            proxy=proxy,
            proxy_read=proxy_read,
        )
        self._supports_device_firmware_update: Final = supports_device_firmware_update
        self._supports_firmware_update_trigger: Final = supports_firmware_update_trigger

    @property
    def supports_device_firmware_update(self) -> bool:
        """Return if the backend supports device firmware updates."""
        return self._supports_device_firmware_update

    @property
    def supports_firmware_update_trigger(self) -> bool:
        """Return if the backend supports triggering system firmware updates."""
        return self._supports_firmware_update_trigger

    @inspector(re_raise=False)
    async def trigger_firmware_update(self) -> bool:
        """
        Trigger the CCU system firmware update process.

        Initiates the CCU's own firmware update (not device firmware). The CCU
        will download and install available system updates.

        Returns:
            True if the update was triggered successfully, False if unsupported.

        """
        if not self._supports_firmware_update_trigger:
            _LOGGER.debug("TRIGGER_FIRMWARE_UPDATE: Not supported by client for %s", self._interface_id)
            return False

        return await self._json_rpc_client.trigger_firmware_update()

    @inspector
    async def update_device_firmware(self, *, device_address: str) -> bool:
        """
        Update firmware on a single Homematic device.

        Uses installFirmware() for HmIP/HmIPW devices and updateFirmware() for
        BidCos devices. The device must have a firmware update available.

        Args:
            device_address: Device address (e.g., "VCU0000001").

        Returns:
            True if the update was initiated successfully, False if device not
            found or update unsupported.

        Raises:
            ClientException: If the RPC call fails.

        """
        if not self._supports_device_firmware_update:
            _LOGGER.debug("UPDATE_DEVICE_FIRMWARE: Not supported by client for %s", self._interface_id)
            return False

        if device := self._central.device_coordinator.get_device(address=device_address):
            _LOGGER.info(
                i18n.tr(
                    "log.client.update_device_firmware.try",
                    device_address=device_address,
                )
            )
            try:
                update_result = (
                    await self._proxy.installFirmware(device_address)
                    if device.product_group in (ProductGroup.HMIPW, ProductGroup.HMIP)
                    else await self._proxy.updateFirmware(device_address)
                )
                result = bool(update_result) if isinstance(update_result, bool) else bool(update_result[0])
                _LOGGER.info(
                    i18n.tr(
                        "log.client.update_device_firmware.result",
                        device_address=device_address,
                        result=("success" if result else "failed"),
                    )
                )
            except BaseHomematicException as bhexc:
                raise ClientException(
                    i18n.tr(
                        "exception.client.update_device_firmware.failed",
                        reason=extract_exc_args(exc=bhexc),
                    )
                ) from bhexc
            return result
        return False
