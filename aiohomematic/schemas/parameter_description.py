"""
Pydantic model for parameter descriptions from RPC responses.

This module validates and normalizes ParameterData (ParameterDescription)
received from Homematic backends via getParamsetDescription().
"""

from __future__ import annotations

# Pydantic field_validators require a fixed signature (cls, v) that cannot use keyword-only args
__kwonly_check__ = False

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from aiohomematic.const import ParameterData

# Parameter TYPE values per Homematic XML-RPC API spec
VALID_PARAMETER_TYPES: frozenset[str] = frozenset(
    {
        "FLOAT",
        "INTEGER",
        "BOOL",
        "ENUM",
        "STRING",
        "ACTION",
        # Additional types found in practice
        "DUMMY",
    }
)


class ParameterDataModel(BaseModel):
    """
    Pydantic model for parameter metadata from RPC getParamsetDescription().

    This model validates and normalizes parameter descriptions received from
    the Homematic backend (CCU/Homegear).
    """

    # Core fields
    type: str = Field(default="", validation_alias="TYPE")
    id: str | None = Field(default=None, validation_alias="ID")

    # Value constraints
    default: Any = Field(default=None, validation_alias="DEFAULT")
    max: Any = Field(default=None, validation_alias="MAX")
    min: Any = Field(default=None, validation_alias="MIN")

    # Flags and operations (bitmasks)
    operations: int = Field(default=0, ge=0, validation_alias="OPERATIONS")
    flags: int = Field(default=0, ge=0, validation_alias="FLAGS")

    # Display metadata
    unit: str | None = Field(default=None, validation_alias="UNIT")
    control: str | None = Field(default=None, validation_alias="CONTROL")
    tab_order: int | None = Field(default=None, validation_alias="TAB_ORDER")

    # Enum values
    value_list: list[str] = Field(
        default_factory=list,
        validation_alias="VALUE_LIST",
    )

    # Special values mapping
    special: dict[str, Any] | list[dict[str, Any]] | None = Field(
        default=None,
        validation_alias="SPECIAL",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )

    @field_validator("operations", "flags", mode="before")
    @classmethod
    def normalize_int_flags(cls, v: Any) -> int:
        """Convert string flags to integer."""
        if v is None:
            return 0
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0

    @field_validator("tab_order", mode="before")
    @classmethod
    def normalize_tab_order(cls, v: Any) -> int | None:
        """Convert tab_order to int if possible."""
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: Any) -> str:
        """Normalize parameter type to uppercase enum value."""
        if v is None:
            return ""
        if isinstance(v, str):
            upper_v = v.upper()
            return upper_v if upper_v in VALID_PARAMETER_TYPES else ""
        return ""

    @field_validator("value_list", mode="before")
    @classmethod
    def normalize_value_list(cls, v: Any) -> list[str]:
        """Ensure value_list is a list of strings."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v else []
        if isinstance(v, (list, tuple)):
            return [str(item) for item in v]
        return []

    @property
    def is_event(self) -> bool:
        """Return True if parameter sends events."""
        return bool(self.operations & 4)

    @property
    def is_readable(self) -> bool:
        """Return True if parameter can be read."""
        return bool(self.operations & 1)

    @property
    def is_writable(self) -> bool:
        """Return True if parameter can be written."""
        return bool(self.operations & 2)

    def to_dict(self) -> ParameterData:
        """
        Convert to ParameterData TypedDict format.

        Returns dict with uppercase keys matching Homematic API format.
        Always includes OPERATIONS and FLAGS as they are essential for parameter handling.
        """
        result: dict[str, Any] = {
            "OPERATIONS": self.operations,
            "FLAGS": self.flags,
        }

        if self.type:
            result["TYPE"] = self.type
        if self.id is not None:
            result["ID"] = self.id
        if self.default is not None:
            result["DEFAULT"] = self.default
        if self.max is not None:
            result["MAX"] = self.max
        if self.min is not None:
            result["MIN"] = self.min
        if self.unit is not None:
            result["UNIT"] = self.unit
        if self.control is not None:
            result["CONTROL"] = self.control
        if self.tab_order is not None:
            result["TAB_ORDER"] = self.tab_order
        if self.value_list:
            result["VALUE_LIST"] = self.value_list
        if self.special is not None:
            result["SPECIAL"] = self.special

        # Include any extra fields from the model
        if self.model_extra:
            result |= self.model_extra

        return result  # type: ignore[return-value]
