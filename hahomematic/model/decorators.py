"""Decorators for data points used within hahomematic."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any, ParamSpec, TypeVar

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
class generic_property[_GETTER, _SETTER](property):
    """Generic property implementation."""

    fget: Callable[[Any], _GETTER] | None
    fset: Callable[[Any, _SETTER], None] | None
    fdel: Callable[[Any], None] | None

    def __init__(
        self,
        fget: Callable[[Any], _GETTER] | None = None,
        fset: Callable[[Any, _SETTER], None] | None = None,
        fdel: Callable[[Any], None] | None = None,
        doc: str | None = None,
    ) -> None:
        """Init the generic property."""
        super().__init__(fget, fset, fdel, doc)
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

    def getter(self, fget: Callable[[Any], _GETTER], /) -> generic_property:
        """Return generic getter."""
        return type(self)(fget, self.fset, self.fdel, self.__doc__)  # pragma: no cover

    def setter(self, fset: Callable[[Any, _SETTER], None], /) -> generic_property:
        """Return generic setter."""
        return type(self)(self.fget, fset, self.fdel, self.__doc__)

    def deleter(self, fdel: Callable[[Any], None], /) -> generic_property:
        """Return generic deleter."""
        return type(self)(self.fget, self.fset, fdel, self.__doc__)

    def __get__(self, obj: Any, gtype: type | None = None, /) -> _GETTER:
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
class config_property[_GETTER, _SETTER](generic_property[_GETTER, _SETTER]):
    """Decorate to mark own config properties."""


# pylint: disable=invalid-name
class info_property[_GETTER, _SETTER](generic_property[_GETTER, _SETTER]):
    """Decorate to mark own info properties."""


# pylint: disable=invalid-name
class state_property[_GETTER, _SETTER](generic_property[_GETTER, _SETTER]):
    """Decorate to mark own value properties."""


def _get_public_attributes_by_class_decorator(data_object: Any, class_decorator: type) -> dict[str, Any]:
    """Return the object attributes by decorator."""
    pub_attributes = [
        y
        for y in dir(data_object.__class__)
        if not y.startswith("_") and isinstance(getattr(data_object.__class__, y), class_decorator)
    ]
    return {x: _get_text_value(getattr(data_object, x)) for x in pub_attributes}


def _get_text_value(value: Any) -> Any:
    """Convert value to text."""
    if isinstance(value, (list, tuple, set)):
        return tuple(_get_text_value(v) for v in value)
    if isinstance(value, Enum):
        return str(value)
    if isinstance(value, datetime):
        return datetime.timestamp(value)
    return value


def get_public_attributes_for_config_property(data_object: Any) -> dict[str, Any]:
    """Return the object attributes by decorator config_property."""
    return _get_public_attributes_by_class_decorator(data_object=data_object, class_decorator=config_property)


def get_public_attributes_for_info_property(data_object: Any) -> dict[str, Any]:
    """Return the object attributes by decorator info_property."""
    return _get_public_attributes_by_class_decorator(data_object=data_object, class_decorator=info_property)


def get_public_attributes_for_state_property(data_object: Any) -> dict[str, Any]:
    """Return the object attributes by decorator state_property."""
    return _get_public_attributes_by_class_decorator(data_object=data_object, class_decorator=state_property)
