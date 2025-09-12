# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025 Daniel Perna, SukramJ
"""Decorators for data points used within aiohomematic."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from enum import Enum
from typing import Any, ParamSpec, TypeVar, cast, overload
from weakref import WeakKeyDictionary

__all__ = [
    "config_property",
    "get_attributes_for_config_property",
    "get_attributes_for_info_property",
    "get_attributes_for_state_property",
    "info_property",
    "state_property",
]

P = ParamSpec("P")
T = TypeVar("T")
R = TypeVar("R")


class _GenericProperty[GETTER, SETTER](property):
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
        log_context: bool = False,
    ) -> None:
        """Init the generic property."""
        super().__init__(fget, fset, fdel, doc)
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc
        self.log_context = log_context

    def getter(self, fget: Callable[[Any], GETTER], /) -> _GenericProperty:
        """Return generic getter."""
        return type(self)(fget, self.fset, self.fdel, self.__doc__)  # pragma: no cover

    def setter(self, fset: Callable[[Any, SETTER], None], /) -> _GenericProperty:
        """Return generic setter."""
        return type(self)(self.fget, fset, self.fdel, self.__doc__)

    def deleter(self, fdel: Callable[[Any], None], /) -> _GenericProperty:
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


# ----- config_property -----


class _ConfigProperty[GETTER, SETTER](_GenericProperty[GETTER, SETTER]):
    """Decorate to mark own config properties."""


@overload
def config_property[PR](func: Callable[[Any], PR], /) -> _ConfigProperty[PR, Any]: ...


@overload
def config_property(*, log_context: bool = ...) -> Callable[[Callable[[Any], R]], _ConfigProperty[R, Any]]: ...


def config_property[PR](
    func: Callable[[Any], PR] | None = None,
    *,
    log_context: bool = False,
) -> _ConfigProperty[PR, Any] | Callable[[Callable[[Any], PR]], _ConfigProperty[PR, Any]]:
    """
    Return an instance of _ConfigProperty wrapping the given function.

    Decorator for config properties supporting both usages:
    - @config_property
    - @config_property(log_context=True)
    """
    if func is None:

        def wrapper(f: Callable[[Any], PR]) -> _ConfigProperty[PR, Any]:
            return _ConfigProperty(f, log_context=log_context)

        return wrapper
    return _ConfigProperty(func, log_context=log_context)


# Expose the underlying property class for discovery
setattr(config_property, "__property_class__", _ConfigProperty)


# ----- info_property -----


class _InfoProperty[GETTER, SETTER](_GenericProperty[GETTER, SETTER]):
    """Decorate to mark own info properties."""


@overload
def info_property[PR](func: Callable[[Any], PR], /) -> _InfoProperty[PR, Any]: ...


@overload
def info_property(*, log_context: bool = ...) -> Callable[[Callable[[Any], R]], _InfoProperty[R, Any]]: ...


def info_property[PR](
    func: Callable[[Any], PR] | None = None,
    *,
    log_context: bool = False,
) -> _InfoProperty[PR, Any] | Callable[[Callable[[Any], PR]], _InfoProperty[PR, Any]]:
    """
    Return an instance of _InfoProperty wrapping the given function.

    Decorator for info properties supporting both usages:
    - @info_property
    - @info_property(log_context=True)
    """
    if func is None:

        def wrapper(f: Callable[[Any], PR]) -> _InfoProperty[PR, Any]:
            return _InfoProperty(f, log_context=log_context)

        return wrapper
    return _InfoProperty(func, log_context=log_context)


# Expose the underlying property class for discovery
setattr(info_property, "__property_class__", _InfoProperty)


# ----- state_property -----


class _StateProperty[GETTER, SETTER](_GenericProperty[GETTER, SETTER]):
    """Decorate to mark own config properties."""


@overload
def state_property[PR](func: Callable[[Any], PR], /) -> _StateProperty[PR, Any]: ...


@overload
def state_property(*, log_context: bool = ...) -> Callable[[Callable[[Any], R]], _StateProperty[R, Any]]: ...


def state_property[PR](
    func: Callable[[Any], PR] | None = None,
    *,
    log_context: bool = False,
) -> _StateProperty[PR, Any] | Callable[[Callable[[Any], PR]], _StateProperty[PR, Any]]:
    """
    Return an instance of _StateProperty wrapping the given function.

    Decorator for state properties supporting both usages:
    - @state_property
    - @state_property(log_context=True)
    """
    if func is None:

        def wrapper(f: Callable[[Any], PR]) -> _StateProperty[PR, Any]:
            return _StateProperty(f, log_context=log_context)

        return wrapper
    return _StateProperty(func, log_context=log_context)


# Expose the underlying property class for discovery
setattr(state_property, "__property_class__", _StateProperty)

# ----------

# Cache for per-class attribute names by decorator to avoid repeated dir() scans
# Use WeakKeyDictionary to allow classes to be garbage-collected without leaking cache entries.
# Structure: {cls: {decorator_class: (attr_name1, attr_name2, ...)}}
_PUBLIC_ATTR_CACHE: WeakKeyDictionary[type, dict[type, tuple[str, ...]]] = WeakKeyDictionary()


def _get_attributes_by_decorator(data_object: Any, decorator: Callable, context: bool = False) -> Mapping[str, Any]:
    """
    Return the object attributes by decorator.

    This caches the attribute names per (class, decorator) to reduce overhead
    from repeated dir()/getattr() scans. Values are not cached as they are
    instance-dependent and may change over time.

    To minimize side effects, exceptions raised by property getters are caught
    and the corresponding value is set to None. This ensures that payload
    construction and attribute introspection do not fail due to individual
    properties with transient errors or expensive side effects.
    """
    cls = data_object.__class__

    # Resolve function-based decorators to their underlying property class, if provided
    resolved_decorator: Any = decorator
    if not isinstance(decorator, type):
        resolved_decorator = getattr(decorator, "__property_class__", decorator)

    # Get or create the per-class cache dict
    if (decorator_cache := _PUBLIC_ATTR_CACHE.get(cls)) is None:
        decorator_cache = {}
        _PUBLIC_ATTR_CACHE[cls] = decorator_cache

    # Get or compute the attribute names for this decorator
    if (names := decorator_cache.get(resolved_decorator)) is None:
        names = tuple(y for y in dir(cls) if isinstance(getattr(cls, y), resolved_decorator))
        decorator_cache[resolved_decorator] = names

    result: dict[str, Any] = {}
    for name in names:
        if context and getattr(cls, name).log_context is False:
            continue
        try:
            value = getattr(data_object, name)
        except Exception:
            # Avoid propagating side effects/errors from getters
            value = None
        result[name] = _get_text_value(value)
    return result


def _get_text_value(value: Any) -> Any:
    """Convert value to text."""
    if isinstance(value, list | tuple | set):
        return tuple(_get_text_value(v) for v in value)
    if isinstance(value, Enum):
        return str(value)
    if isinstance(value, datetime):
        return datetime.timestamp(value)
    return value


def get_attributes_for_config_property(data_object: Any) -> Mapping[str, Any]:
    """Return the object attributes by decorator config_property."""
    return _get_attributes_by_decorator(data_object=data_object, decorator=config_property)


def get_attributes_for_info_property(data_object: Any) -> Mapping[str, Any]:
    """Return the object attributes by decorator info_property."""
    return _get_attributes_by_decorator(data_object=data_object, decorator=info_property)


def get_attributes_for_log_context(data_object: Any) -> Mapping[str, Any]:
    """Return the object attributes by decorator info_property."""
    return dict(_get_attributes_by_decorator(data_object=data_object, decorator=config_property, context=True)) | dict(
        _get_attributes_by_decorator(data_object=data_object, decorator=info_property, context=True)
    )


def get_attributes_for_state_property(data_object: Any) -> Mapping[str, Any]:
    """Return the object attributes by decorator state_property."""
    return _get_attributes_by_decorator(data_object=data_object, decorator=state_property)


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
