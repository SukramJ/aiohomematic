# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025 Daniel Perna, SukramJ
"""Decorators for data points used within aiohomematic."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from enum import Enum
from typing import Any, ParamSpec, TypeVar, cast
from weakref import WeakKeyDictionary

__all__ = [
    "config_property",
    "get_public_attributes_for_config_property",
    "get_public_attributes_for_info_property",
    "get_public_attributes_for_state_property",
    "info_property",
    "state_property",
]

P = ParamSpec("P")
T = TypeVar("T")


# pylint: disable=invalid-name
class generic_property[GETTER, SETTER](property):
    """Generic property implementation."""

    fget: Callable[[Any], GETTER] | None
    fset: Callable[[Any, SETTER], None] | None
    fdel: Callable[[Any], None] | None

    def __init__(
        self,
        fget: Callable[[Any], GETTER] | None = None,
        fset: Callable[[Any, SETTER], None] | None = None,
        fdel: Callable[[Any], None] | None = None,
        doc: str | None = None,
    ) -> None:
        """Init the generic property."""
        super().__init__(fget, fset, fdel, doc)
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

    def getter(self, fget: Callable[[Any], GETTER], /) -> generic_property:
        """Return generic getter."""
        return type(self)(fget, self.fset, self.fdel, self.__doc__)  # pragma: no cover

    def setter(self, fset: Callable[[Any, SETTER], None], /) -> generic_property:
        """Return generic setter."""
        return type(self)(self.fget, fset, self.fdel, self.__doc__)

    def deleter(self, fdel: Callable[[Any], None], /) -> generic_property:
        """Return generic deleter."""
        return type(self)(self.fget, self.fset, fdel, self.__doc__)

    def __get__(self, obj: Any, gtype: type | None = None, /) -> GETTER:  # type: ignore[override]
        """Return the attribute."""
        if obj is None:
            return self  # type: ignore[return-value]
        if self.fget is None:
            raise AttributeError("unreadable attribute")  # pragma: no cover
        return self.fget(obj)

    def __set__(self, obj: Any, value: Any, /) -> None:
        """Set the attribute."""
        if self.fset is None:
            raise AttributeError("can't set attribute")  # pragma: no cover
        self.fset(obj, value)

    def __delete__(self, obj: Any, /) -> None:
        """Delete the attribute."""
        if self.fdel is None:
            raise AttributeError("can't delete attribute")  # pragma: no cover
        self.fdel(obj)


# pylint: disable=invalid-name
class config_property[GETTER, SETTER](generic_property[GETTER, SETTER]):
    """Decorate to mark own config properties."""


# pylint: disable=invalid-name
class info_property[GETTER, SETTER](generic_property[GETTER, SETTER]):
    """Decorate to mark own info properties."""


# pylint: disable=invalid-name
class state_property[GETTER, SETTER](generic_property[GETTER, SETTER]):
    """Decorate to mark own value properties."""


# Cache for per-class attribute names by decorator to avoid repeated dir() scans
# Use WeakKeyDictionary to allow classes to be garbage-collected without leaking cache entries.
# Structure: {cls: {decorator_class: (attr_name1, attr_name2, ...)}}
_PUBLIC_ATTR_CACHE: WeakKeyDictionary[type, dict[type, tuple[str, ...]]] = WeakKeyDictionary()


def _get_public_attributes_by_class_decorator(data_object: Any, class_decorator: type) -> Mapping[str, Any]:
    """
    Return the object attributes by decorator.

    This caches the attribute names per (class, decorator) to reduce overhead
    from repeated dir()/getattr() scans. Values are not cached as they are
    instance-dependent and may change over time.
    """
    cls = data_object.__class__

    # Get or create the per-class cache dict
    if (decorator_cache := _PUBLIC_ATTR_CACHE.get(cls)) is None:
        decorator_cache = {}
        _PUBLIC_ATTR_CACHE[cls] = decorator_cache

    # Get or compute the attribute names for this decorator
    if (names := decorator_cache.get(class_decorator)) is None:
        names = tuple(y for y in dir(cls) if not y.startswith("_") and isinstance(getattr(cls, y), class_decorator))
        decorator_cache[class_decorator] = names

    return {name: _get_text_value(getattr(data_object, name)) for name in names}


def _get_text_value(value: Any) -> Any:
    """Convert value to text."""
    if isinstance(value, (list, tuple, set)):
        return tuple(_get_text_value(v) for v in value)
    if isinstance(value, Enum):
        return str(value)
    if isinstance(value, datetime):
        return datetime.timestamp(value)
    return value


def get_public_attributes_for_config_property(data_object: Any) -> Mapping[str, Any]:
    """Return the object attributes by decorator config_property."""
    return _get_public_attributes_by_class_decorator(data_object=data_object, class_decorator=config_property)


def get_public_attributes_for_info_property(data_object: Any) -> Mapping[str, Any]:
    """Return the object attributes by decorator info_property."""
    return _get_public_attributes_by_class_decorator(data_object=data_object, class_decorator=info_property)


def get_public_attributes_for_state_property(data_object: Any) -> Mapping[str, Any]:
    """Return the object attributes by decorator state_property."""
    return _get_public_attributes_by_class_decorator(data_object=data_object, class_decorator=state_property)


# pylint: disable=invalid-name
class cached_slot_property[T, R]:
    """A property-like descriptor that caches the computed value in a slot attribute. Designed to work with classes that use __slots__ and do not define __dict__."""

    def __init__(self, func: Callable[[T], R]) -> None:
        """Init the cached property."""
        self._func = func  # The function to compute the value
        self._cache_attr = f"_cached_{func.__name__}"  # Default name of the cache attribute
        self._name = func.__name__

    def __get__(self, instance: T | None, owner: type | None = None) -> R:
        """Return the cached value if it exists. Otherwise, compute it using the function and cache it."""
        if instance is None:
            # Accessed from class, return the descriptor itself
            return cast(R, self)

        # If the cached value is not set yet, compute and store it
        if not hasattr(instance, self._cache_attr):
            value = self._func(instance)
            setattr(instance, self._cache_attr, value)

        # Return the cached value
        return cast(R, getattr(instance, self._cache_attr))

    def __set__(self, instance: T, value: Any) -> None:
        """Raise an error to prevent manual assignment to the property."""
        raise AttributeError(f"Can't set read-only cached property '{self._name}'")

    def __delete__(self, instance: T) -> None:
        """Delete the cached value so it can be recomputed on next access."""
        if hasattr(instance, self._cache_attr):
            delattr(instance, self._cache_attr)
