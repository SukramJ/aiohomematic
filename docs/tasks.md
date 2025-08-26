1. [x] Establish architecture overview document

   - [x] Create docs/architecture.md describing high-level components (central, client, model, caches, support) and their interactions
   - [x] Document data flow for XML-RPC/JSON-RPC, event handling, and data point updates
   - [x] Add sequence diagrams for connect, device discovery, state change propagation

2. [ ] Define clear module boundaries and responsibilities

   - [ ] Audit cross-module imports to reduce coupling (e.g., model vs central vs client)
   - [ ] Introduce interfaces/protocols for device and data point abstractions to reduce concrete dependencies
   - [ ] Document extension points for new device profiles and calculated data points

3. [ ] Concurrency and async model hardening

   - [ ] Review usage of asyncio Locks (e.g., CustomDpCover.\_command_processing_lock) for potential deadlocks or unnecessary serialization
   - [ ] Ensure all network I/O is properly awaited and shielded against cancellation where necessary
   - [ ] Standardize background task creation (asyncio.create_task) with proper lifecycle management and cancellation during shutdown
   - [ ] Add timeouts and retries to RPC calls with jittered backoff

4. [ ] Error handling and exceptions

   - [ ] Centralize exception types in aiohomematic/exceptions.py and replace ad-hoc raises with domain-specific errors
   - [ ] Ensure RPC errors are mapped to actionable exceptions with context
   - [ ] Implement graceful degradation paths when optional features fail (e.g., partial device data)
   - [ ] Add error boundary logs with consistent structure and levels

5. [ ] Configuration and environment management

   - [ ] Audit configuration options (pyproject, ruff, mypy) and expose runtime tunables (timeouts, logging levels) via env vars or config object
   - [ ] Provide a single configuration entry point (e.g., Context/Settings) passed through central/client
   - [ ] Document configuration precedence and defaults in README.md

6. [ ] Logging strategy standardization

   - [ ] Define logging categories per subsystem (central, client, model, caches)
   - [ ] Replace print or inconsistent logging with structured logs including device_id/channel/parameter context
   - [ ] Ensure no sensitive data is logged; add redaction helpers

7. [ ] Type hints and typing robustness

   - [ ] Enable strict mypy options incrementally (e.g., disallow Any in core modules)
   - [ ] Fill missing type annotations, especially in decorators and generic data point classes
   - [ ] Replace use of Union[...] with | where Python version permits; keep py.typed accurate
   - [ ] Add Protocols/TypedDicts for RPC payloads and device metadata

8. [ ] Public API review and stability

   - [ ] Identify and mark public vs private APIs using **all** and documentation
   - [ ] Add deprecation policy and decorators for transitioning APIs
   - [ ] Provide changelog templates for breaking changes

9. [ ] Data model consistency and validation

   - [ ] Ensure Parameter, DataPointCategory, and Field mappings are exhaustive and validated at startup
   - [ ] Add validators for incoming values (range, enums) and conversions (e.g., convert_hm_level_to_cpv)
   - [ ] Consolidate duplicate constants and normalization logic

10. [ ] Performance and caching

    - [ ] Profile hot paths (device event processing, cache lookups) and add benchmarks
    - [ ] Review caches/dynamic and caches/persistent for eviction policies and thread-safety
    - [ ] Avoid redundant conversions and lookups across layers

11. [ ] I/O resiliency and retry policies

    - [ ] Implement circuit breaker or exponential backoff for gateway connectivity
    - [ ] Add reconnect strategies with jitter to avoid thundering herd
    - [ ] Persist minimal session state to enable warm restarts (where applicable)

12. [ ] Test coverage improvements

    - [ ] Identify coverage gaps using pytest --cov and add targeted tests (e.g., cover.py edge cases: partial open, group level vs level)
    - [ ] Add tests for decorators in aiohomematic/decorators.py and model/decorators.py
    - [ ] Add integration-like tests for central XML-RPC server behavior
    - [ ] Include failure path tests (RPC errors, invalid payloads)

13. [ ] CI/CD enhancements

    - [ ] Add workflow to run linting (ruff, mypy), tests, and coverage gates in CI
    - [ ] Publish coverage to codecov; enforce minimum threshold
    - [ ] Run pre-commit hooks with ruff and formatting

14. [ ] Linting and style consistency

    - [ ] Unify ruff configurations (multiple ruff.toml files) to a single source or clearly scoped configs
    - [ ] Enforce import sorting and module-level dunder order
    - [ ] Fix warnings surfaced by current ruff configs and add ignore rationales

15. [ ] Documentation improvements

    - [ ] Expand README.md with quickstart, architecture summary, and contribution guidelines
    - [ ] Add docs for creating custom device profiles and calculated data points
    - [ ] Document error codes and common troubleshooting steps

16. [ ] Developer ergonomics

    - [ ] Provide script targets (script/ or make) for common tasks: test, lint, typecheck, format, run examples
    - [ ] Improve example.py to showcase multiple device types and error handling
    - [ ] Add devcontainer or compiled instructions for setting up a consistent dev env

17. [ ] Deprecation and compatibility matrix

    - [ ] Document supported Python versions and HomeMatic variants
    - [ ] Add compatibility matrix in docs and enforce via CI job matrix

18. [ ] Security review

    - [ ] Audit XML-RPC server for input validation and path traversal or injection risks
    - [ ] Ensure JSON-RPC handling sanitizes inputs and enforces timeouts
    - [ ] Add bandit to CI and fix or triage findings (tests/bandit.yaml exists)

19. [ ] Resource cleanup and shutdown semantics

    - [ ] Ensure all connections, tasks, and file descriptors are closed on shutdown
    - [ ] Provide explicit close/dispose methods and context manager support when appropriate
    - [ ] Add tests for graceful shutdown paths

20. [ ] Code organization and naming

    - [ ] Review module and class names for clarity and consistency (e.g., abbreviations like hmd, hmed)
    - [ ] Replace ambiguous names with descriptive alternatives and update imports
    - [ ] Add module-level docstrings summarizing purpose and key types

21. [ ] Improve decorators and metadata handling

    - [ ] Audit @state_property and other decorators for side effects and caching behavior
    - [ ] Add documentation and examples for decorators usage
    - [ ] Ensure decorators preserve type information (functools.wraps, typing)

22. [ ] Validation of external data and schema enforcement

    - [ ] Define schemas for RPC messages and validate on borders
    - [ ] Add lenient parsing with clear warnings for unknown fields

23. [ ] Observability and metrics

    - [ ] Add optional metrics hooks (e.g., counters for RPC calls, latencies)
    - [ ] Provide simple adapter interface so users can plug in Prometheus or other backends

24. [ ] Backward compatibility tests

    - [ ] Add fixtures to simulate older gateway behaviors and ensure compatibility
    - [ ] Add regression tests for known past bugs (link to changelog entries)

25. [ ] Release process improvements

    - [ ] Add scripts to bump version, generate changelog, and publish to PyPI
    - [ ] Automate tag creation and GitHub releases with release notes

26. [ ] DataPoint and Device lifecycle clarity

    - [ ] Document lifecycle from discovery to teardown
    - [ ] Ensure transitions are explicit and state changes are debounced when needed

27. [ ] Reduce duplication between generic and custom models

    - [ ] Identify shared logic between custom/_ and generic/_ and refactor into common utilities
    - [ ] Add comprehensive unit tests to guard behavior during refactor

28. [ ] Improve examples and local development helpers

    - [ ] Expand example_local.py and aiohomematic_support/client_local.py with realistic scenarios
    - [ ] Provide mock device data sets (sanitized) under aiohomematic_storage for demos

29. [ ] Continuous performance monitoring

    - [ ] Add optional lightweight tracing for key operations (device update, event dispatch)
    - [ ] Provide hooks to capture slow logs when thresholds exceeded

30. [ ] Housekeeping
    - [x] Remove dead code and unused exports
    - [ ] Normalize file headers, license notices, and copyright
    - [ ] Ensure all public modules are included in aiohomematic.egg-info/top_level.txt if needed
