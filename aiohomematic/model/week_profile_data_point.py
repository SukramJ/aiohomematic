# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Week profile data point for device-level schedule access.

This module provides device-level data points that serve as the central interface
for schedule data — both for climate and non-climate devices. It exposes schedule
metadata, target channel mappings, and delegates read/write operations to the
underlying WeekProfile.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Final, cast, override

from aiohomematic import i18n
from aiohomematic.const import (
    BIDCOS_DEVICE_CHANNEL_DUMMY,
    CallSource,
    DataPointCategory,
    DataPointUsage,
    ScheduleDict,
    ScheduleProfile,
    ScheduleType,
    ServiceScope,
    WeekdayStr,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import ValidationException
from aiohomematic.interfaces import ClimateWeekProfileDataPointProtocol, WeekProfileDataPointProtocol
from aiohomematic.interfaces.model import ChannelProtocol, DeviceProtocol
from aiohomematic.model.data_point import BaseDataPoint
from aiohomematic.model.schedule_models import ClimateSchedule, SimpleSchedule, TargetChannelInfo
from aiohomematic.model.support import DataPointNameData, DataPointPathData, PathData, generate_unique_id
from aiohomematic.model.week_profile import ClimateWeekProfile, DefaultWeekProfile
from aiohomematic.property_decorators import Kind, hm_property

__all__ = [
    "ClimateWeekProfileDataPoint",
    "WeekProfileDataPoint",
    "create_week_profile_data_point",
]

_LOGGER: Final = logging.getLogger(__name__)

_PARAMETER_NAME: Final = "SCHEDULE"
_MAX_SIMPLE_ENTRIES: Final = 24
_MAX_CLIMATE_SLOTS_PER_DAY: Final = 13
_CLIMATE_PROFILES: Final = 6
_WEEKDAYS: Final = 7


class WeekProfileDataPoint(BaseDataPoint, WeekProfileDataPointProtocol):
    """Device-level data point exposing schedule data and metadata."""

    __slots__ = (
        "_available_target_channels",
        "_week_profile",
    )

    _category = DataPointCategory.WEEK_PROFILE

    def __init__(
        self,
        *,
        channel: ChannelProtocol,
        week_profile: ClimateWeekProfile | DefaultWeekProfile,
    ) -> None:
        """Initialize the week profile data point."""
        unique_id = generate_unique_id(
            config_provider=channel.device.config_provider,
            address=channel.device.address,
            parameter=_PARAMETER_NAME,
            prefix="week_profile",
        )
        super().__init__(
            channel=channel,
            unique_id=unique_id,
            is_in_multiple_channels=False,
        )
        self._week_profile: Final = week_profile
        self._available_target_channels: Final[Mapping[str, TargetChannelInfo]] = (
            self._build_target_channel_map() if isinstance(week_profile, DefaultWeekProfile) else {}
        )

    # --- Public Properties (for HA entity attributes) ---

    @property
    def available_target_channels(self) -> Mapping[str, TargetChannelInfo]:
        """Return the target channel mapping (non-climate only)."""
        return self._available_target_channels

    @property
    def max_entries(self) -> int:
        """Return the maximum number of schedule entries."""
        if isinstance(self._week_profile, ClimateWeekProfile):
            return _MAX_CLIMATE_SLOTS_PER_DAY * _WEEKDAYS * _CLIMATE_PROFILES
        return _MAX_SIMPLE_ENTRIES

    @property
    def max_temp(self) -> float | None:
        """Return the maximum temperature (climate only)."""
        if isinstance(self._week_profile, ClimateWeekProfile):
            return self._week_profile.max_temp
        return None

    @property
    def min_temp(self) -> float | None:
        """Return the minimum temperature (climate only)."""
        if isinstance(self._week_profile, ClimateWeekProfile):
            return self._week_profile.min_temp
        return None

    @property
    def schedule(self) -> ScheduleDict:
        """Return the cached schedule data as JSON-serializable dict."""
        return cast(ScheduleDict, self._week_profile.schedule.model_dump(mode="json"))

    @property
    def schedule_channel_address(self) -> str | None:
        """Return the schedule channel address."""
        return self._week_profile.schedule_channel_address

    @property
    def schedule_type(self) -> ScheduleType:
        """Return the schedule type identifier."""
        return ScheduleType.CLIMATE if isinstance(self._week_profile, ClimateWeekProfile) else ScheduleType.DEFAULT

    @property
    def usage(self) -> DataPointUsage:
        """Return the data point usage."""
        return DataPointUsage.DATA_POINT

    @hm_property(kind=Kind.STATE)
    def value(self) -> int:
        """Return the number of active schedule entries."""
        return self._count_active_entries()

    # --- Schedule Operations (delegated to WeekProfile) ---

    def fire_schedule_updated(self) -> None:
        """Notify subscribers that the schedule has changed."""
        self.publish_data_point_updated_event()

    async def get_schedule(self, *, force_load: bool = False) -> ScheduleDict:
        """Fetch and return the schedule from CCU."""
        schedule = await self._week_profile.get_schedule(force_load=force_load)
        return cast(ScheduleDict, schedule.model_dump(mode="json"))

    @override
    async def load_data_point_value(self, *, call_source: CallSource, direct_call: bool = False) -> None:
        """Load the data point value. Schedule data is loaded via WeekProfile."""

    async def reload_schedule(self) -> None:
        """Reload schedule from CCU and update data point state."""
        await self._week_profile.reload_and_cache_schedule(force=True)
        self.publish_data_point_updated_event()

    async def set_schedule(self, *, schedule_data: ScheduleDict) -> None:
        """Write schedule data to CCU."""
        if isinstance(self._week_profile, DefaultWeekProfile):
            await self._week_profile.set_schedule(schedule_data=SimpleSchedule.model_validate(schedule_data))
        else:
            await self._week_profile.set_schedule(schedule_data=schedule_data)

    # --- Internal ---

    def _build_target_channel_map(self) -> dict[str, TargetChannelInfo]:
        """Build the actor_sub -> TargetChannelInfo mapping."""
        device = self._device
        result: dict[str, TargetChannelInfo] = {}

        sorted_groups = sorted(device.channel_groups.items())

        for actor_idx, (_group_no, rebased_config) in enumerate(sorted_groups, start=1):
            channels_in_group: list[tuple[int, str]] = []

            if (pc := rebased_config.primary_channel) is not None:
                channels_in_group.append((pc, "primary"))

            channels_in_group.extend((sec_ch, "secondary") for sec_ch in rebased_config.secondary_channels)

            for sub_idx, (ch_no, ch_type) in enumerate(channels_in_group, start=1):
                key = f"{actor_idx}_{sub_idx}"
                ch_address = f"{device.address}:{ch_no}"
                ch_name = f"Channel {ch_no}"
                if (channel := device.channels.get(ch_address)) is not None:
                    ch_name = channel.name or f"Channel {ch_no}"

                result[key] = TargetChannelInfo(
                    channel_no=ch_no,
                    channel_address=ch_address,
                    name=ch_name,
                    channel_type=ch_type,
                )

        return result

    def _count_active_entries(self) -> int:
        """Count the number of active/defined schedule entries."""
        if isinstance(self._week_profile, ClimateWeekProfile):
            return self._count_climate_entries()
        return self._count_simple_entries()

    def _count_climate_entries(self) -> int:
        """Count defined temperature change points in a ClimateSchedule."""
        schedule = cast(ClimateSchedule, self._week_profile.schedule)
        count = 0
        for profile in schedule.root.values():
            for weekday in profile.root.values():
                count += len(weekday.periods)
        return count

    def _count_simple_entries(self) -> int:
        """Count non-empty entries in a SimpleSchedule."""
        schedule = cast(SimpleSchedule, self._week_profile.schedule)
        count = 0
        for entry in schedule.entries.values():
            if entry.target_channels:
                count += 1
        return count

    @override
    def _get_data_point_name(self) -> DataPointNameData:
        """Create the name for the week profile data point."""
        return DataPointNameData(
            device_name=self._device.name,
            channel_name=self._channel.name or "",
            parameter_name=_PARAMETER_NAME,
        )

    @override
    def _get_data_point_usage(self) -> DataPointUsage:
        """Generate the usage for the data point."""
        return DataPointUsage.DATA_POINT

    @override
    def _get_path_data(self) -> PathData:
        """Return the path data of the data point."""
        return DataPointPathData(
            interface=self._device.client.interface,
            address=self._device.address,
            channel_no=self._channel.no,
            kind=self._category,
        )

    @override
    def _get_signature(self) -> str:
        """Return the signature of the data point."""
        return f"{self._category}/{self._device.model}/{_PARAMETER_NAME}"


class ClimateWeekProfileDataPoint(WeekProfileDataPoint, ClimateWeekProfileDataPointProtocol):
    """Climate-specific week profile data point with profile/weekday operations."""

    __slots__ = ("_schedule_profile_nos",)

    _week_profile: ClimateWeekProfile  # type: ignore[misc]

    def __init__(
        self,
        *,
        channel: ChannelProtocol,
        week_profile: ClimateWeekProfile,
        schedule_profile_nos: int,
    ) -> None:
        """Initialize the climate week profile data point."""
        super().__init__(channel=channel, week_profile=week_profile)
        self._schedule_profile_nos: Final = schedule_profile_nos

    @property
    def available_schedule_profiles(self) -> tuple[ScheduleProfile, ...]:
        """Return available schedule profiles."""
        return self._week_profile.available_schedule_profiles

    @property
    def schedule_profile_nos(self) -> int:
        """Return the number of supported profiles."""
        return self._schedule_profile_nos

    @inspector
    async def copy_schedule(self, *, target_data_point: ClimateWeekProfileDataPointProtocol) -> None:
        """Copy entire schedule to target device's data point."""
        if self.schedule_profile_nos != target_data_point.schedule_profile_nos:
            raise ValidationException(i18n.tr(key="exception.model.week_profile.copy_schedule.profile_count_mismatch"))
        target_wp = _extract_climate_week_profile(data_point=target_data_point)
        await self._week_profile.copy_schedule_to(target_week_profile=target_wp)

    @inspector
    async def copy_schedule_profile(
        self,
        *,
        source_profile: ScheduleProfile,
        target_profile: ScheduleProfile,
        target_data_point: ClimateWeekProfileDataPointProtocol | None = None,
    ) -> None:
        """Copy a profile to another profile or target device."""
        target_wp: ClimateWeekProfile | None = None
        if target_data_point is not None:
            target_wp = _extract_climate_week_profile(data_point=target_data_point)
        await self._week_profile.copy_profile_to(
            source_profile=source_profile,
            target_profile=target_profile,
            target_week_profile=target_wp,
        )

    @inspector
    async def get_schedule_profile(self, *, profile: ScheduleProfile, force_load: bool = False) -> ScheduleDict:
        """Return a single profile as JSON-serializable dict."""
        result = await self._week_profile.get_profile(profile=profile, force_load=force_load)
        return cast(ScheduleDict, result.model_dump(mode="json"))

    @inspector
    async def get_schedule_weekday(
        self,
        *,
        profile: ScheduleProfile,
        weekday: WeekdayStr,
        force_load: bool = False,
    ) -> ScheduleDict:
        """Return a single weekday as JSON-serializable dict."""
        result = await self._week_profile.get_weekday(profile=profile, weekday=weekday, force_load=force_load)
        return result.model_dump(mode="json")

    @override
    async def set_schedule(self, *, schedule_data: ScheduleDict) -> None:
        """Write complete schedule to CCU."""
        await self._week_profile.set_schedule(schedule_data=schedule_data)

    @inspector
    async def set_schedule_profile(self, *, profile: ScheduleProfile, profile_data: ScheduleDict) -> None:
        """Write a single profile to CCU."""
        await self._week_profile.set_profile(profile=profile, profile_data=profile_data)

    @inspector
    async def set_schedule_weekday(
        self,
        *,
        profile: ScheduleProfile,
        weekday: WeekdayStr,
        weekday_data: ScheduleDict,
    ) -> None:
        """Write a single weekday to CCU."""
        await self._week_profile.set_weekday(profile=profile, weekday=weekday, weekday_data=weekday_data)


def _extract_climate_week_profile(
    *,
    data_point: ClimateWeekProfileDataPointProtocol,
) -> ClimateWeekProfile:
    """Extract the ClimateWeekProfile from a ClimateWeekProfileDataPoint."""
    if not isinstance(data_point, ClimateWeekProfileDataPoint):
        raise ValidationException(
            i18n.tr(
                key="exception.model.week_profile.schedule.unsupported",
                name="unknown",
            )
        )
    return data_point._week_profile  # pylint: disable=protected-access


# =============================================================================
# Factory
# =============================================================================


@inspector(scope=ServiceScope.INTERNAL)
def create_week_profile_data_point(*, device: DeviceProtocol) -> None:
    """Create a week profile data point for the device if it has a week profile."""
    if not device.has_week_profile:
        return

    if (week_profile := device.week_profile) is None:
        return

    # Path 1: Channel with WEEK_PROFILE type (non-climate devices)
    schedule_channel = device.default_schedule_channel

    # Path 2: Climate devices — resolve from schedule_channel_no in DeviceConfig
    if schedule_channel is None and isinstance(week_profile, ClimateWeekProfile):
        schedule_channel = _resolve_climate_schedule_channel(device=device)

    if schedule_channel is None:
        return

    if isinstance(week_profile, ClimateWeekProfile):
        data_point: WeekProfileDataPoint = ClimateWeekProfileDataPoint(
            channel=schedule_channel,
            week_profile=week_profile,
            schedule_profile_nos=_get_schedule_profile_nos(device=device),
        )
    elif isinstance(week_profile, DefaultWeekProfile):
        data_point = WeekProfileDataPoint(
            channel=schedule_channel,
            week_profile=week_profile,
        )
    else:
        return

    # Bidirectional linkage
    week_profile.set_week_profile_data_point(week_profile_data_point=data_point)

    # Register on device
    device.set_week_profile_data_point(week_profile_data_point=data_point)


def _resolve_climate_schedule_channel(*, device: DeviceProtocol) -> ChannelProtocol | None:
    """Resolve the schedule channel for climate devices using schedule_channel_no."""
    for channel in device.channels.values():
        if (dp := channel.custom_data_point) is None:
            continue
        if not _has_schedule_channel_no(dp=dp):
            continue
        if (ch_no := dp.device_config.schedule_channel_no) == BIDCOS_DEVICE_CHANNEL_DUMMY:
            # Device channel — keyed by bare device address (no ":0" suffix)
            return device.channels.get(device.address)
        ch_address = f"{device.address}:{ch_no}"
        return device.channels.get(ch_address)
    return None


def _has_schedule_channel_no(*, dp: Any) -> bool:
    """Check if a data point has a schedule_channel_no in its device_config."""
    return (
        hasattr(dp, "device_config")
        and dp.device_config is not None
        and dp.device_config.schedule_channel_no is not None
    )


def _get_schedule_profile_nos(*, device: DeviceProtocol) -> int:
    """Return the number of supported schedule profiles from the climate CDP."""
    for channel in device.channels.values():
        if (dp := channel.custom_data_point) is None:
            continue
        if hasattr(dp, "schedule_profile_nos") and (nos := int(dp.schedule_profile_nos)) > 0:
            return nos
    return 0
