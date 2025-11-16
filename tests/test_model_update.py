"""
Tests for aiohomematic.model.update.DpUpdate behavior using fakes.

Covers properties, latest_firmware selection, in_progress state, register/unregister
of callbacks, and refresh/update methods.
"""

from __future__ import annotations

from typing import Any

from aiohomematic.const import HMIP_FIRMWARE_UPDATE_IN_PROGRESS_STATES, HMIP_FIRMWARE_UPDATE_READY_STATES, Interface
from aiohomematic.model.update import DpUpdate
from aiohomematic.type_aliases import FirmwareUpdateCallback, UnregisterCallback


class _FakeCentral:
    def __init__(self) -> None:
        self.config = type("Cfg", (), {"central_id": "CentralTest"})()
        self._refreshed: list[str] = []

    async def refresh_firmware_data(self, *, device_address: str) -> None:  # noqa: D401
        """Record that refresh was invoked."""
        self._refreshed.append(device_address)


class _FakeDevice:
    def __init__(self) -> None:
        self.central = _FakeCentral()
        self.address = "ADDR1"
        self.model = "HmIP-XYZ"
        self.name = "My Device"
        self.available = True
        self.firmware = "1.0.0"
        self.firmware_update_state = None
        self.available_firmware = None
        self.interface = Interface.BIDCOS_RF
        self._callbacks: list[FirmwareUpdateCallback] = []

    def register_firmware_update_callback(self, *, cb: FirmwareUpdateCallback) -> UnregisterCallback:
        self._callbacks.append(cb)

        def _unregister() -> None:
            self._callbacks.remove(cb)

        return _unregister

    def unregister_firmware_update_callback(self, *, cb: FirmwareUpdateCallback) -> None:
        if cb in self._callbacks:
            self._callbacks.remove(cb)

    async def update_firmware(self, *, refresh_after_update_intervals: tuple[int, ...]) -> bool:  # noqa: D401
        """Pretend to start an update and return success."""
        return True


class TestUpdateDataPoint:
    """Tests for DpUpdate data points."""

    async def test_update_properties_and_latest_firmware_and_in_progress(self) -> None:
        """Test DpUpdate device properties and latest firmware computation."""
        dev = _FakeDevice()
        dp = DpUpdate(device=dev)

        # Basic properties
        assert dp.available is True
        assert dp.firmware == "1.0.0"
        assert dp.firmware_update_state is None

        # latest_firmware for BidCos returns available_firmware if set
        dev.available_firmware = "1.1.0"
        assert dp.latest_firmware == "1.1.0"

        # HMIP: in_progress depends on state, latest depends on READY states
        dev.interface = Interface.HMIP_RF
        dev.firmware_update_state = next(iter(HMIP_FIRMWARE_UPDATE_IN_PROGRESS_STATES))
        assert dp.in_progress is True
        dev.firmware_update_state = next(iter(HMIP_FIRMWARE_UPDATE_READY_STATES))
        dev.available_firmware = "2.0.0"
        assert dp.latest_firmware == "2.0.0"

    async def test_update_register_unregister_and_actions(self, monkeypatch) -> None:
        """Test DpUpdate callback registration and firmware update actions."""
        dev = _FakeDevice()
        dp = DpUpdate(device=dev)

        called: dict[str, Any] = {"count": 0}

        def cb(**kwargs: Any) -> None:  # noqa: D401
            """Execute dummy callback."""
            called["count"] += 1

        unregister = dp.register_data_point_updated_callback(cb=cb, custom_id="CID")
        assert callable(unregister)
        # The device should have the callback stored
        assert dev._callbacks
        unregister()  # remove from device
        assert not dev._callbacks

        # refresh_firmware_data should forward to central and update modified_at
        before = dp.modified_at
        await dp.refresh_firmware_data()
        assert dev.address in dev.central._refreshed
        assert dp.modified_at >= before

        # update_firmware forwards to device
        assert await dp.update_firmware(refresh_after_update_intervals=(1, 2)) is True
