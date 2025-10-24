"""
Tests for model.event factory and generic._determine_data_point_type logic.

Covers event type determination and creation, and generic data point type
selection without instantiating concrete data points.
"""

from __future__ import annotations

from typing import Any

import pytest

from aiohomematic.const import Operations, ParameterType
from aiohomematic.model import event as me
from aiohomematic.model.generic import (
    DpAction,
    DpBinarySensor,
    DpButton,
    DpFloat,
    DpInteger,
    DpSelect,
    DpSensor,
    DpSwitch,
    DpText,
    _determine_data_point_type,
)


class _FakeChannel:
    def __init__(self, *, model: str = "HmIP-ABC") -> None:
        self.device = type("Dev", (), {"model": model, "interface_id": "ifid"})()
        self.address = "ADDR1:1"
        self.central = type(
            "Central",
            (),
            {
                "name": "CentralTest",
                "parameter_visibility": type(
                    "PV",
                    (),
                    {
                        "parameter_is_un_ignored": staticmethod(lambda **_kwargs: False),
                    },
                )(),
                "paramset_descriptions": type(
                    "PSD",
                    (),
                    {
                        "is_in_multiple_channels": staticmethod(lambda **_kwargs: False),
                    },
                )(),
            },
        )()
        # device with minimal fields and central reference for model code
        self.device = type(
            "Dev",
            (),
            {
                "model": model,
                "interface_id": "ifid",
                "central": self.central,
                "address": "ADDR1",
                "client": type("Client", (), {"interface": None})(),
            },
        )()
        self.address = "ADDR1:1"
        self.no = 1
        self._added: list[Any] = []

    def add_data_point(self, *, data_point: Any) -> None:
        self._added.append(data_point)


def _pd(**over: Any) -> dict[str, Any]:
    """Minimal ParameterData helper with sensible defaults."""
    data: dict[str, Any] = {
        "TYPE": ParameterType.INTEGER,
        "OPERATIONS": int(Operations.EVENT | Operations.WRITE | Operations.READ),
        "FLAGS": 0,
    }
    data.update(over)
    return data


def test_safe_create_event_wraps_errors() -> None:
    """Use pytest.raises when constructor errors are wrapped into AioHomematicException."""

    class _Boom(me.GenericEvent):  # type: ignore[misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401
            """Raise immediately without calling super to avoid deep init."""
            raise RuntimeError("boom")

    ch = _FakeChannel()
    from aiohomematic.exceptions import AioHomematicException

    with pytest.raises(AioHomematicException) as excinfo:
        me._safe_create_event(event_t=_Boom, channel=ch, parameter="X", parameter_data=_pd())
    assert "Unable to create event" in str(excinfo.value)


def test_determine_generic_dp_types() -> None:
    """Generic factory should map parameter types and operations to DP classes."""
    ch = _FakeChannel()

    # ACTION write-only -> DpAction
    assert (
        _determine_data_point_type(
            channel=ch,
            parameter="DO_SOMETHING",
            parameter_data=_pd(TYPE=ParameterType.ACTION, OPERATIONS=int(Operations.WRITE)),
        )
        is DpAction
    )

    # ACTION write-only specific button-like action -> DpButton
    assert (
        _determine_data_point_type(
            channel=ch,
            parameter="RESET_MOTION",
            parameter_data=_pd(TYPE=ParameterType.ACTION, OPERATIONS=int(Operations.WRITE)),
        )
        is DpButton
    )

    # ACTION write+read with click events -> DpButton
    assert (
        _determine_data_point_type(
            channel=ch,
            parameter="PRESS_SHORT",
            parameter_data=_pd(TYPE=ParameterType.ACTION, OPERATIONS=int(Operations.READ | Operations.WRITE)),
        )
        is DpButton
    )

    # BOOL with WRITE -> DpSwitch
    assert (
        _determine_data_point_type(
            channel=ch,
            parameter="STATE",
            parameter_data=_pd(TYPE=ParameterType.BOOL, OPERATIONS=int(Operations.READ | Operations.WRITE)),
        )
        is DpSwitch
    )

    # ENUM with WRITE -> DpSelect
    assert (
        _determine_data_point_type(
            channel=ch,
            parameter="MODE",
            parameter_data=_pd(TYPE=ParameterType.ENUM, OPERATIONS=int(Operations.READ | Operations.WRITE)),
        )
        is DpSelect
    )

    # FLOAT with WRITE -> DpFloat (returned via BaseDpNumber type)
    assert (
        _determine_data_point_type(
            channel=ch,
            parameter="LEVEL",
            parameter_data=_pd(TYPE=ParameterType.FLOAT, OPERATIONS=int(Operations.READ | Operations.WRITE)),
        )
        is DpFloat
    )  # type: ignore[name-defined]

    # INTEGER with WRITE -> DpInteger (returned via BaseDpNumber type)
    assert (
        _determine_data_point_type(
            channel=ch,
            parameter="COUNTER",
            parameter_data=_pd(TYPE=ParameterType.INTEGER, OPERATIONS=int(Operations.READ | Operations.WRITE)),
        )
        is DpInteger
    )  # type: ignore[name-defined]

    # STRING with WRITE -> DpText
    assert (
        _determine_data_point_type(
            channel=ch,
            parameter="LABEL",
            parameter_data=_pd(TYPE=ParameterType.STRING, OPERATIONS=int(Operations.READ | Operations.WRITE)),
        )
        is DpText
    )

    # Read-only BOOL-like (VALUE_LIST) -> DpBinarySensor
    assert (
        _determine_data_point_type(
            channel=ch,
            parameter="STATE",
            parameter_data={
                "TYPE": ParameterType.ENUM,
                "OPERATIONS": int(Operations.READ),
                "FLAGS": 0,
                "VALUE_LIST": ("CLOSED", "OPEN"),
            },
        )
        is DpBinarySensor
    )

    # Read-only ENUM not matching binary -> DpSensor
    assert (
        _determine_data_point_type(
            channel=ch,
            parameter="SOMETHING",
            parameter_data={
                "TYPE": ParameterType.ENUM,
                "OPERATIONS": int(Operations.READ),
                "FLAGS": 0,
                "VALUE_LIST": ("A", "B", "C"),
            },
        )
        is DpSensor
    )
