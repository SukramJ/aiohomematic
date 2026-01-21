"""
Pydantic model for device descriptions from RPC responses.

This module validates and normalizes DeviceDescription data received
from Homematic backends via listDevices() and newDevices() callbacks.
"""

from __future__ import annotations

# Pydantic field_validators require a fixed signature (cls, v) that cannot use keyword-only args
__kwonly_check__ = False

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from aiohomematic.const import DeviceDescription


class DeviceDescriptionModel(BaseModel):
    """
    Pydantic model for device description from RPC listDevices().

    This model validates and normalizes device descriptions received from
    the Homematic backend. Handles both device and channel descriptions.

    Based on HM_XmlRpc_API.pdf V2.16 and HMIP_XmlRpc_API_Addendum.pdf V2.10.
    """

    # Required fields
    type: str = Field(..., validation_alias="TYPE")
    address: str = Field(..., validation_alias="ADDRESS")

    # Paramsets (always present, but may be empty)
    paramsets: list[str] = Field(
        default_factory=lambda: ["MASTER", "VALUES"],
        validation_alias="PARAMSETS",
    )

    # Parent/child relationships
    children: list[str] = Field(default_factory=list, validation_alias="CHILDREN")
    parent: str | None = Field(default=None, validation_alias="PARENT")
    parent_type: str | None = Field(default=None, validation_alias="PARENT_TYPE")

    # Device metadata
    subtype: str | None = Field(default=None, validation_alias="SUBTYPE")
    interface: str | None = Field(default=None, validation_alias="INTERFACE")
    index: int | None = Field(default=None, validation_alias="INDEX")
    version: int | None = Field(default=None, validation_alias="VERSION")
    flags: int | None = Field(default=None, validation_alias="FLAGS")
    direction: int | None = Field(default=None, validation_alias="DIRECTION")

    # Firmware information
    firmware: str | None = Field(default=None, validation_alias="FIRMWARE")
    available_firmware: str | None = Field(
        default=None,
        validation_alias="AVAILABLE_FIRMWARE",
    )
    updatable: bool = Field(default=False, validation_alias="UPDATABLE")
    firmware_update_state: str | None = Field(
        default=None,
        validation_alias="FIRMWARE_UPDATE_STATE",
    )
    firmware_updatable: bool | None = Field(
        default=None,
        validation_alias="FIRMWARE_UPDATABLE",
    )

    # RF/connectivity
    rf_address: int | None = Field(default=None, validation_alias="RF_ADDRESS")
    rx_mode: int | None = Field(default=None, validation_alias="RX_MODE")
    aes_active: int | None = Field(default=None, validation_alias="AES_ACTIVE")
    roaming: int | None = Field(default=None, validation_alias="ROAMING")

    # Link roles
    link_source_roles: str | None = Field(
        default=None,
        validation_alias="LINK_SOURCE_ROLES",
    )
    link_target_roles: str | None = Field(
        default=None,
        validation_alias="LINK_TARGET_ROLES",
    )

    # Group/team
    group: str | None = Field(default=None, validation_alias="GROUP")
    team: str | None = Field(default=None, validation_alias="TEAM")
    team_tag: str | None = Field(default=None, validation_alias="TEAM_TAG")
    team_channels: list[str] | None = Field(
        default=None,
        validation_alias="TEAM_CHANNELS",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )

    @field_validator(
        "index",
        "version",
        "flags",
        "direction",
        "rf_address",
        "rx_mode",
        "aes_active",
        "roaming",
        mode="before",
    )
    @classmethod
    def normalize_optional_ints(cls, v: Any) -> int | None:
        """Coerce optional integer fields."""
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @field_validator("children", "paramsets", mode="before")
    @classmethod
    def normalize_string_lists(cls, v: Any) -> list[str]:
        """Normalize lists that may come as None, string, or list."""
        if v is None:
            return []
        if isinstance(v, str):
            return [] if not v else [v]
        if isinstance(v, (list, tuple)):
            return list(v)
        return []

    @field_validator("team_channels", mode="before")
    @classmethod
    def normalize_team_channels(cls, v: Any) -> list[str] | None:
        """Normalize team_channels (can be None)."""
        if v is None:
            return None
        if isinstance(v, str):
            return [v] if v else None
        if isinstance(v, (list, tuple)):
            return list(v) if v else None
        return None

    @field_validator("updatable", mode="before")
    @classmethod
    def normalize_updatable(cls, v: Any) -> bool:
        """Coerce updatable to bool."""
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return False

    @property
    def channel_no(self) -> int | None:
        """Extract channel number from address if this is a channel."""
        if not self.is_channel:
            return None
        if ":" in self.address:
            try:
                return int(self.address.split(":")[1])
            except (IndexError, ValueError):
                return None
        return None

    @property
    def is_channel(self) -> bool:
        """Return True if this is a channel."""
        return self.parent is not None

    @property
    def is_device(self) -> bool:
        """Return True if this is a device (not a channel)."""
        return self.parent is None

    def to_dict(self) -> DeviceDescription:
        """
        Convert to DeviceDescription TypedDict format.

        Returns dict with uppercase keys matching Homematic API format.
        """
        result: dict[str, Any] = {
            "TYPE": self.type,
            "ADDRESS": self.address,
            "PARAMSETS": self.paramsets,
            "CHILDREN": self.children,
        }

        # Add optional fields only if they have values
        if self.parent is not None:
            result["PARENT"] = self.parent
        if self.parent_type is not None:
            result["PARENT_TYPE"] = self.parent_type
        if self.subtype is not None:
            result["SUBTYPE"] = self.subtype
        if self.interface is not None:
            result["INTERFACE"] = self.interface
        if self.index is not None:
            result["INDEX"] = self.index
        if self.version is not None:
            result["VERSION"] = self.version
        if self.flags is not None:
            result["FLAGS"] = self.flags
        if self.direction is not None:
            result["DIRECTION"] = self.direction
        if self.firmware is not None:
            result["FIRMWARE"] = self.firmware
        if self.available_firmware is not None:
            result["AVAILABLE_FIRMWARE"] = self.available_firmware
        if self.updatable:
            result["UPDATABLE"] = self.updatable
        if self.firmware_update_state is not None:
            result["FIRMWARE_UPDATE_STATE"] = self.firmware_update_state
        if self.firmware_updatable is not None:
            result["FIRMWARE_UPDATABLE"] = self.firmware_updatable
        if self.rf_address is not None:
            result["RF_ADDRESS"] = self.rf_address
        if self.rx_mode is not None:
            result["RX_MODE"] = self.rx_mode
        if self.aes_active is not None:
            result["AES_ACTIVE"] = self.aes_active
        if self.roaming is not None:
            result["ROAMING"] = self.roaming
        if self.link_source_roles is not None:
            result["LINK_SOURCE_ROLES"] = self.link_source_roles
        if self.link_target_roles is not None:
            result["LINK_TARGET_ROLES"] = self.link_target_roles
        if self.group is not None:
            result["GROUP"] = self.group
        if self.team is not None:
            result["TEAM"] = self.team
        if self.team_tag is not None:
            result["TEAM_TAG"] = self.team_tag
        if self.team_channels is not None:
            result["TEAM_CHANNELS"] = self.team_channels

        # Include any extra fields from the model
        if self.model_extra:
            result |= self.model_extra

        return result  # type: ignore[return-value]
