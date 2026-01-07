"""
Validation and normalization schemas for API data structures.

Uses voluptuous to validate and normalize data received from Homematic backends.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

import voluptuous as vol

if TYPE_CHECKING:
    from aiohomematic.const import DeviceDescription, ParameterData

_LOGGER: Final = logging.getLogger(__name__)

# ============================================================================
# DeviceDescription Schema
# ============================================================================


def _normalize_children(*, value: Any) -> list[str]:
    """Normalize CHILDREN field to always be a list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [] if value == "" else [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _normalize_paramsets(*, value: Any) -> list[str]:
    """Normalize PARAMSETS field to always be a list."""
    if value is None:
        return ["MASTER", "VALUES"]
    if isinstance(value, (list, tuple)):
        return list(value)
    return ["MASTER", "VALUES"]


DEVICE_DESCRIPTION_SCHEMA = vol.Schema(
    {
        # Required fields per API spec
        vol.Required("TYPE"): vol.Coerce(str),
        vol.Required("ADDRESS"): vol.Coerce(str),
        vol.Required("PARAMSETS", default=["MASTER", "VALUES"]): lambda x: _normalize_paramsets(value=x),
        # Optional fields with normalization
        vol.Optional("CHILDREN", default=[]): lambda x: _normalize_children(value=x),
        vol.Optional("PARENT"): vol.Any(None, str),
        vol.Optional("PARENT_TYPE"): vol.Any(None, str),
        vol.Optional("SUBTYPE"): vol.Any(None, str),
        vol.Optional("FIRMWARE"): vol.Any(None, str),
        vol.Optional("AVAILABLE_FIRMWARE"): vol.Any(None, str),
        vol.Optional("UPDATABLE"): vol.Coerce(bool),
        vol.Optional("FIRMWARE_UPDATE_STATE"): vol.Any(None, str),
        vol.Optional("FIRMWARE_UPDATABLE"): vol.Any(None, bool),
        vol.Optional("INTERFACE"): vol.Any(None, str),
        # Per API spec: RX_MODE is Integer (bitmask)
        vol.Optional("RX_MODE"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("LINK_SOURCE_ROLES"): vol.Any(None, str),
        vol.Optional("LINK_TARGET_ROLES"): vol.Any(None, str),
        # Additional fields from spec (currently commented in const.py)
        vol.Optional("RF_ADDRESS"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("INDEX"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("AES_ACTIVE"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("VERSION"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("FLAGS"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("DIRECTION"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("GROUP"): vol.Any(None, str),
        vol.Optional("TEAM"): vol.Any(None, str),
        vol.Optional("TEAM_TAG"): vol.Any(None, str),
        vol.Optional("TEAM_CHANNELS"): vol.Any(None, list),
        vol.Optional("ROAMING"): vol.Any(None, vol.Coerce(int)),
    },
    extra=vol.ALLOW_EXTRA,  # Allow backend-specific extra fields
)


# ============================================================================
# ParameterData Schema (ParameterDescription in API)
# ============================================================================

# Parameter TYPE values per API spec
VALID_PARAMETER_TYPES = {
    "FLOAT",
    "INTEGER",
    "BOOL",
    "ENUM",
    "STRING",
    "ACTION",
    # Additional types found in practice
    "DUMMY",
    "",
}


def _normalize_parameter_type(*, value: Any) -> str:
    """Normalize and validate parameter TYPE field."""
    if value is None:
        return ""
    str_val = str(value).upper()
    return str_val if str_val in VALID_PARAMETER_TYPES else ""


def _normalize_operations(*, value: Any) -> int:
    """Normalize OPERATIONS to integer bitmask."""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _normalize_flags(*, value: Any) -> int:
    """Normalize FLAGS to integer bitmask."""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _normalize_value_list(*, value: Any) -> list[str]:
    """Normalize VALUE_LIST to list of strings."""
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        return []
    # Convert all items to strings
    return [str(item) for item in value]


PARAMETER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional("TYPE"): lambda x: _normalize_parameter_type(value=x),
        vol.Optional("OPERATIONS", default=0): lambda x: _normalize_operations(value=x),
        vol.Optional("FLAGS", default=0): lambda x: _normalize_flags(value=x),
        vol.Optional("DEFAULT"): vol.Any(None, str, int, float, bool),
        vol.Optional("MAX"): vol.Any(None, str, int, float),
        vol.Optional("MIN"): vol.Any(None, str, int, float),
        vol.Optional("UNIT"): vol.Any(None, str),
        vol.Optional("ID"): vol.Any(None, str),
        # Per API spec: TAB_ORDER is Integer (display ordering)
        vol.Optional("TAB_ORDER"): vol.Any(None, vol.Coerce(int)),
        # Per API spec: CONTROL is String (UI hint)
        vol.Optional("CONTROL"): vol.Any(None, str),
        # Per API spec: VALUE_LIST is Array of String (for ENUM type)
        vol.Optional("VALUE_LIST", default=[]): lambda x: _normalize_value_list(value=x),
        # Per API spec: SPECIAL is Array of Struct {ID: String, VALUE: <TYPE>}
        # In practice: Dict with special value IDs as keys (e.g., {"NOT_USED": 111600.0})
        vol.Optional("SPECIAL"): vol.Any(None, list, dict),
    },
    extra=vol.ALLOW_EXTRA,
)


# ============================================================================
# ParamsetDescription Schema
# ============================================================================


def normalize_paramset_description(
    *,
    paramset: dict[str, Any] | None,
) -> dict[str, ParameterData]:
    """
    Normalize a paramset description dict.

    A ParamsetDescription is a Struct where each key is a parameter name
    and each value is a ParameterDescription (ParameterData).
    """
    if paramset is None:
        return {}
    result: dict[str, ParameterData] = {}
    for param_name, param_data in paramset.items():
        try:
            result[param_name] = PARAMETER_DATA_SCHEMA(param_data)
        except vol.Invalid as err:
            # Log validation failures for debugging
            _LOGGER.debug(
                "Parameter validation failed for %s: %s. Using raw data.",
                param_name,
                err,
            )
            # Keep original data if validation fails
            result[param_name] = param_data
    return result


# ============================================================================
# Public API
# ============================================================================


def normalize_device_description(*, device_description: dict[str, Any] | DeviceDescription) -> DeviceDescription:
    """
    Normalize a device description dict.

    Should be called at all ingestion points:
    - After receiving from list_devices()
    - After receiving from get_device_description()
    - After receiving from newDevices() callback
    - After loading from cache

    Args:
        device_description: Raw device description from backend or cache.

    Returns:
        Normalized DeviceDescription dict with guaranteed field types.

    """
    try:
        return dict(DEVICE_DESCRIPTION_SCHEMA(device_description))  # type: ignore[return-value]
    except vol.Invalid as err:
        # Log validation failures for debugging
        address = device_description.get("ADDRESS", "UNKNOWN")
        _LOGGER.debug(
            "Device description validation failed for %s: %s. Applying fallback normalization.",
            address,
            err,
        )
        # On validation failure, at minimum ensure CHILDREN is a list
        result = dict(device_description)
        children = result.get("CHILDREN")
        if children is None or isinstance(children, str):
            result["CHILDREN"] = []
        return result  # type: ignore[return-value]


def normalize_parameter_data(*, parameter_data: dict[str, Any]) -> ParameterData:
    """
    Normalize a parameter data dict (ParameterDescription).

    Args:
        parameter_data: Raw parameter data from backend or cache.

    Returns:
        Normalized ParameterData dict with guaranteed field types.

    """
    try:
        return dict(PARAMETER_DATA_SCHEMA(parameter_data))  # type: ignore[return-value]
    except vol.Invalid as err:
        # Log validation failures for debugging
        param_id = parameter_data.get("ID", "UNKNOWN")
        _LOGGER.debug(
            "Parameter data validation failed for %s: %s. Using raw data.",
            param_id,
            err,
        )
        return dict(parameter_data)  # type: ignore[return-value]
