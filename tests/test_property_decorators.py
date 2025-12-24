# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for property decorators of aiohomematic."""

from __future__ import annotations

import pytest

from aiohomematic.property_decorators import (
    Kind,
    _GenericProperty,
    config_property,
    get_hm_property_by_kind,
    get_hm_property_by_log_context,
    hm_property,
    info_property,
    state_property,
)

# pylint: disable=protected-access


class TestBasicPropertyDecorators:
    """Test basic property decorator functionality."""

    def test_generic_property_get_set_delete(self) -> None:
        """Test basic get, set, and delete operations."""
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

    def test_generic_property_unreadable_attribute_raises(self) -> None:
        """Test that property without getter raises AttributeError."""
        prop: _GenericProperty[int, int] = _GenericProperty(
            fget=None,
            fset=None,
            fdel=None,
            doc=None,
            kind=Kind.SIMPLE,
            cached=False,
            log_context=False,
        )

        class C:
            p = prop  # type: ignore[assignment]

        with pytest.raises(AttributeError, match="unreadable attribute"):
            _ = C().p  # type: ignore[attr-defined]

    def test_hm_property_read_only(self) -> None:
        """Test read-only hm_property."""
        d = DummyReadOnly()
        assert d.x == 1

        with pytest.raises(AttributeError, match="can't set attribute"):
            DummyReadOnly.x.__set__(d, 2)  # type: ignore[arg-type]

        with pytest.raises(AttributeError, match="can't delete attribute"):
            DummyReadOnly.x.__delete__(d)

    def test_log_context_collection(self) -> None:
        """Test collecting properties marked for log context."""
        test_class = PropertyTestClazz()
        info_context_attributes = get_hm_property_by_log_context(data_object=test_class)
        assert info_context_attributes == {"info_context": "test_info"}

    def test_property_kind_collection(self) -> None:
        """Test collecting properties by kind."""
        test_class = PropertyTestClazz()

        config_attributes = get_hm_property_by_kind(data_object=test_class, kind=Kind.CONFIG)
        assert config_attributes == {"config": "test_config"}

        value_attributes = get_hm_property_by_kind(data_object=test_class, kind=Kind.STATE)
        assert value_attributes == {"value": "test_value"}

        info_attributes = get_hm_property_by_kind(data_object=test_class, kind=Kind.INFO)
        assert info_attributes == {"info": "test_info", "info_context": "test_info"}


class TestCachedProperties:
    """Test cached property functionality."""

    def test_cached_property_basic(self) -> None:
        """Test that cached properties cache their values."""
        test_obj = CachedPropertyTestClazz()

        # First access computes
        val1 = test_obj.cached_value
        assert val1 == "computed_1"

        # Second access returns cached value
        val2 = test_obj.cached_value
        assert val2 == "computed_1"
        assert test_obj.call_count == 1  # Only computed once

    def test_cached_property_invalidation_on_delete(self) -> None:
        """Test that cache is invalidated when property is deleted."""
        test_obj = CachedPropertyTestClazz()

        # Access to cache
        _ = test_obj.cached_value
        assert test_obj.call_count == 1

        # Deleting should invalidate cache
        del test_obj.cached_value

        # Next access should recompute
        val = test_obj.cached_value
        assert val == "computed_2"
        assert test_obj.call_count == 2

    def test_cached_property_invalidation_on_set(self) -> None:
        """Test that cache is invalidated when property is set."""
        test_obj = CachedPropertyTestClazz()

        # Access to cache
        _ = test_obj.cached_value
        assert test_obj.call_count == 1

        # Setting should invalidate cache
        test_obj.cached_value = "new"

        # Next access should recompute
        val = test_obj.cached_value
        assert val == "computed_2"
        assert test_obj.call_count == 2


class TestCachedPropertiesWithSlots:
    """Test cached properties with __slots__ objects."""

    def test_cached_property_slots_basic(self) -> None:
        """Test cached property works with __slots__."""
        test_obj = SlotsClassWithCachedProperty()

        # First access computes
        val1 = test_obj.cached_value
        assert val1 == "slots_1"

        # Second access returns cached value
        val2 = test_obj.cached_value
        assert val2 == "slots_1"
        assert test_obj.call_count == 1

    def test_cached_property_slots_delete_invalidation(self) -> None:
        """Test cache invalidation with __slots__ on delete."""
        test_obj = SlotsClassWithCachedProperty()

        # Access to cache
        _ = test_obj.cached_value
        assert test_obj.call_count == 1

        # Deleting should invalidate cache
        del test_obj.cached_value

        # Next access should recompute
        val = test_obj.cached_value
        assert val == "slots_2"
        assert test_obj.call_count == 2

    def test_cached_property_slots_set_invalidation(self) -> None:
        """Test cache invalidation with __slots__ on set."""
        test_obj = SlotsClassWithCachedProperty()

        # Access to cache
        _ = test_obj.cached_value
        assert test_obj.call_count == 1

        # Setting should invalidate cache
        test_obj.cached_value = "new"

        # Next access should recompute
        val = test_obj.cached_value
        assert val == "slots_2"
        assert test_obj.call_count == 2


class TestCachedPropertySlotsMissing:
    """Test that missing cache slots raise TypeError at class definition time."""

    def test_cached_property_missing_slot_raises_type_error_at_class_definition(self) -> None:
        """Test that defining a class with cached property but missing cache slot raises TypeError."""
        # The error should be raised when the class is DEFINED, not when accessed
        with pytest.raises(TypeError, match="missing cache slot '_cached_cached_value'"):

            class SlotsClassMissingCacheSlot:
                """Test class with __slots__ but WITHOUT the cache slot."""

                __slots__ = ("_storage", "call_count")  # Missing _cached_cached_value!

                def __init__(self):
                    """Init SlotsClassMissingCacheSlot."""
                    self._storage: str = "initial"
                    self.call_count: int = 0

                @hm_property(cached=True)
                def cached_value(self) -> str:
                    """Return a computed value that should be cached."""
                    self.call_count += 1
                    return f"slots_{self.call_count}"

    def test_cached_property_with_dict_in_parent_is_allowed(self) -> None:
        """Test that cached property is allowed if parent class has __dict__."""

        class ParentWithDict:
            """Parent class without __slots__ (has __dict__)."""

        # This should NOT raise because ParentWithDict has __dict__
        class ChildWithSlots(ParentWithDict):
            """Child with __slots__ but parent has __dict__."""

            __slots__ = ("_value",)

            @hm_property(cached=True)
            def cached_value(self) -> str:
                """Return cached value."""
                return "cached"

        obj = ChildWithSlots()
        assert obj.cached_value == "cached"


class TestPropertyDocstrings:
    """Test that property docstrings are preserved."""

    def test_property_doc_from_getter(self) -> None:
        """Test that docstring is taken from getter when not explicitly provided."""
        PropertyTestClazz()
        assert PropertyTestClazz.config.__doc__ == "Return config."
        assert PropertyTestClazz.value.__doc__ == "Return value."


class TestPropertyNameFallbacks:
    """Test property name fallbacks for cached properties."""

    def test_cached_property_name_fallback_to_prop(self) -> None:
        """Test that cache attr name falls back to 'prop' if all are None."""
        prop = _GenericProperty(
            fget=None,
            fset=None,
            fdel=None,
            doc=None,
            kind=Kind.SIMPLE,
            cached=True,
            log_context=False,
        )
        # Should use default 'prop' for cache attribute
        assert prop._cache_attr == "_cached_prop"

    def test_cached_property_name_from_fdel(self) -> None:
        """Test that cache attr name comes from fdel if fget and fset are None."""
        prop = _GenericProperty(
            fget=None,
            fset=None,
            fdel=lambda self: None,
            doc=None,
            kind=Kind.SIMPLE,
            cached=True,
            log_context=False,
        )
        # Should use fdel.__name__ for cache attribute
        assert prop._cache_attr == "_cached_<lambda>"

    def test_cached_property_name_from_fset(self) -> None:
        """Test that cache attr name comes from fset if fget is None."""
        prop = _GenericProperty(
            fget=None,
            fset=lambda self, val: None,
            fdel=None,
            doc=None,
            kind=Kind.SIMPLE,
            cached=True,
            log_context=False,
        )
        # Should use fset.__name__ for cache attribute
        assert prop._cache_attr == "_cached_<lambda>"


# Test fixture classes


class DummyReadOnly:
    """Test class with read-only property."""

    def __init__(self) -> None:
        self._x = 1

    @hm_property
    def x(self) -> int:
        return self._x


class PropertyTestClazz:
    """Test class for generic properties."""

    def __init__(self):
        """Init PropertyTestClazz."""
        self._value: str = "test_value"
        self._config: str = "test_config"
        self._info: str = "test_info"

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

    @info_property
    def info(self) -> str:
        """Return info."""
        return self._info

    @info_property(log_context=True)
    def info_context(self) -> str:
        """Return info context."""
        return self._info


class CachedPropertyTestClazz:
    """Test class for cached properties."""

    def __init__(self):
        """Init CachedPropertyTestClazz."""
        self._storage: str = "initial"
        self.call_count: int = 0

    @hm_property(cached=True)
    def cached_value(self) -> str:
        """Return a computed value that should be cached."""
        self.call_count += 1
        return f"computed_{self.call_count}"

    @cached_value.setter
    def cached_value(self, value: str) -> None:
        """Set the value."""
        self._storage = value

    @cached_value.deleter
    def cached_value(self) -> None:
        """Delete the value."""
        self._storage = "deleted"


class SlotsClassWithCachedProperty:
    """Test class with __slots__ and cached property."""

    __slots__ = ("_storage", "call_count", "_cached_cached_value")

    def __init__(self):
        """Init SlotsClassWithCachedProperty."""
        self._storage: str = "initial"
        self.call_count: int = 0

    @hm_property(cached=True)
    def cached_value(self) -> str:
        """Return a computed value that should be cached."""
        self.call_count += 1
        return f"slots_{self.call_count}"

    @cached_value.setter
    def cached_value(self, value: str) -> None:
        """Set the value."""
        self._storage = value

    @cached_value.deleter
    def cached_value(self) -> None:
        """Delete the value."""
        self._storage = "deleted"
