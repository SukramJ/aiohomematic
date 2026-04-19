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

from collections.abc import Mapping
import logging
from typing import Any, Final, cast, override
import weakref

from aiohomematic import ccu_translations, i18n
from aiohomematic.central.events import DataPointStateChangedEvent
from aiohomematic.const import (
    BIDCOS_DEVICE_CHANNEL_DUMMY,
    CallSource,
    DataPointCategory,
    DataPointUsage,
    Parameter,
    ParamsetKey,
    ScheduleDict,
    ScheduleField,
    ScheduleProfile,
    ScheduleType,
    ServiceScope,
    WeekdayStr,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import ValidationException
from aiohomematic.interfaces import (
    ClimateWeekProfileDataPointProtocol,
    ScheduleChannelSwitchProtocol,
    WeekProfileDataPointProtocol,
)
from aiohomematic.interfaces.model import (
    CallbackDataPointProtocol,
    ChannelProtocol,
    DeviceProtocol,
    GenericDataPointProtocolAny,
)
from aiohomematic.model.custom.profile import RebasedChannelGroupConfig
from aiohomematic.model.data_point import BaseDataPoint
from aiohomematic.model.schedule_models import (
    SCHEDULE_DOMAINS,
    ClimateSchedule,
    SimpleSchedule,
    TargetChannelInfo,
    channel_key_to_bitmask,
    parse_channel_locks,
)
from aiohomematic.model.support import DataPointNameData, DataPointPathData, PathData, generate_unique_id
from aiohomematic.model.week_profile import ClimateWeekProfile, DefaultWeekProfile
from aiohomematic.property_decorators import DelegatedProperty, Kind, hm_property
from aiohomematic.type_aliases import UnsubscribeCallback

__all__ = [
    "ClimateWeekProfileDataPoint",
    "ScheduleChannelSwitch",
    "WeekProfileDataPoint",
    "create_week_profile_data_point",
]

_LOGGER: Final = logging.getLogger(__name__)


def _cleanup_callbacks(callbacks: list[UnsubscribeCallback]) -> None:  # kwonly: disable
    """Clean up subscription callbacks (invoked by weakref.finalize)."""
    for unsub in callbacks:
        unsub()
    callbacks.clear()


_PARAMETER_NAME: Final = "WEEK_PROFILE"
_SCHEDULE_CHANNEL_SWITCH_PARAMETER: Final = "SCHEDULE_CHANNEL_SWITCH"
_SCHEDULE_MANU_MODE: Final = "MANU_MODE"
_SCHEDULE_AUTO_MODE: Final = "AUTO_MODE_WITHOUT_RESET"
# Numeric values for COMBINED_PARAMETER (WPTCL): 0=MANU_MODE, 2=AUTO_MODE_WITHOUT_RESET
_WPTCL_MANU: Final = 0
_WPTCL_AUTO: Final = 2
_MAX_SIMPLE_ENTRIES: Final = 24
_MAX_CLIMATE_SLOTS_PER_DAY: Final = 13
_CLIMATE_PROFILES: Final = 6
_WEEKDAYS: Final = 7


class ScheduleChannelSwitch(BaseDataPoint, ScheduleChannelSwitchProtocol):
    """Per-channel switch to enable/disable schedule participation."""

    __slots__ = (
        "_channel_key",
        "_target_channel_info",
        "_unsubscribe_callbacks",
        "_week_profile_data_point",
    )

    _category = DataPointCategory.SCHEDULE_SWITCH

    def __init__(
        self,
        *,
        channel: ChannelProtocol,
        week_profile_data_point: WeekProfileDataPointProtocol,
        channel_key: str,
        target_channel_info: TargetChannelInfo,
    ) -> None:
        """Initialize the schedule channel switch."""
        # Set attributes BEFORE super().__init__() because BaseDataPoint.__init__
        # calls _get_data_point_name() which needs _channel_key and _target_channel_info.
        self._week_profile_data_point: Final = week_profile_data_point
        self._channel_key: Final = channel_key
        self._target_channel_info: Final = target_channel_info
        self._unsubscribe_callbacks: list[UnsubscribeCallback] = []

        unique_id = generate_unique_id(
            config_provider=channel.device.config_provider,
            address=channel.device.address,
            parameter=f"SCHEDULE_CHANNEL_LOCK_{channel_key}",
            prefix="schedule_channel_switch",
        )
        super().__init__(
            channel=channel,
            unique_id=unique_id,
            is_in_multiple_channels=False,
        )

        # Subscribe to WPDP events for automatic state sync
        self._unsubscribe_callbacks.append(
            self._event_bus_provider.event_bus.subscribe(
                event_type=DataPointStateChangedEvent,
                event_key=week_profile_data_point.unique_id,
                handler=lambda *, event: self.publish_data_point_updated_event(),  # noqa: PLW0108  # pylint: disable=unnecessary-lambda
            )
        )
        weakref.finalize(self, _cleanup_callbacks, self._unsubscribe_callbacks)

    channel_key: Final = DelegatedProperty[str](path="_channel_key", kind=Kind.CONFIG)
    target_channel_info: Final = DelegatedProperty[TargetChannelInfo](path="_target_channel_info", kind=Kind.CONFIG)

    @property
    def usage(self) -> DataPointUsage:
        """Return the data point usage."""
        return DataPointUsage.DATA_POINT

    @hm_property(kind=Kind.STATE)
    def value(self) -> bool | None:
        """Return whether the schedule is enabled for this channel."""
        if (schedule_enabled := self._week_profile_data_point.schedule_enabled) is None:
            return None
        return schedule_enabled.get(self._channel_key)

    @override
    async def load_data_point_value(self, *, call_source: CallSource, direct_call: bool = False) -> None:
        """Load the data point value. Delegated to the parent WPDP."""

    async def turn_off(self) -> None:
        """Disable the schedule for this channel."""
        await self._week_profile_data_point.set_schedule_enabled(enabled=False, channel_key=self._channel_key)

    async def turn_on(self) -> None:
        """Enable the schedule for this channel."""
        await self._week_profile_data_point.set_schedule_enabled(enabled=True, channel_key=self._channel_key)

    @override
    def _get_data_point_name(self) -> DataPointNameData:
        """Create the name for the schedule channel switch."""
        return DataPointNameData(
            device_name=self._device.name,
            channel_name=self._target_channel_info.name,
            parameter_name=f"SCHEDULE_CHANNEL_LOCK_{self._channel_key}",
            parameter_translation=ccu_translations.get_parameter_translation(
                parameter=_SCHEDULE_CHANNEL_SWITCH_PARAMETER,
                locale=self._device.config_provider.config.locale,
            ),
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
        return f"{self._category}/{self._device.model}/SCHEDULE_CHANNEL_LOCK_{self._channel_key}"


class WeekProfileDataPoint(BaseDataPoint, WeekProfileDataPointProtocol):
    """Device-level data point exposing schedule data and metadata."""

    __slots__ = (
        "_available_target_channels",
        "_dp_channel_locks",
        "_unsubscribe_callbacks",
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
        self._dp_channel_locks: GenericDataPointProtocolAny | None = None
        self._unsubscribe_callbacks: list[UnsubscribeCallback] = []
        weakref.finalize(self, _cleanup_callbacks, self._unsubscribe_callbacks)

    available_target_channels: Final = DelegatedProperty[Mapping[str, TargetChannelInfo]](
        path="_available_target_channels"
    )
    schedule_channel_address: Final = DelegatedProperty[str | None](path="_week_profile.schedule_channel_address")
    supported_schedule_fields: Final = DelegatedProperty[frozenset[ScheduleField]](
        path="_week_profile.supported_schedule_fields"
    )

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
    def schedule_domain(self) -> DataPointCategory | None:
        """Return the schedule domain (switch, light, cover, valve) for non-climate devices."""
        if (
            isinstance(self._week_profile, DefaultWeekProfile)
            and (category := self._week_profile.category) in SCHEDULE_DOMAINS
        ):
            return category
        return None

    @property
    def schedule_enabled(self) -> Mapping[str, bool] | None:
        """Return per-channel schedule enabled state, or None if not supported."""
        if self._dp_channel_locks is None:
            return None
        if (value := self._dp_channel_locks.value) is None:
            return None
        return parse_channel_locks(
            locks_value=int(value),
            available_channels=self._available_target_channels,
        )

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
        if self._dp_channel_locks is not None:
            await self._dp_channel_locks.load_data_point_value(call_source=call_source, direct_call=direct_call)

    async def reload_schedule(self) -> None:
        """Reload schedule from CCU and update data point state."""
        await self._week_profile.reload_and_cache_schedule(force=True)
        self.publish_data_point_updated_event()

    def set_channel_locks_data_point(self, *, data_point: GenericDataPointProtocolAny) -> None:
        """Bind the channel locks generic data point for schedule enabled state."""
        self._dp_channel_locks = data_point

        # Subscribe to events for automatic state sync
        self._unsubscribe_callbacks.append(
            self._event_bus_provider.event_bus.subscribe(
                event_type=DataPointStateChangedEvent,
                event_key=data_point.unique_id,
                handler=lambda *, event: self.publish_data_point_updated_event(),  # noqa: PLW0108  # pylint: disable=unnecessary-lambda
            )
        )

    async def set_schedule(self, *, schedule_data: ScheduleDict) -> None:
        """Write schedule data to CCU."""
        if isinstance(self._week_profile, DefaultWeekProfile):
            await self._week_profile.set_schedule(schedule_data=SimpleSchedule.model_validate(schedule_data))
        else:
            await self._week_profile.set_schedule(schedule_data=schedule_data)

    async def set_schedule_enabled(self, *, enabled: bool, channel_key: str | None = None) -> None:
        """
        Enable or disable the weekly program on the device.

        Uses COMBINED_PARAMETER to atomically set target channel bitmask and
        lock mode in a single setValue call. The CCU processes COMBINED_PARAMETER
        values in order: WPTCLS (target channels) then WPTCL (action).
        Format: "WPTCLS={bitmask},WPTCL={mode}" where mode 0=MANU, 2=AUTO.

        After writing, explicitly reads WEEK_PROGRAM_CHANNEL_LOCKS to refresh state,
        because write-only parameters may not trigger RPC callback events.
        """
        if not isinstance(self._week_profile, DefaultWeekProfile):
            return
        if (sca := self._week_profile.schedule_channel_address) is None:
            return

        mode = _WPTCL_AUTO if enabled else _WPTCL_MANU

        if channel_key is not None:
            bitmask = channel_key_to_bitmask(channel_key=channel_key)
        else:
            # All available channels
            bitmask = sum(channel_key_to_bitmask(channel_key=key) for key in self._available_target_channels)

        await self._device.client.set_value(
            channel_address=sca,
            paramset_key=ParamsetKey.VALUES,
            parameter=Parameter.COMBINED_PARAMETER,
            value=f"WPTCLS={bitmask},WPTCL={mode}",
            wait_for_callback=None,
        )

        # Explicitly read current state (write-only params may not trigger events)
        if self._dp_channel_locks is not None:
            await self._dp_channel_locks.load_data_point_value(
                call_source=CallSource.MANUAL_OR_SCHEDULED, direct_call=True
            )

    def _build_target_channel_map(self) -> dict[str, TargetChannelInfo]:
        """Build the actor_sub -> TargetChannelInfo mapping."""
        device = self._device
        result: dict[str, TargetChannelInfo] = {}

        sorted_groups = sorted(_get_schedule_relevant_channel_groups(device=device).items())

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

    __slots__ = (
        "_current_schedule_profile",
        "_dp_profile_pointer",
        "_schedule_profile_nos",
    )

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
        self._current_schedule_profile: ScheduleProfile = ScheduleProfile.P1
        self._dp_profile_pointer: GenericDataPointProtocolAny | None = None
        self._schedule_profile_nos: Final = schedule_profile_nos

    @staticmethod
    def _map_to_schedule_profile(*, value: Any) -> ScheduleProfile | None:
        """Map a device parameter value to ScheduleProfile."""
        if value is None:
            return None
        # IP: ACTIVE_PROFILE is int (1-6) → P1-P6
        if isinstance(value, int):
            try:
                return ScheduleProfile(f"P{value}")
            except ValueError:
                return None
        # RF: WEEK_PROGRAM_POINTER is str ("0", "1", ...) → P1-P6
        str_val = str(value)
        if (idx := int(str_val) if str_val.isnumeric() else None) is not None:
            try:
                return ScheduleProfile(f"P{idx + 1}")
            except ValueError:
                return None
        return None

    available_profiles: Final = DelegatedProperty[tuple[ScheduleProfile, ...]](path="_week_profile.available_profiles")
    current_schedule_profile: Final = DelegatedProperty[ScheduleProfile](
        path="_current_schedule_profile", kind=Kind.STATE
    )
    schedule_profile_nos: Final = DelegatedProperty[int](path="_schedule_profile_nos")

    @property
    def current_profile_schedule(self) -> ScheduleDict | None:
        """Return the schedule data for the current profile."""
        return self.schedule.get(self._current_schedule_profile)

    @property
    def device_active_profile_index(self) -> int | None:
        """Return the 1-based profile index from the device parameter."""
        if self._dp_profile_pointer is None or self._dp_profile_pointer.value is None:
            return None
        value = self._dp_profile_pointer.value
        # IP: ACTIVE_PROFILE is int (1-6) → return directly
        if isinstance(value, int):
            return value
        # RF: WEEK_PROGRAM_POINTER is str ("0", "1", "2") → convert to 1-based
        str_val = str(value)
        if str_val.isnumeric():
            return int(str_val) + 1
        return None

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

    def set_climate_data_point(self, *, climate_data_point: CallbackDataPointProtocol) -> None:
        """Link climate CDP for schedule change notifications."""
        self._unsubscribe_callbacks.append(
            self._event_bus_provider.event_bus.subscribe(
                event_type=DataPointStateChangedEvent,
                event_key=self.unique_id,
                handler=lambda *, event: climate_data_point.publish_data_point_updated_event(),  # noqa: PLW0108  # pylint: disable=unnecessary-lambda
            )
        )

    def set_current_schedule_profile(self, *, profile: ScheduleProfile) -> None:
        """Set the current schedule profile."""
        if self._current_schedule_profile == profile:
            return
        self._current_schedule_profile = profile
        self.publish_data_point_updated_event()

    def set_profile_pointer_data_point(self, *, data_point: GenericDataPointProtocolAny) -> None:
        """Bind the profile pointer generic data point for automatic sync."""
        self._dp_profile_pointer = data_point

        # Read initial value
        if (
            data_point.value is not None
            and (profile := self._map_to_schedule_profile(value=data_point.value)) is not None
        ):
            self._current_schedule_profile = profile

        # Generic DP → CWPDP (profile sync)
        self._unsubscribe_callbacks.append(
            self._event_bus_provider.event_bus.subscribe(
                event_type=DataPointStateChangedEvent,
                event_key=data_point.unique_id,
                handler=lambda *, event: self._on_profile_pointer_updated(),  # noqa: PLW0108  # pylint: disable=unnecessary-lambda
            )
        )

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

    def _on_profile_pointer_updated(self) -> None:
        """Handle profile pointer DP updates to sync current_schedule_profile."""
        if self._dp_profile_pointer is None:
            return
        new_profile = self._map_to_schedule_profile(value=self._dp_profile_pointer.value)
        if new_profile is None or self._current_schedule_profile == new_profile:
            return
        self._current_schedule_profile = new_profile
        self.publish_data_point_updated_event()


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

    # Non-climate bindings: schedule enable/disable via WEEK_PROGRAM_CHANNEL_LOCKS
    if (
        isinstance(data_point, WeekProfileDataPoint)
        and not isinstance(data_point, ClimateWeekProfileDataPoint)
        and (locks_dp := _find_channel_locks_dp(device=device)) is not None
    ):
        data_point.set_channel_locks_data_point(data_point=locks_dp)

        # Create per-channel schedule switches
        switches = _create_schedule_channel_switches(
            channel=schedule_channel,
            week_profile_data_point=data_point,
        )
        if switches:
            device.set_schedule_channel_switches(switches=switches)

    # Climate-specific bindings
    if isinstance(data_point, ClimateWeekProfileDataPoint):
        # Bind profile pointer Generic DP for automatic sync
        if (profile_dp := _find_profile_pointer_dp(device=device)) is not None:
            data_point.set_profile_pointer_data_point(data_point=profile_dp)

        # Link Climate CDP for schedule change notifications
        if (climate_cdp := _find_climate_custom_data_point(device=device)) is not None:
            data_point.set_climate_data_point(climate_data_point=climate_cdp)

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


def _get_schedule_relevant_channel_groups(
    *,
    device: DeviceProtocol,
) -> dict[int, RebasedChannelGroupConfig]:
    """
    Return channel groups relevant for the schedule target channel map.

    If any CDP on the device has an explicit schedule_channel_no, only groups
    from those CDPs are included. This filters out CDPs that are not controlled
    by the schedule (e.g. button locks on multi-config devices like HmIP-DLP).

    If no CDP has schedule_channel_no, all groups are returned (devices using
    default_schedule_channel via channel type).
    """
    all_groups: dict[int, RebasedChannelGroupConfig] = dict(device.channel_groups)
    schedule_groups: dict[int, RebasedChannelGroupConfig] = {}

    for channel in device.channels.values():
        if (
            (cdp := channel.custom_data_point) is not None
            and cdp.group_no is not None
            and _has_schedule_channel_no(dp=cdp)
        ):
            schedule_groups[cdp.group_no] = cdp.channel_group

    return schedule_groups or all_groups


def _find_channel_locks_dp(*, device: DeviceProtocol) -> GenericDataPointProtocolAny | None:
    """Find the WEEK_PROGRAM_CHANNEL_LOCKS generic DP on the schedule channel."""
    for channel in device.channels.values():
        if not channel.is_schedule_channel:
            continue
        if (dp := channel.get_generic_data_point(parameter=Parameter.WEEK_PROGRAM_CHANNEL_LOCKS)) is not None:
            return dp
    return None


def _find_profile_pointer_dp(*, device: DeviceProtocol) -> GenericDataPointProtocolAny | None:
    """Find the ACTIVE_PROFILE or WEEK_PROGRAM_POINTER generic DP on the device."""
    for param in (Parameter.ACTIVE_PROFILE, Parameter.WEEK_PROGRAM_POINTER):
        for channel in device.channels.values():
            if (dp := channel.get_generic_data_point(parameter=param)) is not None:
                return dp
    return None


def _find_climate_custom_data_point(*, device: DeviceProtocol) -> CallbackDataPointProtocol | None:
    """Find the climate custom data point on the device."""
    for channel in device.channels.values():
        if (dp := channel.custom_data_point) is None:
            continue
        if _has_schedule_channel_no(dp=dp):
            return dp
    return None


def _create_schedule_channel_switches(
    *,
    channel: ChannelProtocol,
    week_profile_data_point: WeekProfileDataPoint,
) -> tuple[ScheduleChannelSwitch, ...]:
    """Create ScheduleChannelSwitch instances for each available target channel."""
    switches: list[ScheduleChannelSwitch] = []
    for key, info in week_profile_data_point.available_target_channels.items():
        switches.append(
            ScheduleChannelSwitch(
                channel=channel,
                week_profile_data_point=week_profile_data_point,
                channel_key=key,
                target_channel_info=info,
            )
        )
    return tuple(switches)


def _get_schedule_profile_nos(*, device: DeviceProtocol) -> int:
    """Return the number of supported schedule profiles from the climate CDP."""
    for channel in device.channels.values():
        if (dp := channel.custom_data_point) is None:
            continue
        if hasattr(dp, "schedule_profile_nos") and (nos := int(dp.schedule_profile_nos)) > 0:
            return nos
    return 0
