"""
Backup handler.

Handles backup creation and download operations.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Final

from aiohomematic import i18n
from aiohomematic.client.handlers.base import BaseHandler
from aiohomematic.const import BackupStatus
from aiohomematic.decorators import inspector

if TYPE_CHECKING:
    from aiohomematic.client import AioJsonRpcAioHttpClient
    from aiohomematic.client.rpc_proxy import BaseRpcProxy
    from aiohomematic.const import Interface
    from aiohomematic.interfaces.client import ClientDependencies

_LOGGER: Final = logging.getLogger(__name__)


class BackupHandler(BaseHandler):
    """
    Handler for backup operations.

    Handles:
    - Creating backups on the CCU
    - Downloading backup files
    """

    __slots__ = ("_supports_backup",)

    def __init__(
        self,
        *,
        central: ClientDependencies,
        interface: Interface,
        interface_id: str,
        json_rpc_client: AioJsonRpcAioHttpClient,
        proxy: BaseRpcProxy,
        proxy_read: BaseRpcProxy,
        supports_backup: bool,
    ) -> None:
        """Initialize the backup handler."""
        super().__init__(
            central=central,
            interface=interface,
            interface_id=interface_id,
            json_rpc_client=json_rpc_client,
            proxy=proxy,
            proxy_read=proxy_read,
        )
        self._supports_backup: Final = supports_backup

    @property
    def supports_backup(self) -> bool:
        """Return if the backend supports backup creation and download."""
        return self._supports_backup

    @inspector(re_raise=False)
    async def create_backup_and_download(
        self,
        *,
        max_wait_time: float = 300.0,
        poll_interval: float = 5.0,
    ) -> bytes | None:
        """
        Create a backup on the CCU and download it.

        Start the backup process in the background and poll for completion.
        This avoids blocking the ReGa scripting engine during backup creation.

        Args:
            max_wait_time: Maximum time to wait for backup completion in seconds.
            poll_interval: Time between status polls in seconds.

        Returns:
            Backup file content as bytes, or None if backup creation or download failed.

        """
        if not self._supports_backup:
            _LOGGER.debug("CREATE_BACKUP_AND_DOWNLOAD: Not supported by client for %s", self._interface_id)
            return None

        # Start backup in background
        if not await self._json_rpc_client.create_backup_start():
            _LOGGER.warning(  # i18n-log: ignore
                "CREATE_BACKUP_AND_DOWNLOAD: Failed to start backup process"
            )
            return None

        _LOGGER.debug("CREATE_BACKUP_AND_DOWNLOAD: Backup process started, polling for completion")

        # Poll for completion
        elapsed = 0.0
        while elapsed < max_wait_time:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            status_data = await self._json_rpc_client.create_backup_status()

            if status_data.status == BackupStatus.COMPLETED:
                _LOGGER.info(
                    i18n.tr(
                        "log.client.create_backup_and_download.completed",
                        filename=status_data.filename,
                        size=status_data.size,
                    )
                )
                return await self._json_rpc_client.download_backup()

            if status_data.status == BackupStatus.FAILED:
                _LOGGER.warning(i18n.tr("log.client.create_backup_and_download.failed"))
                return None

            if status_data.status == BackupStatus.IDLE:
                _LOGGER.warning(i18n.tr("log.client.create_backup_and_download.idle"))
                return None

            _LOGGER.info(
                i18n.tr(
                    "log.client.create_backup_and_download.running",
                    elapsed=elapsed,
                )
            )

        _LOGGER.warning(
            i18n.tr(
                "log.client.create_backup_and_download.timeout",
                max_wait_time=max_wait_time,
            )
        )
        return None
