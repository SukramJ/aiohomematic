"""
Pydantic validation schemas for Homematic API data structures.

This package provides runtime validation and normalization of data received
from Homematic backends (CCU, Homegear) via XML-RPC and JSON-RPC.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiohomematic.schemas.device_description import DeviceDescriptionModel
from aiohomematic.schemas.parameter_description import ParameterDataModel

if TYPE_CHECKING:
    from aiohomematic.const import DeviceDescription, ParameterData

__all__ = [
    "DeviceDescriptionModel",
    "ParameterDataModel",
    "normalize_device_description",
    "normalize_parameter_data",
    "normalize_paramset_description",
]


def normalize_device_description(
    *,
    device_description: dict[str, Any] | DeviceDescription,
) -> DeviceDescription:
    """
    Validate and normalize a device description from RPC response.

    Should be called at all ingestion points:
    - After receiving from list_devices()
    - After receiving from get_device_description()
    - After receiving from newDevices() callback
    - After loading from cache

    Args:
        device_description: Raw device description from backend or cache.

    Returns:
        Normalized DeviceDescription dict with guaranteed field types.

    Raises:
        ValidationError: If required fields are missing or invalid.

    """
    model = DeviceDescriptionModel.model_validate(device_description)
    return model.to_dict()


def normalize_parameter_data(
    *,
    parameter_data: dict[str, Any],
) -> ParameterData:
    """
    Validate and normalize parameter data from RPC response.

    Args:
        parameter_data: Raw parameter data from backend or cache.

    Returns:
        Normalized ParameterData dict with guaranteed field types.

    Raises:
        ValidationError: If validation fails.

    """
    model = ParameterDataModel.model_validate(parameter_data)
    return model.to_dict()


def normalize_paramset_description(
    *,
    paramset: dict[str, Any] | None,
) -> dict[str, ParameterData]:
    """
    Validate and normalize a paramset description dict.

    A ParamsetDescription is a Struct where each key is a parameter name
    and each value is a ParameterDescription (ParameterData).

    Args:
        paramset: Raw paramset description from backend or cache.

    Returns:
        Dictionary mapping parameter names to normalized ParameterData.

    Raises:
        ValidationError: If validation fails for any parameter.

    """
    if paramset is None:
        return {}
    result: dict[str, ParameterData] = {}
    for param_name, param_data in paramset.items():
        model = ParameterDataModel.model_validate(param_data)
        result[param_name] = model.to_dict()
    return result
