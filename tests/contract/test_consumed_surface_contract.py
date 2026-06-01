# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract test for the surface ``homematicip_local`` consumes from aiohomematic.

A daemon-backed drop-in replacement (the openccu-loom shim) must satisfy the
exact ``CentralUnit`` + coordinator surface that Home Assistant drives. A prose
checklist in docs drifts the moment a method is renamed; this test binds that
surface to the live classes + the existing ``…Protocol`` interfaces, so a
rename breaks CI instead of the drop-in.

STABILITY GUARANTEE
-------------------
These names are the consumed public contract. Renaming or removing one is a
breaking change for `homematicip_local` and the daemon shim — coordinate it
(major bump + migration guide), do not "fix" the test silently.

See ``docs/drop-in-optimizations.md`` (P2 — consumed coordinator surface).
"""

import pytest

from aiohomematic.backend_detection import detect_backend
from aiohomematic.central import CentralConfig, CentralUnit, DeviceQueryFacade
from aiohomematic.central.coordinators import ClientCoordinator, DeviceCoordinator, HubCoordinator, LinkCoordinator
from aiohomematic.central.events import EventBus, SubscriptionGroup
from aiohomematic.client import AioJsonRpcAioHttpClient, InterfaceConfig
from aiohomematic.const import SystemInformation
from aiohomematic.interfaces import (
    CentralProtocol,
    ClientProviderProtocol,
    DeviceQueryFacadeProtocol,
    HubDataFetcherProtocol,
    HubDataPointManagerProtocol,
    LinkFacadeProtocol,
)

# Consumed member surface, grouped by the class that exposes it. Members are
# resolved at the class level (descriptors / methods / properties), so the
# check never constructs a central or invokes a getter.
_CONSUMED_SURFACE: dict[type, tuple[str, ...]] = {
    CentralUnit: ("start", "stop", "state", "name", "model", "version", "url", "system_information"),
    # HA calls event_bus.create_subscription_group(...) and then drives the
    # returned SubscriptionGroup (subscribe / unsubscribe_all).
    EventBus: ("create_subscription_group", "subscribe"),
    SubscriptionGroup: ("subscribe", "unsubscribe_all"),
    DeviceQueryFacade: ("get_data_points", "get_event_groups", "get_state_paths", "get_un_ignore_candidates"),
    DeviceCoordinator: (
        "get_device",
        "delete_device",
        "add_new_devices_manually",
        "get_virtual_remotes",
        "refresh_firmware_data",
        "create_central_links",
        "remove_central_links",
        "devices",
    ),
    HubCoordinator: (
        "get_hub_data_points",
        "get_system_variable",
        "set_system_variable",
        "fetch_program_data",
        "fetch_sysvar_data",
        "install_mode_dps",
        "connectivity_dps",
        "alarm_messages_dp",
        "service_messages_dp",
        "inbox_dp",
        "update_dp",
        "metrics_dps",
    ),
    ClientCoordinator: ("has_client", "has_clients", "clients"),
    LinkCoordinator: ("get_device_links", "add_link", "remove_link", "get_linkable_channels"),
    AioJsonRpcAioHttpClient: (
        "get_inbox_devices",
        "accept_device_in_inbox",
        "rename_device",
        "rename_channel",
        "get_service_messages",
        "get_alarm_messages",
        "acknowledge_message",
    ),
    CentralConfig: ("check_config",),
}

_SURFACE_ITEMS: tuple[tuple[type, str], ...] = tuple(
    (cls, member) for cls, members in _CONSUMED_SURFACE.items() for member in members
)

# Classes that must nominally implement a consumed protocol (explicit
# inheritance — checked via the MRO so runtime_checkable data-member protocols
# don't trip ``issubclass``).
_PROTOCOL_CONFORMANCE: tuple[tuple[type, type], ...] = (
    (CentralUnit, CentralProtocol),
    (DeviceQueryFacade, DeviceQueryFacadeProtocol),
    (LinkCoordinator, LinkFacadeProtocol),
    (HubCoordinator, HubDataFetcherProtocol),
    (HubCoordinator, HubDataPointManagerProtocol),
    (ClientCoordinator, ClientProviderProtocol),
)


@pytest.mark.parametrize(
    ("cls", "member"),
    _SURFACE_ITEMS,
    ids=[f"{cls.__name__}.{member}" for cls, member in _SURFACE_ITEMS],
)
def test_consumed_member_present(cls: type, member: str) -> None:
    """Verify each consumed member still exists on the class that exposes it."""
    assert hasattr(cls, member), (
        f"{cls.__name__}.{member} is part of the consumed drop-in contract but is missing. "
        f"Renaming/removing it is a breaking change — see docs/drop-in-optimizations.md."
    )


@pytest.mark.parametrize(
    ("cls", "protocol"),
    _PROTOCOL_CONFORMANCE,
    ids=[f"{cls.__name__}<:{protocol.__name__}" for cls, protocol in _PROTOCOL_CONFORMANCE],
)
def test_class_declares_consumed_protocol(cls: type, protocol: type) -> None:
    """Verify each concrete class explicitly implements its consumed protocol."""
    assert protocol in cls.__mro__, (
        f"{cls.__name__} must explicitly inherit {protocol.__name__} (consumed drop-in contract)."
    )


def test_config_symbols_available() -> None:
    """Verify the configuration entry points the shim needs are importable and usable."""
    assert isinstance(CentralConfig, type)
    assert isinstance(InterfaceConfig, type)
    assert isinstance(SystemInformation, type)
    # detect_backend must recognize the backend (incl. "Loom") for the shim.
    assert callable(detect_backend)
