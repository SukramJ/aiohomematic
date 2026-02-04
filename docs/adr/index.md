# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the aiohomematic project. ADRs document significant architectural decisions, their context, and consequences.

## Index

| ADR                                                                | Title                                                         | Status                 |
| ------------------------------------------------------------------ | ------------------------------------------------------------- | ---------------------- |
| [0001](0001-circuit-breaker-and-connection-state.md)               | CircuitBreaker and CentralConnectionState Coexistence         | Accepted               |
| [0002](0002-protocol-based-dependency-injection.md)                | Protocol-Based Dependency Injection                           | Accepted               |
| [0003](0003-explicit-over-composite-protocol-injection.md)         | Explicit over Composite Protocol Injection                    | Accepted               |
| [0004](0004-thread-based-xml-rpc-server.md)                        | Thread-Based XML-RPC Server                                   | Superseded by ADR 0012 |
| [0005](0005-unbounded-parameter-visibility-cache.md)               | Unbounded Parameter Visibility Cache                          | Accepted               |
| [0006](0006-event-system-priorities-and-batching.md)               | Event System Priorities and Batching                          | Accepted               |
| [0007](0007-device-slots-reduction-rejected.md)                    | Device Slots Reduction via Composition                        | Rejected               |
| [0008](0008-taskgroup-migration-deferred.md)                       | TaskGroup Migration                                           | Deferred               |
| [0009](0009-interface-event-consolidation.md)                      | Interface Event Consolidation                                 | Accepted               |
| [0010](0010-protocol-combination-analysis.md)                      | Protocol Combination Analysis                                 | Accepted               |
| [0011](0011-storage-abstraction.md)                                | Storage Abstraction Layer                                     | Accepted               |
| [0012](0012-async-xml-rpc-server-poc.md)                           | Async XML-RPC Server                                          | Accepted               |
| [0013](0013-interface-client-backend-strategy.md)                  | InterfaceClient with Backend Strategy Pattern                 | Accepted               |
| [0013](0013-implementation-status.md)                              | Implementation Status (tracking document)                     | --                     |
| [0014](0014-retry-logic-removal.md)                                | Removal of Retry Logic for RPC Operations                     | Accepted               |
| [0015](0015-description-normalization-concept.md)                  | Description Data Normalization and Validation                 | Accepted               |
| [0016](0016-paramset-description-patching.md)                      | Paramset Description Patching                                 | Accepted               |
| [0017](0017-startup-auth-error-handling.md)                        | Defensive Client Initialization with Staged Validation        | Accepted               |
| [0018](0018_contract_tests.md)                                     | Contract Tests for CUxD/CCU-Jack Stability                    | Accepted               |
| [0019](0019-derived-binary-sensors.md)                             | Derived Binary Sensors from Enum Data Points                  | Accepted               |
| [0020](0020-command-throttling-priority-and-optimistic-updates.md) | Command Throttling with Priority Queue and Optimistic Updates | Accepted               |
| [0021](0021-blind-command-processing-lock.md)                      | Blind Command Processing Lock and Target Preservation         | Accepted               |
