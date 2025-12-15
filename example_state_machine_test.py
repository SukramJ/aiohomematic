"""
State Machine Test Example for aiohomematic.

This script tests the Central State Machine, Health Tracking, and Recovery
Coordinator with a real CCU instance. It monitors state transitions and
health changes in real-time.

Usage:
    1. Update CCU_HOST, CCU_USERNAME, CCU_PASSWORD below
    2. Run: python example_state_machine_test.py
    3. When prompted, restart your CCU to test recovery behavior
    4. Press Ctrl+C to stop

The script will display:
- Central state transitions (STARTING -> INITIALIZING -> RUNNING, etc.)
- Client state transitions for each interface
- Health score changes
- Recovery attempts and results
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
import logging
import os
import signal
import sys
from typing import TYPE_CHECKING

from aiohomematic import const
from aiohomematic.central import CentralConfig, CentralUnit
from aiohomematic.central.event_bus import CentralStateChangedEvent, ClientStateChangedEvent, SystemEventTypeData
from aiohomematic.client import InterfaceConfig
from aiohomematic.const import CentralState, ClientState

if TYPE_CHECKING:
    pass

# Configure logging - show INFO for our messages, DEBUG for aiohomematic internals
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d [%(levelname)8s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
_LOGGER = logging.getLogger(__name__)

# Reduce noise from some modules
logging.getLogger("aiohomematic.client.json_rpc").setLevel(logging.INFO)
logging.getLogger("aiohomematic.client.rpc_proxy").setLevel(logging.INFO)

# =============================================================================
# CONFIGURATION - Set via environment variables or .env file
# =============================================================================
# Required environment variables:
#   CCU_HOST     - Your CCU IP address (e.g., 192.168.178.116)
#   CCU_USERNAME - Your CCU username (e.g., Admin)
#   CCU_PASSWORD - Your CCU password
#
# Optional:
#   CCU_PORT_HMIP    - HmIP-RF port (default: 2010)
#   CCU_PORT_BIDCOS  - BidCos-RF port (default: 2001)
#   CCU_CALLBACK_PORT - XML-RPC callback port (default: 54323)
#
# You can set these using: source script/set_ccu_env.sh
# =============================================================================

CCU_HOST = os.environ.get("CCU_HOST", "")
CCU_USERNAME = os.environ.get("CCU_USERNAME", "")
CCU_PASSWORD = os.environ.get("CCU_PASSWORD", "")
CCU_PORT_HMIP = int(os.environ.get("CCU_PORT_HMIP", "2010"))
CCU_PORT_BIDCOS = int(os.environ.get("CCU_PORT_BIDCOS", "2001"))
CCU_CALLBACK_PORT = int(os.environ.get("CCU_CALLBACK_PORT", "54323"))


def _check_env() -> bool:
    """Check if required environment variables are set."""
    missing = []
    if not CCU_HOST:
        missing.append("CCU_HOST")
    if not CCU_USERNAME:
        missing.append("CCU_USERNAME")
    if not CCU_PASSWORD:
        missing.append("CCU_PASSWORD")

    if missing:
        print("\n" + "=" * 70)  # noqa: T201
        print("ERROR: Missing required environment variables")  # noqa: T201
        print("=" * 70)  # noqa: T201
        print(f"Missing: {', '.join(missing)}")  # noqa: T201
        print()  # noqa: T201
        print("Set them using:")  # noqa: T201
        print("  export CCU_HOST='192.168.178.116'")  # noqa: T201
        print("  export CCU_USERNAME='Admin'")  # noqa: T201
        print("  export CCU_PASSWORD='your_password'")  # noqa: T201
        print()  # noqa: T201
        print("Or use the helper script:")  # noqa: T201
        print("  source script/set_ccu_env.sh")  # noqa: T201
        print("=" * 70 + "\n")  # noqa: T201
        return False
    return True


# =============================================================================


class StateMachineTestMonitor:
    """
    Monitor for testing state machines with a real CCU.

    This class:
    - Subscribes to all state change events
    - Displays state transitions in real-time
    - Tracks health scores and recovery attempts
    - Provides a summary on exit
    """

    def __init__(self) -> None:
        """Initialize the monitor."""
        self.central: CentralUnit | None = None
        self.start_time = datetime.now()
        self.shutdown_event = asyncio.Event()

        # Track state history
        self.central_state_history: list[tuple[datetime, CentralState, CentralState, str]] = []
        self.client_state_history: list[tuple[datetime, str, ClientState, ClientState]] = []
        self.health_snapshots: list[tuple[datetime, float, dict[str, float]]] = []

        # Counters
        self.event_count = 0
        self.reconnect_count = 0

    def _on_central_state_changed(self, event: CentralStateChangedEvent) -> None:
        """Handle central state changes."""
        self.central_state_history.append((event.timestamp, event.old_state, event.new_state, event.reason))
        self._print_state_change(
            component="CENTRAL",
            old_state=event.old_state.value,
            new_state=event.new_state.value,
            reason=event.reason,
        )

        # Take health snapshot on significant state changes
        if event.new_state in (CentralState.RUNNING, CentralState.DEGRADED, CentralState.FAILED):
            self._capture_health_snapshot()

    def _on_client_state_changed(self, event: ClientStateChangedEvent) -> None:
        """Handle client state changes."""
        self.client_state_history.append((event.timestamp, event.interface_id, event.old_state, event.new_state))

        # Extract short interface name
        short_name = event.interface_id.split("-")[-1] if "-" in event.interface_id else event.interface_id

        self._print_state_change(
            component=f"CLIENT:{short_name}",
            old_state=event.old_state.value,
            new_state=event.new_state.value,
        )

        if event.new_state == ClientState.RECONNECTING:
            self.reconnect_count += 1

    def _on_system_event(self, event: SystemEventTypeData) -> None:
        """Handle system events."""
        self.event_count += 1
        if event.system_event in (
            const.SystemEventType.NEW_DEVICES,
            const.SystemEventType.DEVICES_CREATED,
            const.SystemEventType.DELETE_DEVICES,
        ):
            _LOGGER.info(
                "\033[33m[SYSTEM EVENT]\033[0m %s (data keys: %s)",
                event.system_event.value,
                list(event.data.keys()) if event.data else "none",
            )

    def _print_state_change(
        self,
        *,
        component: str,
        old_state: str,
        new_state: str,
        reason: str = "",
    ) -> None:
        """Print a formatted state change message."""
        # Color codes for different states
        colors = {
            "STARTING": "\033[90m",  # Gray
            "INITIALIZING": "\033[33m",  # Yellow
            "INITIALIZED": "\033[33m",  # Yellow
            "CONNECTING": "\033[33m",  # Yellow
            "CONNECTED": "\033[32m",  # Green
            "RUNNING": "\033[32m",  # Green
            "DEGRADED": "\033[35m",  # Magenta
            "RECOVERING": "\033[36m",  # Cyan
            "RECONNECTING": "\033[36m",  # Cyan
            "DISCONNECTED": "\033[31m",  # Red
            "FAILED": "\033[31m",  # Red
            "STOPPING": "\033[90m",  # Gray
            "STOPPED": "\033[90m",  # Gray
            "CREATED": "\033[90m",  # Gray
        }
        reset = "\033[0m"

        old_color = colors.get(old_state, "")
        new_color = colors.get(new_state, "")

        reason_str = f" ({reason})" if reason else ""
        _LOGGER.info(
            "\033[1m[%s]\033[0m %s%s%s -> %s%s%s%s",
            component,
            old_color,
            old_state,
            reset,
            new_color,
            new_state,
            reset,
            reason_str,
        )

    def _capture_health_snapshot(self) -> None:
        """Capture current health state."""
        if self.central is None:
            return

        try:
            # Access health tracker if available
            health_tracker = getattr(self.central, "_health_tracker", None)
            if health_tracker is None:
                return

            central_health = health_tracker.health
            overall_score = central_health.overall_health_score

            client_scores = {}
            for iid, conn_health in central_health.client_health.items():
                short_name = iid.split("-")[-1] if "-" in iid else iid
                client_scores[short_name] = conn_health.health_score

            self.health_snapshots.append((datetime.now(), overall_score, client_scores))

            _LOGGER.info(
                "\033[34m[HEALTH]\033[0m Overall: %.1f%% | %s",
                overall_score * 100,
                " | ".join(f"{k}: {v * 100:.0f}%" for k, v in client_scores.items()),
            )
        except Exception as ex:
            _LOGGER.debug("Could not capture health snapshot: %s", ex)

    def _print_summary(self) -> None:
        """Print a summary of the test session."""
        duration = (datetime.now() - self.start_time).total_seconds()

        print("\n" + "=" * 70)  # noqa: T201
        print("STATE MACHINE TEST SUMMARY")  # noqa: T201
        print("=" * 70)  # noqa: T201
        print(f"Duration: {duration:.1f} seconds")  # noqa: T201
        print(f"Total events received: {self.event_count}")  # noqa: T201
        print(f"Reconnection attempts: {self.reconnect_count}")  # noqa: T201
        print()  # noqa: T201

        # Central state transitions
        print("Central State Transitions:")  # noqa: T201
        print("-" * 40)  # noqa: T201
        for ts, old_state, new_state, reason in self.central_state_history:
            print(f"  {ts.strftime('%H:%M:%S')} {old_state.value:15} -> {new_state.value:15} {reason}")  # noqa: T201

        # Client state transitions (grouped by interface)
        print("\nClient State Transitions:")  # noqa: T201
        print("-" * 40)  # noqa: T201
        interfaces: dict[str, list[tuple[datetime, ClientState, ClientState]]] = {}
        for ts, iid, client_old, client_new in self.client_state_history:
            short_name = iid.split("-")[-1] if "-" in iid else iid
            if short_name not in interfaces:
                interfaces[short_name] = []
            interfaces[short_name].append((ts, client_old, client_new))

        for iface, transitions in interfaces.items():
            print(f"  {iface}:")  # noqa: T201
            for ts, client_old, client_new in transitions:
                print(f"    {ts.strftime('%H:%M:%S')} {client_old.value:15} -> {client_new.value}")  # noqa: T201

        # Health snapshots
        if self.health_snapshots:
            print("\nHealth Snapshots:")  # noqa: T201
            print("-" * 40)  # noqa: T201
            for ts, overall, client_scores in self.health_snapshots:
                client_str = " | ".join(f"{k}: {v * 100:.0f}%" for k, v in client_scores.items())
                print(f"  {ts.strftime('%H:%M:%S')} Overall: {overall * 100:.1f}% | {client_str}")  # noqa: T201

        print("=" * 70)  # noqa: T201

    async def run(self) -> None:
        """Run the test monitor."""
        central_name = "ccu-dev"

        # Configure interfaces
        interface_configs = {
            InterfaceConfig(
                central_name=central_name,
                interface=const.Interface.HMIP_RF,
                port=CCU_PORT_HMIP,
            ),
            InterfaceConfig(
                central_name=central_name,
                interface=const.Interface.BIDCOS_RF,
                port=CCU_PORT_BIDCOS,
            ),
        }

        # Create central
        self.central = CentralConfig(
            name=central_name,
            host=CCU_HOST,
            username=CCU_USERNAME,
            password=CCU_PASSWORD,
            central_id="state-machine-test",
            storage_directory="aiohomematic_storage",
            interface_configs=interface_configs,
            callback_port_xml_rpc=CCU_CALLBACK_PORT,
        ).create_central()

        # Subscribe to events
        event_bus = self.central.event_bus

        event_bus.subscribe(
            event_type=CentralStateChangedEvent,
            event_key=None,
            handler=self._on_central_state_changed,
        )

        event_bus.subscribe(
            event_type=ClientStateChangedEvent,
            event_key=None,
            handler=self._on_client_state_changed,
        )

        event_bus.subscribe(
            event_type=SystemEventTypeData,
            event_key=None,
            handler=self._on_system_event,
        )

        print("\n" + "=" * 70)  # noqa: T201
        print("STATE MACHINE TEST - Starting")  # noqa: T201
        print("=" * 70)  # noqa: T201
        print(f"CCU Host: {CCU_HOST}")  # noqa: T201
        print(f"Interfaces: HmIP-RF ({CCU_PORT_HMIP}), BidCos-RF ({CCU_PORT_BIDCOS})")  # noqa: T201
        print()  # noqa: T201
        print("Instructions:")  # noqa: T201
        print("  1. Wait for RUNNING state (all clients connected)")  # noqa: T201
        print("  2. Restart your CCU to test recovery behavior")  # noqa: T201
        print("  3. Watch the state transitions and health scores")  # noqa: T201
        print("  4. Press Ctrl+C to stop and see summary")  # noqa: T201
        print("=" * 70 + "\n")  # noqa: T201

        try:
            # Start central
            await self.central.start()

            # Initial health capture
            await asyncio.sleep(2)
            self._capture_health_snapshot()

            # Wait until shutdown
            print("\n--- Monitoring active. Press Ctrl+C to stop ---\n")  # noqa: T201

            # Periodic health check
            while not self.shutdown_event.is_set():
                try:
                    await asyncio.wait_for(self.shutdown_event.wait(), timeout=30.0)
                except TimeoutError:
                    # Periodic health snapshot every 30 seconds
                    self._capture_health_snapshot()

        except asyncio.CancelledError:
            _LOGGER.info("Received shutdown signal")
        finally:
            print("\n--- Shutting down ---\n")  # noqa: T201
            await self.central.stop()
            self._print_summary()

    def request_shutdown(self) -> None:
        """Request graceful shutdown."""
        self.shutdown_event.set()


async def main() -> None:
    """Run the state machine test."""
    monitor = StateMachineTestMonitor()

    # Setup signal handlers
    loop = asyncio.get_running_loop()

    def signal_handler() -> None:
        monitor.request_shutdown()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    await monitor.run()


if __name__ == "__main__":
    if not _check_env():
        sys.exit(1)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
    sys.exit(0)
