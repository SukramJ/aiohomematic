# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for enum and constant stability.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for enums and constants.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. Enum values remain stable (no removals or renames)
2. Enum types are correct (StrEnum, IntEnum, Enum)
3. Critical constants maintain their values
4. Interface types match expected backends

See ADR-0018 for architectural context.
"""

from __future__ import annotations

from enum import Enum, StrEnum

from aiohomematic.const import (
    Backend,
    CentralState,
    ClientState,
    DataPointCategory,
    DataPointUsage,
    DescriptionMarker,
    DeviceFirmwareState,
    DeviceProfile,
    DeviceTriggerEventType,
    FailureReason,
    Interface,
    OptionalSettings,
    Parameter,
    ParamsetKey,
    ProxyInitState,
    RecoveryResult,
    RecoveryStage,
    RpcServerType,
    SystemEventType,
)

# =============================================================================
# Contract: Interface Enum
# =============================================================================


class TestInterfaceEnumContract:
    """Contract: Interface enum values must remain stable."""

    def test_interface_has_bidcos_rf(self) -> None:
        """Contract: Interface.BIDCOS_RF must exist."""
        assert hasattr(Interface, "BIDCOS_RF")
        assert Interface.BIDCOS_RF.value == "BidCos-RF"

    def test_interface_has_bidcos_wired(self) -> None:
        """Contract: Interface.BIDCOS_WIRED must exist."""
        assert hasattr(Interface, "BIDCOS_WIRED")
        assert Interface.BIDCOS_WIRED.value == "BidCos-Wired"

    def test_interface_has_ccu_jack(self) -> None:
        """Contract: Interface.CCU_JACK must exist."""
        assert hasattr(Interface, "CCU_JACK")
        assert Interface.CCU_JACK.value == "CCU-Jack"

    def test_interface_has_cuxd(self) -> None:
        """Contract: Interface.CUXD must exist."""
        assert hasattr(Interface, "CUXD")
        assert Interface.CUXD.value == "CUxD"

    def test_interface_has_hmip_rf(self) -> None:
        """Contract: Interface.HMIP_RF must exist."""
        assert hasattr(Interface, "HMIP_RF")
        assert Interface.HMIP_RF.value == "HmIP-RF"

    def test_interface_has_virtual_devices(self) -> None:
        """Contract: Interface.VIRTUAL_DEVICES must exist."""
        assert hasattr(Interface, "VIRTUAL_DEVICES")
        assert Interface.VIRTUAL_DEVICES.value == "VirtualDevices"

    def test_interface_is_strenum(self) -> None:
        """Contract: Interface is a StrEnum."""
        assert issubclass(Interface, StrEnum)


# =============================================================================
# Contract: Backend Enum
# =============================================================================


class TestBackendEnumContract:
    """Contract: Backend enum values must remain stable."""

    def test_backend_has_ccu(self) -> None:
        """Contract: Backend.CCU must exist."""
        assert hasattr(Backend, "CCU")
        assert Backend.CCU.value == "CCU"

    def test_backend_has_homegear(self) -> None:
        """Contract: Backend.HOMEGEAR must exist."""
        assert hasattr(Backend, "HOMEGEAR")
        assert Backend.HOMEGEAR.value == "Homegear"

    def test_backend_has_pydevccu(self) -> None:
        """Contract: Backend.PYDEVCCU must exist."""
        assert hasattr(Backend, "PYDEVCCU")
        assert Backend.PYDEVCCU.value == "PyDevCCU"

    def test_backend_is_strenum(self) -> None:
        """Contract: Backend is a StrEnum."""
        assert issubclass(Backend, StrEnum)


# =============================================================================
# Contract: DataPointCategory Enum
# =============================================================================


class TestDataPointCategoryEnumContract:
    """Contract: DataPointCategory enum values must remain stable."""

    def test_datapointcategory_has_binary_sensor(self) -> None:
        """Contract: DataPointCategory.BINARY_SENSOR must exist."""
        assert hasattr(DataPointCategory, "BINARY_SENSOR")
        assert DataPointCategory.BINARY_SENSOR.value == "binary_sensor"

    def test_datapointcategory_has_button(self) -> None:
        """Contract: DataPointCategory.BUTTON must exist."""
        assert hasattr(DataPointCategory, "BUTTON")
        assert DataPointCategory.BUTTON.value == "button"

    def test_datapointcategory_has_climate(self) -> None:
        """Contract: DataPointCategory.CLIMATE must exist."""
        assert hasattr(DataPointCategory, "CLIMATE")
        assert DataPointCategory.CLIMATE.value == "climate"

    def test_datapointcategory_has_cover(self) -> None:
        """Contract: DataPointCategory.COVER must exist."""
        assert hasattr(DataPointCategory, "COVER")
        assert DataPointCategory.COVER.value == "cover"

    def test_datapointcategory_has_event(self) -> None:
        """Contract: DataPointCategory.EVENT must exist."""
        assert hasattr(DataPointCategory, "EVENT")
        assert DataPointCategory.EVENT.value == "event"

    def test_datapointcategory_has_light(self) -> None:
        """Contract: DataPointCategory.LIGHT must exist."""
        assert hasattr(DataPointCategory, "LIGHT")
        assert DataPointCategory.LIGHT.value == "light"

    def test_datapointcategory_has_lock(self) -> None:
        """Contract: DataPointCategory.LOCK must exist."""
        assert hasattr(DataPointCategory, "LOCK")
        assert DataPointCategory.LOCK.value == "lock"

    def test_datapointcategory_has_number(self) -> None:
        """Contract: DataPointCategory.NUMBER must exist."""
        assert hasattr(DataPointCategory, "NUMBER")
        assert DataPointCategory.NUMBER.value == "number"

    def test_datapointcategory_has_select(self) -> None:
        """Contract: DataPointCategory.SELECT must exist."""
        assert hasattr(DataPointCategory, "SELECT")
        assert DataPointCategory.SELECT.value == "select"

    def test_datapointcategory_has_sensor(self) -> None:
        """Contract: DataPointCategory.SENSOR must exist."""
        assert hasattr(DataPointCategory, "SENSOR")
        assert DataPointCategory.SENSOR.value == "sensor"

    def test_datapointcategory_has_siren(self) -> None:
        """Contract: DataPointCategory.SIREN must exist."""
        assert hasattr(DataPointCategory, "SIREN")
        assert DataPointCategory.SIREN.value == "siren"

    def test_datapointcategory_has_switch(self) -> None:
        """Contract: DataPointCategory.SWITCH must exist."""
        assert hasattr(DataPointCategory, "SWITCH")
        assert DataPointCategory.SWITCH.value == "switch"

    def test_datapointcategory_has_text(self) -> None:
        """Contract: DataPointCategory.TEXT must exist."""
        assert hasattr(DataPointCategory, "TEXT")
        assert DataPointCategory.TEXT.value == "text"

    def test_datapointcategory_has_update(self) -> None:
        """Contract: DataPointCategory.UPDATE must exist."""
        assert hasattr(DataPointCategory, "UPDATE")
        assert DataPointCategory.UPDATE.value == "update"

    def test_datapointcategory_has_valve(self) -> None:
        """Contract: DataPointCategory.VALVE must exist."""
        assert hasattr(DataPointCategory, "VALVE")
        assert DataPointCategory.VALVE.value == "valve"

    def test_datapointcategory_hub_categories_exist(self) -> None:
        """Contract: Hub data point categories must exist."""
        hub_categories = [
            "HUB_SENSOR",
            "HUB_BINARY_SENSOR",
            "HUB_SWITCH",
            "HUB_SELECT",
            "HUB_NUMBER",
            "HUB_TEXT",
            "HUB_BUTTON",
            "HUB_UPDATE",
        ]
        for category in hub_categories:
            assert hasattr(DataPointCategory, category)

    def test_datapointcategory_is_strenum(self) -> None:
        """Contract: DataPointCategory is a StrEnum."""
        assert issubclass(DataPointCategory, StrEnum)


# =============================================================================
# Contract: DataPointUsage Enum
# =============================================================================


class TestDataPointUsageEnumContract:
    """Contract: DataPointUsage enum values must remain stable."""

    def test_datapointusage_has_cdp_primary(self) -> None:
        """Contract: DataPointUsage.CDP_PRIMARY must exist."""
        assert hasattr(DataPointUsage, "CDP_PRIMARY")

    def test_datapointusage_has_cdp_secondary(self) -> None:
        """Contract: DataPointUsage.CDP_SECONDARY must exist."""
        assert hasattr(DataPointUsage, "CDP_SECONDARY")

    def test_datapointusage_has_data_point(self) -> None:
        """Contract: DataPointUsage.DATA_POINT must exist."""
        assert hasattr(DataPointUsage, "DATA_POINT")

    def test_datapointusage_has_event(self) -> None:
        """Contract: DataPointUsage.EVENT must exist."""
        assert hasattr(DataPointUsage, "EVENT")

    def test_datapointusage_has_no_create(self) -> None:
        """Contract: DataPointUsage.NO_CREATE must exist."""
        assert hasattr(DataPointUsage, "NO_CREATE")

    def test_datapointusage_is_strenum(self) -> None:
        """Contract: DataPointUsage is a StrEnum."""
        assert issubclass(DataPointUsage, StrEnum)


# =============================================================================
# Contract: ParamsetKey Enum
# =============================================================================


class TestParamsetKeyEnumContract:
    """Contract: ParamsetKey enum values must remain stable."""

    def test_paramsetkey_has_master(self) -> None:
        """Contract: ParamsetKey.MASTER must exist."""
        assert hasattr(ParamsetKey, "MASTER")
        assert ParamsetKey.MASTER.value == "MASTER"

    def test_paramsetkey_has_values(self) -> None:
        """Contract: ParamsetKey.VALUES must exist."""
        assert hasattr(ParamsetKey, "VALUES")
        assert ParamsetKey.VALUES.value == "VALUES"

    def test_paramsetkey_is_strenum(self) -> None:
        """Contract: ParamsetKey is a StrEnum."""
        assert issubclass(ParamsetKey, StrEnum)


# =============================================================================
# Contract: SystemEventType Enum
# =============================================================================


class TestSystemEventTypeEnumContract:
    """Contract: SystemEventType enum values must remain stable."""

    def test_systemeventtype_has_delete_devices(self) -> None:
        """Contract: SystemEventType.DELETE_DEVICES must exist."""
        assert hasattr(SystemEventType, "DELETE_DEVICES")

    def test_systemeventtype_has_devices_created(self) -> None:
        """Contract: SystemEventType.DEVICES_CREATED must exist."""
        assert hasattr(SystemEventType, "DEVICES_CREATED")

    def test_systemeventtype_has_hub_refreshed(self) -> None:
        """Contract: SystemEventType.HUB_REFRESHED must exist."""
        assert hasattr(SystemEventType, "HUB_REFRESHED")

    def test_systemeventtype_has_new_devices(self) -> None:
        """Contract: SystemEventType.NEW_DEVICES must exist."""
        assert hasattr(SystemEventType, "NEW_DEVICES")

    def test_systemeventtype_has_update_device(self) -> None:
        """Contract: SystemEventType.UPDATE_DEVICE must exist."""
        assert hasattr(SystemEventType, "UPDATE_DEVICE")

    def test_systemeventtype_is_strenum(self) -> None:
        """Contract: SystemEventType is a StrEnum."""
        assert issubclass(SystemEventType, StrEnum)


# =============================================================================
# Contract: DeviceTriggerEventType Enum
# =============================================================================


class TestDeviceTriggerEventTypeEnumContract:
    """Contract: DeviceTriggerEventType enum values must remain stable."""

    def test_devicetriggereventtype_has_device_error(self) -> None:
        """Contract: DeviceTriggerEventType.DEVICE_ERROR must exist."""
        assert hasattr(DeviceTriggerEventType, "DEVICE_ERROR")
        assert DeviceTriggerEventType.DEVICE_ERROR.value == "homematic.device_error"

    def test_devicetriggereventtype_has_impulse(self) -> None:
        """Contract: DeviceTriggerEventType.IMPULSE must exist."""
        assert hasattr(DeviceTriggerEventType, "IMPULSE")
        assert DeviceTriggerEventType.IMPULSE.value == "homematic.impulse"

    def test_devicetriggereventtype_has_keypress(self) -> None:
        """Contract: DeviceTriggerEventType.KEYPRESS must exist."""
        assert hasattr(DeviceTriggerEventType, "KEYPRESS")
        assert DeviceTriggerEventType.KEYPRESS.value == "homematic.keypress"

    def test_devicetriggereventtype_has_short_property(self) -> None:
        """Contract: DeviceTriggerEventType has short property."""
        assert DeviceTriggerEventType.KEYPRESS.short == "keypress"
        assert DeviceTriggerEventType.IMPULSE.short == "impulse"

    def test_devicetriggereventtype_is_strenum(self) -> None:
        """Contract: DeviceTriggerEventType is a StrEnum."""
        assert issubclass(DeviceTriggerEventType, StrEnum)


# =============================================================================
# Contract: DeviceFirmwareState Enum
# =============================================================================


class TestDeviceFirmwareStateEnumContract:
    """Contract: DeviceFirmwareState enum values must remain stable."""

    def test_devicefirmwarestate_has_new_firmware_available(self) -> None:
        """Contract: DeviceFirmwareState.NEW_FIRMWARE_AVAILABLE must exist."""
        assert hasattr(DeviceFirmwareState, "NEW_FIRMWARE_AVAILABLE")

    def test_devicefirmwarestate_has_performing_update(self) -> None:
        """Contract: DeviceFirmwareState.PERFORMING_UPDATE must exist."""
        assert hasattr(DeviceFirmwareState, "PERFORMING_UPDATE")

    def test_devicefirmwarestate_has_unknown(self) -> None:
        """Contract: DeviceFirmwareState.UNKNOWN must exist."""
        assert hasattr(DeviceFirmwareState, "UNKNOWN")

    def test_devicefirmwarestate_has_up_to_date(self) -> None:
        """Contract: DeviceFirmwareState.UP_TO_DATE must exist."""
        assert hasattr(DeviceFirmwareState, "UP_TO_DATE")

    def test_devicefirmwarestate_is_strenum(self) -> None:
        """Contract: DeviceFirmwareState is a StrEnum."""
        assert issubclass(DeviceFirmwareState, StrEnum)


# =============================================================================
# Contract: CentralState Enum
# =============================================================================


class TestCentralStateEnumContract:
    """Contract: CentralState enum values must remain stable."""

    def test_centralstate_is_strenum(self) -> None:
        """Contract: CentralState is a StrEnum."""
        assert issubclass(CentralState, StrEnum)

    def test_centralstate_lifecycle_states(self) -> None:
        """Contract: CentralState has all lifecycle states."""
        required_states = [
            "STARTING",
            "INITIALIZING",
            "RUNNING",
            "DEGRADED",
            "RECOVERING",
            "FAILED",
            "STOPPED",
        ]
        for state in required_states:
            assert hasattr(CentralState, state)


# =============================================================================
# Contract: ClientState Enum
# =============================================================================


class TestClientStateEnumContract:
    """Contract: ClientState enum values must remain stable."""

    def test_clientstate_is_strenum(self) -> None:
        """Contract: ClientState is a StrEnum."""
        assert issubclass(ClientState, StrEnum)

    def test_clientstate_lifecycle_states(self) -> None:
        """Contract: ClientState has all lifecycle states."""
        required_states = [
            "CREATED",
            "INITIALIZING",
            "INITIALIZED",
            "CONNECTING",
            "CONNECTED",
            "DISCONNECTED",
            "RECONNECTING",
            "STOPPING",
            "STOPPED",
            "FAILED",
        ]
        for state in required_states:
            assert hasattr(ClientState, state)


# =============================================================================
# Contract: FailureReason Enum
# =============================================================================


class TestFailureReasonEnumContract:
    """Contract: FailureReason enum values must remain stable."""

    def test_failurereason_has_auth(self) -> None:
        """Contract: FailureReason.AUTH must exist."""
        assert hasattr(FailureReason, "AUTH")
        assert FailureReason.AUTH.value == "auth"

    def test_failurereason_has_network(self) -> None:
        """Contract: FailureReason.NETWORK must exist."""
        assert hasattr(FailureReason, "NETWORK")
        assert FailureReason.NETWORK.value == "network"

    def test_failurereason_has_none(self) -> None:
        """Contract: FailureReason.NONE must exist."""
        assert hasattr(FailureReason, "NONE")
        assert FailureReason.NONE.value == "none"

    def test_failurereason_has_timeout(self) -> None:
        """Contract: FailureReason.TIMEOUT must exist."""
        assert hasattr(FailureReason, "TIMEOUT")
        assert FailureReason.TIMEOUT.value == "timeout"

    def test_failurereason_is_strenum(self) -> None:
        """Contract: FailureReason is a StrEnum."""
        assert issubclass(FailureReason, StrEnum)


# =============================================================================
# Contract: RecoveryStage Enum
# =============================================================================


class TestRecoveryStageEnumContract:
    """Contract: RecoveryStage enum values must remain stable."""

    def test_recoverystage_has_failed(self) -> None:
        """Contract: RecoveryStage.FAILED must exist."""
        assert hasattr(RecoveryStage, "FAILED")

    def test_recoverystage_has_idle(self) -> None:
        """Contract: RecoveryStage.IDLE must exist."""
        assert hasattr(RecoveryStage, "IDLE")

    def test_recoverystage_has_reconnecting(self) -> None:
        """Contract: RecoveryStage.RECONNECTING must exist."""
        assert hasattr(RecoveryStage, "RECONNECTING")

    def test_recoverystage_has_recovered(self) -> None:
        """Contract: RecoveryStage.RECOVERED must exist."""
        assert hasattr(RecoveryStage, "RECOVERED")

    def test_recoverystage_has_rpc_checking(self) -> None:
        """Contract: RecoveryStage.RPC_CHECKING must exist."""
        assert hasattr(RecoveryStage, "RPC_CHECKING")

    def test_recoverystage_has_tcp_checking(self) -> None:
        """Contract: RecoveryStage.TCP_CHECKING must exist."""
        assert hasattr(RecoveryStage, "TCP_CHECKING")

    def test_recoverystage_is_strenum(self) -> None:
        """Contract: RecoveryStage is a StrEnum."""
        assert issubclass(RecoveryStage, StrEnum)


# =============================================================================
# Contract: RecoveryResult Enum
# =============================================================================


class TestRecoveryResultEnumContract:
    """Contract: RecoveryResult enum values must remain stable."""

    def test_recoveryresult_is_strenum(self) -> None:
        """Contract: RecoveryResult is a StrEnum."""
        assert issubclass(RecoveryResult, StrEnum)

    def test_recoveryresult_values(self) -> None:
        """Contract: RecoveryResult has expected values."""
        assert hasattr(RecoveryResult, "SUCCESS")
        assert hasattr(RecoveryResult, "PARTIAL")
        assert hasattr(RecoveryResult, "FAILED")
        assert hasattr(RecoveryResult, "MAX_RETRIES")


# =============================================================================
# Contract: ProxyInitState Enum
# =============================================================================


class TestProxyInitStateEnumContract:
    """Contract: ProxyInitState enum values must remain stable."""

    def test_proxyinitstate_is_enum(self) -> None:
        """Contract: ProxyInitState is an Enum with integer values."""
        assert issubclass(ProxyInitState, Enum)

    def test_proxyinitstate_values(self) -> None:
        """Contract: ProxyInitState has expected integer values."""
        assert ProxyInitState.INIT_SUCCESS.value == 1
        assert ProxyInitState.INIT_FAILED.value == 0
        assert ProxyInitState.DE_INIT_SUCCESS.value == 8
        assert ProxyInitState.DE_INIT_FAILED.value == 4
        assert ProxyInitState.DE_INIT_SKIPPED.value == 16


# =============================================================================
# Contract: RpcServerType Enum
# =============================================================================


class TestRpcServerTypeEnumContract:
    """Contract: RpcServerType enum values must remain stable."""

    def test_rpcservertype_has_none(self) -> None:
        """Contract: RpcServerType.NONE must exist (for CUxD/CCU-Jack)."""
        assert hasattr(RpcServerType, "NONE")

    def test_rpcservertype_has_xml_rpc(self) -> None:
        """Contract: RpcServerType.XML_RPC must exist."""
        assert hasattr(RpcServerType, "XML_RPC")

    def test_rpcservertype_is_strenum(self) -> None:
        """Contract: RpcServerType is a StrEnum."""
        assert issubclass(RpcServerType, StrEnum)


# =============================================================================
# Contract: DeviceProfile Enum
# =============================================================================


class TestDeviceProfileEnumContract:
    """Contract: DeviceProfile enum values must remain stable."""

    def test_deviceprofile_has_ip_cover(self) -> None:
        """Contract: DeviceProfile.IP_COVER must exist."""
        assert hasattr(DeviceProfile, "IP_COVER")

    def test_deviceprofile_has_ip_dimmer(self) -> None:
        """Contract: DeviceProfile.IP_DIMMER must exist."""
        assert hasattr(DeviceProfile, "IP_DIMMER")

    def test_deviceprofile_has_ip_switch(self) -> None:
        """Contract: DeviceProfile.IP_SWITCH must exist."""
        assert hasattr(DeviceProfile, "IP_SWITCH")

    def test_deviceprofile_has_ip_thermostat(self) -> None:
        """Contract: DeviceProfile.IP_THERMOSTAT must exist."""
        assert hasattr(DeviceProfile, "IP_THERMOSTAT")

    def test_deviceprofile_has_rf_thermostat(self) -> None:
        """Contract: DeviceProfile.RF_THERMOSTAT must exist."""
        assert hasattr(DeviceProfile, "RF_THERMOSTAT")

    def test_deviceprofile_is_strenum(self) -> None:
        """Contract: DeviceProfile is a StrEnum."""
        assert issubclass(DeviceProfile, StrEnum)


# =============================================================================
# Contract: DescriptionMarker Enum
# =============================================================================


class TestDescriptionMarkerEnumContract:
    """Contract: DescriptionMarker enum values must remain stable."""

    def test_descriptionmarker_is_strenum(self) -> None:
        """Contract: DescriptionMarker is a StrEnum."""
        assert issubclass(DescriptionMarker, StrEnum)

    def test_descriptionmarker_values(self) -> None:
        """Contract: DescriptionMarker has expected values."""
        assert hasattr(DescriptionMarker, "HAHM")
        assert hasattr(DescriptionMarker, "HX")
        assert hasattr(DescriptionMarker, "INTERNAL")


# =============================================================================
# Contract: OptionalSettings Enum
# =============================================================================


class TestOptionalSettingsEnumContract:
    """Contract: OptionalSettings enum values must remain stable."""

    def test_optionalsettings_is_strenum(self) -> None:
        """Contract: OptionalSettings is a StrEnum."""
        assert issubclass(OptionalSettings, StrEnum)


# =============================================================================
# Contract: Parameter Constants
# =============================================================================


class TestParameterConstantsContract:
    """Contract: Parameter constants must remain stable."""

    def test_parameter_has_humidity(self) -> None:
        """Contract: Parameter.HUMIDITY must exist."""
        assert hasattr(Parameter, "HUMIDITY")

    def test_parameter_has_level(self) -> None:
        """Contract: Parameter.LEVEL must exist."""
        assert hasattr(Parameter, "LEVEL")
        assert Parameter.LEVEL.value == "LEVEL"

    def test_parameter_has_set_point_temperature(self) -> None:
        """Contract: Parameter.SET_POINT_TEMPERATURE must exist."""
        assert hasattr(Parameter, "SET_POINT_TEMPERATURE")

    def test_parameter_has_state(self) -> None:
        """Contract: Parameter.STATE must exist."""
        assert hasattr(Parameter, "STATE")
        assert Parameter.STATE.value == "STATE"

    def test_parameter_has_temperature(self) -> None:
        """Contract: Parameter.TEMPERATURE must exist."""
        assert hasattr(Parameter, "TEMPERATURE")

    def test_parameter_is_strenum(self) -> None:
        """Contract: Parameter is a StrEnum."""
        assert issubclass(Parameter, StrEnum)
