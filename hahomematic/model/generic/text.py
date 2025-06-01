"""Module for data points implemented using the text category."""

from __future__ import annotations

from typing import cast

from hahomematic.const import DataPointCategory
from hahomematic.model.decorators import state_property
from hahomematic.model.generic.data_point import GenericDataPoint
from hahomematic.model.support import check_length_and_log


class DpText(GenericDataPoint[str, str]):
    """
    Implementation of a text.

    This is a default data point that gets automatically generated.
    """

    _category = DataPointCategory.TEXT

    @state_property
    def value(self) -> str | None:
        """Get the value of the data_point."""
        return cast(str | None, check_length_and_log(name=self.name, value=self._value))
