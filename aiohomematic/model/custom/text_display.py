# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Custom text display data points for devices with LCD displays.

This module provides support for HmIP devices with text display capabilities,
such as the HmIP-WRCD (Wall-mount Remote Control with Display).

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import logging
from typing import Final, TypedDict, Unpack

from aiohomematic import i18n
from aiohomematic.const import DataPointCategory, DeviceProfile, Field
from aiohomematic.exceptions import ValidationException
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.field import DataPointField
from aiohomematic.model.custom.registry import DeviceProfileRegistry
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import DpAction, DpActionSelect, DpBinarySensor
from aiohomematic.property_decorators import DelegatedProperty, Kind, state_property

__all__ = ["CustomDpTextDisplay", "TextDisplayArgs"]

_LOGGER: Final = logging.getLogger(__name__)

# Default values for send_text parameters
_DEFAULT_BACKGROUND_COLOR: Final = "WHITE"
_DEFAULT_TEXT_COLOR: Final = "BLACK"
_DEFAULT_ALIGNMENT: Final = "CENTER"
_DEFAULT_DISPLAY_ID: Final = 1
_DEFAULT_REPEAT: Final = 1
_DEFAULT_INTERVAL: Final = 1

# Validation ranges
_MIN_DISPLAY_ID: Final = 1
_MAX_DISPLAY_ID: Final = 5
_MIN_INTERVAL: Final = 1
_MAX_INTERVAL: Final = 15


class TextDisplayArgs(TypedDict, total=False):
    """Arguments for send_text method."""

    text: str
    icon: str
    background_color: str
    text_color: str
    alignment: str
    display_id: int
    sound: str
    repeat: int
    interval: int


class CustomDpTextDisplay(CustomDataPoint):
    """Class for HomematicIP text display data point."""

    __slots__ = ()  # Required to prevent __dict__ creation (descriptors are class-level)

    _category = DataPointCategory.TEXT_DISPLAY

    # Declarative data point field definitions
    _dp_acoustic_notification_selection: Final = DataPointField(
        field=Field.ACOUSTIC_NOTIFICATION_SELECTION, dpt=DpActionSelect
    )
    _dp_display_data_alignment: Final = DataPointField(field=Field.DISPLAY_DATA_ALIGNMENT, dpt=DpActionSelect)
    _dp_display_data_background_color: Final = DataPointField(
        field=Field.DISPLAY_DATA_BACKGROUND_COLOR, dpt=DpActionSelect
    )
    _dp_display_data_commit: Final = DataPointField(field=Field.DISPLAY_DATA_COMMIT, dpt=DpAction)
    _dp_display_data_icon: Final = DataPointField(field=Field.DISPLAY_DATA_ICON, dpt=DpActionSelect)
    _dp_display_data_id: Final = DataPointField(field=Field.DISPLAY_DATA_ID, dpt=DpActionSelect)
    _dp_display_data_string: Final = DataPointField(field=Field.DISPLAY_DATA_STRING, dpt=DpAction)
    _dp_display_data_text_color: Final = DataPointField(field=Field.DISPLAY_DATA_TEXT_COLOR, dpt=DpActionSelect)
    _dp_interval: Final = DataPointField(field=Field.INTERVAL, dpt=DpActionSelect)
    _dp_repetitions: Final = DataPointField(field=Field.REPETITIONS, dpt=DpActionSelect)
    _dp_burst_limit_warning: Final = DataPointField(field=Field.BURST_LIMIT_WARNING, dpt=DpBinarySensor)

    # Expose available options via DelegatedProperty
    @staticmethod
    def _get_index_from_value_list(*, value: str | None, value_list: tuple[str, ...] | None) -> int | None:
        """Get the index of a value in a value list."""
        if value is None or value_list is None:
            return None
        if value in value_list:
            return value_list.index(value)
        return None

    @staticmethod
    def _get_repetition_string(*, repeat: int) -> str:
        """Convert repetition int to device string format (REPETITIONS_XXX)."""
        if repeat == 0:
            return "NO_REPETITION"
        if repeat == -1:
            return "INFINITE_REPETITIONS"
        return f"REPETITIONS_{repeat:03d}"

    _available_repetitions: Final = DelegatedProperty[tuple[str, ...] | None](path="_dp_repetitions.values")
    available_alignments: Final = DelegatedProperty[tuple[str, ...] | None](
        path="_dp_display_data_alignment.values", kind=Kind.STATE
    )
    available_background_colors: Final = DelegatedProperty[tuple[str, ...] | None](
        path="_dp_display_data_background_color.values", kind=Kind.STATE
    )
    available_icons: Final = DelegatedProperty[tuple[str, ...] | None](
        path="_dp_display_data_icon.values", kind=Kind.STATE
    )
    available_sounds: Final = DelegatedProperty[tuple[str, ...] | None](
        path="_dp_acoustic_notification_selection.values", kind=Kind.STATE
    )
    available_text_colors: Final = DelegatedProperty[tuple[str, ...] | None](
        path="_dp_display_data_text_color.values", kind=Kind.STATE
    )
    burst_limit_warning: Final = DelegatedProperty[bool](path="_dp_burst_limit_warning.value")

    @state_property
    def supports_icons(self) -> bool:
        """Return true if display supports icons."""
        return self.available_icons is not None

    @state_property
    def supports_sounds(self) -> bool:
        """Return true if display supports sounds."""
        return self.available_sounds is not None

    @bind_collector
    async def send_text(
        self,
        *,
        collector: CallParameterCollector | None = None,
        **kwargs: Unpack[TextDisplayArgs],
    ) -> None:
        """
        Send text to the display.

        Args:
            collector: Optional call parameter collector.
            **kwargs: Display parameters from TextDisplayArgs:
                text: The text to display (required).
                icon: Icon name from available_icons (optional).
                background_color: Background color (optional, default: WHITE).
                text_color: Text color (optional, default: BLACK).
                alignment: Text alignment (optional, default: CENTER).
                display_id: Display slot 1-5 (optional, default: 1).
                sound: Sound name from available_sounds (optional).
                repeat: Sound repetitions 0-15 (optional, default: 1).
                interval: Interval between sound tones 1-15 (optional, default: 1).

        """
        # Warn if burst limit is active
        if self.burst_limit_warning:
            _LOGGER.warning(
                i18n.tr(
                    key="log.model.custom.text_display.send_text.burst_limit_warning",
                    full_name=self.full_name,
                )
            )

        text = kwargs.get("text", "")
        icon = kwargs.get("icon")
        background_color = kwargs.get("background_color", _DEFAULT_BACKGROUND_COLOR)
        text_color = kwargs.get("text_color", _DEFAULT_TEXT_COLOR)
        alignment = kwargs.get("alignment", _DEFAULT_ALIGNMENT)
        display_id = kwargs.get("display_id", _DEFAULT_DISPLAY_ID)
        sound = kwargs.get("sound")
        repeat = kwargs.get("repeat", _DEFAULT_REPEAT)
        interval = kwargs.get("interval", _DEFAULT_INTERVAL)

        # Validate icon if provided
        if icon is not None and self.available_icons and icon not in self.available_icons:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.custom.text_display.invalid_icon",
                    full_name=self.full_name,
                    value=icon,
                )
            )

        # Validate background color
        if self.available_background_colors and background_color not in self.available_background_colors:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.custom.text_display.invalid_background_color",
                    full_name=self.full_name,
                    value=background_color,
                )
            )

        # Validate text color
        if self.available_text_colors and text_color not in self.available_text_colors:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.custom.text_display.invalid_text_color",
                    full_name=self.full_name,
                    value=text_color,
                )
            )

        # Validate alignment
        if self.available_alignments and alignment not in self.available_alignments:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.custom.text_display.invalid_alignment",
                    full_name=self.full_name,
                    value=alignment,
                )
            )

        # Validate display_id
        if not _MIN_DISPLAY_ID <= display_id <= _MAX_DISPLAY_ID:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.custom.text_display.invalid_display_id",
                    full_name=self.full_name,
                    value=display_id,
                )
            )

        # Validate sound if provided
        if sound is not None and self.available_sounds and sound not in self.available_sounds:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.custom.text_display.invalid_sound",
                    full_name=self.full_name,
                    value=sound,
                )
            )

        # Validate repeat - convert to string format for validation
        if (repetition_value := self._get_repetition_string(repeat=repeat)) not in (self._available_repetitions or ()):
            raise ValidationException(
                i18n.tr(
                    key="exception.model.custom.text_display.invalid_repeat",
                    full_name=self.full_name,
                    value=repeat,
                )
            )

        # Validate interval
        if not _MIN_INTERVAL <= interval <= _MAX_INTERVAL:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.custom.text_display.invalid_interval",
                    full_name=self.full_name,
                    value=interval,
                )
            )

        # Get icon value (use first icon = NO_ICON if not specified)
        icon_value = self.available_icons[0] if self.available_icons else "NO_ICON"
        if icon is not None:
            icon_value = icon

        # Send display parameters using individual data points
        # The collector batches these into a single put_paramset call
        await self._dp_display_data_background_color.send_value(value=background_color, collector=collector)
        await self._dp_display_data_text_color.send_value(value=text_color, collector=collector)
        await self._dp_display_data_icon.send_value(value=icon_value, collector=collector)
        await self._dp_display_data_alignment.send_value(value=alignment, collector=collector)
        await self._dp_display_data_string.send_value(value=text, collector=collector)
        await self._dp_display_data_id.send_value(value=display_id, collector=collector)

        # Send sound parameters if sound is specified
        if sound is not None:
            await self._dp_acoustic_notification_selection.send_value(value=sound, collector=collector)
            await self._dp_repetitions.send_value(value=repetition_value, collector=collector)
            await self._dp_interval.send_value(value=interval, collector=collector)

        # DISPLAY_DATA_COMMIT triggers the display update - must be last
        await self._dp_display_data_commit.send_value(value=True, collector=collector)


# =============================================================================
# DeviceProfileRegistry Registration
# =============================================================================

# IP Text Display (HmIP-WRCD)
DeviceProfileRegistry.register(
    category=DataPointCategory.TEXT_DISPLAY,
    models="HmIP-WRCD",
    data_point_class=CustomDpTextDisplay,
    profile_type=DeviceProfile.IP_TEXT_DISPLAY,
    channels=(3,),
)
