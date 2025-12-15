# Home Assistant Integration Migration Plan

**Created**: 2025-12-14
**Target**: Migrate Homematic(IP) Local to new aiohomematic APIs
**Prerequisites**: aiohomematic 2025.12.x with Integration Events (SystemStatusEvent, DeviceLifecycleEvent, DataPointsCreatedEvent, DeviceTriggerEvent) and Callback API
**Status**: Ready for execution

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Migration Steps](#migration-steps)
4. [Code Changes](#code-changes)
5. [Testing Plan](#testing-plan)
6. [Rollback Plan](#rollback-plan)
7. [Progress Tracking](#progress-tracking)

---

## Overview

### Goal

Migrate Homematic(IP) Local integration from 9 separate EventBus subscriptions to 4 focused integration events: `SystemStatusEvent`, `DeviceLifecycleEvent`, `DataPointsCreatedEvent`, `DeviceTriggerEvent`.

### Benefits

- **Simpler code**: 9 event handlers → 4 focused handlers
- **Less coupling**: Fewer integration points with aiohomematic
- **Easier maintenance**: Clear responsibility per event handler
- **Better performance**: Fewer subscriptions, targeted event handling

### Success Criteria

- [ ] 9 EventBus subscriptions reduced to 4
- [ ] All functionality preserved (no regressions)
- [ ] Code is clean with no legacy handlers
- [ ] All tests pass
- [ ] Pre-commit hooks pass

---

## Prerequisites

### aiohomematic Version

**Required**: `aiohomematic >= 2025.12.0`

**Check version**:

```bash
python -c "from aiohomematic.const import VERSION; print(VERSION)"
```

**Verify Integration Events available**:

```python
try:
    from aiohomematic.central.integration_events import (
        SystemStatusEvent,
        DeviceLifecycleEvent,
        DataPointsCreatedEvent,
        DeviceTriggerEvent,
    )
    print("✅ Integration events available")
except ImportError:
    print("❌ Integration events not available - update aiohomematic")
```

### Backup

**Before starting migration**:

1. Create feature branch: `git checkout -b feature/integration-events`
2. Commit current state: `git commit -am "Backup before integration events migration"`
3. Push backup: `git push -u origin feature/integration-events`

---

## Migration Steps

### Phase 1: Preparation (Day 1, Morning)

#### Step 1.1: Review Current Implementation

**File**: `custom_components/homematicip_local/control_unit.py`

**Review lines 283-345**: All 9 current subscriptions

```bash
# Count current subscriptions
grep -n "event_bus.subscribe" custom_components/homematicip_local/control_unit.py | wc -l
# Should output: 9
```

**Document current handlers**:

- `_on_system_event` (line ~350)
- `_on_homematic_event` (line ~450)
- `_on_central_state_changed` (line ~500)
- `_on_connection_state_changed` (line ~550)
- `_on_callback_state_changed` (line ~600)
- `_on_client_state_changed` (line ~650)
- `_on_fetch_data_failed` (line ~700)
- `_on_pingpong_mismatch` (line ~750)
- `_on_device_availability_changed` (line ~800)

**Checklist**:

- [ ] Identify all 9 handler methods
- [ ] Document what each handler does
- [ ] Note any shared logic between handlers
- [ ] Identify HA dispatcher calls in each handler
- [ ] Identify HA issue creation calls in each handler

**Estimated Time**: 30 minutes

---

#### Step 1.2: Create Test Baseline

**Run full test suite** to establish baseline:

```bash
cd /Users/markus/Documents/GitHub/homematicip_local
pytest tests/ -v --tb=short > baseline_tests.txt
```

**Checklist**:

- [ ] All tests pass
- [ ] Baseline results saved to `baseline_tests.txt`
- [ ] Note any flaky tests

**Estimated Time**: 15 minutes

---

### Phase 2: Implementation (Day 1, Afternoon)

#### Step 2.1: Add Integration Event Handlers

**File**: `custom_components/homematicip_local/control_unit.py`

**Add 4 new handler methods** (before any modifications to existing code):

```python
from aiohomematic.central.integration_events import (
   DataPointsCreatedEvent,
   DeviceLifecycleEvent,
   DeviceLifecycleEventType,
   DeviceTriggerEvent,
   IntegrationIssue,
   SystemStatusEvent,
)
from aiohomematic.const import CentralState, ClientState


# Handler 1: SystemStatusEvent (Infrastructure + Lifecycle)
async def _on_system_status(self, *, event: SystemStatusEvent) -> None:
   """Handle system status event from aiohomematic."""
   # Central state changes
   if event.central_state == CentralState.RUNNING:
      _LOGGER.info("Central %s is running", self._central.name)
   elif event.central_state == CentralState.FAILED:
      _LOGGER.error("Central %s failed to start", self._central.name)
      ir.async_create_issue(
         hass=self._hass,
         domain=DOMAIN,
         issue_id=f"{self._entry_id}_central_failed",
         is_fixable=False,
         severity=ir.IssueSeverity.ERROR,
         translation_key="central_failed",
         translation_placeholders={"name": self._central.name},
      )

   # Connection state changes: tuple[str, bool] = (interface_id, connected)
   if event.connection_state:
      interface_id, connected = event.connection_state
      _LOGGER.debug("Connection state for %s: connected=%s", interface_id, connected)
      if not connected:
         ir.async_create_issue(
            hass=self._hass,
            domain=DOMAIN,
            issue_id=f"{self._entry_id}_connection_{interface_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="connection_failed",
            translation_placeholders={"interface_id": interface_id},
         )

   # Client state changes: tuple[str, ClientState, ClientState] = (interface_id, old_state, new_state)
   if event.client_state:
      interface_id, old_state, new_state = event.client_state
      _LOGGER.debug("Client state for %s: %s -> %s", interface_id, old_state, new_state)
      if new_state == ClientState.FAILED:
         ir.async_create_issue(
            hass=self._hass,
            domain=DOMAIN,
            issue_id=f"{self._entry_id}_client_{interface_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="client_failed",
            translation_placeholders={"interface_id": interface_id},
         )

   # Callback state changes: tuple[str, bool] = (interface_id, alive)
   if event.callback_state:
      interface_id, alive = event.callback_state
      _LOGGER.debug("Callback state for %s: alive=%s", interface_id, alive)
      if not alive:
         ir.async_create_issue(
            hass=self._hass,
            domain=DOMAIN,
            issue_id=f"{self._entry_id}_callback_{interface_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="callback_server_failed",
            translation_placeholders={"interface_id": interface_id},
         )

   # Issues from aiohomematic
   for issue in event.issues:
      ir.async_create_issue(
         hass=self._hass,
         domain=DOMAIN,
         issue_id=f"{self._entry_id}_{issue.issue_id}",
         is_fixable=False,
         severity=ir.IssueSeverity.ERROR if issue.severity == "error" else ir.IssueSeverity.WARNING,
         translation_key=issue.translation_key,
         translation_placeholders=dict(issue.translation_placeholders),
      )


# Handler 2: DeviceLifecycleEvent (Device lifecycle + availability)
async def _on_device_lifecycle(self, *, event: DeviceLifecycleEvent) -> None:
   """Handle device lifecycle event from aiohomematic."""
   if event.event_type == DeviceLifecycleEventType.CREATED:
      _LOGGER.debug("Devices created: %s", event.device_addresses)
      if event.includes_virtual_remotes:
         self._async_add_virtual_remotes_to_device_registry()

   elif event.event_type == DeviceLifecycleEventType.AVAILABILITY_CHANGED:
      for device_address, available in event.availability_changes:
         _LOGGER.debug("Device %s availability: %s", device_address, available)
         device_registry = dr.async_get(self._hass)
         if ha_device := device_registry.async_get_device(
                 identifiers={(DOMAIN, device_address)}
         ):
            device_registry.async_update_device(
               device_id=ha_device.id,
               disabled_by=None if available else dr.DeviceEntryDisabler.INTEGRATION,
            )


# Handler 3: DataPointsCreatedEvent (Entity discovery)
async def _on_data_points_created(self, *, event: DataPointsCreatedEvent) -> None:
   """Handle data points created event from aiohomematic."""
   for category, data_points in event.new_data_points:
      if data_points:
         platform = CATEGORY_TO_PLATFORM.get(category)
         if platform:
            async_dispatcher_send(
               self._hass,
               signal_new_data_point(entry_id=self._entry_id, platform=platform),
               data_points,
            )


# Handler 4: DeviceTriggerEvent (Device triggers for HA event bus)
async def _on_device_trigger(self, *, event: DeviceTriggerEvent) -> None:
   """Handle device trigger event from aiohomematic."""
   self._hass.bus.async_fire(
      event_type=f"{DOMAIN}.event",
      event_data={
         "entry_id": self._entry_id,
         "interface_id": event.interface_id,
         "channel_address": event.channel_address,
         "parameter": event.parameter,
         "value": event.value,
      },
   )
```

**Checklist**:

- [ ] Add imports for `SystemStatusEvent`, `DeviceLifecycleEvent`, `DataPointsCreatedEvent`, `DeviceTriggerEvent`
- [ ] Add import for `IntegrationIssue`, `DeviceLifecycleEventType`
- [ ] Add `_on_system_status` method
- [ ] Add `_on_device_lifecycle` method
- [ ] Add `_on_data_points_created` method
- [ ] Add `_on_device_trigger` method
- [ ] Handle all state changes in SystemStatusEvent
- [ ] Handle device lifecycle and availability in DeviceLifecycleEvent
- [ ] Handle entity discovery in DataPointsCreatedEvent
- [ ] Handle device triggers in DeviceTriggerEvent
- [ ] Preserve all existing functionality

**Estimated Time**: 2 hours

---

#### Step 2.2: Add New Subscription

**File**: `custom_components/homematicip_local/control_unit.py`

**In `start_central()` method**, add new subscriptions **BEFORE** old subscriptions:

```python
async def start_central(self) -> None:
   """Start the central unit."""
   # ... existing code ...

   # NEW: 4 focused event subscriptions
   _LOGGER.debug("Subscribing to integration events")

   # 1. SystemStatusEvent (Infrastructure + Lifecycle)
   self._unsubscribe_callbacks.append(
      self._central.event_bus.subscribe(
         event_type=SystemStatusEvent,
         handler=self._on_system_status,
      )
   )

   # 2. DeviceLifecycleEvent (Device lifecycle + availability)
   self._unsubscribe_callbacks.append(
      self._central.event_bus.subscribe(
         event_type=DeviceLifecycleEvent,
         handler=self._on_device_lifecycle,
      )
   )

   # 3. DataPointsCreatedEvent (Entity discovery)
   self._unsubscribe_callbacks.append(
      self._central.event_bus.subscribe(
         event_type=DataPointsCreatedEvent,
         handler=self._on_data_points_created,
      )
   )

   # 4. DeviceTriggerEvent (Device triggers)
   self._unsubscribe_callbacks.append(
      self._central.event_bus.subscribe(
         event_type=DeviceTriggerEvent,
         handler=self._on_device_trigger,
      )
   )

   # OLD: Keep old subscriptions for now (will remove in Step 2.4)
   self._unsubscribe_callbacks.append(
      self._central.event_bus.subscribe(
         event_type=BackendSystemEventData,
         handler=self._on_system_event,
      )
   )
   # ... 8 more old subscriptions ...
```

**Checklist**:

- [ ] Add 4 new subscriptions at top of subscription block
- [ ] Keep old subscriptions (for testing)
- [ ] Add debug logging

**Estimated Time**: 15 minutes

---

#### Step 2.3: Test New Handler

**Run tests** with both old and new subscriptions active:

```bash
pytest tests/ -v --tb=short -k "test_control_unit"
```

**Verify**:

- [ ] No new test failures
- [ ] New handler is invoked (check logs)
- [ ] No duplicate issues created (old + new handlers)

**If issues found**:

- Fix the 4 handler methods (`_on_system_status`, `_on_device_lifecycle`, `_on_data_points_created`, `_on_device_trigger`)
- Re-test until green

**Estimated Time**: 1 hour

---

### Phase 3: Cleanup (Day 2, Morning)

#### Step 2.4: Remove Old Subscriptions

**File**: `custom_components/homematicip_local/control_unit.py`

**In `start_central()` method**, remove old subscriptions:

```python
async def start_central(self) -> None:
   """Start the central unit."""
   # ... existing code ...

   # 4 focused integration event subscriptions
   _LOGGER.debug("Subscribing to integration events")

   self._unsubscribe_callbacks.append(
      self._central.event_bus.subscribe(
         event_type=SystemStatusEvent,
         handler=self._on_system_status,
      )
   )
   self._unsubscribe_callbacks.append(
      self._central.event_bus.subscribe(
         event_type=DeviceLifecycleEvent,
         handler=self._on_device_lifecycle,
      )
   )
   self._unsubscribe_callbacks.append(
      self._central.event_bus.subscribe(
         event_type=DataPointsCreatedEvent,
         handler=self._on_data_points_created,
      )
   )
   self._unsubscribe_callbacks.append(
      self._central.event_bus.subscribe(
         event_type=DeviceTriggerEvent,
         handler=self._on_device_trigger,
      )
   )

   # OLD SUBSCRIPTIONS REMOVED (9 lines deleted)
```

**Checklist**:

- [ ] Remove all 9 old `event_bus.subscribe()` calls
- [ ] Verify no compilation errors
- [ ] Count remaining subscriptions: should be 4

**Estimated Time**: 10 minutes

---

#### Step 2.5: Remove Old Handlers

**File**: `custom_components/homematicip_local/control_unit.py`

**Delete old handler methods** (9 methods, ~450 lines total):

```python
# DELETE these methods:
# async def _on_system_event(self, event: BackendSystemEventData) -> None:
# async def _on_homematic_event(self, event: HomematicEvent) -> None:
# async def _on_central_state_changed(self, event: CentralStateChangedEvent) -> None:
# async def _on_connection_state_changed(self, event: ConnectionStateChangedEvent) -> None:
# async def _on_callback_state_changed(self, event: CallbackStateChangedEvent) -> None:
# async def _on_client_state_changed(self, event: ClientStateChangedEvent) -> None:
# async def _on_fetch_data_failed(self, event: FetchDataFailedEvent) -> None:
# async def _on_pingpong_mismatch(self, event: PingPongMismatchEvent) -> None:
# async def _on_device_availability_changed(self, event: DeviceAvailabilityChangedEvent) -> None:
```

**IMPORTANT**: ⚠️ **NO LEGACY CODE** - completely remove old handlers

**Checklist**:

- [ ] Delete `_on_system_event` method
- [ ] Delete `_on_homematic_event` method
- [ ] Delete `_on_central_state_changed` method
- [ ] Delete `_on_connection_state_changed` method
- [ ] Delete `_on_callback_state_changed` method
- [ ] Delete `_on_client_state_changed` method
- [ ] Delete `_on_fetch_data_failed` method
- [ ] Delete `_on_pingpong_mismatch` method
- [ ] Delete `_on_device_availability_changed` method
- [ ] Verify no references to deleted methods remain
- [ ] Run `ruff check` to verify no unused imports

**Estimated Time**: 30 minutes

---

#### Step 2.6: Clean Up Imports

**File**: `custom_components/homematicip_local/control_unit.py`

**Remove unused imports**:

```python
# REMOVE legacy event imports (these no longer exist):
# - BackendSystemEventData (replaced by DeviceLifecycleEvent, DataPointsCreatedEvent)
# - CallbackStateChangedEvent (replaced by SystemStatusEvent.callback_state)
# - CentralStateChangedEvent (replaced by SystemStatusEvent.central_state)
# - ClientStateChangedEvent (replaced by SystemStatusEvent.client_state)
# - ConnectionStateChangedEvent (replaced by SystemStatusEvent.connection_state)
# - DeviceAvailabilityChangedEvent (replaced by DeviceLifecycleEvent.availability_changes)
# - FetchDataFailedEvent (replaced by SystemStatusEvent.issues)
# - HomematicEvent (replaced by DeviceTriggerEvent)
# - PingPongMismatchEvent (replaced by SystemStatusEvent.issues)

# ADD new integration events (all from integration_events module):
from aiohomematic.central.integration_events import (
    DataPointsCreatedEvent,
    DeviceLifecycleEvent,
    DeviceLifecycleEventType,
    DeviceTriggerEvent,
    IntegrationIssue,
    SystemStatusEvent,
)
```

**Checklist**:

- [ ] Remove all legacy event imports (they no longer exist in aiohomematic)
- [ ] Add all integration event imports from `aiohomematic.central.integration_events`
- [ ] Run `ruff check --fix` to clean up imports
- [ ] Verify no import errors

**Estimated Time**: 15 minutes

---

### Phase 4: Validation (Day 2, Afternoon)

#### Step 2.7: Run Full Test Suite

**Run all tests**:

```bash
pytest tests/ -v --tb=short > migration_tests.txt
```

**Compare with baseline**:

```bash
diff baseline_tests.txt migration_tests.txt
```

**Checklist**:

- [ ] All tests pass
- [ ] No new failures compared to baseline
- [ ] No test skipped due to missing functionality
- [ ] Test output saved to `migration_tests.txt`

**If failures**:

- Review test failures
- Fix issues in event handlers (`_on_system_status`, `_on_device_lifecycle`, etc.)
- Re-run tests until green

**Estimated Time**: 1 hour

---

#### Step 2.8: Manual Testing

**Test scenarios**:

1. **Central startup**:

   ```bash
   # Start HA with integration
   # Verify: No errors in logs
   # Verify: All devices discovered
   # Verify: All entities created
   ```

2. **Connection loss**:

   ```bash
   # Stop CCU
   # Verify: HA repair issue created
   # Restart CCU
   # Verify: Issue auto-resolved
   ```

3. **Device availability**:

   ```bash
   # Remove battery from device
   # Verify: Device marked unavailable in HA
   # Re-insert battery
   # Verify: Device marked available
   ```

4. **Homematic events**:

   ```bash
   # Trigger device event (e.g., press button)
   # Verify: HA event fired
   # Verify: Event data correct
   ```

5. **New device addition**:
   ```bash
   # Add new device via CCU
   # Verify: Device discovered in HA
   # Verify: Entities created
   ```

**Checklist**:

- [ ] Central startup works
- [ ] Connection loss handled
- [ ] Device availability updates
- [ ] Homematic events fired
- [ ] New device discovery works

**Estimated Time**: 1 hour

---

#### Step 2.9: Code Quality Checks

**Run pre-commit hooks**:

```bash
pre-commit run --all-files
```

**Run type checker**:

```bash
mypy custom_components/homematicip_local/
```

**Checklist**:

- [ ] ruff passes (no linting errors)
- [ ] ruff format passes (code formatted)
- [ ] mypy passes (no type errors)
- [ ] codespell passes (no spelling errors)

**Estimated Time**: 30 minutes

---

### Phase 5: Documentation (Day 2, Evening)

#### Step 2.10: Update Changelog

**File**: `changelog.md`

**Add entry**:

```markdown
## [YYYY.MM.DD] - 2025-12-XX

### Changed

- Migrated to aiohomematic integration events (simplified event handling, 9 subscriptions → 4)

### Internal

- Removed 9 legacy event handlers in control_unit.py (~450 lines removed)
- Added 4 focused handlers: `_on_system_status`, `_on_device_lifecycle`, `_on_data_points_created`, `_on_device_trigger`
```

**Checklist**:

- [ ] Add changelog entry
- [ ] Update version number
- [ ] Note breaking changes (if any)

**Estimated Time**: 10 minutes

---

#### Step 2.11: Update Documentation

**File**: `README.md` (if needed)

**Update integration notes** (if documented):

```markdown
## Integration with aiohomematic

Homematic(IP) Local uses aiohomematic's integration events for
simplified event handling. This provides 4 focused subscription points:

- SystemStatusEvent: Infrastructure + lifecycle
- DeviceLifecycleEvent: Device lifecycle + availability
- DataPointsCreatedEvent: Entity discovery
- DeviceTriggerEvent: Device triggers
```

**Checklist**:

- [ ] Update README if needed
- [ ] Update any architecture docs
- [ ] Note aiohomematic version requirement

**Estimated Time**: 15 minutes

---

### Phase 6: Finalization (Day 3)

#### Step 2.12: Create Pull Request

**Commit changes**:

```bash
git add .
git commit -m "Migrate to integration events

- Replace 9 EventBus subscriptions with 4 focused subscriptions
- Remove 9 legacy event handlers (~450 lines)
- Add 4 focused handlers for integration events
- All tests passing
- Requires aiohomematic >= 2025.12.0"

git push -u origin feature/integration-events
```

**Create PR**:

- Title: "Migrate to integration events from aiohomematic 2025.12.x"
- Description: Link to this migration plan
- Label: "enhancement", "refactoring"

**Checklist**:

- [ ] Commit all changes
- [ ] Push to remote
- [ ] Create PR
- [ ] Request review

**Estimated Time**: 15 minutes

---

## Code Changes Summary

### Files Modified

1. **`custom_components/homematicip_local/control_unit.py`**
   - **Added**: `_on_integration_status()` method (~100 lines)
   - **Removed**: 9 old event handler methods (~450 lines)
   - **Modified**: `start_central()` - replaced 9 subscriptions with 1
   - **Modified**: Imports - removed 9 event types, added 2 new
   - **Net change**: ~350 lines removed

### Lines of Code

**Before Migration**:

- `control_unit.py`: ~1000 lines
- Event handlers: 9 methods, ~450 lines
- Subscriptions: 9 subscriptions, ~45 lines

**After Migration**:

- `control_unit.py`: ~650 lines (-35%)
- Event handlers: 1 method, ~100 lines
- Subscriptions: 1 subscription, ~5 lines

**Total Reduction**: ~350 lines (-35%)

### Backward Compatibility

**IMPORTANT**: No backward compatibility layer needed.

- ✅ Clean migration (no legacy code)
- ✅ All old handlers deleted
- ✅ 4 focused new handlers
- ✅ Requires aiohomematic >= 2025.12.0

If older aiohomematic versions must be supported:

- Add version check in `async_setup_entry`
- Use old subscriptions if integration events not available
- **NOT RECOMMENDED** - better to require new aiohomematic version

---

## Testing Plan

### Automated Tests

**Test Coverage**:

- [ ] `test_control_unit.py`: All existing tests pass
- [ ] `test_config_flow.py`: Config flow tests pass
- [ ] Platform tests: All platform tests pass
- [ ] Service tests: All service tests pass

**New Tests** (optional):

- [ ] Test `_on_system_status` with various event combinations
- [ ] Test `_on_device_lifecycle` with all lifecycle event types
- [ ] Test `_on_data_points_created` for entity discovery
- [ ] Test `_on_device_trigger` for device triggers
- [ ] Test device availability updates

### Manual Tests

**Test Scenarios**:

1. **Fresh Installation**

   - [ ] Install integration
   - [ ] Verify all devices discovered
   - [ ] Verify all entities created

2. **Upgrade from Previous Version**

   - [ ] Upgrade integration
   - [ ] Restart HA
   - [ ] Verify no errors
   - [ ] Verify all functionality preserved

3. **Error Scenarios**

   - [ ] Connection loss → HA issue created
   - [ ] Client failure → HA issue created
   - [ ] Callback failure → HA issue created

4. **Event Scenarios**
   - [ ] Device event → HA event fired
   - [ ] Device added → Entities created
   - [ ] Device removed → Entities removed

### Performance Testing

**Metrics to check**:

- [ ] Startup time (should be unchanged or faster)
- [ ] Memory usage (should be slightly lower)
- [ ] CPU usage (should be unchanged)
- [ ] Event latency (should be unchanged)

---

## Rollback Plan

### If Migration Fails

**Option 1: Revert Commit**

```bash
git revert HEAD
git push
```

**Option 2: Revert to Previous Version**

```bash
git checkout main
git push origin feature/integration-status-event --force
```

**Option 3: Hotfix**

If critical issue found after merge:

1. Create hotfix branch
2. Revert to old subscriptions temporarily
3. Fix issue in separate PR
4. Re-apply migration

### Rollback Checklist

- [ ] Identify failure mode
- [ ] Document issue
- [ ] Choose rollback strategy
- [ ] Execute rollback
- [ ] Verify system functional
- [ ] Notify users

---

## Progress Tracking

### Migration Checklist

#### Phase 1: Preparation (Day 1, Morning)

- [ ] Step 1.1: Review current implementation (30 min)
- [ ] Step 1.2: Create test baseline (15 min)

#### Phase 2: Implementation (Day 1, Afternoon)

- [ ] Step 2.1: Add integration event handlers (2 hours)
- [ ] Step 2.2: Add new subscriptions (15 min)
- [ ] Step 2.3: Test new handlers (1 hour)

#### Phase 3: Cleanup (Day 2, Morning)

- [ ] Step 2.4: Remove old subscriptions (10 min)
- [ ] Step 2.5: Remove old handlers (30 min)
- [ ] Step 2.6: Clean up imports (15 min)

#### Phase 4: Validation (Day 2, Afternoon)

- [ ] Step 2.7: Run full test suite (1 hour)
- [ ] Step 2.8: Manual testing (1 hour)
- [ ] Step 2.9: Code quality checks (30 min)

#### Phase 5: Documentation (Day 2, Evening)

- [ ] Step 2.10: Update changelog (10 min)
- [ ] Step 2.11: Update documentation (15 min)

#### Phase 6: Finalization (Day 3)

- [ ] Step 2.12: Create pull request (15 min)

### Timeline

| Day   | Phase          | Hours | Status         |
| ----- | -------------- | ----- | -------------- |
| 1 AM  | Preparation    | 1     | ⏸️ Not Started |
| 1 PM  | Implementation | 3     | ⏸️ Not Started |
| 2 AM  | Cleanup        | 1     | ⏸️ Not Started |
| 2 PM  | Validation     | 2.5   | ⏸️ Not Started |
| 2 Eve | Documentation  | 0.5   | ⏸️ Not Started |
| 3     | Finalization   | 0.5   | ⏸️ Not Started |

**Total Estimated Time**: 8.5 hours (~2 days)

---

## Risk Mitigation

### Common Issues

**Issue 1: New handler doesn't receive events**

- **Cause**: Subscription not registered
- **Fix**: Verify subscription in `start_central()`
- **Prevention**: Add debug logging for subscription

**Issue 2: Duplicate issues created**

- **Cause**: Old and new handlers both active
- **Fix**: Ensure old subscriptions removed
- **Prevention**: Test with both handlers, verify no duplicates

**Issue 3: Missing functionality**

- **Cause**: Logic not ported from old handler
- **Fix**: Review old handler, port missing logic
- **Prevention**: Comprehensive review of all 9 old handlers

**Issue 4: Test failures**

- **Cause**: Tests depend on old event types
- **Fix**: Update tests to expect new integration events
- **Prevention**: Run tests after each phase

### Validation Steps

Before considering migration complete:

- [ ] All automated tests pass
- [ ] All manual test scenarios pass
- [ ] No errors in HA logs
- [ ] No regressions reported
- [ ] Code quality checks pass
- [ ] Documentation updated
- [ ] Changelog updated

---

## Notes

### Critical Requirements

✅ **This migration ensures**:

- All 9 old handlers **completely removed** (no legacy code)
- All 9 old subscriptions **completely removed**
- Clean, single `_on_integration_status` handler
- No backward compatibility shims
- No deprecated code paths

### Future Enhancements

**Not in scope for this migration**:

1. Callback Registration API usage (optional, separate PR)
2. Performance optimizations
3. Additional event filtering

**Consider in future**:

- Use Callback Registration API for data point discovery
- Optimize event handling logic
- Add event metrics/monitoring

---

**Document Version**: 1.0
**Last Updated**: 2025-12-14
**Status**: Ready for execution
**Estimated Completion**: 2 days
