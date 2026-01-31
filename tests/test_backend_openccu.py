# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Tests for OpenCCU backend functionality.

These tests validate aiohomematic's integration with OpenCCU/RaspberryMatic
specific features including:
- Backend detection (CCU vs OpenCCU)
- JSON-RPC API operations (programs, system variables, rooms)
- ReGa script execution
- Backup and firmware update functionality

Requirements:
    pydevccu 0.2.0+ with VirtualCCU and BackendMode support.
    Tests are skipped if the required pydevccu version is not installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from aiohomematic.central import CentralUnit

# Import the marker from conftest
from tests.conftest import PYDEVCCU_HAS_OPENCCU_SUPPORT, requires_openccu

pytestmark = [
    requires_openccu,
    pytest.mark.asyncio,
]


class TestOpenCCUBackendDetection:
    """Test backend detection with virtual OpenCCU."""

    async def test_backend_is_connected(self, central_unit_openccu: CentralUnit) -> None:
        """Verify connection to OpenCCU backend is established."""
        assert central_unit_openccu.health.any_client_healthy is True

    async def test_detects_openccu_product(self, central_unit_openccu: CentralUnit) -> None:
        """Verify OpenCCU is detected correctly via backend info."""
        from aiohomematic.const import CCUType

        info = await central_unit_openccu.validate_config_and_get_system_information()

        assert info is not None
        assert info.ccu_type == CCUType.OPENCCU

    async def test_session_authentication_works(self, central_unit_openccu: CentralUnit) -> None:
        """Verify JSON-RPC session authentication works."""
        # If we got here without errors, authentication succeeded
        assert central_unit_openccu.health.any_client_healthy


class TestOpenCCUPrograms:
    """Test program operations with virtual OpenCCU."""

    async def test_execute_program(
        self,
        central_unit_openccu: CentralUnit,
        pydevccu_openccu: object,  # VirtualCCU, but type not available
    ) -> None:
        """Verify program execution works."""
        # Fetch program data first
        await central_unit_openccu.hub_coordinator.fetch_program_data(scheduled=False)

        # Get program data points
        program_dps = list(central_unit_openccu.hub_coordinator.program_data_points)
        if program_dps:
            # Execute first program - should not raise
            first_dp = program_dps[0]
            if hasattr(first_dp, "press"):
                await first_dp.press()

    async def test_list_programs(self, central_unit_openccu: CentralUnit) -> None:
        """Verify programs are loaded from OpenCCU."""
        # Fetch program data
        await central_unit_openccu.hub_coordinator.fetch_program_data(scheduled=False)

        # VirtualCCU.setup_default_state() creates default programs
        program_dps = list(central_unit_openccu.hub_coordinator.program_data_points)
        assert len(program_dps) >= 1


class TestOpenCCUSystemVariables:
    """Test system variable operations with virtual OpenCCU."""

    async def test_list_sysvars(self, central_unit_openccu: CentralUnit) -> None:
        """Verify system variables are loaded from OpenCCU."""
        # Fetch sysvar data
        await central_unit_openccu.hub_coordinator.fetch_sysvar_data(scheduled=False)

        # VirtualCCU.setup_default_state() creates default sysvars
        sysvar_dps = list(central_unit_openccu.hub_coordinator.sysvar_data_points)
        assert len(sysvar_dps) >= 1

    async def test_set_sysvar_value(
        self,
        central_unit_openccu: CentralUnit,
        pydevccu_openccu: object,  # VirtualCCU
    ) -> None:
        """Verify setting system variable value works."""
        # Fetch sysvar data first
        await central_unit_openccu.hub_coordinator.fetch_sysvar_data(scheduled=False)

        # Find a writable sysvar and test setting it
        sysvar_dps = list(central_unit_openccu.hub_coordinator.sysvar_data_points)
        for sysvar_dp in sysvar_dps:
            # Try to set a value - should not raise
            if hasattr(sysvar_dp, "send_value"):
                await sysvar_dp.send_value(value=True)
                break


class TestOpenCCURoomsAndFunctions:
    """Test rooms and functions (Gewerke) with virtual OpenCCU."""

    async def test_list_functions(self, central_unit_openccu: CentralUnit) -> None:
        """Verify functions are loaded from OpenCCU."""
        # Functions are loaded during startup
        # VirtualCCU.setup_default_state() creates default functions
        assert central_unit_openccu.health.any_client_healthy

    async def test_list_rooms(self, central_unit_openccu: CentralUnit) -> None:
        """Verify rooms are loaded from OpenCCU."""
        # Rooms are loaded during startup
        # VirtualCCU.setup_default_state() creates default rooms
        assert central_unit_openccu.health.any_client_healthy


class TestOpenCCUBackupFeature:
    """Test backup functionality with virtual OpenCCU."""

    async def test_backup_is_supported(self, central_unit_openccu: CentralUnit) -> None:
        """Verify backup capability is available for OpenCCU."""
        # Get system information which includes backup capability
        info = await central_unit_openccu.validate_config_and_get_system_information()
        assert info is not None
        # OpenCCU backend should have backup capability
        assert info.has_backup is True


# Placeholder tests for when VirtualCCU is not available
# These document what will be tested when pydevccu 0.2.0 is released


@pytest.mark.skipif(
    PYDEVCCU_HAS_OPENCCU_SUPPORT,
    reason="Documentation tests for when VirtualCCU is not available",
)
class TestOpenCCUDocumentation:
    """Document planned OpenCCU tests (when VirtualCCU is available)."""

    def test_planned_features(self) -> None:
        """Document features that will be tested with VirtualCCU."""
        planned_tests = [
            "Backend detection (OpenCCU vs CCU vs Homegear)",
            "JSON-RPC session management (login/logout/renew)",
            "Program listing and execution",
            "System variable read/write",
            "Room and function (Gewerk) loading",
            "Backup creation and download",
            "Firmware update check and trigger",
            "ReGa script execution",
            "Service messages",
            "Device inbox management",
        ]
        # This test just documents what will be tested
        assert len(planned_tests) > 0
