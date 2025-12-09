"""
System variable handler.

Handles system variable CRUD operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

from aiohomematic.client.handlers.base import BaseHandler
from aiohomematic.const import DescriptionMarker, SystemVariableData
from aiohomematic.decorators import inspector

if TYPE_CHECKING:
    pass

_LOGGER: Final = logging.getLogger(__name__)


class SystemVariableHandler(BaseHandler):
    """
    Handler for system variable operations.

    Handles:
    - Getting all system variables
    - Getting single system variable
    - Setting system variables
    - Deleting system variables
    """

    __slots__ = ()

    @inspector
    async def delete_system_variable(self, *, name: str) -> bool:
        """Delete a system variable from the backend."""
        return await self._json_rpc_client.delete_system_variable(name=name)

    @inspector(re_raise=False)
    async def get_all_system_variables(
        self,
        *,
        markers: tuple[DescriptionMarker | str, ...],
    ) -> tuple[SystemVariableData, ...] | None:
        """Get all system variables from the backend."""
        return await self._json_rpc_client.get_all_system_variables(markers=markers)

    @inspector
    async def get_system_variable(self, *, name: str) -> Any:
        """Get single system variable from the backend."""
        return await self._json_rpc_client.get_system_variable(name=name)

    @inspector(measure_performance=True)
    async def set_system_variable(self, *, legacy_name: str, value: Any) -> bool:
        """Set a system variable on the backend."""
        return await self._json_rpc_client.set_system_variable(legacy_name=legacy_name, value=value)
