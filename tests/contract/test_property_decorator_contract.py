# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for property decorator classification.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for property decorator usage
across model classes. Any reclassification that breaks these tests requires
a MAJOR version bump since it changes payload structure for consumers
(aiohomematic2mqtt, homematicip_local).

The contract ensures that:
1. state_payload contains only dynamic runtime values
2. config_payload contains only static configuration
3. info_payload contains only identification/metadata
4. No property key appears in multiple payload categories
5. Key consumer-facing properties are always present in expected payloads
6. quantity and value_behavior are available on sensor data points

See ADR for architectural context and rationale.
"""

import pytest

from aiohomematic.const import DataPointCategory, Quantity, ValueBehavior

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

TEST_DEVICES: frozenset[str] = frozenset(
    {
        "VCU2128127",  # HmIP-eTRV (climate)
        "VCU3609622",  # HmIP-eTRV-E (climate)
        "VCU0000054",  # HmIP-BROLL (cover/shutter)
        "VCU0000263",  # HmIP-BBL (cover/blind)
        "VCU0000350",  # HmIP-BSL (light dimmer)
        "VCU5765055",  # HmIP-SWSD (siren)
    }
)


# ---------------------------------------------------------------------------
# Payload disjointedness: no key in multiple payload categories
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [(TEST_DEVICES, True, None, None)],
)
async def test_payload_keys_are_disjoint(
    central_client_factory_with_ccu_client,
):
    """Ensure no key appears in both state_payload and config_payload."""
    central, *_ = central_client_factory_with_ccu_client
    for device in central.devices:
        for dp in device.generic_data_points.values():
            state_keys = set(dp.state_payload.keys())
            config_keys = set(dp.config_payload.keys())
            info_keys = set(dp.info_payload.keys())

            overlap_sc = state_keys & config_keys
            overlap_si = state_keys & info_keys
            overlap_ci = config_keys & info_keys

            assert not overlap_sc, f"{dp.state_path}: keys in both state and config: {overlap_sc}"
            assert not overlap_si, f"{dp.state_path}: keys in both state and info: {overlap_si}"
            assert not overlap_ci, f"{dp.state_path}: keys in both config and info: {overlap_ci}"


# ---------------------------------------------------------------------------
# Classification invariants: specific properties in correct payload
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [(TEST_DEVICES, True, None, None)],
)
async def test_min_max_temp_are_config_not_state(
    central_client_factory_with_ccu_client,
):
    """min_temp and max_temp must be in config_payload, not state_payload."""
    central, *_ = central_client_factory_with_ccu_client
    for device in central.devices:
        for dp in device.custom_data_points.values():
            if dp.category == DataPointCategory.CLIMATE:
                config_keys = set(dp.config_payload.keys())
                state_keys = set(dp.state_payload.keys())

                assert "min_temp" in config_keys, f"{dp}: min_temp missing from config_payload"
                assert "max_temp" in config_keys, f"{dp}: max_temp missing from config_payload"
                assert "min_temp" not in state_keys, f"{dp}: min_temp should not be in state_payload"
                assert "max_temp" not in state_keys, f"{dp}: max_temp should not be in state_payload"


# ---------------------------------------------------------------------------
# Quantity and ValueBehavior on sensor data points
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [(TEST_DEVICES, True, None, None)],
)
async def test_quantity_in_config_payload_for_known_sensors(
    central_client_factory_with_ccu_client,
):
    """Quantity should appear in config_payload for data points with known parameters."""
    central, *_ = central_client_factory_with_ccu_client
    # Parameters that must have a quantity mapping
    known_params = {
        "ACTUAL_TEMPERATURE",
        "HUMIDITY",
        "OPERATING_VOLTAGE",
        "ENERGY_COUNTER",
        "POWER",
        "VOLTAGE",
        "CURRENT",
        "RSSI_DEVICE",
        "RSSI_PEER",
        "LOW_BAT",
        "LOWBAT",
    }
    for device in central.devices:
        for dp in device.generic_data_points.values():
            if dp.parameter in known_params:
                config = dp.config_payload
                assert "quantity" in config, f"{dp.state_path} ({dp.parameter}): quantity missing from config_payload"
                assert config["quantity"] is not None, (
                    f"{dp.state_path} ({dp.parameter}): quantity should not be None for known parameter"
                )


@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [(TEST_DEVICES, True, None, None)],
)
async def test_value_behavior_in_config_payload_for_known_sensors(
    central_client_factory_with_ccu_client,
):
    """value_behavior should appear in config_payload for sensor data points."""
    central, *_ = central_client_factory_with_ccu_client
    # Parameters that must have value_behavior
    measurement_params = {
        "ACTUAL_TEMPERATURE",
        "HUMIDITY",
        "OPERATING_VOLTAGE",
        "POWER",
        "VOLTAGE",
        "CURRENT",
    }
    counter_params = {"ENERGY_COUNTER"}

    for device in central.devices:
        for dp in device.generic_data_points.values():
            if dp.parameter in measurement_params:
                config = dp.config_payload
                assert config.get("value_behavior") == ValueBehavior.INSTANTANEOUS, (
                    f"{dp.state_path} ({dp.parameter}): expected INSTANTANEOUS, got {config.get('value_behavior')}"
                )
            elif dp.parameter in counter_params:
                config = dp.config_payload
                assert config.get("value_behavior") == ValueBehavior.MONOTONIC, (
                    f"{dp.state_path} ({dp.parameter}): expected MONOTONIC, got {config.get('value_behavior')}"
                )


# ---------------------------------------------------------------------------
# Quantity enum completeness
# ---------------------------------------------------------------------------


def test_quantity_enum_covers_essential_types():
    """Verify Quantity enum includes all essential measurement types."""
    essential = {
        "temperature",
        "humidity",
        "voltage",
        "current",
        "power",
        "energy",
        "pressure",
        "illuminance",
        "signal_strength",
        "wind_speed",
        "battery",
        "motion",
        "smoke",
        "window",
    }
    quantity_values = {q.value for q in Quantity}
    missing = essential - quantity_values
    assert not missing, f"Quantity enum missing essential types: {missing}"


def test_value_behavior_enum_values():
    """Verify ValueBehavior enum has exactly the expected values."""
    assert set(ValueBehavior) == {
        ValueBehavior.INSTANTANEOUS,
        ValueBehavior.CUMULATIVE,
        ValueBehavior.MONOTONIC,
    }
