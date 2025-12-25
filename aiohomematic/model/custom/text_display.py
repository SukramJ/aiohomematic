# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Custom text display data points for devices with LCD displays.

This module provides support for HmIP devices with text display capabilities,
such as the HmIP-WRCD (Wall-mount Remote Control with Display).

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from typing import Final, TypedDict, Unpack

from aiohomematic import i18n
from aiohomematic.const import DataPointCategory, DeviceProfile, Field
from aiohomematic.exceptions import ValidationException
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.field import DataPointField
from aiohomematic.model.custom.registry import DeviceProfileRegistry
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import DpAction, DpActionSelect
from aiohomematic.property_decorators import DelegatedProperty, Kind, state_property

__all__ = ["CustomDpTextDisplay", "TextDisplayArgs"]


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


class CustomDpTextDisplay(CustomDataPoint):
    """Class for HomematicIP text display data point."""

    __slots__ = ()  # Required to prevent __dict__ creation (descriptors are class-level)

    _category = DataPointCategory.TEXT_DISPLAY

    # Declarative data point field definitions
    _dp_combined_parameter: Final = DataPointField(field=Field.COMBINED_PARAMETER, dpt=DpAction)
    _dp_acoustic_notification_selection: Final = DataPointField(
        field=Field.ACOUSTIC_NOTIFICATION_SELECTION, dpt=DpActionSelect
    )
    _dp_display_data_icon: Final = DataPointField(field=Field.DISPLAY_DATA_ICON, dpt=DpActionSelect)
    _dp_display_data_background_color: Final = DataPointField(
        field=Field.DISPLAY_DATA_BACKGROUND_COLOR, dpt=DpActionSelect
    )
    _dp_display_data_text_color: Final = DataPointField(field=Field.DISPLAY_DATA_TEXT_COLOR, dpt=DpActionSelect)
    _dp_display_data_alignment: Final = DataPointField(field=Field.DISPLAY_DATA_ALIGNMENT, dpt=DpActionSelect)

    # Expose available options via DelegatedProperty
    @staticmethod
    def _get_index_from_value_list(*, value: str | None, value_list: tuple[str, ...] | None) -> int | None:
        """Get the index of a value in a value list."""
        if value is None or value_list is None:
            return None
        if value in value_list:
            return value_list.index(value)
        return None

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
                display_id: Display slot 1-3 (optional, default: 1).
                sound: Sound name from available_sounds (optional).
                repeat: Sound repetitions 0-15 (optional, default: 1).

        """
        text = kwargs.get("text", "")
        icon = kwargs.get("icon")
        background_color = kwargs.get("background_color", "WHITE")
        text_color = kwargs.get("text_color", "BLACK")
        alignment = kwargs.get("alignment", "CENTER")
        display_id = kwargs.get("display_id", 1)
        sound = kwargs.get("sound")
        repeat = kwargs.get("repeat", 1)

        # Validate icon if provided
        if icon is not None and self.available_icons and icon not in self.available_icons:
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.text_display.invalid_icon",
                    full_name=self.full_name,
                    value=icon,
                )
            )

        # Validate background color
        if self.available_background_colors and background_color not in self.available_background_colors:
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.text_display.invalid_background_color",
                    full_name=self.full_name,
                    value=background_color,
                )
            )

        # Validate text color
        if self.available_text_colors and text_color not in self.available_text_colors:
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.text_display.invalid_text_color",
                    full_name=self.full_name,
                    value=text_color,
                )
            )

        # Validate alignment
        if self.available_alignments and alignment not in self.available_alignments:
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.text_display.invalid_alignment",
                    full_name=self.full_name,
                    value=alignment,
                )
            )

        # Validate display_id
        if not 1 <= display_id <= 3:
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.text_display.invalid_display_id",
                    full_name=self.full_name,
                    value=display_id,
                )
            )

        # Validate sound if provided
        if sound is not None and self.available_sounds and sound not in self.available_sounds:
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.text_display.invalid_sound",
                    full_name=self.full_name,
                    value=sound,
                )
            )

        # Validate repeat
        if not 0 <= repeat <= 15:
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.text_display.invalid_repeat",
                    full_name=self.full_name,
                    value=repeat,
                )
            )

        # Get icon index (0 = NO_ICON if not specified)
        icon_index = 0
        if icon is not None:
            icon_index = self._get_index_from_value_list(value=icon, value_list=self.available_icons) or 0

        # Build COMBINED_PARAMETER string
        # Format: {DDBC=color,DDTC=color,DDI=index,DDA=align,DDS=text,DDID=id},{R=repeat,ANS=sound_index}
        display_part = (
            f"{{DDBC={background_color},DDTC={text_color},DDI={icon_index},"
            f"DDA={alignment},DDS={text},DDID={display_id}}}"
        )

        # Only add sound part if sound is specified
        if sound is not None:
            sound_index = self._get_index_from_value_list(value=sound, value_list=self.available_sounds) or 0
            sound_part = f"{{R={repeat},ANS={sound_index}}}"
            combined_value = f"{display_part},{sound_part}"
        else:
            combined_value = display_part

        await self._dp_combined_parameter.send_value(value=combined_value, collector=collector)


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
