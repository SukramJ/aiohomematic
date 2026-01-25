# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for hub entity stability.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for hub entities.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. Hub data point types exist
2. Hub entity classes have required properties
3. Hub categories are stable
4. Named tuples for hub groupings are stable

See ADR-0018 for architectural context.
"""

from __future__ import annotations

from aiohomematic.const import HUB_CATEGORIES, DataPointCategory
from aiohomematic.model.hub import (
    ConnectivityDpType,
    HmConnectionLatencySensor,
    HmInboxSensor,
    HmLastEventAgeSensor,
    HmSystemHealthSensor,
    HmUpdate,
    InstallModeDpButton,
    InstallModeDpSensor,
    MetricsDpType,
    ProgramDpButton,
    ProgramDpSwitch,
    ProgramDpType,
    SysvarDpBinarySensor,
    SysvarDpNumber,
    SysvarDpSelect,
    SysvarDpSensor,
    SysvarDpSwitch,
    SysvarDpText,
)

# =============================================================================
# Contract: Hub Categories
# =============================================================================


class TestHubCategoriesContract:
    """Contract: Hub categories must remain stable."""

    def test_hub_categories_contains_hub_binary_sensor(self) -> None:
        """Contract: HUB_CATEGORIES contains HUB_BINARY_SENSOR."""
        assert DataPointCategory.HUB_BINARY_SENSOR in HUB_CATEGORIES

    def test_hub_categories_contains_hub_button(self) -> None:
        """Contract: HUB_CATEGORIES contains HUB_BUTTON."""
        assert DataPointCategory.HUB_BUTTON in HUB_CATEGORIES

    def test_hub_categories_contains_hub_number(self) -> None:
        """Contract: HUB_CATEGORIES contains HUB_NUMBER."""
        assert DataPointCategory.HUB_NUMBER in HUB_CATEGORIES

    def test_hub_categories_contains_hub_select(self) -> None:
        """Contract: HUB_CATEGORIES contains HUB_SELECT."""
        assert DataPointCategory.HUB_SELECT in HUB_CATEGORIES

    def test_hub_categories_contains_hub_sensor(self) -> None:
        """Contract: HUB_CATEGORIES contains HUB_SENSOR."""
        assert DataPointCategory.HUB_SENSOR in HUB_CATEGORIES

    def test_hub_categories_contains_hub_switch(self) -> None:
        """Contract: HUB_CATEGORIES contains HUB_SWITCH."""
        assert DataPointCategory.HUB_SWITCH in HUB_CATEGORIES

    def test_hub_categories_contains_hub_text(self) -> None:
        """Contract: HUB_CATEGORIES contains HUB_TEXT."""
        assert DataPointCategory.HUB_TEXT in HUB_CATEGORIES

    def test_hub_categories_contains_hub_update(self) -> None:
        """Contract: HUB_CATEGORIES contains HUB_UPDATE."""
        assert DataPointCategory.HUB_UPDATE in HUB_CATEGORIES

    def test_hub_categories_is_tuple(self) -> None:
        """Contract: HUB_CATEGORIES is a tuple."""
        assert isinstance(HUB_CATEGORIES, tuple)


# =============================================================================
# Contract: Program Data Point Classes
# =============================================================================


class TestProgramDataPointClassesContract:
    """Contract: Program data point classes must exist."""

    def test_programdpbutton_exists(self) -> None:
        """Contract: ProgramDpButton class exists."""
        assert ProgramDpButton is not None

    def test_programdpswitch_exists(self) -> None:
        """Contract: ProgramDpSwitch class exists."""
        assert ProgramDpSwitch is not None


# =============================================================================
# Contract: Sysvar Data Point Classes
# =============================================================================


class TestSysvarDataPointClassesContract:
    """Contract: Sysvar data point classes must exist."""

    def test_sysvardpbinarysensor_exists(self) -> None:
        """Contract: SysvarDpBinarySensor class exists."""
        assert SysvarDpBinarySensor is not None

    def test_sysvardpnumber_exists(self) -> None:
        """Contract: SysvarDpNumber class exists."""
        assert SysvarDpNumber is not None

    def test_sysvardpselect_exists(self) -> None:
        """Contract: SysvarDpSelect class exists."""
        assert SysvarDpSelect is not None

    def test_sysvardpsensor_exists(self) -> None:
        """Contract: SysvarDpSensor class exists."""
        assert SysvarDpSensor is not None

    def test_sysvardpswitch_exists(self) -> None:
        """Contract: SysvarDpSwitch class exists."""
        assert SysvarDpSwitch is not None

    def test_sysvardptext_exists(self) -> None:
        """Contract: SysvarDpText class exists."""
        assert SysvarDpText is not None


# =============================================================================
# Contract: Install Mode Data Point Classes
# =============================================================================


class TestInstallModeDataPointClassesContract:
    """Contract: Install mode data point classes must exist."""

    def test_installmodedpbutton_exists(self) -> None:
        """Contract: InstallModeDpButton class exists."""
        assert InstallModeDpButton is not None

    def test_installmodedpsensor_exists(self) -> None:
        """Contract: InstallModeDpSensor class exists."""
        assert InstallModeDpSensor is not None


# =============================================================================
# Contract: Metrics Data Point Classes
# =============================================================================


class TestMetricsDataPointClassesContract:
    """Contract: Metrics data point classes must exist."""

    def test_hmconnectionlatencysensor_exists(self) -> None:
        """Contract: HmConnectionLatencySensor class exists."""
        assert HmConnectionLatencySensor is not None

    def test_hmlasteventagesensor_exists(self) -> None:
        """Contract: HmLastEventAgeSensor class exists."""
        assert HmLastEventAgeSensor is not None

    def test_hmsystemhealthsensor_exists(self) -> None:
        """Contract: HmSystemHealthSensor class exists."""
        assert HmSystemHealthSensor is not None


# =============================================================================
# Contract: Inbox and Update Classes
# =============================================================================


class TestInboxUpdateClassesContract:
    """Contract: Inbox and update classes must exist."""

    def test_hminboxsensor_exists(self) -> None:
        """Contract: HmInboxSensor class exists."""
        assert HmInboxSensor is not None

    def test_hmupdate_exists(self) -> None:
        """Contract: HmUpdate class exists."""
        assert HmUpdate is not None


# =============================================================================
# Contract: ProgramDpType NamedTuple
# =============================================================================


class TestProgramDpTypeContract:
    """Contract: ProgramDpType must remain stable."""

    def test_programdptype_has_button_field(self) -> None:
        """Contract: ProgramDpType has button field."""
        assert "button" in ProgramDpType._fields

    def test_programdptype_has_pid_field(self) -> None:
        """Contract: ProgramDpType has pid field."""
        assert "pid" in ProgramDpType._fields

    def test_programdptype_has_switch_field(self) -> None:
        """Contract: ProgramDpType has switch field."""
        assert "switch" in ProgramDpType._fields

    def test_programdptype_is_namedtuple(self) -> None:
        """Contract: ProgramDpType is a NamedTuple."""
        assert hasattr(ProgramDpType, "_fields")


# =============================================================================
# Contract: MetricsDpType NamedTuple
# =============================================================================


class TestMetricsDpTypeContract:
    """Contract: MetricsDpType must remain stable."""

    def test_metricsdptype_has_connection_latency_field(self) -> None:
        """Contract: MetricsDpType has connection_latency field."""
        assert "connection_latency" in MetricsDpType._fields

    def test_metricsdptype_has_last_event_age_field(self) -> None:
        """Contract: MetricsDpType has last_event_age field."""
        assert "last_event_age" in MetricsDpType._fields

    def test_metricsdptype_has_system_health_field(self) -> None:
        """Contract: MetricsDpType has system_health field."""
        assert "system_health" in MetricsDpType._fields

    def test_metricsdptype_is_namedtuple(self) -> None:
        """Contract: MetricsDpType is a NamedTuple."""
        assert hasattr(MetricsDpType, "_fields")


# =============================================================================
# Contract: ConnectivityDpType NamedTuple
# =============================================================================


class TestConnectivityDpTypeContract:
    """Contract: ConnectivityDpType must remain stable."""

    def test_connectivitydptype_has_interface_field(self) -> None:
        """Contract: ConnectivityDpType has interface field."""
        assert "interface" in ConnectivityDpType._fields

    def test_connectivitydptype_has_interface_id_field(self) -> None:
        """Contract: ConnectivityDpType has interface_id field."""
        assert "interface_id" in ConnectivityDpType._fields

    def test_connectivitydptype_has_sensor_field(self) -> None:
        """Contract: ConnectivityDpType has sensor field."""
        assert "sensor" in ConnectivityDpType._fields

    def test_connectivitydptype_is_namedtuple(self) -> None:
        """Contract: ConnectivityDpType is a NamedTuple."""
        assert hasattr(ConnectivityDpType, "_fields")


# =============================================================================
# Contract: Hub Class Imports
# =============================================================================


class TestHubClassImportsContract:
    """Contract: Hub classes must be importable from aiohomematic.model.hub."""

    def test_hub_binary_sensor_import(self) -> None:
        """Contract: Binary sensor classes importable from model.hub."""
        from aiohomematic.model.hub import SysvarDpBinarySensor

        assert SysvarDpBinarySensor is not None

    def test_hub_button_import(self) -> None:
        """Contract: Button classes importable from model.hub."""
        from aiohomematic.model.hub import ProgramDpButton

        assert ProgramDpButton is not None

    def test_hub_inbox_import(self) -> None:
        """Contract: Inbox classes importable from model.hub."""
        from aiohomematic.model.hub import HmInboxSensor

        assert HmInboxSensor is not None

    def test_hub_install_mode_import(self) -> None:
        """Contract: Install mode classes importable from model.hub."""
        from aiohomematic.model.hub import InstallModeDpButton, InstallModeDpSensor

        assert InstallModeDpButton is not None
        assert InstallModeDpSensor is not None

    def test_hub_metrics_import(self) -> None:
        """Contract: Metrics classes importable from model.hub."""
        from aiohomematic.model.hub import HmConnectionLatencySensor, HmLastEventAgeSensor, HmSystemHealthSensor

        assert HmSystemHealthSensor is not None
        assert HmConnectionLatencySensor is not None
        assert HmLastEventAgeSensor is not None

    def test_hub_number_import(self) -> None:
        """Contract: Number classes importable from model.hub."""
        from aiohomematic.model.hub import SysvarDpNumber

        assert SysvarDpNumber is not None

    def test_hub_select_import(self) -> None:
        """Contract: Select classes importable from model.hub."""
        from aiohomematic.model.hub import SysvarDpSelect

        assert SysvarDpSelect is not None

    def test_hub_sensor_import(self) -> None:
        """Contract: Sensor classes importable from model.hub."""
        from aiohomematic.model.hub import SysvarDpSensor

        assert SysvarDpSensor is not None

    def test_hub_switch_import(self) -> None:
        """Contract: Switch classes importable from model.hub."""
        from aiohomematic.model.hub import ProgramDpSwitch, SysvarDpSwitch

        assert ProgramDpSwitch is not None
        assert SysvarDpSwitch is not None

    def test_hub_text_import(self) -> None:
        """Contract: Text classes importable from model.hub."""
        from aiohomematic.model.hub import SysvarDpText

        assert SysvarDpText is not None

    def test_hub_update_import(self) -> None:
        """Contract: Update classes importable from model.hub."""
        from aiohomematic.model.hub import HmUpdate

        assert HmUpdate is not None
