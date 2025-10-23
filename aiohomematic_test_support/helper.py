"""Helpers for tests."""

from __future__ import annotations

import importlib.resources
import logging
import os
from typing import Any

import orjson

from aiohomematic.central import CentralUnit
from aiohomematic.const import UTF_8
from aiohomematic.model.custom import CustomDataPoint

_LOGGER = logging.getLogger(__name__)


# pylint: disable=protected-access


def _load_json_file(anchor: str, resource: str, file_name: str) -> Any | None:
    """Load json file from disk into dict."""
    package_path = str(importlib.resources.files(anchor))
    with open(
        file=os.path.join(package_path, resource, file_name),
        encoding=UTF_8,
    ) as fptr:
        return orjson.loads(fptr.read())


def get_prepared_custom_data_point(central: CentralUnit, address: str, channel_no: int) -> CustomDataPoint | None:
    """Return the hm custom_data_point."""
    if cdp := central.get_custom_data_point(address=address, channel_no=channel_no):
        for dp in cdp._data_points.values():
            dp._state_uncertain = False
        return cdp
    return None


def load_device_description(file_name: str) -> Any:
    """Load device description."""
    dev_desc = _load_json_file(anchor="pydevccu", resource="device_descriptions", file_name=file_name)
    assert dev_desc
    return dev_desc
