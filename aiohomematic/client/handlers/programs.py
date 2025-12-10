"""
Program handler.

Handles program execution and state management.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from aiohomematic.client.handlers.base import BaseHandler
from aiohomematic.const import DescriptionMarker, ProgramData
from aiohomematic.decorators import inspector
from aiohomematic.interfaces.client import ProgramOperations

if TYPE_CHECKING:
    from aiohomematic.client import AioJsonRpcAioHttpClient
    from aiohomematic.client.rpc_proxy import BaseRpcProxy
    from aiohomematic.const import Interface
    from aiohomematic.interfaces.client import ClientDependencies

_LOGGER: Final = logging.getLogger(__name__)


class ProgramHandler(BaseHandler, ProgramOperations):
    """
    Handler for program operations.

    Implements ProgramOperations protocol for ISP-compliant client operations.

    Handles:
    - Getting all programs
    - Executing programs
    - Setting program state
    - Checking program IDs
    """

    __slots__ = ("_supports_programs",)

    def __init__(
        self,
        *,
        central: ClientDependencies,
        interface: Interface,
        interface_id: str,
        json_rpc_client: AioJsonRpcAioHttpClient,
        proxy: BaseRpcProxy,
        proxy_read: BaseRpcProxy,
        supports_programs: bool,
    ) -> None:
        """Initialize the program handler."""
        super().__init__(
            central=central,
            interface=interface,
            interface_id=interface_id,
            json_rpc_client=json_rpc_client,
            proxy=proxy,
            proxy_read=proxy_read,
        )
        self._supports_programs: Final = supports_programs

    @property
    def supports_programs(self) -> bool:
        """Return if interface supports programs."""
        return self._supports_programs

    @inspector
    async def execute_program(self, *, pid: str) -> bool:
        """
        Trigger execution of a CCU program.

        CCU programs are user-defined scripts created in the CCU's web interface.
        This method triggers immediate execution of the program.

        Args:
            pid: Program ID (ReGa internal identifier).

        Returns:
            True if execution was triggered, False if unsupported.

        """
        if not self._supports_programs:
            _LOGGER.debug("EXECUTE_PROGRAM: Not supported by client for %s", self._interface_id)
            return False

        return await self._json_rpc_client.execute_program(pid=pid)

    @inspector(re_raise=False)
    async def get_all_programs(
        self,
        *,
        markers: tuple[DescriptionMarker | str, ...],
    ) -> tuple[ProgramData, ...]:
        """
        Return all CCU programs matching the given markers.

        Programs can be filtered by markers in their description field. Only
        programs containing at least one of the specified markers are returned.

        Args:
            markers: Tuple of DescriptionMarker values or strings to filter by.

        Returns:
            Tuple of ProgramData dicts containing id, name, description, etc.

        """
        if not self._supports_programs:
            _LOGGER.debug("GET_ALL_PROGRAMS: Not supported by client for %s", self._interface_id)
            return ()

        return await self._json_rpc_client.get_all_programs(markers=markers)

    @inspector
    async def has_program_ids(self, *, rega_id: int) -> bool:
        """
        Check if a channel is used in any CCU programs.

        Args:
            rega_id: ReGaHSS internal ID of the channel to check.

        Returns:
            True if the channel is referenced in at least one program.

        """
        if not self._supports_programs:
            _LOGGER.debug("HAS_PROGRAM_IDS: Not supported by client for %s", self._interface_id)
            return False

        return await self._json_rpc_client.has_program_ids(rega_id=rega_id)

    @inspector
    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """
        Enable or disable a CCU program.

        Args:
            pid: Program ID (ReGa internal identifier).
            state: True to enable, False to disable the program.

        Returns:
            True if the state was changed successfully.

        """
        return await self._json_rpc_client.set_program_state(pid=pid, state=state)
