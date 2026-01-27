# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for aiohomematic stability guarantees.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for aiohomematic. Any change that
breaks these tests requires a MAJOR version bump and coordination with
plugin maintainers (e.g., Homematic(IP) Local for Home Assistant).

Test Modules
------------
**Tier 0 - Regression Prevention (Run before any refactoring):**

- test_cuxd_ccu_jack_contract.py: CUxD/CCU-Jack special handling (JSON-RPC only)

**Tier 1 - Critical (Public API used by Home Assistant):**

- test_capability_contract.py: Backend capabilities (CUxD, CCU-Jack, CCU, Homegear)
- test_enum_constants_contract.py: Enum values and constants stability
- test_configuration_contract.py: CentralConfig, InterfaceConfig, TimeoutConfig
- test_exception_hierarchy_contract.py: Exception types and hierarchy
- test_subscription_api_contract.py: EventBus subscription mechanics

**Tier 2 - High (Public API with moderate impact):**

- test_client_state_machine_contract.py: Client state machine transitions
- test_central_state_machine_contract.py: Central state machine transitions
- test_connection_recovery_contract.py: Connection recovery behavior
- test_event_system_contract.py: Event types and structure
- test_client_lifecycle_contract.py: Client lifecycle methods
- test_hub_entities_contract.py: Hub data point types and lifecycle
- test_protocol_interfaces_contract.py: Protocol interface stability

Contract Scope
--------------
1. **CUxD/CCU-Jack Contracts**: JSON-RPC-only interfaces, no XML-RPC, no ping/pong
2. **State Machine Contracts**: Valid/invalid transitions, failure tracking, properties
3. **Capability Contracts**: Capability flags, capability-gated behavior
4. **Recovery Contracts**: Exponential backoff, max attempts, stage progression
5. **Event Contracts**: Event types, required fields, immutability
6. **Lifecycle Contracts**: init/deinit, reconnect, stop behavior
7. **Enum Contracts**: Enum values must not change without major version bump
8. **Configuration Contracts**: Config field stability and defaults
9. **Exception Contracts**: Exception hierarchy and name attributes
10. **Protocol Contracts**: Protocol interface member stability
11. **Hub Entity Contracts**: Hub data point type stability
12. **Subscription Contracts**: EventBus API and handler patterns

See ADR-0018 for architectural context and rationale.
"""

from __future__ import annotations
