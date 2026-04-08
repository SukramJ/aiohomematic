# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Link coordinator for device direct link management.

This module provides the LinkCoordinator, a high-level facade
for listing, creating, and removing direct links between device channels,
as well as discovering linkable channel candidates.

The coordinator encapsulates link business logic (deduplication, enrichment,
role-based filtering) behind a clean, consumer-friendly interface.

Public API of this module is defined by __all__.
"""

from dataclasses import dataclass
import inspect
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohomematic.ccu_translations import get_channel_type_translation
from aiohomematic.const import LINKABLE_INTERFACES, ParamsetKey
from aiohomematic.exceptions import BaseHomematicException
from aiohomematic.interfaces.central import LinkFacadeProtocol
from aiohomematic.support.address import get_device_address
from aiohomematic.support.text_utils import fix_xml_rpc_encoding

if TYPE_CHECKING:
    from aiohomematic.central.device_registry import DeviceRegistry

_LOGGER: Final = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DeviceLink:
    """Enriched direct link between two channels."""

    sender_address: str
    """Sender channel address."""

    receiver_address: str
    """Receiver channel address."""

    name: str
    """Link name."""

    description: str
    """Link description."""

    flags: int
    """Link flags."""

    sender_device_name: str
    """Name of the sender device."""

    sender_device_model: str
    """Model of the sender device."""

    sender_channel_type: str
    """Channel type of the sender channel."""

    sender_channel_type_label: str
    """Translated label of the sender channel type."""

    sender_channel_name: str
    """User-defined name of the sender channel."""

    receiver_device_name: str
    """Name of the receiver device."""

    receiver_device_model: str
    """Model of the receiver device."""

    receiver_channel_type: str
    """Channel type of the receiver channel."""

    receiver_channel_type_label: str
    """Translated label of the receiver channel type."""

    receiver_channel_name: str
    """User-defined name of the receiver channel."""

    peer_address: str
    """Address of the peer channel (remote end)."""

    peer_device_name: str
    """Name of the peer device."""

    peer_device_model: str
    """Model of the peer device."""

    direction: str
    """Direction relative to the queried device: 'outgoing' or 'incoming'."""


@dataclass(frozen=True, slots=True)
class LinkableChannel:
    """Channel candidate for linking."""

    address: str
    """Channel address."""

    channel_type: str
    """Channel type name."""

    channel_type_label: str
    """Translated label of the channel type."""

    channel_name: str
    """User-defined name of the channel."""

    device_address: str
    """Address of the owning device."""

    device_name: str
    """Name of the owning device."""

    device_model: str
    """Model of the owning device."""


class LinkCoordinator(LinkFacadeProtocol):
    """
    High-level facade for device link management operations.

    Provides clean access to link listing, linkable channel discovery,
    and link creation/removal without exposing internal coordinator structure.
    Intended for consumption by configuration UIs and third-party integrations.
    """

    __slots__ = ("_device_registry",)

    def __init__(self, *, device_registry: DeviceRegistry) -> None:
        """Initialize the link coordinator."""
        self._device_registry: Final = device_registry

    async def add_link(
        self,
        *,
        sender_channel_address: str,
        receiver_channel_address: str,
        name: str = "",
        description: str = "created by HA",
    ) -> bool:
        """Create a direct link between two channels."""
        sender_device_addr = get_device_address(address=sender_channel_address)
        if (device := self._device_registry.get_device(address=sender_device_addr)) is None:
            return False

        effective_name = name or f"{sender_channel_address} -> {receiver_channel_address}"

        try:
            await device.client.add_link(
                sender_address=sender_channel_address,
                receiver_address=receiver_channel_address,
                name=effective_name,
                description=description,
            )
        except BaseHomematicException:
            _LOGGER.exception(  # i18n-log: ignore
                "ADD_LINK: Failed to add link %s -> %s",
                sender_channel_address,
                receiver_channel_address,
            )
            return False
        return True

    async def get_device_links(
        self,
        *,
        device_address: str,
        locale: str = "en",
    ) -> tuple[DeviceLink, ...]:
        """Return all enriched direct links for a device."""
        if (device := self._device_registry.get_device(address=device_address)) is None:
            return ()

        if device.interface not in LINKABLE_INTERFACES:
            return ()

        links: list[DeviceLink] = []
        seen: set[tuple[str, str]] = set()

        for channel in device.channels.values():
            try:
                raw_links: Any = await device.client.get_links(channel_address=channel.address, flags=0)
            except BaseHomematicException:
                continue

            if not isinstance(raw_links, list):
                continue

            for link_info in raw_links:
                sender_addr: str = link_info.get("SENDER", "")
                receiver_addr: str = link_info.get("RECEIVER", "")
                if not sender_addr or not receiver_addr:
                    continue

                # Deduplicate
                if (key := (sender_addr, receiver_addr)) in seen:
                    continue
                seen.add(key)

                # Determine direction relative to current device
                is_sender = sender_addr.startswith(device_address)

                # Resolve peer device
                peer_addr = receiver_addr if is_sender else sender_addr
                peer_device_addr = get_device_address(address=peer_addr)
                peer_device = self._device_registry.get_device(address=peer_device_addr)

                # Resolve sender and receiver channels for type info
                sender_device_addr = get_device_address(address=sender_addr)
                sender_dev = device if sender_device_addr == device.address else peer_device
                sender_channel = sender_dev.get_channel(channel_address=sender_addr) if sender_dev else None

                receiver_device_addr = get_device_address(address=receiver_addr)
                receiver_dev = device if receiver_device_addr == device.address else peer_device
                receiver_channel = receiver_dev.get_channel(channel_address=receiver_addr) if receiver_dev else None

                links.append(
                    DeviceLink(
                        sender_address=sender_addr,
                        receiver_address=receiver_addr,
                        name=fix_xml_rpc_encoding(text=link_info.get("NAME", "")),
                        description=fix_xml_rpc_encoding(text=link_info.get("DESCRIPTION", "")),
                        flags=link_info.get("FLAGS", 0),
                        sender_device_name=(
                            device.name if is_sender else (peer_device.name if peer_device else peer_device_addr)
                        ),
                        sender_device_model=(device.model if is_sender else (peer_device.model if peer_device else "")),
                        sender_channel_type=(sender_channel.type_name if sender_channel else ""),
                        sender_channel_type_label=(
                            get_channel_type_translation(channel_type=sender_channel.type_name, locale=locale)
                            or sender_channel.type_name
                        )
                        if sender_channel
                        else "",
                        sender_channel_name=sender_channel.name if sender_channel else "",
                        receiver_device_name=(
                            device.name if not is_sender else (peer_device.name if peer_device else peer_device_addr)
                        ),
                        receiver_device_model=(
                            device.model if not is_sender else (peer_device.model if peer_device else "")
                        ),
                        receiver_channel_type=(receiver_channel.type_name if receiver_channel else ""),
                        receiver_channel_type_label=(
                            get_channel_type_translation(channel_type=receiver_channel.type_name, locale=locale)
                            or receiver_channel.type_name
                        )
                        if receiver_channel
                        else "",
                        receiver_channel_name=receiver_channel.name if receiver_channel else "",
                        peer_address=peer_addr,
                        peer_device_name=(peer_device.name if peer_device else peer_device_addr),
                        peer_device_model=peer_device.model if peer_device else "",
                        direction="outgoing" if is_sender else "incoming",
                    )
                )

        return tuple(links)

    async def get_link_info(
        self,
        *,
        sender_address: str,
        receiver_address: str,
    ) -> dict[str, Any]:
        """Get link info (name and description) for a link between two channels."""
        if (device := self._device_registry.get_device(address=sender_address)) is None:
            return {}
        return await device.client.get_link_info(
            interface=device.interface,
            sender_address=sender_address,
            receiver_address=receiver_address,
        )

    def get_linkable_channels(
        self,
        *,
        interface_id: str,
        source_channel_address: str,
        role: str,
        locale: str = "en",
    ) -> tuple[LinkableChannel, ...]:
        """Return channels compatible for linking with the given channel."""
        candidates: list[LinkableChannel] = []

        for device in self._device_registry.devices:
            if device.interface_id != interface_id:
                continue
            if device.interface not in LINKABLE_INTERFACES:
                continue

            for channel in device.channels.values():
                # Skip the source channel itself
                if channel.address == source_channel_address:
                    continue

                # Check if this channel has LINK in its paramset keys
                if not (any(pk == ParamsetKey.LINK for pk in channel.paramset_keys)):
                    continue

                if role == "sender":
                    # Source is sender — look for receivers (channels with target roles)
                    if not channel.link_peer_target_categories:
                        continue
                elif not channel.link_peer_source_categories:
                    # Source is receiver — look for senders (channels with source roles)
                    continue

                candidates.append(
                    LinkableChannel(
                        address=channel.address,
                        channel_type=channel.type_name,
                        channel_type_label=get_channel_type_translation(
                            channel_type=channel.type_name,
                            locale=locale,
                        )
                        or channel.type_name,
                        channel_name=channel.name,
                        device_address=device.address,
                        device_name=device.name or device.address,
                        device_model=device.model,
                    )
                )

        return tuple(candidates)

    async def remove_link(
        self,
        *,
        sender_channel_address: str,
        receiver_channel_address: str,
    ) -> bool:
        """Remove a direct link between two channels."""
        sender_device_addr = get_device_address(address=sender_channel_address)
        if (device := self._device_registry.get_device(address=sender_device_addr)) is None:
            return False

        try:
            await device.client.remove_link(
                sender_address=sender_channel_address,
                receiver_address=receiver_channel_address,
            )
        except BaseHomematicException:
            _LOGGER.exception(  # i18n-log: ignore
                "REMOVE_LINK: Failed to remove link %s -> %s",
                sender_channel_address,
                receiver_channel_address,
            )
            return False
        return True

    async def set_link_info(
        self,
        *,
        sender_address: str,
        receiver_address: str,
        name: str,
        description: str,
    ) -> bool:
        """Set link info (name and description) for a link between two channels."""
        if (device := self._device_registry.get_device(address=sender_address)) is None:
            return False
        return await device.client.set_link_info(
            interface=device.interface,
            sender_address=sender_address,
            receiver_address=receiver_address,
            name=name,
            description=description,
        )


__all__ = tuple(
    sorted(
        name
        for name, obj in globals().items()
        if not name.startswith("_")
        and (name.isupper() or inspect.isfunction(obj) or inspect.isclass(obj))
        and getattr(obj, "__module__", __name__) == __name__
    )
)
