# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Test support infrastructure for aiohomematic.

Overview
--------
This package provides reusable test utilities for testing aiohomematic functionality
without requiring a live Homematic backend. It includes factories for creating test
instances, mock implementations for RPC communication, and session playback capabilities
for reproducible testing.

Key Components
--------------
- **factory**: Factory classes for creating CentralUnit and Client instances with
  pre-recorded or mocked backend responses.
- **mock**: Mock implementations for XML-RPC and JSON-RPC clients with session
  playback support for deterministic testing.
- **helper**: Test helper utilities for common testing operations.
- **const**: Test-specific constants and configuration values.

Usage Example
-------------
Using the factory to create a test central with session playback:

    from aiohomematic_test_support.factory import FactoryWithClient
    from aiohomematic_test_support.mock import SessionPlayer

    player = SessionPlayer(session_data_path="tests/data/ccu_session.zip")
    factory = FactoryWithClient(player=player)
    central, client = await factory()

    # Test operations
    await central.start()
    device = central.device_coordinator.get_device_by_address("VCU0000001")
    await central.stop()

The session player replays pre-recorded backend responses, enabling fast and
reproducible tests without backend dependencies.

Notes
-----
This is a separate package from the main aiohomematic library. Install with
test dependencies to access test support functionality.

"""

from __future__ import annotations

__version__ = "0.1.0"
