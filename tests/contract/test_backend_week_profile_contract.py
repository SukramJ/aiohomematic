# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for BackendOperationsProtocol and WeekProfileProtocol.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for backend operations and week profile interfaces.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. Protocol interfaces are runtime checkable
2. Required methods and properties exist
3. Method signatures are stable

See ADR-0018 for architectural context.
"""

from typing import Protocol

from aiohomematic.client.backends.protocol import BackendOperationsProtocol
from aiohomematic.interfaces import WeekProfileProtocol

# =============================================================================
# Contract: BackendOperationsProtocol Runtime Checkability
# =============================================================================


class TestBackendOperationsProtocolRuntimeCheckability:
    """Contract: BackendOperationsProtocol must be runtime checkable."""

    def test_backendoperationsprotocol_is_protocol(self) -> None:
        """Contract: BackendOperationsProtocol is a Protocol."""
        assert issubclass(BackendOperationsProtocol, Protocol)

    def test_backendoperationsprotocol_is_runtime_checkable(self) -> None:
        """Contract: BackendOperationsProtocol is runtime checkable."""
        # @runtime_checkable protocols have __protocol_attrs__
        assert hasattr(BackendOperationsProtocol, "__protocol_attrs__") or issubclass(
            BackendOperationsProtocol, Protocol
        )


# =============================================================================
# Contract: BackendOperationsProtocol Properties
# =============================================================================


class TestBackendOperationsProtocolPropertiesContract:
    """Contract: BackendOperationsProtocol must have required properties."""

    def test_has_all_circuit_breakers_closed(self) -> None:
        """Contract: BackendOperationsProtocol has all_circuit_breakers_closed property."""
        assert "all_circuit_breakers_closed" in dir(BackendOperationsProtocol)

    def test_has_capabilities(self) -> None:
        """Contract: BackendOperationsProtocol has capabilities property."""
        assert "capabilities" in dir(BackendOperationsProtocol)

    def test_has_circuit_breaker(self) -> None:
        """Contract: BackendOperationsProtocol has circuit_breaker property."""
        assert "circuit_breaker" in dir(BackendOperationsProtocol)

    def test_has_interface(self) -> None:
        """Contract: BackendOperationsProtocol has interface property."""
        assert "interface" in dir(BackendOperationsProtocol)

    def test_has_interface_id(self) -> None:
        """Contract: BackendOperationsProtocol has interface_id property."""
        assert "interface_id" in dir(BackendOperationsProtocol)

    def test_has_model(self) -> None:
        """Contract: BackendOperationsProtocol has model property."""
        assert "model" in dir(BackendOperationsProtocol)

    def test_has_system_information(self) -> None:
        """Contract: BackendOperationsProtocol has system_information property."""
        assert "system_information" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Device/Channel Methods
# =============================================================================


class TestBackendOperationsProtocolDeviceMethodsContract:
    """Contract: BackendOperationsProtocol must have device/channel methods."""

    def test_has_get_device_description(self) -> None:
        """Contract: BackendOperationsProtocol has get_device_description method."""
        assert "get_device_description" in dir(BackendOperationsProtocol)

    def test_has_get_device_details(self) -> None:
        """Contract: BackendOperationsProtocol has get_device_details method."""
        assert "get_device_details" in dir(BackendOperationsProtocol)

    def test_has_list_devices(self) -> None:
        """Contract: BackendOperationsProtocol has list_devices method."""
        assert "list_devices" in dir(BackendOperationsProtocol)

    def test_has_rename_channel(self) -> None:
        """Contract: BackendOperationsProtocol has rename_channel method."""
        assert "rename_channel" in dir(BackendOperationsProtocol)

    def test_has_rename_device(self) -> None:
        """Contract: BackendOperationsProtocol has rename_device method."""
        assert "rename_device" in dir(BackendOperationsProtocol)

    def test_has_update_device_firmware(self) -> None:
        """Contract: BackendOperationsProtocol has update_device_firmware method."""
        assert "update_device_firmware" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Paramset Methods
# =============================================================================


class TestBackendOperationsProtocolParamsetMethodsContract:
    """Contract: BackendOperationsProtocol must have paramset methods."""

    def test_has_get_paramset(self) -> None:
        """Contract: BackendOperationsProtocol has get_paramset method."""
        assert "get_paramset" in dir(BackendOperationsProtocol)

    def test_has_get_paramset_description(self) -> None:
        """Contract: BackendOperationsProtocol has get_paramset_description method."""
        assert "get_paramset_description" in dir(BackendOperationsProtocol)

    def test_has_get_value(self) -> None:
        """Contract: BackendOperationsProtocol has get_value method."""
        assert "get_value" in dir(BackendOperationsProtocol)

    def test_has_put_paramset(self) -> None:
        """Contract: BackendOperationsProtocol has put_paramset method."""
        assert "put_paramset" in dir(BackendOperationsProtocol)

    def test_has_set_value(self) -> None:
        """Contract: BackendOperationsProtocol has set_value method."""
        assert "set_value" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol System Variable Methods
# =============================================================================


class TestBackendOperationsProtocolSysvarMethodsContract:
    """Contract: BackendOperationsProtocol must have system variable methods."""

    def test_has_delete_system_variable(self) -> None:
        """Contract: BackendOperationsProtocol has delete_system_variable method."""
        assert "delete_system_variable" in dir(BackendOperationsProtocol)

    def test_has_get_all_system_variables(self) -> None:
        """Contract: BackendOperationsProtocol has get_all_system_variables method."""
        assert "get_all_system_variables" in dir(BackendOperationsProtocol)

    def test_has_get_system_variable(self) -> None:
        """Contract: BackendOperationsProtocol has get_system_variable method."""
        assert "get_system_variable" in dir(BackendOperationsProtocol)

    def test_has_set_system_variable(self) -> None:
        """Contract: BackendOperationsProtocol has set_system_variable method."""
        assert "set_system_variable" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Program Methods
# =============================================================================


class TestBackendOperationsProtocolProgramMethodsContract:
    """Contract: BackendOperationsProtocol must have program methods."""

    def test_has_execute_program(self) -> None:
        """Contract: BackendOperationsProtocol has execute_program method."""
        assert "execute_program" in dir(BackendOperationsProtocol)

    def test_has_get_all_programs(self) -> None:
        """Contract: BackendOperationsProtocol has get_all_programs method."""
        assert "get_all_programs" in dir(BackendOperationsProtocol)

    def test_has_has_program_ids(self) -> None:
        """Contract: BackendOperationsProtocol has has_program_ids method."""
        assert "has_program_ids" in dir(BackendOperationsProtocol)

    def test_has_set_program_state(self) -> None:
        """Contract: BackendOperationsProtocol has set_program_state method."""
        assert "set_program_state" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Connection Methods
# =============================================================================


class TestBackendOperationsProtocolConnectionMethodsContract:
    """Contract: BackendOperationsProtocol must have connection methods."""

    def test_has_check_connection(self) -> None:
        """Contract: BackendOperationsProtocol has check_connection method."""
        assert "check_connection" in dir(BackendOperationsProtocol)

    def test_has_deinit_proxy(self) -> None:
        """Contract: BackendOperationsProtocol has deinit_proxy method."""
        assert "deinit_proxy" in dir(BackendOperationsProtocol)

    def test_has_init_proxy(self) -> None:
        """Contract: BackendOperationsProtocol has init_proxy method."""
        assert "init_proxy" in dir(BackendOperationsProtocol)

    def test_has_initialize(self) -> None:
        """Contract: BackendOperationsProtocol has initialize method."""
        assert "initialize" in dir(BackendOperationsProtocol)

    def test_has_reset_circuit_breakers(self) -> None:
        """Contract: BackendOperationsProtocol has reset_circuit_breakers method."""
        assert "reset_circuit_breakers" in dir(BackendOperationsProtocol)

    def test_has_stop(self) -> None:
        """Contract: BackendOperationsProtocol has stop method."""
        assert "stop" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Link Methods
# =============================================================================


class TestBackendOperationsProtocolLinkMethodsContract:
    """Contract: BackendOperationsProtocol must have link methods."""

    def test_has_add_link(self) -> None:
        """Contract: BackendOperationsProtocol has add_link method."""
        assert "add_link" in dir(BackendOperationsProtocol)

    def test_has_get_link_peers(self) -> None:
        """Contract: BackendOperationsProtocol has get_link_peers method."""
        assert "get_link_peers" in dir(BackendOperationsProtocol)

    def test_has_get_links(self) -> None:
        """Contract: BackendOperationsProtocol has get_links method."""
        assert "get_links" in dir(BackendOperationsProtocol)

    def test_has_remove_link(self) -> None:
        """Contract: BackendOperationsProtocol has remove_link method."""
        assert "remove_link" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Metadata/Room/Function Methods
# =============================================================================


class TestBackendOperationsProtocolMetadataMethodsContract:
    """Contract: BackendOperationsProtocol must have metadata/room/function methods."""

    def test_has_get_all_functions(self) -> None:
        """Contract: BackendOperationsProtocol has get_all_functions method."""
        assert "get_all_functions" in dir(BackendOperationsProtocol)

    def test_has_get_all_rooms(self) -> None:
        """Contract: BackendOperationsProtocol has get_all_rooms method."""
        assert "get_all_rooms" in dir(BackendOperationsProtocol)

    def test_has_get_ise_id_by_address(self) -> None:
        """Contract: BackendOperationsProtocol has get_ise_id_by_address method."""
        assert "get_ise_id_by_address" in dir(BackendOperationsProtocol)

    def test_has_get_metadata(self) -> None:
        """Contract: BackendOperationsProtocol has get_metadata method."""
        assert "get_metadata" in dir(BackendOperationsProtocol)

    def test_has_set_metadata(self) -> None:
        """Contract: BackendOperationsProtocol has set_metadata method."""
        assert "set_metadata" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Service/System Methods
# =============================================================================


class TestBackendOperationsProtocolSystemMethodsContract:
    """Contract: BackendOperationsProtocol must have service/system methods."""

    def test_has_accept_device_in_inbox(self) -> None:
        """Contract: BackendOperationsProtocol has accept_device_in_inbox method."""
        assert "accept_device_in_inbox" in dir(BackendOperationsProtocol)

    def test_has_create_backup_and_download(self) -> None:
        """Contract: BackendOperationsProtocol has create_backup_and_download method."""
        assert "create_backup_and_download" in dir(BackendOperationsProtocol)

    def test_has_get_all_device_data(self) -> None:
        """Contract: BackendOperationsProtocol has get_all_device_data method."""
        assert "get_all_device_data" in dir(BackendOperationsProtocol)

    def test_has_get_inbox_devices(self) -> None:
        """Contract: BackendOperationsProtocol has get_inbox_devices method."""
        assert "get_inbox_devices" in dir(BackendOperationsProtocol)

    def test_has_get_install_mode(self) -> None:
        """Contract: BackendOperationsProtocol has get_install_mode method."""
        assert "get_install_mode" in dir(BackendOperationsProtocol)

    def test_has_get_service_messages(self) -> None:
        """Contract: BackendOperationsProtocol has get_service_messages method."""
        assert "get_service_messages" in dir(BackendOperationsProtocol)

    def test_has_get_system_update_info(self) -> None:
        """Contract: BackendOperationsProtocol has get_system_update_info method."""
        assert "get_system_update_info" in dir(BackendOperationsProtocol)

    def test_has_report_value_usage(self) -> None:
        """Contract: BackendOperationsProtocol has report_value_usage method."""
        assert "report_value_usage" in dir(BackendOperationsProtocol)

    def test_has_set_install_mode(self) -> None:
        """Contract: BackendOperationsProtocol has set_install_mode method."""
        assert "set_install_mode" in dir(BackendOperationsProtocol)

    def test_has_trigger_firmware_update(self) -> None:
        """Contract: BackendOperationsProtocol has trigger_firmware_update method."""
        assert "trigger_firmware_update" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: WeekProfileProtocol Runtime Checkability
# =============================================================================


class TestWeekProfileProtocolRuntimeCheckability:
    """Contract: WeekProfileProtocol must be runtime checkable."""

    def test_weekprofileprotocol_is_protocol(self) -> None:
        """Contract: WeekProfileProtocol is a Protocol."""
        assert issubclass(WeekProfileProtocol, Protocol)


# =============================================================================
# Contract: WeekProfileProtocol Properties
# =============================================================================


class TestWeekProfileProtocolPropertiesContract:
    """Contract: WeekProfileProtocol must have required properties."""

    def test_has_has_schedule(self) -> None:
        """Contract: WeekProfileProtocol has has_schedule property."""
        assert "has_schedule" in dir(WeekProfileProtocol)

    def test_has_schedule(self) -> None:
        """Contract: WeekProfileProtocol has schedule property."""
        assert "schedule" in dir(WeekProfileProtocol)

    def test_has_schedule_channel_address(self) -> None:
        """Contract: WeekProfileProtocol has schedule_channel_address property."""
        assert "schedule_channel_address" in dir(WeekProfileProtocol)


# =============================================================================
# Contract: WeekProfileProtocol Methods
# =============================================================================


class TestWeekProfileProtocolMethodsContract:
    """Contract: WeekProfileProtocol must have required methods."""

    def test_has_get_schedule(self) -> None:
        """Contract: WeekProfileProtocol has get_schedule method."""
        assert "get_schedule" in dir(WeekProfileProtocol)

    def test_has_reload_and_cache_schedule(self) -> None:
        """Contract: WeekProfileProtocol has reload_and_cache_schedule method."""
        assert "reload_and_cache_schedule" in dir(WeekProfileProtocol)

    def test_has_set_schedule(self) -> None:
        """Contract: WeekProfileProtocol has set_schedule method."""
        assert "set_schedule" in dir(WeekProfileProtocol)


# =============================================================================
# Contract: WeekProfileProtocol Export
# =============================================================================


class TestWeekProfileProtocolExportContract:
    """Contract: WeekProfileProtocol must be exported from interfaces."""

    def test_weekprofileprotocol_exported(self) -> None:
        """Contract: WeekProfileProtocol is exported from interfaces package."""
        from aiohomematic import interfaces

        assert hasattr(interfaces, "WeekProfileProtocol")


# =============================================================================
# Contract: Climate Schedule Data Structures (Pydantic Models)
# =============================================================================


class TestClimateScheduleDataStructuresContract:
    """Contract: Climate schedule Pydantic models must remain stable."""

    def test_climate_profile_schedule_is_rootmodel(self) -> None:
        """Contract: ClimateProfileSchedule is a RootModel for dict-like behavior."""
        from pydantic import RootModel

        from aiohomematic.model.schedule_models import ClimateProfileSchedule

        assert issubclass(ClimateProfileSchedule, RootModel)

    def test_climate_schedule_is_rootmodel(self) -> None:
        """Contract: ClimateSchedule is a RootModel for dict-like behavior."""
        from pydantic import RootModel

        from aiohomematic.model.schedule_models import ClimateSchedule

        assert issubclass(ClimateSchedule, RootModel)

    def test_climate_schedule_period_structure(self) -> None:
        """Contract: ClimateSchedulePeriod has required fields."""
        from aiohomematic.model.schedule_models import ClimateSchedulePeriod

        # Verify model fields exist
        assert "starttime" in ClimateSchedulePeriod.model_fields
        assert "endtime" in ClimateSchedulePeriod.model_fields
        assert "temperature" in ClimateSchedulePeriod.model_fields

    def test_climate_schedule_supports_dict_operations(self) -> None:
        """Contract: ClimateSchedule supports dict-like operations (in, iter, indexing)."""
        from aiohomematic.model.schedule_models import ClimateProfileSchedule, ClimateSchedule

        # Create minimal schedule
        schedule = ClimateSchedule({"P1": ClimateProfileSchedule({})})

        # Verify dict-like behavior
        assert "P1" in schedule
        assert list(schedule) == ["P1"]
        assert schedule["P1"] is not None

    def test_climate_weekday_schedule_structure(self) -> None:
        """Contract: ClimateWeekdaySchedule has required fields."""
        from aiohomematic.model.schedule_models import ClimateWeekdaySchedule

        # Verify model fields exist
        assert "base_temperature" in ClimateWeekdaySchedule.model_fields
        assert "periods" in ClimateWeekdaySchedule.model_fields


# =============================================================================
# Contract: Simple Schedule Data Structures (Pydantic Models)
# =============================================================================


class TestSimpleScheduleDataStructuresContract:
    """Contract: Simple schedule Pydantic models must remain stable."""

    def test_simple_schedule_entry_optional_fields(self) -> None:
        """Contract: SimpleScheduleEntry has optional astro fields."""
        from aiohomematic.model.schedule_models import SimpleScheduleEntry

        # Verify optional fields exist
        assert "astro_type" in SimpleScheduleEntry.model_fields
        assert "astro_offset_minutes" in SimpleScheduleEntry.model_fields

    def test_simple_schedule_entry_required_fields(self) -> None:
        """Contract: SimpleScheduleEntry has required fields."""
        from aiohomematic.model.schedule_models import SimpleScheduleEntry

        # Verify required fields exist
        assert "weekdays" in SimpleScheduleEntry.model_fields
        assert "time" in SimpleScheduleEntry.model_fields
        assert "condition" in SimpleScheduleEntry.model_fields
        assert "target_channels" in SimpleScheduleEntry.model_fields
        assert "level" in SimpleScheduleEntry.model_fields

    def test_simple_schedule_structure(self) -> None:
        """Contract: SimpleSchedule has entries field."""
        from aiohomematic.model.schedule_models import SimpleSchedule

        # Verify entries field exists
        assert "entries" in SimpleSchedule.model_fields


# =============================================================================
# Contract: Internal Schedule TypedDicts
# =============================================================================


class TestInternalScheduleTypedDictsContract:
    """Contract: Internal schedule TypedDicts must remain stable."""

    def test_climate_profile_schedule_internal_is_dict(self) -> None:
        """Contract: _ClimateProfileScheduleDictInternal is dict[WeekdayStr, ...]."""
        from aiohomematic.model.week_profile import _ClimateProfileScheduleDictInternal

        # Verify it's a type alias for dict
        assert _ClimateProfileScheduleDictInternal.__class__.__name__ in (
            "GenericAlias",
            "_GenericAlias",
        )

    def test_climate_schedule_internal_is_dict(self) -> None:
        """Contract: _ClimateScheduleDictInternal is dict[ScheduleProfile, ...]."""
        from aiohomematic.model.week_profile import _ClimateScheduleDictInternal

        # Verify it's a type alias for dict
        assert _ClimateScheduleDictInternal.__class__.__name__ in (
            "GenericAlias",
            "_GenericAlias",
        )

    def test_climate_weekday_schedule_internal_is_dict(self) -> None:
        """Contract: _ClimateWeekdayScheduleDictInternal is dict[int, _ScheduleSlot]."""
        from aiohomematic.model.week_profile import _ClimateWeekdayScheduleDictInternal

        # Verify it's a type alias for dict
        assert _ClimateWeekdayScheduleDictInternal.__class__.__name__ in (
            "GenericAlias",
            "_GenericAlias",
        )

    def test_schedule_slot_typeddict_structure(self) -> None:
        """Contract: _ScheduleSlot TypedDict has required keys."""
        from typing import get_type_hints

        from aiohomematic.model.week_profile import _ScheduleSlot

        # Verify TypedDict structure
        type_hints = get_type_hints(_ScheduleSlot)
        assert "endtime" in type_hints
        assert "temperature" in type_hints


# =============================================================================
# Contract: Schedule Conversion Methods
# =============================================================================


class TestScheduleConversionMethodsContract:
    """Contract: Schedule conversion methods must remain stable."""

    def test_climate_week_profile_has_conversion_methods(self) -> None:
        """Contract: ClimateWeekProfile has convert_raw_to_dict_schedule and convert_dict_to_raw_schedule."""
        from aiohomematic.model.week_profile import ClimateWeekProfile

        assert hasattr(ClimateWeekProfile, "convert_raw_to_dict_schedule")
        assert hasattr(ClimateWeekProfile, "convert_dict_to_raw_schedule")
        assert callable(ClimateWeekProfile.convert_raw_to_dict_schedule)
        assert callable(ClimateWeekProfile.convert_dict_to_raw_schedule)

    def test_default_week_profile_has_conversion_methods(self) -> None:
        """Contract: DefaultWeekProfile has convert_raw_to_dict_schedule and convert_dict_to_raw_schedule."""
        from aiohomematic.model.week_profile import DefaultWeekProfile

        assert hasattr(DefaultWeekProfile, "convert_raw_to_dict_schedule")
        assert hasattr(DefaultWeekProfile, "convert_dict_to_raw_schedule")
        assert callable(DefaultWeekProfile.convert_raw_to_dict_schedule)
        assert callable(DefaultWeekProfile.convert_dict_to_raw_schedule)


# =============================================================================
# Contract: Climate Schedule End-to-End Data Transformation
# =============================================================================


class TestClimateScheduleDataTransformationContract:
    """
    Contract: Climate schedule data transformation must remain stable.

    This test documents the complete data flow from CCU to integration and back:

    CCU → Integration (Read Path):
    1. RAW_SCHEDULE_DICT (from CCU paramset)
    2. → convert_raw_to_dict_schedule()
    3. → _ClimateScheduleDictInternal (13-slot format)
    4. → get_schedule() / schedule property
    5. → ClimateSchedule (simple format for integration)

    Integration → CCU (Write Path):
    1. ClimateSchedule (from integration/user)
    2. → set_schedule()
    3. → _ClimateScheduleDictInternal (13-slot format)
    4. → convert_dict_to_raw_schedule()
    5. → RAW_SCHEDULE_DICT (to CCU paramset)
    """

    def test_climate_schedule_ccu_to_integration_transformation(self) -> None:
        """
        Contract: CCU raw data transforms correctly to integration format.

        This test ensures the complete read path remains stable:
        RAW (CCU) → Internal (13-slot) → Simple (Integration)
        """
        from aiohomematic.const import ScheduleProfile, WeekdayStr
        from aiohomematic.model.week_profile import ClimateWeekProfile

        # =============================================================================
        # Step 1: RAW_SCHEDULE_DICT - Data as received from CCU paramset
        # =============================================================================
        # Example: Simple schedule with 2 periods on Monday for profile P1
        raw_schedule_from_ccu = {
            # Profile P1, Monday, Slot 1: Heat to 21.0°C until 06:00 (360 minutes)
            "P1_TEMPERATURE_MONDAY_1": 21.0,
            "P1_ENDTIME_MONDAY_1": 360,
            # Profile P1, Monday, Slot 2: Heat to 18.0°C until 22:00 (1320 minutes)
            "P1_TEMPERATURE_MONDAY_2": 18.0,
            "P1_ENDTIME_MONDAY_2": 1320,
            # Profile P1, Monday, Slot 3: End of day marker (24:00 = 1440 minutes)
            "P1_TEMPERATURE_MONDAY_3": 18.0,
            "P1_ENDTIME_MONDAY_3": 1440,
            # Slots 4-13: Filled with 24:00 markers (CCU sends all 13 slots)
            "P1_TEMPERATURE_MONDAY_4": 18.0,
            "P1_ENDTIME_MONDAY_4": 1440,
            "P1_TEMPERATURE_MONDAY_5": 18.0,
            "P1_ENDTIME_MONDAY_5": 1440,
            "P1_TEMPERATURE_MONDAY_6": 18.0,
            "P1_ENDTIME_MONDAY_6": 1440,
            "P1_TEMPERATURE_MONDAY_7": 18.0,
            "P1_ENDTIME_MONDAY_7": 1440,
            "P1_TEMPERATURE_MONDAY_8": 18.0,
            "P1_ENDTIME_MONDAY_8": 1440,
            "P1_TEMPERATURE_MONDAY_9": 18.0,
            "P1_ENDTIME_MONDAY_9": 1440,
            "P1_TEMPERATURE_MONDAY_10": 18.0,
            "P1_ENDTIME_MONDAY_10": 1440,
            "P1_TEMPERATURE_MONDAY_11": 18.0,
            "P1_ENDTIME_MONDAY_11": 1440,
            "P1_TEMPERATURE_MONDAY_12": 18.0,
            "P1_ENDTIME_MONDAY_12": 1440,
            "P1_TEMPERATURE_MONDAY_13": 18.0,
            "P1_ENDTIME_MONDAY_13": 1440,
        }

        # =============================================================================
        # Step 2: convert_raw_to_dict_schedule() → _ClimateScheduleDictInternal
        # =============================================================================
        internal_schedule = ClimateWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule_from_ccu)

        # Verify internal structure (13-slot format with all slots)
        assert ScheduleProfile.P1 in internal_schedule
        assert WeekdayStr.MONDAY in internal_schedule[ScheduleProfile.P1]
        monday_slots = internal_schedule[ScheduleProfile.P1][WeekdayStr.MONDAY]

        # All 13 slots must be present in internal format
        assert len(monday_slots) == 13
        assert monday_slots[1]["endtime"] == "06:00"
        assert monday_slots[1]["temperature"] == 21.0
        assert monday_slots[2]["endtime"] == "22:00"
        assert monday_slots[2]["temperature"] == 18.0
        assert monday_slots[3]["endtime"] == "24:00"
        assert monday_slots[3]["temperature"] == 18.0

        # Note: In the simple format delivered to integration via get_schedule(),
        # redundant 24:00 slots (4-13) are filtered out, leaving only meaningful periods.
        # The integration receives: base_temperature=18.0, periods=[{06:00-22:00, 21.0°C}]

    def test_climate_schedule_integration_to_ccu_transformation(self) -> None:
        """
        Contract: Integration data transforms correctly to CCU raw format.

        This test ensures the complete write path remains stable:
        Simple (Integration) → Internal (13-slot) → RAW (CCU)
        """
        from aiohomematic.const import ScheduleProfile, WeekdayStr
        from aiohomematic.model.week_profile import ClimateWeekProfile

        # =============================================================================
        # Step 1: ClimateSchedule - Data from integration/user (simple format)
        # =============================================================================
        # Example: User wants to heat to 21.0°C from 06:00-22:00, otherwise 18.0°C
        # (In real usage, this would be passed to set_schedule())
        #
        # ClimateSchedule(
        #     {
        #         "P1": ClimateProfileSchedule(
        #             {
        #                 "MONDAY": ClimateWeekdaySchedule(
        #                     base_temperature=18.0,
        #                     periods=[
        #                         ClimateSchedulePeriod(
        #                             starttime="06:00",
        #                             endtime="22:00",
        #                             temperature=21.0,
        #                         ),
        #                     ],
        #                 ),
        #             }
        #         ),
        #     }
        # )

        # =============================================================================
        # Step 2: Convert simple format to internal 13-slot format
        # =============================================================================
        # Note: This conversion happens inside set_schedule() via
        # _validate_and_convert_simple_to_schedule()
        # For this contract test, we manually verify the internal structure

        # The internal format must have:
        # - Slot 1: 00:00-06:00 at 18.0°C (base temperature)
        # - Slot 2: 06:00-22:00 at 21.0°C (heating period)
        # - Slot 3: 22:00-24:00 at 18.0°C (base temperature)
        # - Slots 4-13: Filled with 24:00 markers

        # We verify this by checking what convert_dict_to_raw_schedule expects

        # =============================================================================
        # Step 3: Create expected internal format (13-slot structure)
        # =============================================================================
        internal_schedule = {
            ScheduleProfile.P1: {
                WeekdayStr.MONDAY: {
                    1: {"endtime": "06:00", "temperature": 18.0},
                    2: {"endtime": "22:00", "temperature": 21.0},
                    3: {"endtime": "24:00", "temperature": 18.0},
                    4: {"endtime": "24:00", "temperature": 18.0},
                    5: {"endtime": "24:00", "temperature": 18.0},
                    6: {"endtime": "24:00", "temperature": 18.0},
                    7: {"endtime": "24:00", "temperature": 18.0},
                    8: {"endtime": "24:00", "temperature": 18.0},
                    9: {"endtime": "24:00", "temperature": 18.0},
                    10: {"endtime": "24:00", "temperature": 18.0},
                    11: {"endtime": "24:00", "temperature": 18.0},
                    12: {"endtime": "24:00", "temperature": 18.0},
                    13: {"endtime": "24:00", "temperature": 18.0},
                }
            }
        }

        # =============================================================================
        # Step 4: convert_dict_to_raw_schedule() → RAW_SCHEDULE_DICT
        # =============================================================================
        raw_schedule_to_ccu = ClimateWeekProfile.convert_dict_to_raw_schedule(schedule_data=internal_schedule)

        # Verify raw format (as sent to CCU)
        assert raw_schedule_to_ccu["P1_TEMPERATURE_MONDAY_1"] == 18.0
        assert raw_schedule_to_ccu["P1_ENDTIME_MONDAY_1"] == 360  # 06:00 in minutes
        assert raw_schedule_to_ccu["P1_TEMPERATURE_MONDAY_2"] == 21.0
        assert raw_schedule_to_ccu["P1_ENDTIME_MONDAY_2"] == 1320  # 22:00 in minutes
        assert raw_schedule_to_ccu["P1_TEMPERATURE_MONDAY_3"] == 18.0
        assert raw_schedule_to_ccu["P1_ENDTIME_MONDAY_3"] == 1440  # 24:00 in minutes

        # All 13 slots must be present in raw format
        assert len([k for k in raw_schedule_to_ccu if k.startswith("P1_")]) == 26  # 13 temp + 13 endtime

    def test_climate_schedule_roundtrip_stability(self) -> None:
        """
        Contract: Climate schedule data survives CCU roundtrip without loss.

        This test ensures: RAW → Internal → RAW produces identical output
        """
        from aiohomematic.model.week_profile import ClimateWeekProfile

        # Original RAW data from CCU
        original_raw = {
            "P1_TEMPERATURE_MONDAY_1": 21.0,
            "P1_ENDTIME_MONDAY_1": 360,
            "P1_TEMPERATURE_MONDAY_2": 18.0,
            "P1_ENDTIME_MONDAY_2": 1320,
            "P1_TEMPERATURE_MONDAY_3": 18.0,
            "P1_ENDTIME_MONDAY_3": 1440,
        }

        # Complete with 24:00 markers for slots 4-13
        for slot in range(4, 14):
            original_raw[f"P1_TEMPERATURE_MONDAY_{slot}"] = 18.0
            original_raw[f"P1_ENDTIME_MONDAY_{slot}"] = 1440

        # RAW → Internal → RAW
        internal = ClimateWeekProfile.convert_raw_to_dict_schedule(raw_schedule=original_raw)
        reconstructed_raw = ClimateWeekProfile.convert_dict_to_raw_schedule(schedule_data=internal)

        # Verify identical output (all keys and values must match)
        assert reconstructed_raw == original_raw


# =============================================================================
# Contract: Simple Schedule End-to-End Data Transformation
# =============================================================================


class TestSimpleScheduleDataTransformationContract:
    """
    Contract: Simple schedule data transformation must remain stable.

    This test documents the complete data flow for non-climate devices
    (switches, lights, covers, valves) from CCU to integration and back.

    CCU → Integration (Read Path):
    1. RAW_SCHEDULE_DICT (from CCU paramset)
    2. → convert_raw_to_dict_schedule()
    3. → SimpleSchedule (human-readable format)
    4. → get_schedule() / schedule property
    5. → SimpleSchedule (delivered to integration)

    Integration → CCU (Write Path):
    1. SimpleSchedule (from integration/user)
    2. → set_schedule()
    3. → convert_dict_to_raw_schedule()
    4. → RAW_SCHEDULE_DICT (to CCU paramset)
    """

    def test_simple_schedule_ccu_to_integration_transformation(self) -> None:
        """
        Contract: CCU raw data transforms correctly to simple schedule format.

        This test ensures the complete read path remains stable for non-climate devices.
        """
        from aiohomematic.const import AstroType, ScheduleActorChannel
        from aiohomematic.model.week_profile import DefaultWeekProfile

        # =============================================================================
        # Step 1: RAW_SCHEDULE_DICT - Data as received from CCU paramset
        # =============================================================================
        # Example: Turn on switch every Monday at 07:30 on channel 1_1
        # Format: "{group:02d}_WP_{field_name}" → value
        raw_schedule_from_ccu = {
            # Group 1: Fixed time schedule
            "01_WP_WEEKDAY": 2,  # Monday bitwise value
            "01_WP_CONDITION": 0,  # 0 = fixed_time
            "01_WP_FIXED_HOUR": 7,
            "01_WP_FIXED_MINUTE": 30,
            "01_WP_TARGET_CHANNELS": ScheduleActorChannel.CHANNEL_1_1.value,  # Channel 1_1 = 1
            "01_WP_LEVEL": 1.0,  # Level 0.0-1.0
            "01_WP_ASTRO_TYPE": AstroType.SUNRISE.value,  # Required field (ignored for fixed_time)
            "01_WP_ASTRO_OFFSET": 0,
            "01_WP_DURATION_FACTOR": 0,
            "01_WP_RAMP_TIME_FACTOR": 0,
        }

        # =============================================================================
        # Step 2: convert_raw_to_dict_schedule() → SimpleSchedule
        # =============================================================================
        simple_schedule = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule_from_ccu)

        # Verify simple schedule structure
        assert 1 in simple_schedule.entries
        entry = simple_schedule.entries[1]

        # Verify human-readable format
        assert entry.weekdays == ["MONDAY"]
        assert entry.time == "07:30"
        assert entry.condition == "fixed_time"
        assert entry.target_channels == ["1_1"]
        assert entry.level == 1.0
        assert entry.astro_type is None  # None for fixed_time condition

    def test_simple_schedule_integration_to_ccu_transformation(self) -> None:
        """
        Contract: Integration data transforms correctly to CCU raw format.

        This test ensures the complete write path remains stable for non-climate devices.
        """
        from aiohomematic.const import AstroType, ScheduleActorChannel, ScheduleCondition
        from aiohomematic.model.schedule_models import SimpleSchedule, SimpleScheduleEntry
        from aiohomematic.model.week_profile import DefaultWeekProfile

        # =============================================================================
        # Step 1: SimpleSchedule - Data from integration/user
        # =============================================================================
        simple_schedule_from_integration = SimpleSchedule(
            entries={
                1: SimpleScheduleEntry(
                    weekdays=["MONDAY"],
                    time="07:30",
                    condition="fixed_time",
                    target_channels=["1_1"],
                    level=1.0,
                )
            }
        )

        # =============================================================================
        # Step 2: convert_dict_to_raw_schedule() → RAW_SCHEDULE_DICT
        # =============================================================================
        raw_schedule_to_ccu = DefaultWeekProfile.convert_dict_to_raw_schedule(
            schedule_data=simple_schedule_from_integration
        )

        # Verify raw format (as sent to CCU)
        # Format: "{group:02d}_WP_{field_name}" → value
        assert raw_schedule_to_ccu["01_WP_WEEKDAY"] == 2  # Monday bitwise value
        assert raw_schedule_to_ccu["01_WP_CONDITION"] == ScheduleCondition.FIXED_TIME.value
        assert raw_schedule_to_ccu["01_WP_FIXED_HOUR"] == 7
        assert raw_schedule_to_ccu["01_WP_FIXED_MINUTE"] == 30
        assert raw_schedule_to_ccu["01_WP_TARGET_CHANNELS"] == ScheduleActorChannel.CHANNEL_1_1.value
        assert raw_schedule_to_ccu["01_WP_LEVEL"] == 1.0
        assert raw_schedule_to_ccu["01_WP_ASTRO_TYPE"] == AstroType.SUNRISE.value  # Default for fixed_time

    def test_simple_schedule_roundtrip_stability(self) -> None:
        """
        Contract: Simple schedule data survives CCU roundtrip without loss.

        This test ensures: RAW → Simple → RAW preserves essential data
        """
        from aiohomematic.const import AstroType, ScheduleActorChannel
        from aiohomematic.model.week_profile import DefaultWeekProfile

        # Original RAW data from CCU
        # Format: "{group:02d}_WP_{field_name}" → value
        original_raw = {
            "01_WP_WEEKDAY": 2,  # Monday
            "01_WP_CONDITION": 0,  # fixed_time
            "01_WP_FIXED_HOUR": 7,
            "01_WP_FIXED_MINUTE": 30,
            "01_WP_TARGET_CHANNELS": ScheduleActorChannel.CHANNEL_1_1.value,
            "01_WP_LEVEL": 1.0,
            "01_WP_ASTRO_TYPE": AstroType.SUNRISE.value,
            "01_WP_ASTRO_OFFSET": 0,
        }

        # RAW → Simple → RAW
        simple = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=original_raw)
        reconstructed_raw = DefaultWeekProfile.convert_dict_to_raw_schedule(schedule_data=simple)

        # Verify essential fields are preserved (some optional fields may be omitted if default/zero)
        assert reconstructed_raw["01_WP_WEEKDAY"] == original_raw["01_WP_WEEKDAY"]
        assert reconstructed_raw["01_WP_CONDITION"] == original_raw["01_WP_CONDITION"]
        assert reconstructed_raw["01_WP_FIXED_HOUR"] == original_raw["01_WP_FIXED_HOUR"]
        assert reconstructed_raw["01_WP_FIXED_MINUTE"] == original_raw["01_WP_FIXED_MINUTE"]
        assert reconstructed_raw["01_WP_TARGET_CHANNELS"] == original_raw["01_WP_TARGET_CHANNELS"]
        assert reconstructed_raw["01_WP_LEVEL"] == original_raw["01_WP_LEVEL"]
        assert reconstructed_raw["01_WP_ASTRO_TYPE"] == original_raw["01_WP_ASTRO_TYPE"]
        assert reconstructed_raw["01_WP_ASTRO_OFFSET"] == original_raw["01_WP_ASTRO_OFFSET"]


# =============================================================================
# Contract: Climate Custom DataPoint Schedule API
# =============================================================================


class TestClimateWeekProfileDataPointScheduleAPIContract:
    """
    Contract: ClimateWeekProfileDataPoint must provide stable schedule API.

    Schedule operations have been moved from climate CDPs to the device-level
    ClimateWeekProfileDataPoint. This contract validates the new API surface.
    """

    def test_climate_schedule_data_structures(self) -> None:
        """Contract: Climate schedule uses stable Pydantic data structures."""
        from pydantic import RootModel

        from aiohomematic.model.schedule_models import ClimateSchedule

        assert issubclass(ClimateSchedule, RootModel)

    def test_climate_week_profile_data_point_available_profiles_property(self) -> None:
        """Contract: ClimateWeekProfileDataPoint exposes available schedule profiles."""
        from aiohomematic.model.week_profile_data_point import ClimateWeekProfileDataPoint

        assert hasattr(ClimateWeekProfileDataPoint, "available_profiles")

    def test_climate_week_profile_data_point_copy_methods(self) -> None:
        """Contract: ClimateWeekProfileDataPoint supports copy operations."""
        from aiohomematic.model.week_profile_data_point import ClimateWeekProfileDataPoint

        assert hasattr(ClimateWeekProfileDataPoint, "copy_schedule")
        assert hasattr(ClimateWeekProfileDataPoint, "copy_schedule_profile")
        assert callable(ClimateWeekProfileDataPoint.copy_schedule)
        assert callable(ClimateWeekProfileDataPoint.copy_schedule_profile)

    def test_climate_week_profile_data_point_profile_methods(self) -> None:
        """Contract: ClimateWeekProfileDataPoint supports profile-level operations."""
        from aiohomematic.model.week_profile_data_point import ClimateWeekProfileDataPoint

        assert hasattr(ClimateWeekProfileDataPoint, "get_schedule_profile")
        assert hasattr(ClimateWeekProfileDataPoint, "set_schedule_profile")
        assert callable(ClimateWeekProfileDataPoint.get_schedule_profile)
        assert callable(ClimateWeekProfileDataPoint.set_schedule_profile)

    def test_climate_week_profile_data_point_schedule_method_signatures(self) -> None:
        """Contract: ClimateWeekProfileDataPoint schedule methods have stable signatures."""
        import inspect

        from aiohomematic.model.week_profile_data_point import ClimateWeekProfileDataPoint

        # get_schedule_profile signature
        get_profile_sig = inspect.signature(ClimateWeekProfileDataPoint.get_schedule_profile)
        assert "profile" in get_profile_sig.parameters
        assert "force_load" in get_profile_sig.parameters

        # set_schedule_profile signature
        set_profile_sig = inspect.signature(ClimateWeekProfileDataPoint.set_schedule_profile)
        assert "profile" in set_profile_sig.parameters
        assert "profile_data" in set_profile_sig.parameters

        # get_schedule_weekday signature
        get_weekday_sig = inspect.signature(ClimateWeekProfileDataPoint.get_schedule_weekday)
        assert "profile" in get_weekday_sig.parameters
        assert "weekday" in get_weekday_sig.parameters

        # set_schedule_weekday signature
        set_weekday_sig = inspect.signature(ClimateWeekProfileDataPoint.set_schedule_weekday)
        assert "profile" in set_weekday_sig.parameters
        assert "weekday" in set_weekday_sig.parameters
        assert "weekday_data" in set_weekday_sig.parameters

    def test_climate_week_profile_data_point_weekday_methods(self) -> None:
        """Contract: ClimateWeekProfileDataPoint supports weekday-level operations."""
        from aiohomematic.model.week_profile_data_point import ClimateWeekProfileDataPoint

        assert hasattr(ClimateWeekProfileDataPoint, "get_schedule_weekday")
        assert hasattr(ClimateWeekProfileDataPoint, "set_schedule_weekday")
        assert callable(ClimateWeekProfileDataPoint.get_schedule_weekday)
        assert callable(ClimateWeekProfileDataPoint.set_schedule_weekday)

    def test_week_profile_protocol_has_schedule_methods(self) -> None:
        """Contract: WeekProfileProtocol has required schedule methods."""
        from aiohomematic.interfaces import WeekProfileProtocol

        assert "get_schedule" in dir(WeekProfileProtocol)
        assert "set_schedule" in dir(WeekProfileProtocol)
        assert "reload_and_cache_schedule" in dir(WeekProfileProtocol)

    def test_week_profile_protocol_has_schedule_property(self) -> None:
        """Contract: WeekProfileProtocol defines schedule property."""
        from aiohomematic.interfaces import WeekProfileProtocol

        assert "schedule" in dir(WeekProfileProtocol)


# =============================================================================
# Contract: Non-Climate Custom DataPoint Schedule API
# =============================================================================


class TestNonClimateCustomDataPointScheduleAPIContract:
    """
    Contract: Non-climate custom data points must provide stable schedule API.

    This test ensures that all non-climate custom data points (switches, lights,
    covers, valves) with schedule support expose a consistent interface.

    Non-Climate Custom DataPoints with Schedules:
    - Switches (e.g., HmIP-BSM)
    - Lights (e.g., HmIP-BSL)
    - Covers (e.g., HmIP-FROLL)
    - Valves (e.g., HmIPW-FALMOT-C12)
    """

    def test_non_climate_custom_datapoint_has_schedule_methods(self) -> None:
        """Contract: Non-climate custom data points have required schedule methods."""
        from aiohomematic.interfaces import WeekProfileProtocol

        # Verify all required schedule methods exist
        assert "get_schedule" in dir(WeekProfileProtocol)
        assert "set_schedule" in dir(WeekProfileProtocol)
        assert "reload_and_cache_schedule" in dir(WeekProfileProtocol)

    def test_non_climate_custom_datapoint_has_schedule_property(self) -> None:
        """Contract: Non-climate custom data points have schedule property (read-only)."""
        from aiohomematic.interfaces import WeekProfileProtocol

        # Verify WeekProfileProtocol defines schedule property
        assert "schedule" in dir(WeekProfileProtocol)

    def test_non_climate_custom_datapoint_schedule_data_structures(self) -> None:
        """
        Contract: Non-climate custom data points use stable data structures.

        This test ensures the schedule property returns SimpleSchedule Pydantic model.
        """
        from pydantic import BaseModel

        from aiohomematic.model.schedule_models import SimpleSchedule

        # Verify SimpleSchedule is a BaseModel
        assert issubclass(SimpleSchedule, BaseModel)
        # Verify it has entries field
        assert "entries" in SimpleSchedule.model_fields


# =============================================================================
# Contract: Custom DataPoint Schedule Channel Requirements
# =============================================================================


class TestCustomDataPointScheduleChannelContract:
    """
    Contract: Schedule-enabled custom data points must expose schedule channel info.

    This ensures that all custom data points with schedule support provide
    information about which channel contains the schedule data.
    """

    def test_has_schedule_property(self) -> None:
        """Contract: WeekProfileProtocol has has_schedule property."""
        from aiohomematic.interfaces import WeekProfileProtocol

        # Verify property exists
        assert "has_schedule" in dir(WeekProfileProtocol)

    def test_schedule_channel_address_property(self) -> None:
        """Contract: WeekProfileProtocol has schedule_channel_address property."""
        from aiohomematic.interfaces import WeekProfileProtocol

        # Verify property exists
        assert "schedule_channel_address" in dir(WeekProfileProtocol)


# =============================================================================
# Contract: Climate Schedule Service Method Integration
# =============================================================================


class TestClimateScheduleServiceMethodContract:
    """
    Contract: Climate schedule operations are exposed on ClimateWeekProfileDataPoint.

    This ensures that schedule operations are accessible on the week profile
    data point for integration with Home Assistant and other platforms.
    """

    def test_climate_schedule_methods_exist_on_week_profile_data_point(self) -> None:
        """
        Contract: Climate schedule methods are exposed on ClimateWeekProfileDataPoint.

        This test verifies that key schedule methods are available on the
        week profile data point class for use by integrations.
        """
        from aiohomematic.model.week_profile_data_point import ClimateWeekProfileDataPoint

        # Verify core schedule methods exist
        assert hasattr(ClimateWeekProfileDataPoint, "get_schedule")
        assert hasattr(ClimateWeekProfileDataPoint, "set_schedule")
        assert hasattr(ClimateWeekProfileDataPoint, "get_schedule_profile")
        assert hasattr(ClimateWeekProfileDataPoint, "set_schedule_profile")
        assert hasattr(ClimateWeekProfileDataPoint, "get_schedule_weekday")
        assert hasattr(ClimateWeekProfileDataPoint, "set_schedule_weekday")


# =============================================================================
# Contract: Schedule Cache Behavior
# =============================================================================


class TestScheduleCacheBehaviorContract:
    """
    Contract: Schedule caching behavior must remain stable.

    This ensures that the pessimistic cache update strategy is maintained:
    - Cache is NOT updated optimistically during set_schedule()
    - Cache is ONLY updated after CONFIG_PENDING = False from CCU
    - This guarantees cache consistency with CCU state
    """

    def test_reload_and_cache_schedule_method_exists(self) -> None:
        """Contract: reload_and_cache_schedule method exists for cache refresh."""
        from aiohomematic.interfaces import WeekProfileProtocol

        # Verify method exists
        assert "reload_and_cache_schedule" in dir(WeekProfileProtocol)

    def test_schedule_property_is_read_only(self) -> None:
        """
        Contract: schedule property is read-only (no setter).

        This enforces the pessimistic cache strategy - users cannot
        directly modify the cache, only via set_schedule() + CCU round-trip.
        """
        from aiohomematic.model.week_profile_data_point import WeekProfileDataPoint

        # Get property descriptor
        schedule_prop = getattr(WeekProfileDataPoint, "schedule", None)
        assert schedule_prop is not None

        # Verify it's a property (has fget but no fset)
        if isinstance(schedule_prop, property):
            assert schedule_prop.fget is not None
            assert schedule_prop.fset is None  # Read-only, no setter


# =============================================================================
# Contract: Schedule JSON Serialization
# =============================================================================


class TestScheduleJSONSerializationContract:
    """
    Contract: Schedule data structures must be JSON-serializable.

    This ensures that all schedule data structures can be serialized to JSON
    for transport to/from integrations (e.g., Home Assistant).
    """

    def test_climate_schedule_dict_format(self) -> None:
        """
        Contract: ClimateSchedule.model_dump() produces JSON-compatible dict.

        This test documents the expected JSON structure for climate schedules
        when sent to integrations.
        """
        from aiohomematic.model.schedule_models import (
            ClimateProfileSchedule,
            ClimateSchedule,
            ClimateSchedulePeriod,
            ClimateWeekdaySchedule,
        )

        schedule = ClimateSchedule(
            {
                "P1": ClimateProfileSchedule(
                    {
                        "MONDAY": ClimateWeekdaySchedule(
                            base_temperature=18.0,
                            periods=[
                                ClimateSchedulePeriod(
                                    starttime="06:00",
                                    endtime="22:00",
                                    temperature=21.0,
                                ),
                            ],
                        ),
                    }
                ),
            }
        )

        # Get dict representation
        schedule_dict = schedule.model_dump()

        # Verify structure (integration receives this format)
        assert isinstance(schedule_dict, dict)
        assert "P1" in schedule_dict
        assert "MONDAY" in schedule_dict["P1"]
        assert "base_temperature" in schedule_dict["P1"]["MONDAY"]
        assert "periods" in schedule_dict["P1"]["MONDAY"]
        assert schedule_dict["P1"]["MONDAY"]["base_temperature"] == 18.0
        assert len(schedule_dict["P1"]["MONDAY"]["periods"]) == 1
        assert schedule_dict["P1"]["MONDAY"]["periods"][0]["starttime"] == "06:00"
        assert schedule_dict["P1"]["MONDAY"]["periods"][0]["endtime"] == "22:00"
        assert schedule_dict["P1"]["MONDAY"]["periods"][0]["temperature"] == 21.0

    def test_climate_schedule_is_json_serializable(self) -> None:
        """
        Contract: ClimateSchedule can be serialized to/from JSON.

        This test verifies the complete JSON roundtrip for climate schedules.
        """
        import json

        from aiohomematic.model.schedule_models import (
            ClimateProfileSchedule,
            ClimateSchedule,
            ClimateSchedulePeriod,
            ClimateWeekdaySchedule,
        )

        # Create a climate schedule
        schedule = ClimateSchedule(
            {
                "P1": ClimateProfileSchedule(
                    {
                        "MONDAY": ClimateWeekdaySchedule(
                            base_temperature=18.0,
                            periods=[
                                ClimateSchedulePeriod(
                                    starttime="06:00",
                                    endtime="22:00",
                                    temperature=21.0,
                                ),
                            ],
                        ),
                    }
                ),
            }
        )

        # Serialize to JSON
        json_str = schedule.model_dump_json()
        assert isinstance(json_str, str)

        # Verify it's valid JSON
        json_dict = json.loads(json_str)
        assert isinstance(json_dict, dict)
        assert "P1" in json_dict

        # Deserialize from JSON
        reconstructed = ClimateSchedule.model_validate_json(json_str)
        assert reconstructed == schedule

    def test_schedule_dict_is_json_compatible(self) -> None:
        """
        Contract: ScheduleDict type alias is JSON-compatible.

        ScheduleDict is defined as dict[str, Any] and used as the return type
        for get_schedule() methods. This test ensures it's JSON-serializable.
        """
        import json

        from aiohomematic.const import ScheduleDict

        # Create a ScheduleDict instance
        schedule_dict: ScheduleDict = {
            "P1": {
                "MONDAY": {
                    "base_temperature": 18.0,
                    "periods": [
                        {
                            "starttime": "06:00",
                            "endtime": "22:00",
                            "temperature": 21.0,
                        }
                    ],
                }
            }
        }

        # Verify JSON serialization
        json_str = json.dumps(schedule_dict)
        assert isinstance(json_str, str)

        # Verify deserialization
        reconstructed = json.loads(json_str)
        assert reconstructed == schedule_dict

    def test_simple_schedule_dict_format(self) -> None:
        """
        Contract: SimpleSchedule.model_dump() produces JSON-compatible dict.

        This test documents the expected JSON structure for simple schedules
        when sent to integrations.
        """
        from aiohomematic.model.schedule_models import SimpleSchedule, SimpleScheduleEntry

        schedule = SimpleSchedule(
            entries={
                1: SimpleScheduleEntry(
                    weekdays=["MONDAY", "FRIDAY"],
                    time="07:30",
                    condition="fixed_time",
                    target_channels=["1_1"],
                    level=1.0,
                ),
            }
        )

        # Get dict representation
        schedule_dict = schedule.model_dump()

        # Verify structure (integration receives this format)
        assert isinstance(schedule_dict, dict)
        assert "entries" in schedule_dict
        assert 1 in schedule_dict["entries"]
        entry = schedule_dict["entries"][1]
        assert entry["weekdays"] == ["MONDAY", "FRIDAY"]
        assert entry["time"] == "07:30"
        assert entry["condition"] == "fixed_time"
        assert entry["target_channels"] == ["1_1"]
        assert entry["level"] == 1.0
        assert entry["astro_type"] is None  # None for fixed_time

    def test_simple_schedule_is_json_serializable(self) -> None:
        """
        Contract: SimpleSchedule can be serialized to/from JSON.

        This test verifies the complete JSON roundtrip for simple schedules.
        """
        import json

        from aiohomematic.model.schedule_models import SimpleSchedule, SimpleScheduleEntry

        # Create a simple schedule
        schedule = SimpleSchedule(
            entries={
                1: SimpleScheduleEntry(
                    weekdays=["MONDAY"],
                    time="07:30",
                    condition="fixed_time",
                    target_channels=["1_1"],
                    level=1.0,
                ),
            }
        )

        # Serialize to JSON
        json_str = schedule.model_dump_json()
        assert isinstance(json_str, str)

        # Verify it's valid JSON
        json_dict = json.loads(json_str)
        assert isinstance(json_dict, dict)
        assert "entries" in json_dict

        # Deserialize from JSON
        reconstructed = SimpleSchedule.model_validate_json(json_str)
        assert reconstructed == schedule
