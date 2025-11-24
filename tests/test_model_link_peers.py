"""Tests for link peer functionality on Channel, including change events."""

from __future__ import annotations

import pytest

# We reuse the real central/client factory fixtures from tests/conftest.py
# The randomized Homegear session contains the devices used below.
TEST_DEVICES: set[str] = {"VCU2128127", "VCU6354483"}


class TestChannelLinkPeers:
    """Tests for Channel link peer functionality."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_channel_link_peer_change_detection_and_properties(
        self,
        central_client_factory_with_homegear_client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test link peer change detection and property behavior for single vs multiple peers."""
        central, client, _ = central_client_factory_with_homegear_client
        device = central.get_device(address="VCU2128127")
        ch = device.get_channel(channel_address=f"{device.address}:1")

        # Force transmitter condition
        ch._link_source_categories = True  # type: ignore[attr-defined]

        # Sequence of returns: first single, then same (no event), then multiple (event)
        seq = [
            (f"{device.address}:2",),
            (f"{device.address}:2",),
            (f"{device.address}:2", f"{device.address}:3"),
        ]

        async def _fake_get_link_peers(*, address: str):  # noqa: D401, ARG001
            # Pop from the sequence until exhausted; then keep returning last
            if seq:
                return seq.pop(0)
            return (f"{device.address}:2",)

        monkeypatch.setattr(client, "get_link_peers", _fake_get_link_peers, raising=False)

        calls: list[str] = []

        def _on_changed() -> None:
            calls.append("changed")

        ch.subscribe_to_link_peer_changed(handler=_on_changed)

        # 1st init: should emit
        await ch.init_link_peer()
        await central.looper.block_till_done()
        assert calls == ["changed"]
        assert ch.link_peer_addresses == (f"{device.address}:2",)
        assert len(ch.link_peer_channels) == 1

        # 2nd init with same data: no additional emit
        await ch.init_link_peer()
        await central.looper.block_till_done()
        assert calls == ["changed"]

        # 3rd init with changed peers (multiple): should emit
        await ch.init_link_peer()
        await central.looper.block_till_done()
        assert calls == ["changed", "changed"]

        # With multiple peers: property returns a tuple and peer channel cannot be resolved
        addr = ch.link_peer_addresses
        assert isinstance(addr, tuple) and len(addr) == 2
        assert len(ch.link_peer_channels) == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_channel_link_peer_initialization_and_events(
        self,
        central_client_factory_with_homegear_client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test link peer address loading and change event emission on initialization."""
        central, client, _ = central_client_factory_with_homegear_client
        device = central.get_device(address="VCU2128127")
        # Use channel 1, which exists for this device in the test dataset
        ch = device.get_channel(channel_address=f"{device.address}:1")

        # Force transmitter condition to ensure init_link_peer tries to fetch peers
        ch._link_source_categories = True  # type: ignore[attr-defined]

        # Prepare a deterministic get_link_peers implementation
        peer_addr_single = f"{device.address}:2"

        async def _fake_get_link_peers(*, address: str):  # noqa: D401, ARG001
            return (peer_addr_single,)

        monkeypatch.setattr(client, "get_link_peers", _fake_get_link_peers, raising=False)

        calls: list[str] = []

        def _on_changed() -> None:
            calls.append("changed")

        unreg = ch.subscribe_to_link_peer_changed(handler=_on_changed)

        # Trigger init
        await ch.init_link_peer()
        await central.looper.block_till_done()

        # Ensure callback fired once and addresses are set
        assert calls == ["changed"]
        assert ch.link_peer_addresses == (peer_addr_single,)

        # Exactly one peer => channel should resolve
        peer_ch = ch.link_peer_channels[0]
        assert peer_ch is not None
        assert peer_ch.address == peer_addr_single

        # Cleanup callback
        if unreg:
            unreg()
