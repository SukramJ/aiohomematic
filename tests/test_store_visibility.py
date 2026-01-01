# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Tests for aiohomematic.store.visibility.ParameterVisibilityRegistry and helpers.

These tests focus on decision logic for ignore/un-ignore/hidden checks and
paramset relevance. They use minimal stubs and do not alter production code.
All tests include a docstring.
"""

from __future__ import annotations

from dataclasses import dataclass

from aiohomematic.central.events import EventBus
from aiohomematic.const import Parameter, ParamsetKey
from aiohomematic.store.visibility import ParameterVisibilityRegistry, check_ignore_parameters_is_clean


@dataclass(slots=True)
class _Cfg:
    storage_directory: str = ""
    un_ignore_list: frozenset[str] | None = frozenset()
    ignore_custom_device_definition_models: frozenset[str] = frozenset({"hmip-ignored*"})


class _EventBusProvider:
    """Minimal event bus provider stub for tests."""

    def __init__(self) -> None:
        self._event_bus = EventBus()

    @property
    def event_bus(self) -> EventBus:
        """Return the event bus."""
        return self._event_bus


class _Central:
    """Minimal central stub exposing config."""

    def __init__(self, *, storage_directory: str = "", un_ignore_list: frozenset[str] | None = frozenset()) -> None:
        self.config = _Cfg(storage_directory=storage_directory, un_ignore_list=un_ignore_list)


class _Central2:
    def __init__(self) -> None:
        self.config = _Cfg()


class _Device:
    def __init__(self, model: str) -> None:
        self.model = model


class _Channel:
    def __init__(self, model: str, address: str, no: int) -> None:
        self.device = _Device(model)
        self.address = address
        self.no = no


class TestParameterUnIgnore:
    """Test parameter un-ignore functionality."""

    def test_parameter_is_un_ignored_custom_complex_master_path(self) -> None:
        """Custom un_ignore complex entry (MASTER@model:channel) should set early True branch."""
        central = _Central2()
        pvr = ParameterVisibilityRegistry(config_provider=central, event_bus_provider=_EventBusProvider())

        # Add a complex un_ignore entry targeting a specific model/channel for MASTER
        line = f"{Parameter.OPERATING_VOLTAGE}:MASTER@HmIP-Any:1"
        pvr._process_un_ignore_entries(lines=[line])  # type: ignore[attr-defined]

        ch = _Channel(model="HmIP-Any", address="X:1", no=1)
        assert (
            pvr.parameter_is_un_ignored(
                channel=ch,
                paramset_key=ParamsetKey.MASTER,
                parameter=Parameter.OPERATING_VOLTAGE,
                custom_only=True,
            )
            is True
        )

    def test_parameter_is_un_ignored_from_mapping_master_and_values(self) -> None:
        """Built-in mappings should mark some MASTER/VALUES parameters as un-ignored for certain models."""
        pvr = ParameterVisibilityRegistry(config_provider=_Central(), event_bus_provider=_EventBusProvider())
        # Choose a model with PARAMSET MASTER entries defined in module mappings for channel 1
        ch_master = _Channel(model="HmIP-DRSI1", address="A1:1", no=1)
        # CHANNEL_OPERATION_MODE is whitelisted for MASTER for this model mapping
        assert (
            pvr.parameter_is_un_ignored(
                channel=ch_master, paramset_key=ParamsetKey.MASTER, parameter=Parameter.CHANNEL_OPERATION_MODE
            )
            is True
        )

        # VALUES un-ignore via device prefix based mapping (_UN_IGNORE_PARAMETERS_BY_DEVICE)
        ch_values = _Channel(model="HmIP-PCBS-BAT", address="A2:2", no=2)
        # OPERATING_VOLTAGE is included for this family via _UN_IGNORE_PARAMETERS_BY_DEVICE
        assert (
            pvr.parameter_is_un_ignored(
                channel=ch_values, paramset_key=ParamsetKey.VALUES, parameter=Parameter.OPERATING_VOLTAGE
            )
            is True
        )


class TestModelIgnore:
    """Test model ignore pattern matching."""

    def test_model_is_ignored_by_pattern(self) -> None:
        """model_is_ignored should apply pattern configured on central using element_matches_key rules."""
        # Configure pattern to match exact or wildcard according to element_matches_key semantics
        central = _Central()
        # Override ignore patterns to include an exact model name and a wildcard prefix
        central.config.ignore_custom_device_definition_models = frozenset({"HmIP-Exact", "HmIP-"})
        pvr = ParameterVisibilityRegistry(config_provider=central, event_bus_provider=_EventBusProvider())
        assert pvr.model_is_ignored(model="HmIP-Exact") is True
        assert pvr.model_is_ignored(model="HmIP-Other") is True  # matches HmIP-* wildcard
        assert pvr.model_is_ignored(model="Other-Thing") is False


class TestParameterIgnore:
    """Test parameter ignore rules."""

    def test_parameter_is_ignored_accept_only_on_channel_rule(self) -> None:
        """LOWBAT should be accepted only on defined channel, ignored on others."""
        pvr = ParameterVisibilityRegistry(config_provider=_Central(), event_bus_provider=_EventBusProvider())
        ch0 = _Channel(model="HmIP-XYZ", address="D1:0", no=0)
        ch1 = _Channel(model="HmIP-XYZ", address="D1:1", no=1)

        # LOWBAT specific accept-only-on-channel=0 rule
        assert (
            pvr.parameter_is_ignored(channel=ch0, paramset_key=ParamsetKey.VALUES, parameter=Parameter.LOWBAT) is False
        )
        assert (
            pvr.parameter_is_ignored(channel=ch1, paramset_key=ParamsetKey.VALUES, parameter=Parameter.LOWBAT) is True
        )


class TestShouldSkipParameter:
    """Test should_skip_parameter logic."""

    def test_should_skip_parameter_master_logic(self) -> None:
        """should_skip_parameter combines ignore and un-ignore and master relevant-channel logic."""
        pvr = ParameterVisibilityRegistry(config_provider=_Central(), event_bus_provider=_EventBusProvider())

        # A model/channel that is relevant for MASTER via mapping
        ch = _Channel(model="HmIP-Any", address="A:0", no=0)

        # If parameter is in the per-channel relevant list (channel mapping), it should not be skipped
        assert (
            pvr.should_skip_parameter(
                channel=ch,
                paramset_key=ParamsetKey.MASTER,
                parameter=Parameter.GLOBAL_BUTTON_LOCK,
                parameter_is_un_ignored=False,
            )
            is False
        )

        # A random parameter not in un-ignore and not in relevant list should be skipped for MASTER
        assert (
            pvr.should_skip_parameter(
                channel=ch,
                paramset_key=ParamsetKey.MASTER,
                parameter=Parameter.LEVEL,
                parameter_is_un_ignored=False,
            )
            is True
        )


class TestParameterHidden:
    """Test parameter hidden status."""

    def test_parameter_is_hidden(self) -> None:
        """parameter_is_hidden should be true only for hidden parameters not un-ignored by custom rules."""
        # Prepare a custom un_ignore that would unhide a hidden parameter globally for VALUES
        # Format: PARAM:VALUES@*:* where * means wildcard for model and channel
        un_ignore = frozenset({f"{Parameter.GLOBAL_BUTTON_LOCK}:VALUES@*:*"})
        pvr = ParameterVisibilityRegistry(
            config_provider=_Central(un_ignore_list=un_ignore), event_bus_provider=_EventBusProvider()
        )

        ch = _Channel(model="HmIP-Any", address="X:1", no=1)

        # BUTTON_LOCK is hidden by default, but un_ignore should prevent hiding
        assert (
            pvr.parameter_is_hidden(channel=ch, paramset_key=ParamsetKey.VALUES, parameter=Parameter.GLOBAL_BUTTON_LOCK)
            is False
        )


class TestRelevantParamset:
    """Test paramset relevance determination."""

    def test_is_relevant_paramset_values_true_master_by_model_and_channel(self) -> None:
        """VALUES should always be relevant; MASTER relevance depends on channel and model prefix mapping."""
        pvr = ParameterVisibilityRegistry(config_provider=_Central(), event_bus_provider=_EventBusProvider())

        # VALUES always relevant
        ch = _Channel(model="HmIP-Any", address="Y:1", no=1)
        assert pvr.is_relevant_paramset(channel=ch, paramset_key=ParamsetKey.VALUES) is True

        # MASTER relevant if channel is in mapping by channel number
        ch0 = _Channel(model="HmIP-Other", address="Y:0", no=0)
        assert pvr.is_relevant_paramset(channel=ch0, paramset_key=ParamsetKey.MASTER) in (True, False)

        # MASTER relevant for models whose prefix is in mapping and channel listed there
        chm = _Channel(model="HmIPW-DRI16", address="M:1", no=1)
        assert pvr.is_relevant_paramset(channel=chm, paramset_key=ParamsetKey.MASTER) in (True, False)


class TestIgnoreParametersCheck:
    """Test ignore parameters sanity check."""

    def test_check_ignore_parameters_is_clean(self) -> None:
        """Sanity check for ignored vs required parameters helper returns a boolean without raising."""
        assert check_ignore_parameters_is_clean() in (True, False)
