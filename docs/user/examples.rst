Examples
========

This page provides examples of common usage patterns.

Reading Device Values
---------------------

.. code-block:: python

    async def read_temperature(central, device_address):
        """Read temperature from a thermostat."""
        device = central.get_device(address=device_address)
        if not device:
            return None

        # Get temperature data point
        temp_dp = device.get_data_point(
            channel_address=f"{device_address}:1",
            parameter="ACTUAL_TEMPERATURE"
        )

        return temp_dp.value if temp_dp else None

Controlling Devices
-------------------

.. code-block:: python

    async def set_thermostat(central, device_address, temperature):
        """Set target temperature for a thermostat."""
        device = central.get_device(address=device_address)
        if not device:
            return False

        # Get setpoint data point
        setpoint_dp = device.get_data_point(
            channel_address=f"{device_address}:1",
            parameter="SET_TEMPERATURE"
        )

        if setpoint_dp and setpoint_dp.is_writable:
            await setpoint_dp.send_value(temperature)
            return True

        return False

Event Handling
--------------

.. code-block:: python

    from aiohomematic.central.event_bus import DataPointUpdatedEvent

    async def monitor_changes(central):
        """Monitor all data point changes."""
        async def handle_update(event: DataPointUpdatedEvent):
            print(f"Changed: {event.state_path} = {event.value}")

        # Subscribe to all updates
        central.event_bus.subscribe(
            event_type=DataPointUpdatedEvent,
            handler=handle_update
        )

Working with Programs
---------------------

.. code-block:: python

    async def execute_program(central, program_name):
        """Execute a CCU program."""
        program = central.get_program_data_point(legacy_name=program_name)
        if program:
            await program.button.press()
            return True
        return False

System Variables
----------------

.. code-block:: python

    async def get_system_variable(central, var_name):
        """Get system variable value."""
        sysvar = central.get_sysvar_data_point(legacy_name=var_name)
        return sysvar.value if sysvar else None

    async def set_system_variable(central, var_name, value):
        """Set system variable value."""
        await central.set_system_variable(
            legacy_name=var_name,
            value=value
        )

Device Discovery
----------------

.. code-block:: python

    async def list_all_devices(central):
        """List all discovered devices."""
        for device in central.devices:
            print(f"Device: {device.name}")
            print(f"  Address: {device.address}")
            print(f"  Type: {device.device_type}")
            print(f"  Interface: {device.interface}")
            print(f"  Channels: {len(device.channels)}")
            print()

Complete Application
--------------------

.. code-block:: python

    import asyncio
    from aiohomematic.central import CentralConfig
    from aiohomematic.client import InterfaceConfig, Interface
    from aiohomematic.central.event_bus import DataPointUpdatedEvent

    class HomematicMonitor:
        """Monitor Homematic devices."""

        def __init__(self, config: CentralConfig):
            self.central = config.create_central()

        async def start(self):
            """Start monitoring."""
            # Subscribe to events
            self.central.event_bus.subscribe(
                event_type=DataPointUpdatedEvent,
                handler=self._handle_update
            )

            # Start central
            await self.central.start()
            print(f"Started monitoring {len(self.central.devices)} devices")

        async def stop(self):
            """Stop monitoring."""
            await self.central.stop()

        async def _handle_update(self, event: DataPointUpdatedEvent):
            """Handle data point updates."""
            print(f"{event.state_path} = {event.value}")

        async def set_temperature(self, device_address, temp):
            """Set thermostat temperature."""
            device = self.central.get_device(address=device_address)
            if device:
                dp = device.get_data_point(
                    channel_address=f"{device_address}:1",
                    parameter="SET_TEMPERATURE"
                )
                if dp and dp.is_writable:
                    await dp.send_value(temp)

    async def main():
        # Configuration
        config = CentralConfig(
            name="Home",
            host="192.168.1.100",
            username="admin",
            password="secret",
            central_id="home",
            interface_configs={
                InterfaceConfig(
                    central_name="home",
                    interface=Interface.HMIP_RF,
                    port=2010,
                ),
            },
        )

        # Create monitor
        monitor = HomematicMonitor(config)
        await monitor.start()

        # Run for a while
        await asyncio.sleep(3600)

        # Stop
        await monitor.stop()

    if __name__ == "__main__":
        asyncio.run(main())

See Also
--------

- :doc:`quickstart` - Basic usage guide
- :doc:`configuration` - Configuration options
- :doc:`../api/central` - Complete API reference
