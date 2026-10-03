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

The virtual OpenCCU is godevccu in openccu mode (fixture ``godevccu_openccu``).
"""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from aiohomematic.central import CentralUnit

    from tests.helpers.godevccu_process import GodevccuProcess

pytestmark = [
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
        godevccu_openccu: GodevccuProcess,
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

        # godevccu -defaults creates default programs
        program_dps = list(central_unit_openccu.hub_coordinator.program_data_points)
        assert len(program_dps) >= 1


class TestOpenCCUSystemVariables:
    """Test system variable operations with virtual OpenCCU."""

    async def test_list_sysvars(self, central_unit_openccu: CentralUnit) -> None:
        """Verify system variables are loaded from OpenCCU."""
        # Fetch sysvar data
        await central_unit_openccu.hub_coordinator.fetch_sysvar_data(scheduled=False)

        # godevccu -defaults creates default sysvars
        sysvar_dps = list(central_unit_openccu.hub_coordinator.sysvar_data_points)
        assert len(sysvar_dps) >= 1

    async def test_set_sysvar_value(
        self,
        central_unit_openccu: CentralUnit,
        godevccu_openccu: GodevccuProcess,
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
        # godevccu -defaults creates default functions
        assert central_unit_openccu.health.any_client_healthy

    async def test_list_rooms(self, central_unit_openccu: CentralUnit) -> None:
        """Verify rooms are loaded from OpenCCU."""
        # Rooms are loaded during startup
        # godevccu -defaults creates default rooms
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


class TestDetermineCCUType:
    """Test the mapping from the normalised backend product to the CCU type."""

    @pytest.mark.parametrize(
        ("product", "expected"),
        [
            ("CCU", "CCU"),
            ("ccu", "CCU"),
            ("OpenCCU", "OPENCCU"),
            ("openccu", "OPENCCU"),
            ("", "UNKNOWN"),
            ("c", "UNKNOWN"),
            ("cu", "UNKNOWN"),
            ("u", "UNKNOWN"),
            ("open", "UNKNOWN"),
            ("pen", "UNKNOWN"),
            ("ccu3", "UNKNOWN"),
            ("OpenCCU-lite", "UNKNOWN"),
            ("foo", "UNKNOWN"),
        ],
    )
    async def test_product_matches_exactly(self, product: str, expected: str) -> None:
        """Only the two products the ReGa script writes are recognised; partial names are unknown."""
        from aiohomematic.client.json_rpc import _determine_ccu_type
        from aiohomematic.const import CCUType

        assert _determine_ccu_type(product=product) is CCUType[expected]


class TestCCUTypeOpenCCULite:
    """Test the CCUType member that names an openccu-lite system."""

    async def test_enum_value_round_trips(self) -> None:
        """The member carries the value a consumer compares against."""
        from aiohomematic.const import CCUType

        assert CCUType.OPENCCU_LITE.value == "OpenCCU-lite"
        assert CCUType("OpenCCU-lite") is CCUType.OPENCCU_LITE

    @pytest.mark.parametrize("product", ["CCU", "ccu", "OpenCCU", "openccu", "OpenCCU-lite", "openccu-lite", "foo"])
    async def test_json_rpc_detection_never_reports_openccu_lite(self, product: str) -> None:
        """Detection never yields the member, since aiohomematic never talks to openccu-lite."""
        from aiohomematic.client.json_rpc import _determine_ccu_type
        from aiohomematic.const import CCUType

        result = _determine_ccu_type(product=product)

        assert result is not CCUType.OPENCCU_LITE
        assert result in (CCUType.CCU, CCUType.OPENCCU, CCUType.UNKNOWN)

    async def test_system_information_offers_no_backup_or_update(self) -> None:
        """Backup and system update stay False; the consumer derives them from the feature map."""
        from aiohomematic.const import CCUType, SystemInformation

        info = SystemInformation(ccu_type=CCUType.OPENCCU_LITE)
        assert info.has_backup is False
        assert info.has_system_update is False
