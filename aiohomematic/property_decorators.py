# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Decorators and helpers for declaring public attributes on data point classes.

This module provides four decorator factories that behave like the built-in
@property, but additionally annotate properties with a semantic category so they
can be automatically collected to build payloads and log contexts:
- config_property: configuration-related properties.
- info_property: informational/metadata properties.
- state_property: dynamic state properties.
- hm_property: can be used to mark log_context or cached, where the other properties don't match

All decorators accept an optional keyword-only argument log_context. If set to
True, the property will be included in the LogContextMixin.log_context mapping.

Notes on caching
- Marked with cached=True always store on first access and invalidates on set/delete.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import contextlib
from datetime import datetime
from enum import Enum, StrEnum
from functools import singledispatch
from typing import Any, Final, ParamSpec, Self, TypeVar, cast, overload
from weakref import WeakKeyDictionary

__all__ = [
    "DelegatedProperty",
    "Kind",
    "_GenericProperty",
    "config_property",
    "get_hm_property_by_kind",
    "hm_property",
    "info_property",
    "state_property",
]

P = ParamSpec("P")
T = TypeVar("T")
R = TypeVar("R")


class Kind(StrEnum):
    """Enum for property feature flags."""

    CONFIG = "config"
    INFO = "info"
    SIMPLE = "simple"
    STATE = "state"


class DelegatedProperty[ValueT]:
    """
    Descriptor that delegates property access to a nested attribute path.

    This descriptor simplifies forwarding properties that just return an
    attribute from a nested object, eliminating boilerplate. It behaves
    like a read-only @property and can be overridden by subclasses.

    Supports the same features as the other property decorators:
    - kind: Categorize as config/info/state/simple for get_hm_property_by_kind()
    - cached: Cache the delegated value on first access
    - log_context: Include in structured log context

    Usage:
        # Simple delegation:
        interface: Final = DelegatedProperty[Interface](path="_config.interface")

        # With caching and kind:
        state: Final = DelegatedProperty[ClientState](
            path="_state_machine.state",
            kind=Kind.STATE,
            cached=True,
        )

        # With log_context:
        interface_id: Final = DelegatedProperty[str](
            path="_config.interface_id",
            kind=Kind.INFO,
            log_context=True,
        )

    Note:
        Do NOT use type annotations on the left side like `interface: Interface = ...`
        as this confuses mypy. The generic type parameter provides type information.

    """

    __slots__ = ("_cache_attr", "_cached", "_doc", "_parts", "_path", "kind", "log_context")

    __kwonly_check__ = False

    def __init__(
        self,
        *,
        path: str,
        doc: str | None = None,
        kind: Kind = Kind.SIMPLE,
        cached: bool = False,
        log_context: bool = False,
    ) -> None:
        """
        Initialize the delegated property descriptor.

        Args:
            path: Dot-separated attribute path (e.g., "_config.interface").
            doc: Optional docstring for the property.
            kind: Categorize as config/info/state/simple.
            cached: Enable per-instance caching of the delegated value.
            log_context: Include this property in structured log context if True.

        """
        self._path: Final = path
        self._parts: Final = tuple(path.split("."))
        self._doc = doc
        self.kind: Final = kind
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
    Base descriptor used by all property decorators in this module.

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
        kind: Kind = Kind.SIMPLE,
        cached: bool = False,
        log_context: bool = False,
    ) -> None:
        """
        Initialize the descriptor.

        Mirrors the standard property signature and adds two options:
        - kind: specify the kind of property (e.g. simple, cached, config, info, state).
        - cached: enable per-instance caching of the computed value.
        - log_context: mark this property as relevant for structured logging.
        """
        super().__init__(fget, fset, fdel, doc)
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc
        self.kind: Final = kind
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
            kind=self.kind,
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
            kind=self.kind,
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
            kind=self.kind,
            cached=self._cached,
            log_context=self.log_context,
        )


# ----- hm_property -----


@overload
def hm_property[PR](func: Callable[[Any], PR], /) -> _GenericProperty[PR, Any]: ...  # kwonly: disable


@overload
def hm_property(  # kwonly: disable
    *, kind: Kind = ..., cached: bool = ..., log_context: bool = ...
) -> Callable[[Callable[[Any], R]], _GenericProperty[R, Any]]: ...


def hm_property[PR](  # kwonly: disable
    func: Callable[[Any], PR] | None = None,
    *,
    kind: Kind = Kind.SIMPLE,
    cached: bool = False,
    log_context: bool = False,
) -> _GenericProperty[PR, Any] | Callable[[Callable[[Any], PR]], _GenericProperty[PR, Any]]:
    """
    Decorate a method as a computed attribute.

    Supports both usages:
    - @hm_property
    - @hm_property(kind=..., cached=True, log_context=True)

    Args:
        func: The function being decorated when used as @hm_property without
            parentheses. When used as a factory (i.e., @hm_property(...)), this
            is None and the returned callable expects the function to decorate.
        kind: Specify the kind of property (e.g. simple, config, info, state).
        cached: Optionally enable per-instance caching for this property.
        log_context: Include this property in structured log context if True.

    """
    if func is None:

        def wrapper(f: Callable[[Any], PR]) -> _GenericProperty[PR, Any]:
            return _GenericProperty(f, kind=kind, cached=cached, log_context=log_context)

        return wrapper
    return _GenericProperty(func, kind=kind, cached=cached, log_context=log_context)


# ----- config_property -----


@overload
def config_property[PR](func: Callable[[Any], PR], /) -> _GenericProperty[PR, Any]: ...  # kwonly: disable


@overload
def config_property(  # kwonly: disable
    *, cached: bool = ..., log_context: bool = ...
) -> Callable[[Callable[[Any], R]], _GenericProperty[R, Any]]: ...


def config_property[PR](  # kwonly: disable
    func: Callable[[Any], PR] | None = None,
    *,
    cached: bool = False,
    log_context: bool = False,
) -> _GenericProperty[PR, Any] | Callable[[Callable[[Any], PR]], _GenericProperty[PR, Any]]:
    """
    Decorate a method as a configuration property.

    Supports both usages:
    - @config_property
    - @config_property(cached=True, log_context=True)

    Args:
        func: The function being decorated when used as @config_property without
            parentheses. When used as a factory (i.e., @config_property(...)), this is
            None and the returned callable expects the function to decorate.
        cached: Enable per-instance caching for this property when True.
        log_context: Include this property in structured log context if True.

    """
    if func is None:

        def wrapper(f: Callable[[Any], PR]) -> _GenericProperty[PR, Any]:
            return _GenericProperty(f, kind=Kind.CONFIG, cached=cached, log_context=log_context)

        return wrapper
    return _GenericProperty(func, kind=Kind.CONFIG, cached=cached, log_context=log_context)


# ----- info_property -----


@overload
def info_property[PR](func: Callable[[Any], PR], /) -> _GenericProperty[PR, Any]: ...  # kwonly: disable


@overload
def info_property(  # kwonly: disable
    *, cached: bool = ..., log_context: bool = ...
) -> Callable[[Callable[[Any], R]], _GenericProperty[R, Any]]: ...


def info_property[PR](  # kwonly: disable
    func: Callable[[Any], PR] | None = None,
    *,
    cached: bool = False,
    log_context: bool = False,
) -> _GenericProperty[PR, Any] | Callable[[Callable[[Any], PR]], _GenericProperty[PR, Any]]:
    """
    Decorate a method as an informational/metadata property.

    Supports both usages:
    - @info_property
    - @info_property(cached=True, log_context=True)

    Args:
        func: The function being decorated when used as @info_property without
            parentheses. When used as a factory (i.e., @info_property(...)), this is
            None and the returned callable expects the function to decorate.
        cached: Enable per-instance caching for this property when True.
        log_context: Include this property in structured log context if True.

    """
    if func is None:

        def wrapper(f: Callable[[Any], PR]) -> _GenericProperty[PR, Any]:
            return _GenericProperty(f, kind=Kind.INFO, cached=cached, log_context=log_context)

        return wrapper
    return _GenericProperty(func, kind=Kind.INFO, cached=cached, log_context=log_context)


# ----- state_property -----


@overload
def state_property[PR](func: Callable[[Any], PR], /) -> _GenericProperty[PR, Any]: ...  # kwonly: disable


@overload
def state_property(  # kwonly: disable
    *, cached: bool = ..., log_context: bool = ...
) -> Callable[[Callable[[Any], R]], _GenericProperty[R, Any]]: ...


def state_property[PR](  # kwonly: disable
    func: Callable[[Any], PR] | None = None,
    *,
    cached: bool = False,
    log_context: bool = False,
) -> _GenericProperty[PR, Any] | Callable[[Callable[[Any], PR]], _GenericProperty[PR, Any]]:
    """
    Decorate a method as a dynamic state property.

    Supports both usages:
    - @state_property
    - @state_property(cached=True, log_context=True)

    Args:
        func: The function being decorated when used as @state_property without
            parentheses. When used as a factory (i.e., @state_property(...)), this is
            None and the returned callable expects the function to decorate.
        cached: Enable per-instance caching for this property when True.
        log_context: Include this property in structured log context if True.

    """
    if func is None:

        def wrapper(f: Callable[[Any], PR]) -> _GenericProperty[PR, Any]:
            return _GenericProperty(f, kind=Kind.STATE, cached=cached, log_context=log_context)

        return wrapper
    return _GenericProperty(func, kind=Kind.STATE, cached=cached, log_context=log_context)


# ----------


# Cache for per-class attribute names by decorator to avoid repeated dir() scans
# Use WeakKeyDictionary to allow classes to be garbage-collected without leaking cache entries.
# Structure: {cls: {decorator_class: (attr_name1, attr_name2, ...)}}
_PUBLIC_ATTR_CACHE: WeakKeyDictionary[type, dict[Kind, tuple[str, ...]]] = WeakKeyDictionary()


def get_hm_property_by_kind(*, data_object: Any, kind: Kind, context: bool = False) -> Mapping[str, Any]:
    """
    Collect properties from an object that are defined using a specific decorator.

    Args:
        data_object: The instance to inspect.
        kind: The decorator class to use for filtering.
        context: If True, only include properties where the descriptor has
            log_context=True. When such a property's value is a LogContextMixin, its
            items are flattened into the result using a short prefix of the property
            name (e.g. "p.key").

    Returns:
        Mapping[str, Any]: A mapping of attribute name to normalized value. Values are converted via
        _get_text_value() to provide stable JSON/log-friendly types.

    Notes:
        Attribute NAMES are cached per (class, decorator) to avoid repeated dir()
        scans. Values are never cached here since they are instance-dependent.
        Getter exceptions are swallowed and represented as None so payload building
        remains robust and side-effect free.

    """
    # Lazy import to avoid circular dependency
    from aiohomematic.support import LogContextMixin  # noqa: PLC0415

    cls = data_object.__class__

    # Get or create the per-class cache dict
    if (decorator_cache := _PUBLIC_ATTR_CACHE.get(cls)) is None:
        decorator_cache = {}
        _PUBLIC_ATTR_CACHE[cls] = decorator_cache

    if (names := decorator_cache.get(kind)) is None:
        names = tuple(
            y
            for y in dir(cls)
            if (gp := getattr(cls, y)) and isinstance(gp, _GenericProperty | DelegatedProperty) and gp.kind == kind
        )
        decorator_cache[kind] = names

    result: dict[str, Any] = {}
    for name in names:
        if context and getattr(cls, name).log_context is False:
            continue
        try:
            value = getattr(data_object, name)
            if isinstance(value, LogContextMixin):
                result.update({f"{name[:1]}.{k}": v for k, v in value.log_context.items()})
            else:
                result[name] = _get_text_value(value)
        except Exception:
            # Avoid propagating side effects/errors from getters
            result[name] = None
    return result


@singledispatch
def _get_text_value(value: Any) -> Any:  # kwonly: disable
    """
    Normalize values for payload/logging purposes.

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


def get_hm_property_by_log_context(*, data_object: Any) -> Mapping[str, Any]:
    """
    Return combined log context attributes across all property categories.

    Includes only properties declared with log_context=True and flattens
    values that implement LogContextMixin by prefixing with a short key.

    Args:
        data_object: The instance from which to collect attributes marked for
            log context across all property categories.

    Returns:
        Mapping[str, Any]: A mapping of attribute name to normalized value for logging.

    """
    result: dict[str, Any] = {}
    for kind in Kind:
        result.update(get_hm_property_by_kind(data_object=data_object, kind=kind, context=True))

    return result
