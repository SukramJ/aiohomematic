"""Tests for switch data points of aiohomematic."""

from __future__ import annotations

from aiohomematic.property_decorators import (
    Kind,
    config_property,
    get_hm_property_by_kind,
    get_hm_property_by_log_context,
    info_property,
    state_property,
)

# pylint: disable=protected-access


def test_generic_property() -> None:
    """Test CustomDpSwitch."""
    test_class = PropertyTestClazz()
    assert test_class.value == "test_value"
    assert test_class.config == "test_config"
    test_class.value = "new_value"
    test_class.config = "new_config"
    assert test_class.value == "new_value"
    assert test_class.config == "new_config"
    del test_class.value
    del test_class.config
    assert test_class.value == ""
    assert test_class.config == ""


def test_generic_property_read() -> None:
    """Test CustomDpSwitch."""
    test_class = PropertyTestClazz()
    config_attributes = get_hm_property_by_kind(data_object=test_class, kind=Kind.CONFIG)
    assert config_attributes == {"config": "test_config"}
    value_attributes = get_hm_property_by_kind(data_object=test_class, kind=Kind.STATE)
    assert value_attributes == {"value": "test_value"}
    info_attributes = get_hm_property_by_kind(data_object=test_class, kind=Kind.INFO)
    assert info_attributes == {"info": "test_info", "info_context": "test_info"}
    info_context_attributes = get_hm_property_by_log_context(data_object=test_class)
    assert info_context_attributes == {"info_context": "test_info"}


class PropertyTestClazz:
    """test class for generic_properties."""

    def __init__(self):
        """Init PropertyTestClazz."""
        self._value: str = "test_value"
        self._config: str = "test_config"
        self._info: str = "test_info"

    @state_property
    def value(self) -> str:
        """Return value."""
        return self._value

    @value.setter
    def value(self, value: str) -> None:
        """Set value."""
        self._value = value

    @value.deleter
    def value(self) -> None:
        """Delete value."""
        self._value = ""

    @config_property
    def config(self) -> str:
        """Return config."""
        return self._config

    @config.setter
    def config(self, config: str) -> None:
        """Set config."""
        self._config = config

    @config.deleter
    def config(self) -> None:
        """Delete config."""
        self._config = ""

    @info_property
    def info(self) -> str:
        """Return info."""
        return self._info

    @info_property(log_context=True)
    def info_context(self) -> str:
        """Return info context."""
        return self._info
