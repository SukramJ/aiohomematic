# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Decorators and helpers for declaring public attributes on data point classes.

This module provides a property descriptor (hm_property) and a delegation
descriptor (DelegatedProperty) that behave like the built-in @property, but
additionally support two orthogonal, optional features:
- cached: per-instance caching of the computed/delegated value.
- log_context: inclusion in the LogContextMixin.log_context mapping.

Notes on caching
- Marked with cached=True always store on first access and invalidates on set/delete.
"""

from collections.abc import Callable, Mapping
import contextlib
import dataclasses
from datetime import datetime
from enum import Enum
from functools import singledispatch
from typing import Any, Final, ParamSpec, Self, TypeVar, cast, overload
from weakref import WeakKeyDictionary

from aiohomematic._log_context_protocol import LogContextProtocol

__all__ = [
    "DelegatedProperty",
    "_GenericProperty",
    "get_hm_property_by_log_context",
    "get_hm_property_names",
    "hm_property",
]

P = ParamSpec("P")
T = TypeVar("T")
R = TypeVar("R")


class DelegatedProperty[ValueT]:
    """
    Descriptor that delegates property access to a nested attribute path.

    This descriptor simplifies forwarding properties that just return an
    attribute from a nested object, eliminating boilerplate. It behaves
    like a read-only @property and can be overridden by subclasses.

    Supports the same optional features as hm_property:
    - cached: Cache the delegated value on first access
    - log_context: Include in structured log context

    Usage:
        # Simple delegation:
        interface: Final = DelegatedProperty[Interface](path="_config.interface")

        # With caching:
        state: Final = DelegatedProperty[ClientState](
            path="_state_machine.state",
            cached=True,
        )

        # With log_context:
        interface_id: Final = DelegatedProperty[str](
            path="_config.interface_id",
            log_context=True,
        )

    Note:
        Do NOT use type annotations on the left side like `interface: Interface = ...`
        as this confuses mypy. The generic type parameter provides type information.

    """

    __slots__ = ("_cache_attr", "_cached", "_doc", "_parts", "_path", "log_context")

    __kwonly_check__ = False

    def __init__(
        self,
        *,
        path: str,
        doc: str | None = None,
        cached: bool = False,
        log_context: bool = False,
    ) -> None:
        """
        Initialize the delegated property descriptor.

        Args:
            path: Dot-separated attribute path (e.g., "_config.interface").
            doc: Optional docstring for the property.
            cached: Enable per-instance caching of the delegated value.
            log_context: Include this property in structured log context if True.

        """
        self._path: Final = path
        self._parts: Final = tuple(path.split("."))
        self._doc = doc
        self._cached: Final = cached
        self.log_context = log_context
        if cached:
            # Use the property name (set in __set_name__) for cache attribute
            # Fallback to path-based name if __set_name__ is not called
            self._cache_attr = ""  # Will be set in __set_name__

    @overload
    def __get__(self, instance: None, owner: type) -> Self: ...

    @overload
    def __get__(self, instance: object, owner: type) -> ValueT: ...

    def __get__(self, instance: object | None, owner: type) -> ValueT | Self:
        """Return the delegated attribute value."""
        if instance is None:
            return self

        if not self._cached:
            value: Any = instance
            for part in self._parts:
                value = getattr(value, part)
            return cast(ValueT, value)

        # Caching enabled - check cache first
        cache_attr = self._cache_attr
        try:
            inst_dict = instance.__dict__
            if cache_attr in inst_dict:
                return cast(ValueT, inst_dict[cache_attr])

            # Not cached yet, resolve and store
            value = instance
            for part in self._parts:
                value = getattr(value, part)
            inst_dict[cache_attr] = value
        except AttributeError:
            # Object uses __slots__, use slot for caching
            try:
                return cast(ValueT, getattr(instance, cache_attr))
            except AttributeError:
                # Cache slot exists but not set, compute and store
                value = instance
                for part in self._parts:
                    value = getattr(value, part)
                setattr(instance, cache_attr, value)
        return cast(ValueT, value)

    def __set__(self, instance: object, value: Any) -> None:
        """Raise AttributeError - this is a read-only property."""
        raise AttributeError("can't set attribute")  # i18n-exc: ignore

    def __set_name__(self, owner: type, name: str) -> None:
        """Set cache attribute name and validate cache slot exists when class is defined."""
        if not self._cached:
            return

        # Set cache attribute name based on property name
        self._cache_attr = f"_cached_{name}"

        # Collect all slots from the class hierarchy
        all_slots: set[str] = set()
        has_dict = False

        for cls in owner.__mro__:
            if cls is object:
                continue
            if (cls_slots := getattr(cls, "__slots__", None)) is None:
                # Class without __slots__ has __dict__
                has_dict = True
                continue
            if isinstance(cls_slots, str):
                all_slots.add(cls_slots)
            else:
                all_slots.update(cls_slots)
            if "__dict__" in all_slots:
                has_dict = True

        # If class has __dict__, caching works via instance.__dict__
        if has_dict:
            return

        # Check if cache slot exists in any class in the hierarchy
        if (cache_attr := self._cache_attr) not in all_slots:
            msg = f"Class {owner.__name__} uses __slots__ but is missing cache slot '{cache_attr}' required by DelegatedProperty(cached=True) on '{name}'"
            raise TypeError(msg)  # i18n-exc: ignore


class _GenericProperty[GETTER, SETTER](property):
    """
    Base descriptor used by hm_property in this module.

    Extends the built-in property to optionally cache the computed value on the
    instance and to carry a log_context flag.

    Args:
    - fget/fset/fdel: Standard property callables.
    - doc: Optional docstring of the property.
    - cached: If True, the computed value is cached per instance and
      invalidated when the descriptor receives a set/delete.
    - log_context: If True, the property is included in get_attributes_for_log_context().

    """

    __kwonly_check__ = False

    fget: Callable[[Any], GETTER] | None
    fset: Callable[[Any, SETTER], None] | None
    fdel: Callable[[Any], None] | None

    def __init__(
        self,
        fget: Callable[[Any], GETTER] | None = None,
        fset: Callable[[Any, SETTER], None] | None = None,
        fdel: Callable[[Any], None] | None = None,
        doc: str | None = None,
        cached: bool = False,
        log_context: bool = False,
    ) -> None:
        """
        Initialize the descriptor.

        Mirrors the standard property signature and adds options:
        - cached: enable per-instance caching of the computed value.
        - log_context: mark this property as relevant for structured logging.
        """
        super().__init__(fget, fset, fdel, doc)
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc
        self._cached: Final = cached
        self.log_context = log_context
        self._cache_attr: str = ""
        if cached:
            if fget is not None:
                func_name = fget.__name__
            elif fset is not None:
                func_name = fset.__name__
            elif fdel is not None:
                func_name = fdel.__name__
            else:
                func_name = "prop"
            self._cache_attr = f"_cached_{func_name}"

    def __delete__(self, instance: Any, /) -> None:
        """Delete the attribute and invalidate cache if enabled."""
        # Delete the cached value so it can be recomputed on next access.
        if self._cached:
            cache_attr = self._cache_attr
            try:
                instance.__dict__.pop(cache_attr, None)
            except AttributeError:
                # Object uses __slots__, reset slot to unset state
                with contextlib.suppress(AttributeError):
                    delattr(instance, cache_attr)

        if self.fdel is None:
            raise AttributeError("can't delete attribute")  # i18n-exc: ignore
        self.fdel(instance)

    @overload
    def __get__(self, instance: None, owner: type[Any], /) -> Self: ...

    @overload
    def __get__(self, instance: object, owner: type[Any] | None = None, /) -> GETTER: ...

    def __get__(self, instance: object | None, owner: type[Any] | None = None, /) -> GETTER | Self:
        """
        Return the attribute value.

        If caching is enabled, compute on first access and return the per-instance
        cached value on subsequent accesses.
        """
        if instance is None:
            # Accessed from class, return the descriptor itself
            return self

        if (fget := self.fget) is None:
            raise AttributeError("unreadable attribute")  # i18n-exc: ignore

        if not self._cached:
            return fget(instance)

        # Use direct __dict__ access when available for better performance
        # Store cache_attr in local variable to avoid repeated attribute lookup
        cache_attr = self._cache_attr

        try:
            inst_dict = instance.__dict__
            # Use 'in' check first to distinguish between missing and None
            if cache_attr in inst_dict:
                return cast(GETTER, inst_dict[cache_attr])

            # Not cached yet, compute and store
            value = fget(instance)
            inst_dict[cache_attr] = value
        except AttributeError:
            # Object uses __slots__, use slot for caching
            try:
                return cast(GETTER, getattr(instance, cache_attr))
            except AttributeError:
                # Cache slot exists but not set, compute and store
                value = fget(instance)
                setattr(instance, cache_attr, value)
        return value

    def __set__(self, instance: Any, value: Any, /) -> None:
        """Set the attribute value and invalidate cache if enabled."""
        # Delete the cached value so it can be recomputed on next access.
        if self._cached:
            cache_attr = self._cache_attr
            try:
                instance.__dict__.pop(cache_attr, None)
            except AttributeError:
                # Object uses __slots__, reset slot to unset state
                with contextlib.suppress(AttributeError):
                    delattr(instance, cache_attr)

        if self.fset is None:
            raise AttributeError("can't set attribute")  # i18n-exc: ignore
        self.fset(instance, value)

    def __set_name__(self, owner: type, name: str) -> None:
        """Validate cache slot exists when class is defined."""
        if not self._cached:
            return

        # Collect all slots from the class hierarchy
        all_slots: set[str] = set()
        has_dict = False

        for cls in owner.__mro__:
            if cls is object:
                continue
            if (cls_slots := getattr(cls, "__slots__", None)) is None:
                # Class without __slots__ has __dict__
                has_dict = True
                continue
            if isinstance(cls_slots, str):
                all_slots.add(cls_slots)
            else:
                all_slots.update(cls_slots)
            if "__dict__" in all_slots:
                has_dict = True

        # If class has __dict__, caching works via instance.__dict__
        if has_dict:
            return

        # Check if cache slot exists in any class in the hierarchy
        if (cache_attr := self._cache_attr) not in all_slots:
            msg = f"Class {owner.__name__} uses __slots__ but is missing cache slot '{cache_attr}' required by @hm_property(cached=True) on '{name}'"
            raise TypeError(msg)  # i18n-exc: ignore

    def deleter(self, fdel: Callable[[Any], None], /) -> _GenericProperty[GETTER, SETTER]:
        """Return generic deleter."""
        return type(self)(
            fget=self.fget,
            fset=self.fset,
            fdel=fdel,
            doc=self.__doc__,
            cached=self._cached,
            log_context=self.log_context,
        )

    def getter(self, fget: Callable[[Any], GETTER], /) -> _GenericProperty[GETTER, SETTER]:
        """Return generic getter."""
        return type(self)(
            fget=fget,
            fset=self.fset,
            fdel=self.fdel,
            doc=self.__doc__,
            cached=self._cached,
            log_context=self.log_context,
        )

    def setter(self, fset: Callable[[Any, SETTER], None], /) -> _GenericProperty[GETTER, SETTER]:
        """Return generic setter."""
        return type(self)(
            fget=self.fget,
            fset=fset,
            fdel=self.fdel,
            doc=self.__doc__,
            cached=self._cached,
            log_context=self.log_context,
        )


# ----- hm_property -----


@overload
def hm_property[PR](func: Callable[[Any], PR], /) -> _GenericProperty[PR, Any]: ...  # kwonly: disable


@overload
def hm_property(  # kwonly: disable
    *, cached: bool = ..., log_context: bool = ...
) -> Callable[[Callable[[Any], R]], _GenericProperty[R, Any]]: ...


def hm_property[PR](  # kwonly: disable
    func: Callable[[Any], PR] | None = None,
    *,
    cached: bool = False,
    log_context: bool = False,
) -> _GenericProperty[PR, Any] | Callable[[Callable[[Any], PR]], _GenericProperty[PR, Any]]:
    """
    Decorate a method as a computed attribute.

    Supports both usages:
    - @hm_property
    - @hm_property(cached=True, log_context=True)

    Args:
        func: The function being decorated when used as @hm_property without
            parentheses. When used as a factory (i.e., @hm_property(...)), this
            is None and the returned callable expects the function to decorate.
        cached: Optionally enable per-instance caching for this property.
        log_context: Include this property in structured log context if True.

    """
    if func is None:

        def wrapper(f: Callable[[Any], PR]) -> _GenericProperty[PR, Any]:
            return _GenericProperty(f, cached=cached, log_context=log_context)

        return wrapper
    return _GenericProperty(func, cached=cached, log_context=log_context)


# ----------


# Cache for per-class descriptor names to avoid repeated dir() scans.
# Use WeakKeyDictionary to allow classes to be garbage-collected without leaking cache entries.
_PUBLIC_ATTR_CACHE: WeakKeyDictionary[type, tuple[str, ...]] = WeakKeyDictionary()


def _get_hm_property_names(*, cls: type) -> tuple[str, ...]:
    """Return (and cache) the names of all hm_property/DelegatedProperty descriptors on a class."""
    if (cached := _PUBLIC_ATTR_CACHE.get(cls)) is not None:
        return cached

    names = tuple(y for y in dir(cls) if isinstance(getattr(cls, y, None), _GenericProperty | DelegatedProperty))
    _PUBLIC_ATTR_CACHE[cls] = names
    return names


def get_hm_property_names(*, data_object: Any) -> tuple[str, ...]:
    """
    Return the names of all hm_property/DelegatedProperty descriptors on the object's class.

    Args:
        data_object: The instance whose class is inspected for decorated properties.

    Returns:
        tuple[str, ...]: Attribute names of every property declared via hm_property or
        DelegatedProperty on the class (own and inherited), in dir() order.

    Notes:
        Attribute NAMES are cached per class to avoid repeated dir() scans. This does not
        touch the getters; callers that need to exercise every getter should call getattr()
        for each returned name themselves.

    """
    return _get_hm_property_names(cls=data_object.__class__)


@singledispatch
def _get_text_value(value: Any) -> Any:  # kwonly: disable
    """
    Normalize values for logging purposes.

    Uses singledispatch for type-based conversion. Register new type handlers
    with @_get_text_value.register(YourType).

    Default behavior (unregistered types):
        Returns value unchanged.

    Registered conversions:
        - list/tuple/set → tuple (items normalized recursively)
        - Enum → str representation
        - datetime → unix timestamp (float)

    Args:
        value: The input value to normalize into a log-/JSON-friendly representation.

    Returns:
        The normalized value, potentially converted as described above.

    """
    return value


@_get_text_value.register(list)
@_get_text_value.register(tuple)
@_get_text_value.register(set)
def _get_text_value_sequence(value: list[Any] | tuple[Any, ...] | set[Any]) -> tuple[Any, ...]:  # kwonly: disable
    """Convert sequence types to tuple with normalized items."""
    return tuple(_get_text_value(v) for v in value)


@_get_text_value.register(Enum)
def _get_text_value_enum(value: Enum) -> str:  # kwonly: disable
    """Convert Enum to string representation."""
    return str(value)


@_get_text_value.register(datetime)
def _get_text_value_datetime(value: datetime) -> float:  # kwonly: disable
    """Convert datetime to unix timestamp."""
    return datetime.timestamp(value)


def _get_text_value_with_dataclass_fallback(*, value: Any) -> Any:
    """Normalize value, converting dataclass instances to dicts."""
    result = _get_text_value(value)
    # If singledispatch returned unchanged and it's a dataclass, convert to dict
    if result is value and dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: _get_text_value(v) for k, v in dataclasses.asdict(value).items()}
    return result


def get_hm_property_by_log_context(*, data_object: Any) -> Mapping[str, Any]:
    """
    Return combined log context attributes for an object.

    Includes only properties declared with log_context=True and flattens values that
    implement LogContextProtocol by prefixing with a short key.

    Args:
        data_object: The instance from which to collect attributes marked for log context.

    Returns:
        Mapping[str, Any]: A mapping of attribute name to normalized value for logging.

    Notes:
        Getter exceptions are swallowed and represented as None so log context collection
        remains robust and side-effect free.

    """
    cls = data_object.__class__
    result: dict[str, Any] = {}
    for name in _get_hm_property_names(cls=cls):
        if getattr(cls, name).log_context is False:
            continue
        try:
            value = getattr(data_object, name)
            if isinstance(value, LogContextProtocol):
                result.update({f"{name[:1]}.{k}": v for k, v in value.log_context.items()})
            else:
                result[name] = _get_text_value_with_dataclass_fallback(value=value)
        except Exception:  # noqa: BLE001 - log context collection must never fail; getters may have arbitrary side effects
            result[name] = None
    return result
