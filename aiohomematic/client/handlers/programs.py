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

if TYPE_CHECKING:
    from aiohomematic.client import AioJsonRpcAioHttpClient
    from aiohomematic.client.rpc_proxy import BaseRpcProxy
    from aiohomematic.const import Interface
    from aiohomematic.interfaces.client import ClientDependencies

_LOGGER: Final = logging.getLogger(__name__)


class ProgramHandler(BaseHandler):
    """
    Handler for program operations.

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
        """Execute a program on the backend."""
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
        """Get all programs, if available."""
        if not self._supports_programs:
            _LOGGER.debug("GET_ALL_PROGRAMS: Not supported by client for %s", self._interface_id)
            return ()

        return await self._json_rpc_client.get_all_programs(markers=markers)

    @inspector
    async def has_program_ids(self, *, rega_id: int) -> bool:
        """Return if a channel has program ids."""
        if not self._supports_programs:
            _LOGGER.debug("HAS_PROGRAM_IDS: Not supported by client for %s", self._interface_id)
            return False

        return await self._json_rpc_client.has_program_ids(rega_id=rega_id)

    @inspector
    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Set the program state on the backend."""
        return await self._json_rpc_client.set_program_state(pid=pid, state=state)
