"""
System variable handler.

Handles system variable CRUD operations.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from aiohomematic.client.handlers.base import BaseHandler
from aiohomematic.const import DescriptionMarker, SystemVariableData
from aiohomematic.decorators import inspector
from aiohomematic.interfaces.client import SystemVariableOperations

_LOGGER: Final = logging.getLogger(__name__)


class SystemVariableHandler(BaseHandler, SystemVariableOperations):
    """
    Handler for system variable operations.

    Implements SystemVariableOperations protocol for ISP-compliant client operations.

    Handles:
    - Getting all system variables
    - Getting single system variable
    - Setting system variables
    - Deleting system variables
    """

    __slots__ = ()

    @inspector
    async def delete_system_variable(self, *, name: str) -> bool:
        """
        Delete a system variable from the CCU.

        Args:
            name: Name of the system variable to delete.

        Returns:
            True if deleted successfully.

        """
        return await self._json_rpc_client.delete_system_variable(name=name)

    @inspector(re_raise=False)
    async def get_all_system_variables(
        self,
        *,
        markers: tuple[DescriptionMarker | str, ...],
    ) -> tuple[SystemVariableData, ...] | None:
        """
        Return all CCU system variables matching the given markers.

        System variables are global variables stored on the CCU that can be
        used in programs and scripts. Variables can be filtered by markers
        in their description field.

        Args:
            markers: Tuple of DescriptionMarker values or strings to filter by.

        Returns:
            Tuple of SystemVariableData dicts, or None on error.

        """
        return await self._json_rpc_client.get_all_system_variables(markers=markers)

    @inspector
    async def get_system_variable(self, *, name: str) -> Any:
        """
        Return the current value of a system variable.

        Args:
            name: Name of the system variable.

        Returns:
            Current value (type depends on variable definition).

        """
        return await self._json_rpc_client.get_system_variable(name=name)

    @inspector(measure_performance=True)
    async def set_system_variable(self, *, legacy_name: str, value: Any) -> bool:
        """
        Set the value of a system variable.

        Args:
            legacy_name: Original name of the system variable.
            value: New value to set (must match variable's type definition).

        Returns:
            True if the value was set successfully.

        """
        return await self._json_rpc_client.set_system_variable(legacy_name=legacy_name, value=value)
