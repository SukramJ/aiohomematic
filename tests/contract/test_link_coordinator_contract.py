# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for link coordinator class stability.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for link coordinator classes.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. LinkFacadeProtocol methods remain stable
2. DeviceLink fields remain stable
3. LinkableChannel fields remain stable

See ADR-0018 for architectural context.
"""

from __future__ import annotations

from aiohomematic.central.coordinators import DeviceLink, LinkableChannel

# =============================================================================
# Contract: LinkFacadeProtocol Methods
# =============================================================================


class TestLinkFacadeProtocolContract:
    """Contract: LinkFacadeProtocol methods must remain stable."""

    def test_has_add_link_method(self) -> None:
        """Contract: LinkFacadeProtocol has add_link method."""
        from aiohomematic.interfaces import LinkFacadeProtocol

        assert hasattr(LinkFacadeProtocol, "add_link")

    def test_has_get_device_links_method(self) -> None:
        """Contract: LinkFacadeProtocol has get_device_links method."""
        from aiohomematic.interfaces import LinkFacadeProtocol

        assert hasattr(LinkFacadeProtocol, "get_device_links")

    def test_has_get_linkable_channels_method(self) -> None:
        """Contract: LinkFacadeProtocol has get_linkable_channels method."""
        from aiohomematic.interfaces import LinkFacadeProtocol

        assert hasattr(LinkFacadeProtocol, "get_linkable_channels")

    def test_has_remove_link_method(self) -> None:
        """Contract: LinkFacadeProtocol has remove_link method."""
        from aiohomematic.interfaces import LinkFacadeProtocol

        assert hasattr(LinkFacadeProtocol, "remove_link")


# =============================================================================
# Contract: DeviceLink Fields
# =============================================================================


class TestDeviceLinkFieldsContract:
    """Contract: DeviceLink fields must remain stable."""

    def test_has_description(self) -> None:
        """Contract: DeviceLink has description field."""
        link = self._make_link()
        assert hasattr(link, "description")
        assert isinstance(link.description, str)

    def test_has_direction(self) -> None:
        """Contract: DeviceLink has direction field."""
        link = self._make_link()
        assert hasattr(link, "direction")
        assert isinstance(link.direction, str)

    def test_has_flags(self) -> None:
        """Contract: DeviceLink has flags field."""
        link = self._make_link()
        assert hasattr(link, "flags")
        assert isinstance(link.flags, int)

    def test_has_name(self) -> None:
        """Contract: DeviceLink has name field."""
        link = self._make_link()
        assert hasattr(link, "name")
        assert isinstance(link.name, str)

    def test_has_peer_address(self) -> None:
        """Contract: DeviceLink has peer_address field."""
        link = self._make_link()
        assert hasattr(link, "peer_address")
        assert isinstance(link.peer_address, str)

    def test_has_peer_device_model(self) -> None:
        """Contract: DeviceLink has peer_device_model field."""
        link = self._make_link()
        assert hasattr(link, "peer_device_model")
        assert isinstance(link.peer_device_model, str)

    def test_has_peer_device_name(self) -> None:
        """Contract: DeviceLink has peer_device_name field."""
        link = self._make_link()
        assert hasattr(link, "peer_device_name")
        assert isinstance(link.peer_device_name, str)

    def test_has_receiver_address(self) -> None:
        """Contract: DeviceLink has receiver_address field."""
        link = self._make_link()
        assert hasattr(link, "receiver_address")
        assert isinstance(link.receiver_address, str)

    def test_has_receiver_channel_type(self) -> None:
        """Contract: DeviceLink has receiver_channel_type field."""
        link = self._make_link()
        assert hasattr(link, "receiver_channel_type")
        assert isinstance(link.receiver_channel_type, str)

    def test_has_receiver_channel_type_label(self) -> None:
        """Contract: DeviceLink has receiver_channel_type_label field."""
        link = self._make_link()
        assert hasattr(link, "receiver_channel_type_label")
        assert isinstance(link.receiver_channel_type_label, str)

    def test_has_receiver_device_model(self) -> None:
        """Contract: DeviceLink has receiver_device_model field."""
        link = self._make_link()
        assert hasattr(link, "receiver_device_model")
        assert isinstance(link.receiver_device_model, str)

    def test_has_receiver_device_name(self) -> None:
        """Contract: DeviceLink has receiver_device_name field."""
        link = self._make_link()
        assert hasattr(link, "receiver_device_name")
        assert isinstance(link.receiver_device_name, str)

    def test_has_sender_address(self) -> None:
        """Contract: DeviceLink has sender_address field."""
        link = self._make_link()
        assert hasattr(link, "sender_address")
        assert isinstance(link.sender_address, str)

    def test_has_sender_channel_type(self) -> None:
        """Contract: DeviceLink has sender_channel_type field."""
        link = self._make_link()
        assert hasattr(link, "sender_channel_type")
        assert isinstance(link.sender_channel_type, str)

    def test_has_sender_channel_type_label(self) -> None:
        """Contract: DeviceLink has sender_channel_type_label field."""
        link = self._make_link()
        assert hasattr(link, "sender_channel_type_label")
        assert isinstance(link.sender_channel_type_label, str)

    def test_has_sender_device_model(self) -> None:
        """Contract: DeviceLink has sender_device_model field."""
        link = self._make_link()
        assert hasattr(link, "sender_device_model")
        assert isinstance(link.sender_device_model, str)

    def test_has_sender_device_name(self) -> None:
        """Contract: DeviceLink has sender_device_name field."""
        link = self._make_link()
        assert hasattr(link, "sender_device_name")
        assert isinstance(link.sender_device_name, str)

    def _make_link(self) -> DeviceLink:
        """Create a DeviceLink with all fields."""
        return DeviceLink(
            sender_address="VCU0000001:1",
            receiver_address="VCU0000002:1",
            name="Test Link",
            description="test",
            flags=0,
            sender_device_name="Dev1",
            sender_device_model="HM-LC-Sw1",
            sender_channel_type="SWITCH",
            sender_channel_type_label="Switch",
            receiver_device_name="Dev2",
            receiver_device_model="HM-LC-Dim1",
            receiver_channel_type="DIMMER",
            receiver_channel_type_label="Dimmer",
            peer_address="VCU0000002:1",
            peer_device_name="Dev2",
            peer_device_model="HM-LC-Dim1",
            direction="outgoing",
        )


# =============================================================================
# Contract: LinkableChannel Fields
# =============================================================================


class TestLinkableChannelFieldsContract:
    """Contract: LinkableChannel fields must remain stable."""

    def test_has_address(self) -> None:
        """Contract: LinkableChannel has address field."""
        ch = self._make_channel()
        assert hasattr(ch, "address")
        assert isinstance(ch.address, str)

    def test_has_channel_type(self) -> None:
        """Contract: LinkableChannel has channel_type field."""
        ch = self._make_channel()
        assert hasattr(ch, "channel_type")
        assert isinstance(ch.channel_type, str)

    def test_has_channel_type_label(self) -> None:
        """Contract: LinkableChannel has channel_type_label field."""
        ch = self._make_channel()
        assert hasattr(ch, "channel_type_label")
        assert isinstance(ch.channel_type_label, str)

    def test_has_device_address(self) -> None:
        """Contract: LinkableChannel has device_address field."""
        ch = self._make_channel()
        assert hasattr(ch, "device_address")
        assert isinstance(ch.device_address, str)

    def test_has_device_model(self) -> None:
        """Contract: LinkableChannel has device_model field."""
        ch = self._make_channel()
        assert hasattr(ch, "device_model")
        assert isinstance(ch.device_model, str)

    def test_has_device_name(self) -> None:
        """Contract: LinkableChannel has device_name field."""
        ch = self._make_channel()
        assert hasattr(ch, "device_name")
        assert isinstance(ch.device_name, str)

    def _make_channel(self) -> LinkableChannel:
        """Create a LinkableChannel with all fields."""
        return LinkableChannel(
            address="VCU0000001:1",
            channel_type="SWITCH",
            channel_type_label="Switch",
            device_address="VCU0000001",
            device_name="Test Device",
            device_model="HM-LC-Sw1",
        )
