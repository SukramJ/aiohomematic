Quick Start
===========

This guide will help you get started with aiohomematic quickly.

Basic Usage
-----------

Create a CentralConfig and start the central unit:

.. code-block:: python

    import asyncio
    from aiohomematic.central import CentralConfig
    from aiohomematic.client import InterfaceConfig, Interface

    async def main():
        # Create interface configuration
        interface_configs = {
            InterfaceConfig(
                central_name="ccu-main",
                interface=Interface.HMIP_RF,
                port=2010,
            ),
        }

        # Create central configuration
        config = CentralConfig(
            name="MyCCU",
            host="192.168.1.100",
            username="admin",
            password="secret",
            central_id="unique-id",
            interface_configs=interface_configs,
        )

        # Create and start central unit
        central = config.create_central()
        await central.start()

        # Access devices
        for device in central.devices:
            print(f"Device: {device.name} ({device.address})")

        # Stop central unit
        await central.stop()

    asyncio.run(main())

Accessing Devices
-----------------

Get a specific device by address:

.. code-block:: python

    device = central.get_device(address="VCU0000001")
    if device:
        print(f"Found device: {device.name}")

Accessing Data Points
---------------------

Get data points from a device:

.. code-block:: python

    # Get all data points
    data_points = device.get_data_points()

    # Get a specific data point
    dp = device.get_data_point(
        channel_address="VCU0000001:1",
        parameter="TEMPERATURE"
    )

    if dp:
        # Read current value
        value = dp.value
        print(f"Temperature: {value}")

        # Subscribe to updates
        def callback(name, new_value):
            print(f"{name} changed to {new_value}")

        dp.subscribe(callback)

Setting Values
--------------

Set a data point value:

.. code-block:: python

    # Get a writable data point
    dp = device.get_data_point(
        channel_address="VCU0000001:1",
        parameter="SET_TEMPERATURE"
    )

    if dp and dp.is_writable:
        # Set new value
        await dp.send_value(21.5)

Working with Events
-------------------

Subscribe to device events:

.. code-block:: python

    from aiohomematic.central.events import DataPointUpdatedEvent

    async def handle_update(event: DataPointUpdatedEvent):
        print(f"Data point {event.state_path} = {event.value}")

    # Subscribe to data point updates
    central.event_bus.subscribe(
        event_type=DataPointUpdatedEvent,
        handler=handle_update
    )

Complete Example
----------------

.. code-block:: python

    import asyncio
    from aiohomematic.central import CentralConfig
    from aiohomematic.client import InterfaceConfig, Interface
    from aiohomematic.central.events import DataPointUpdatedEvent

    async def main():
        # Configuration
        config = CentralConfig(
            name="MyCCU",
            host="192.168.1.100",
            username="admin",
            password="secret",
            central_id="ccu-main",
            interface_configs={
                InterfaceConfig(
                    central_name="ccu-main",
                    interface=Interface.HMIP_RF,
                    port=2010,
                ),
            },
        )

        # Create central
        central = config.create_central()

        # Subscribe to events
        async def log_updates(event: DataPointUpdatedEvent):
            print(f"{event.state_path} = {event.value}")

        central.event_bus.subscribe(
            event_type=DataPointUpdatedEvent,
            handler=log_updates
        )

        # Start
        await central.start()

        # Use the central
        print(f"Connected to {central.name}")
        print(f"Found {len(central.devices)} devices")

        # Keep running
        await asyncio.sleep(60)

        # Stop
        await central.stop()

    if __name__ == "__main__":
        asyncio.run(main())

Next Steps
----------

- Read the :doc:`configuration` guide for advanced configuration options
- Explore the :doc:`examples` for more usage patterns
- Check the :doc:`../api/central` for complete API documentation
