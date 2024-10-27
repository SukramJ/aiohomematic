"""Module for data points implemented using the text category."""

from __future__ import annotations

from hahomematic.const import DataPointCategory
from hahomematic.model.generic.data_point import GenericDataPoint


class DpText(GenericDataPoint[str, str]):
    """
    Implementation of a text.

    This is a default data point that gets automatically generated.
    """

    _category = DataPointCategory.TEXT
