# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Test the LinkCoordinator facade."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from aiohomematic.central.coordinators import DeviceLink, LinkableChannel, LinkCoordinator
from aiohomematic.const import Interface, ParamsetKey
from aiohomematic.exceptions import BaseHomematicException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_channel(
    *,
    address: str = "VCU0000001:1",
    type_name: str = "SWITCH",
    paramset_keys: tuple[ParamsetKey, ...] = (ParamsetKey.MASTER, ParamsetKey.VALUES),
    link_peer_source_categories: tuple[str, ...] = (),
    link_peer_target_categories: tuple[str, ...] = (),
) -> MagicMock:
    """Build a mock channel."""
    channel = MagicMock()
    channel.address = address
    channel.type_name = type_name
    channel.paramset_keys = paramset_keys
    channel.link_peer_source_categories = link_peer_source_categories
    channel.link_peer_target_categories = link_peer_target_categories
    return channel


def _make_device(
    *,
    address: str = "VCU0000001",
    name: str = "Test Device",
    model: str = "HM-LC-Sw1-Pl",
    interface: Interface = Interface.HMIP_RF,
    interface_id: str = "ccu-HmIP-RF",
    channels: dict[str, MagicMock] | None = None,
) -> MagicMock:
    """Build a mock device."""
    device = MagicMock()
    device.address = address
    device.name = name
    device.model = model
    device.interface = interface
    device.interface_id = interface_id
    device.channels = channels or {}
    device.client = AsyncMock()

    def get_channel(*, channel_address: str) -> MagicMock | None:
        return device.channels.get(channel_address)

    device.get_channel = get_channel
    return device


def _make_coordinator(
    *,
    devices: list[MagicMock] | None = None,
    device_map: dict[str, MagicMock] | None = None,
) -> tuple[LinkCoordinator, MagicMock]:
    """Build a LinkCoordinator with mocked device registry."""
    registry = MagicMock()
    device_list = devices or []
    type(registry).devices = PropertyMock(return_value=tuple(device_list))

    if device_map is not None:
        registry.get_device.side_effect = lambda *, address: device_map.get(address)
    else:
        d_map = {d.address: d for d in device_list}
        registry.get_device.side_effect = lambda *, address: d_map.get(address)

    coordinator = LinkCoordinator(device_registry=registry)
    return coordinator, registry


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestDeviceLink:
    """Test DeviceLink dataclass."""

    def test_creation(self) -> None:
        """Test DeviceLink can be created."""
        link = DeviceLink(
            sender_address="VCU0000001:1",
            receiver_address="VCU0000002:1",
            name="Test Link",
            description="test",
            flags=0,
            sender_device_name="Dev1",
            sender_device_model="HM-LC-Sw1",
            sender_channel_type="SWITCH",
            sender_channel_type_label="Switch",
            sender_channel_name="Licht Küche",
            receiver_device_name="Dev2",
            receiver_device_model="HM-LC-Dim1",
            receiver_channel_type="DIMMER",
            receiver_channel_type_label="Dimmer",
            receiver_channel_name="Dimmer Flur",
            peer_address="VCU0000002:1",
            peer_device_name="Dev2",
            peer_device_model="HM-LC-Dim1",
            direction="outgoing",
        )
        assert link.sender_address == "VCU0000001:1"
        assert link.direction == "outgoing"
        assert link.sender_channel_name == "Licht Küche"
        assert link.receiver_channel_name == "Dimmer Flur"

    def test_frozen(self) -> None:
        """Test DeviceLink is frozen."""
        link = DeviceLink(
            sender_address="VCU0000001:1",
            receiver_address="VCU0000002:1",
            name="",
            description="",
            flags=0,
            sender_device_name="",
            sender_device_model="",
            sender_channel_type="",
            sender_channel_type_label="",
            sender_channel_name="",
            receiver_device_name="",
            receiver_device_model="",
            receiver_channel_type="",
            receiver_channel_type_label="",
            receiver_channel_name="",
            peer_address="",
            peer_device_name="",
            peer_device_model="",
            direction="outgoing",
        )
        with pytest.raises(AttributeError):
            link.sender_address = "other"  # type: ignore[misc]


class TestLinkableChannel:
    """Test LinkableChannel dataclass."""

    def test_creation(self) -> None:
        """Test LinkableChannel can be created."""
        ch = LinkableChannel(
            address="VCU0000001:1",
            channel_type="SWITCH",
            channel_type_label="Switch",
            channel_name="Licht Küche",
            device_address="VCU0000001",
            device_name="Test Device",
            device_model="HM-LC-Sw1",
        )
        assert ch.address == "VCU0000001:1"
        assert ch.device_model == "HM-LC-Sw1"
        assert ch.channel_name == "Licht Küche"

    def test_frozen(self) -> None:
        """Test LinkableChannel is frozen."""
        ch = LinkableChannel(
            address="VCU0000001:1",
            channel_type="SWITCH",
            channel_type_label="Switch",
            channel_name="",
            device_address="VCU0000001",
            device_name="Test",
            device_model="HM-LC-Sw1",
        )
        with pytest.raises(AttributeError):
            ch.address = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# get_device_links
# ---------------------------------------------------------------------------


class TestGetDeviceLinks:
    """Test LinkCoordinator.get_device_links."""

    @pytest.mark.asyncio
    async def test_deduplicates_links(self) -> None:
        """Test duplicate links are deduplicated."""
        ch1 = _make_channel(address="VCU0000001:1")
        ch2 = _make_channel(address="VCU0000001:2")
        device = _make_device(
            channels={"VCU0000001:1": ch1, "VCU0000001:2": ch2},
        )

        # Both channels return the same link
        link_data = [{"SENDER": "VCU0000001:1", "RECEIVER": "VCU0000002:1", "NAME": "", "DESCRIPTION": "", "FLAGS": 0}]
        device.client.get_links.return_value = link_data

        peer = _make_device(address="VCU0000002")
        coordinator, _ = _make_coordinator(
            devices=[device, peer],
            device_map={device.address: device, peer.address: peer},
        )

        result = await coordinator.get_device_links(device_address="VCU0000001")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_handles_get_links_exception(self) -> None:
        """Test exception during get_links is handled gracefully."""
        ch1 = _make_channel(address="VCU0000001:1")
        device = _make_device(channels={"VCU0000001:1": ch1})
        device.client.get_links.side_effect = BaseHomematicException("connection error")

        coordinator, _ = _make_coordinator(
            devices=[device],
            device_map={device.address: device},
        )

        result = await coordinator.get_device_links(device_address="VCU0000001")
        assert result == ()

    @pytest.mark.asyncio
    async def test_incoming_direction(self) -> None:
        """Test incoming link direction detection."""
        ch1 = _make_channel(address="VCU0000001:1", type_name="DIMMER")
        device = _make_device(
            address="VCU0000001",
            channels={"VCU0000001:1": ch1},
        )

        peer_ch = _make_channel(address="VCU0000002:1", type_name="SWITCH")
        peer_device = _make_device(
            address="VCU0000002",
            name="Sender Device",
            channels={"VCU0000002:1": peer_ch},
        )

        device.client.get_links.return_value = [
            {
                "SENDER": "VCU0000002:1",
                "RECEIVER": "VCU0000001:1",
                "NAME": "",
                "DESCRIPTION": "",
                "FLAGS": 0,
            }
        ]

        coordinator, _ = _make_coordinator(
            devices=[device, peer_device],
            device_map={device.address: device, peer_device.address: peer_device},
        )

        result = await coordinator.get_device_links(device_address="VCU0000001")
        assert len(result) == 1
        assert result[0].direction == "incoming"
        assert result[0].peer_device_name == "Sender Device"

    @pytest.mark.asyncio
    async def test_non_linkable_interface_returns_empty(self) -> None:
        """Test return empty for non-linkable interface."""
        device = _make_device(interface=Interface.CUXD)
        coordinator, _ = _make_coordinator(devices=[device], device_map={device.address: device})
        result = await coordinator.get_device_links(device_address=device.address)
        assert result == ()

    @pytest.mark.asyncio
    async def test_returns_enriched_links(self) -> None:
        """Test return enriched links for a device."""
        ch1 = _make_channel(address="VCU0000001:1", type_name="SWITCH")
        device = _make_device(
            address="VCU0000001",
            channels={"VCU0000001:1": ch1},
        )

        peer_ch = _make_channel(address="VCU0000002:1", type_name="DIMMER")
        peer_device = _make_device(
            address="VCU0000002",
            name="Peer Device",
            model="HM-LC-Dim1",
            channels={"VCU0000002:1": peer_ch},
        )

        device.client.get_links.return_value = [
            {
                "SENDER": "VCU0000001:1",
                "RECEIVER": "VCU0000002:1",
                "NAME": "Link1",
                "DESCRIPTION": "desc",
                "FLAGS": 0,
            }
        ]

        coordinator, _ = _make_coordinator(
            devices=[device, peer_device],
            device_map={device.address: device, peer_device.address: peer_device},
        )

        result = await coordinator.get_device_links(device_address="VCU0000001")
        assert len(result) == 1
        link = result[0]
        assert link.sender_address == "VCU0000001:1"
        assert link.receiver_address == "VCU0000002:1"
        assert link.direction == "outgoing"
        assert link.sender_device_name == "Test Device"
        assert link.peer_device_name == "Peer Device"

    @pytest.mark.asyncio
    async def test_unknown_device_returns_empty(self) -> None:
        """Test return empty for unknown device."""
        coordinator, _registry = _make_coordinator(device_map={})
        result = await coordinator.get_device_links(device_address="UNKNOWN")
        assert result == ()


# ---------------------------------------------------------------------------
# get_linkable_channels
# ---------------------------------------------------------------------------


class TestGetLinkableChannels:
    """Test LinkCoordinator.get_linkable_channels."""

    def test_empty_registry(self) -> None:
        """Test empty device registry returns empty tuple."""
        coordinator, _ = _make_coordinator(devices=[])
        result = coordinator.get_linkable_channels(
            interface_id="ccu-HmIP-RF",
            source_channel_address="VCU0000001:1",
            role="sender",
        )
        assert result == ()

    def test_filters_by_interface_id(self) -> None:
        """Test devices with different interface_id are excluded."""
        ch = _make_channel(
            address="VCU0000002:1",
            paramset_keys=(ParamsetKey.LINK,),
            link_peer_target_categories=("SWITCH",),
        )
        device = _make_device(
            address="VCU0000002",
            interface_id="ccu-BidCos-RF",
            channels={"VCU0000002:1": ch},
        )

        coordinator, _ = _make_coordinator(devices=[device])
        result = coordinator.get_linkable_channels(
            interface_id="ccu-HmIP-RF",
            source_channel_address="VCU0000001:1",
            role="sender",
        )
        assert result == ()

    def test_filters_non_linkable_interface(self) -> None:
        """Test devices with non-linkable interface are excluded."""
        ch = _make_channel(
            address="VCU0000002:1",
            paramset_keys=(ParamsetKey.LINK,),
            link_peer_target_categories=("SWITCH",),
        )
        device = _make_device(
            address="VCU0000002",
            interface=Interface.CUXD,
            interface_id="ccu-HmIP-RF",
            channels={"VCU0000002:1": ch},
        )

        coordinator, _ = _make_coordinator(devices=[device])
        result = coordinator.get_linkable_channels(
            interface_id="ccu-HmIP-RF",
            source_channel_address="VCU0000001:1",
            role="sender",
        )
        assert result == ()

    def test_receiver_role_filters_by_source_categories(self) -> None:
        """Test receiver role requires source categories on candidate."""
        ch_with_source = _make_channel(
            address="VCU0000002:1",
            paramset_keys=(ParamsetKey.LINK,),
            link_peer_source_categories=("SWITCH",),
        )
        ch_without_source = _make_channel(
            address="VCU0000002:2",
            paramset_keys=(ParamsetKey.LINK,),
            link_peer_source_categories=(),
        )
        device = _make_device(
            address="VCU0000002",
            channels={"VCU0000002:1": ch_with_source, "VCU0000002:2": ch_without_source},
        )

        coordinator, _ = _make_coordinator(devices=[device])
        result = coordinator.get_linkable_channels(
            interface_id="ccu-HmIP-RF",
            source_channel_address="VCU0000001:1",
            role="receiver",
        )
        assert len(result) == 1
        assert result[0].address == "VCU0000002:1"

    def test_requires_link_paramset(self) -> None:
        """Test channels without LINK paramset key are excluded."""
        ch = _make_channel(
            address="VCU0000002:1",
            paramset_keys=(ParamsetKey.MASTER, ParamsetKey.VALUES),
            link_peer_target_categories=("SWITCH",),
        )
        device = _make_device(
            address="VCU0000002",
            channels={"VCU0000002:1": ch},
        )

        coordinator, _ = _make_coordinator(devices=[device])
        result = coordinator.get_linkable_channels(
            interface_id="ccu-HmIP-RF",
            source_channel_address="VCU0000001:1",
            role="sender",
        )
        assert result == ()

    def test_returns_matching_channels(self) -> None:
        """Test return matching linkable channels."""
        ch = _make_channel(
            address="VCU0000002:1",
            type_name="DIMMER",
            paramset_keys=(ParamsetKey.LINK,),
            link_peer_target_categories=("SWITCH",),
        )
        device = _make_device(
            address="VCU0000002",
            name="Target Device",
            model="HM-LC-Dim1",
            channels={"VCU0000002:1": ch},
        )

        coordinator, _ = _make_coordinator(devices=[device])
        result = coordinator.get_linkable_channels(
            interface_id="ccu-HmIP-RF",
            source_channel_address="VCU0000001:1",
            role="sender",
        )
        assert len(result) == 1
        assert result[0].address == "VCU0000002:1"
        assert result[0].device_name == "Target Device"
        assert result[0].device_model == "HM-LC-Dim1"

    def test_sender_role_filters_by_target_categories(self) -> None:
        """Test sender role requires target categories on candidate."""
        ch_with_target = _make_channel(
            address="VCU0000002:1",
            paramset_keys=(ParamsetKey.LINK,),
            link_peer_target_categories=("SWITCH",),
        )
        ch_without_target = _make_channel(
            address="VCU0000002:2",
            paramset_keys=(ParamsetKey.LINK,),
            link_peer_target_categories=(),
        )
        device = _make_device(
            address="VCU0000002",
            channels={"VCU0000002:1": ch_with_target, "VCU0000002:2": ch_without_target},
        )

        coordinator, _ = _make_coordinator(devices=[device])
        result = coordinator.get_linkable_channels(
            interface_id="ccu-HmIP-RF",
            source_channel_address="VCU0000001:1",
            role="sender",
        )
        assert len(result) == 1
        assert result[0].address == "VCU0000002:1"

    def test_skips_source_channel(self) -> None:
        """Test source channel itself is excluded."""
        ch = _make_channel(
            address="VCU0000001:1",
            paramset_keys=(ParamsetKey.LINK,),
            link_peer_target_categories=("SWITCH",),
        )
        device = _make_device(
            address="VCU0000001",
            channels={"VCU0000001:1": ch},
        )

        coordinator, _ = _make_coordinator(devices=[device])
        result = coordinator.get_linkable_channels(
            interface_id="ccu-HmIP-RF",
            source_channel_address="VCU0000001:1",
            role="sender",
        )
        assert result == ()


# ---------------------------------------------------------------------------
# add_link
# ---------------------------------------------------------------------------


class TestAddLink:
    """Test LinkCoordinator.add_link."""

    @pytest.mark.asyncio
    async def test_delegates_to_client(self) -> None:
        """Test delegation to client add_link."""
        device = _make_device(address="VCU0000001")
        coordinator, _ = _make_coordinator(
            devices=[device],
            device_map={device.address: device},
        )

        result = await coordinator.add_link(
            sender_channel_address="VCU0000001:1",
            receiver_channel_address="VCU0000002:1",
            name="My Link",
            description="test desc",
        )
        assert result is True
        device.client.add_link.assert_called_once_with(
            sender_address="VCU0000001:1",
            receiver_address="VCU0000002:1",
            name="My Link",
            description="test desc",
        )

    @pytest.mark.asyncio
    async def test_exception_returns_false(self) -> None:
        """Test exception during add_link returns False."""
        device = _make_device(address="VCU0000001")
        device.client.add_link.side_effect = BaseHomematicException("fail")
        coordinator, _ = _make_coordinator(
            devices=[device],
            device_map={device.address: device},
        )

        result = await coordinator.add_link(
            sender_channel_address="VCU0000001:1",
            receiver_channel_address="VCU0000002:1",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_generates_default_name(self) -> None:
        """Test empty name generates default."""
        device = _make_device(address="VCU0000001")
        coordinator, _ = _make_coordinator(
            devices=[device],
            device_map={device.address: device},
        )

        await coordinator.add_link(
            sender_channel_address="VCU0000001:1",
            receiver_channel_address="VCU0000002:1",
        )
        device.client.add_link.assert_called_once_with(
            sender_address="VCU0000001:1",
            receiver_address="VCU0000002:1",
            name="VCU0000001:1 -> VCU0000002:1",
            description="created by HA",
        )

    @pytest.mark.asyncio
    async def test_unknown_device_returns_false(self) -> None:
        """Test return False for unknown sender device."""
        coordinator, _ = _make_coordinator(device_map={})
        result = await coordinator.add_link(
            sender_channel_address="UNKNOWN:1",
            receiver_channel_address="VCU0000002:1",
        )
        assert result is False


# ---------------------------------------------------------------------------
# remove_link
# ---------------------------------------------------------------------------


class TestRemoveLink:
    """Test LinkCoordinator.remove_link."""

    @pytest.mark.asyncio
    async def test_delegates_to_client(self) -> None:
        """Test delegation to client remove_link."""
        device = _make_device(address="VCU0000001")
        coordinator, _ = _make_coordinator(
            devices=[device],
            device_map={device.address: device},
        )

        result = await coordinator.remove_link(
            sender_channel_address="VCU0000001:1",
            receiver_channel_address="VCU0000002:1",
        )
        assert result is True
        device.client.remove_link.assert_called_once_with(
            sender_address="VCU0000001:1",
            receiver_address="VCU0000002:1",
        )

    @pytest.mark.asyncio
    async def test_exception_returns_false(self) -> None:
        """Test exception during remove_link returns False."""
        device = _make_device(address="VCU0000001")
        device.client.remove_link.side_effect = BaseHomematicException("fail")
        coordinator, _ = _make_coordinator(
            devices=[device],
            device_map={device.address: device},
        )

        result = await coordinator.remove_link(
            sender_channel_address="VCU0000001:1",
            receiver_channel_address="VCU0000002:1",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_unknown_device_returns_false(self) -> None:
        """Test return False for unknown sender device."""
        coordinator, _ = _make_coordinator(device_map={})
        result = await coordinator.remove_link(
            sender_channel_address="UNKNOWN:1",
            receiver_channel_address="VCU0000002:1",
        )
        assert result is False


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """Test LinkCoordinator satisfies LinkFacadeProtocol."""

    def test_is_instance_of_protocol(self) -> None:
        """Test LinkCoordinator is a LinkFacadeProtocol instance."""
        from aiohomematic.interfaces import LinkFacadeProtocol

        coordinator, _ = _make_coordinator()
        assert isinstance(coordinator, LinkFacadeProtocol)
