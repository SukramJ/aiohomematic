Configuration
=============

This guide covers advanced configuration options for aiohomematic.

CentralConfig Options
---------------------

The ``CentralConfig`` class provides numerous configuration options:

.. code-block:: python

    from aiohomematic.central import CentralConfig
    from aiohomematic.const import OptionalSettings

    config = CentralConfig(
        name="MyCCU",
        host="192.168.1.100",
        username="admin",
        password="secret",
        central_id="unique-id",
        interface_configs={...},

        # Optional settings
        tls=False,                              # Use TLS
        verify_tls=True,                        # Verify TLS certificates
        callback_host=None,                     # Callback host for XML-RPC server
        callback_port=None,                     # Callback port
        json_port=80,                           # JSON-RPC port

        # Feature toggles
        enable_device_firmware_check=True,      # Check device firmware
        enable_program_scan=True,               # Scan for programs
        enable_sysvar_scan=True,                # Scan for system variables

        # Caching
        storage_directory="./cache",            # Cache directory
        use_caches=True,                        # Enable caching

        # Advanced
        optional_settings=(                     # Optional feature flags
            OptionalSettings.SESSION_RECORDER,
            OptionalSettings.PERFORMANCE_METRICS,
        ),
    )

Interface Configuration
-----------------------

Configure individual interfaces:

.. code-block:: python

    from aiohomematic.client import InterfaceConfig, Interface

    # BidCos-RF interface
    bidcos_rf = InterfaceConfig(
        central_name="ccu-main",
        interface=Interface.BIDCOS_RF,
        port=2001,
    )

    # HmIP-RF interface
    hmip_rf = InterfaceConfig(
        central_name="ccu-main",
        interface=Interface.HMIP_RF,
        port=2010,
    )

    # Virtual devices
    virtual = InterfaceConfig(
        central_name="ccu-main",
        interface=Interface.VIRTUAL_DEVICES,
        port=2010,
    )

    # Use all interfaces
    config = CentralConfig(
        # ...
        interface_configs={bidcos_rf, hmip_rf, virtual},
    )

Caching Configuration
---------------------

Control caching behavior:

.. code-block:: python

    config = CentralConfig(
        # ...
        use_caches=True,                    # Enable all caches
        storage_directory="./my_cache",     # Custom cache location
    )

    # Access cache coordinatorconfigured as empty placeholder:
    central = config.create_central()
    await central.start()

    # Force cache refresh
    await central.cache_coordinator.load_all()

    # Save caches
    await central.save_files(
        save_device_descriptions=True,
        save_paramset_descriptions=True,
    )

Optional Settings
-----------------

Enable optional features:

.. code-block:: python

    from aiohomematic.const import OptionalSettings

    config = CentralConfig(
        # ...
        optional_settings=(
            OptionalSettings.SESSION_RECORDER,      # Record RPC sessions
            OptionalSettings.PERFORMANCE_METRICS,   # Track performance
        ),
    )

Logging Configuration
---------------------

Configure logging for aiohomematic:

.. code-block:: python

    import logging

    # Set log level for all aiohomematic modules
    logging.getLogger("aiohomematic").setLevel(logging.DEBUG)

    # Set log level for specific modules
    logging.getLogger("aiohomematic.central").setLevel(logging.DEBUG)
    logging.getLogger("aiohomematic.client").setLevel(logging.INFO)

See Also
--------

- :doc:`quickstart` - Basic usage examples
- :doc:`examples` - Advanced usage patterns
- :class:`aiohomematic.central.CentralConfig` - Full API reference
