"""Tests for command retry handler."""

from __future__ import annotations

import asyncio
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from xmlrpc.client import Fault as XmlRpcFault

import pytest

from aiohomematic.client import CommandPriority, CommandRetryHandler
from aiohomematic.client.command_retry import CommandRetryMetrics, _get_fault_code, is_retryable
from aiohomematic.const import DataPointKey, ParamsetKey, TimeoutConfig
from aiohomematic.exceptions import (
    AuthFailure,
    CircuitBreakerOpenException,
    ClientException,
    CommandSupersededError,
    InternalBackendException,
    NoConnectionException,
    UnsupportedException,
    ValidationException,
)

# =============================================================================
# is_retryable tests
# =============================================================================


class TestIsRetryable:
    """Tests for the is_retryable function."""

    def test_auth_failure_not_retryable(self) -> None:
        """Test that AuthFailure is not retryable."""
        assert is_retryable(exc=AuthFailure()) is False

    def test_circuit_breaker_not_retryable(self) -> None:
        """Test that CircuitBreakerOpenException is not retryable."""
        assert is_retryable(exc=CircuitBreakerOpenException()) is False

    def test_client_exception_with_duty_cycle_fault(self) -> None:
        """Test that ClientException wrapping DutyCycle fault is retryable."""
        fault = XmlRpcFault(-8, "insufficient duty cycle")
        exc = ClientException("failed")
        exc.__cause__ = fault
        assert is_retryable(exc=exc) is True

    def test_client_exception_with_non_retryable_fault_code(self) -> None:
        """Test that ClientException wrapping non-retryable fault is not retryable."""
        fault = XmlRpcFault(-2, "unknown device")
        exc = ClientException("failed")
        exc.__cause__ = fault
        assert is_retryable(exc=exc) is False

    def test_client_exception_with_retryable_fault_code(self) -> None:
        """Test that ClientException wrapping retryable fault is retryable."""
        fault = XmlRpcFault(-1, "device unreachable")
        exc = ClientException("failed")
        exc.__cause__ = fault
        assert is_retryable(exc=exc) is True

    def test_client_exception_with_transmission_pending_fault(self) -> None:
        """Test that ClientException wrapping transmission pending fault is retryable."""
        fault = XmlRpcFault(-10, "transmission pending")
        exc = ClientException("failed")
        exc.__cause__ = fault
        assert is_retryable(exc=exc) is True

    def test_client_exception_with_unknown_parameter_fault(self) -> None:
        """Test that ClientException wrapping unknown parameter fault is not retryable."""
        fault = XmlRpcFault(-5, "unknown parameter")
        exc = ClientException("failed")
        exc.__cause__ = fault
        assert is_retryable(exc=exc) is False

    def test_client_exception_without_cause_not_retryable(self) -> None:
        """Test that ClientException without cause is not retryable."""
        assert is_retryable(exc=ClientException("some error")) is False

    def test_internal_backend_is_retryable(self) -> None:
        """Test that InternalBackendException is retryable."""
        assert is_retryable(exc=InternalBackendException()) is True

    def test_no_connection_is_retryable(self) -> None:
        """Test that NoConnectionException is retryable."""
        assert is_retryable(exc=NoConnectionException()) is True

    def test_superseded_not_retryable(self) -> None:
        """Test that CommandSupersededError is not retryable."""
        assert is_retryable(exc=CommandSupersededError()) is False

    def test_timeout_error_is_retryable(self) -> None:
        """Test that TimeoutError is retryable."""
        assert is_retryable(exc=TimeoutError()) is True

    def test_unsupported_not_retryable(self) -> None:
        """Test that UnsupportedException is not retryable."""
        assert is_retryable(exc=UnsupportedException()) is False

    def test_validation_not_retryable(self) -> None:
        """Test that ValidationException is not retryable."""
        assert is_retryable(exc=ValidationException()) is False


# =============================================================================
# _get_fault_code tests
# =============================================================================


class TestGetFaultCode:
    """Tests for the _get_fault_code function."""

    def test_direct_fault_cause(self) -> None:
        """Test direct XML-RPC fault in cause chain."""
        fault = XmlRpcFault(-1, "unreachable")
        exc = ClientException("failed")
        exc.__cause__ = fault
        assert _get_fault_code(exc=exc) == -1

    def test_nested_fault_cause(self) -> None:
        """Test nested XML-RPC fault in cause chain."""
        fault = XmlRpcFault(-8, "duty cycle")
        inner = ClientException("inner")
        inner.__cause__ = fault
        outer = ClientException("outer")
        outer.__cause__ = inner
        assert _get_fault_code(exc=outer) == -8

    def test_no_cause(self) -> None:
        """Test exception without cause returns None."""
        assert _get_fault_code(exc=ClientException("error")) is None


# =============================================================================
# CommandRetryMetrics tests
# =============================================================================


class TestCommandRetryMetrics:
    """Tests for CommandRetryMetrics."""

    def test_snapshot_creates_copy(self) -> None:
        """Test that snapshot creates an independent copy."""
        metrics = CommandRetryMetrics()
        metrics.total_retries = 5
        metrics.successful_retries = 3
        snapshot = metrics.snapshot()
        assert snapshot.total_retries == 5
        assert snapshot.successful_retries == 3
        # Modifying original doesn't affect snapshot
        metrics.total_retries = 10
        assert snapshot.total_retries == 5


# =============================================================================
# CommandRetryHandler tests
# =============================================================================


def _make_event_bus() -> MagicMock:
    """Create a mock EventBus."""
    event_bus = MagicMock()
    event_bus.subscribe = MagicMock(return_value=MagicMock())
    return event_bus


def _make_dpk(*, parameter: str = "LEVEL") -> DataPointKey:
    """Create a test DataPointKey."""
    return DataPointKey(
        interface_id="test-interface",
        channel_address="VCU0000001:1",
        paramset_key=ParamsetKey.VALUES,
        parameter=parameter,
    )


@pytest.fixture
def retry_handler() -> CommandRetryHandler:
    """Create a CommandRetryHandler with test config."""
    return CommandRetryHandler(
        interface_id="test-interface",
        timeout_config=TimeoutConfig(),
        event_bus=_make_event_bus(),
    )


class TestCommandRetryHandler:
    """Tests for CommandRetryHandler."""

    @pytest.mark.asyncio
    async def test_no_retry_on_auth_failure(self, retry_handler: CommandRetryHandler) -> None:
        """Test that AuthFailure is not retried."""
        operation = AsyncMock(side_effect=AuthFailure())
        with pytest.raises(AuthFailure):
            await retry_handler.execute_with_retry(
                operation=operation,
                dpk=_make_dpk(),
            )
        assert operation.call_count == 1
        assert retry_handler.metrics.total_retries == 0

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_fault_code(self, retry_handler: CommandRetryHandler) -> None:
        """Test no retry on XML-RPC fault code -2 (UNKNOWN_DEVICE)."""
        fault = XmlRpcFault(-2, "unknown device")
        exc = ClientException("failed")
        exc.__cause__ = fault
        operation = AsyncMock(side_effect=exc)
        with pytest.raises(ClientException):
            await retry_handler.execute_with_retry(
                operation=operation,
                dpk=_make_dpk(),
            )
        assert operation.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_validation(self, retry_handler: CommandRetryHandler) -> None:
        """Test that ValidationException is not retried."""
        operation = AsyncMock(side_effect=ValidationException())
        with pytest.raises(ValidationException):
            await retry_handler.execute_with_retry(
                operation=operation,
                dpk=_make_dpk(),
            )
        assert operation.call_count == 1

    @pytest.mark.asyncio
    async def test_recovery_wait_timeout(self) -> None:
        """Test that recovery wait timeout raises the error."""
        handler = CommandRetryHandler(
            interface_id="test",
            timeout_config=TimeoutConfig(command_retry_recovery_wait=0.1),
            event_bus=_make_event_bus(),
        )
        operation = AsyncMock(side_effect=NoConnectionException())
        with pytest.raises(NoConnectionException):
            await handler.execute_with_retry(
                operation=operation,
                dpk=_make_dpk(),
            )
        assert handler.metrics.recovery_waits >= 1
        assert handler.metrics.recovery_wait_timeouts >= 1

    @pytest.mark.asyncio
    async def test_retry_disabled_globally(self) -> None:
        """Test retry disabled via max_attempts=0."""
        handler = CommandRetryHandler(
            interface_id="test",
            timeout_config=TimeoutConfig(command_retry_max_attempts=0),
            event_bus=_make_event_bus(),
        )
        operation = AsyncMock(side_effect=TimeoutError())
        with pytest.raises(TimeoutError):
            await handler.execute_with_retry(
                operation=operation,
                dpk=_make_dpk(),
            )
        assert operation.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_disabled_per_call(self, retry_handler: CommandRetryHandler) -> None:
        """Test retry disabled per call."""
        operation = AsyncMock(side_effect=TimeoutError())
        with pytest.raises(TimeoutError):
            await retry_handler.execute_with_retry(
                operation=operation,
                dpk=_make_dpk(),
                retry=False,
            )
        assert operation.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_exhausted(self, retry_handler: CommandRetryHandler) -> None:
        """Test retry exhaustion raises last exception."""
        operation = AsyncMock(side_effect=TimeoutError())
        with pytest.raises(TimeoutError):
            await retry_handler.execute_with_retry(
                operation=operation,
                dpk=_make_dpk(),
            )
        assert operation.call_count == 3
        assert retry_handler.metrics.exhausted_retries == 1

    @pytest.mark.asyncio
    async def test_retry_on_internal_backend_exception(self, retry_handler: CommandRetryHandler) -> None:
        """Test retry on InternalBackendException."""
        operation = AsyncMock(side_effect=[InternalBackendException(), "ok"])
        result = await retry_handler.execute_with_retry(
            operation=operation,
            dpk=_make_dpk(),
        )
        assert result == "ok"
        assert operation.call_count == 2
        assert retry_handler.metrics.successful_retries == 1

    @pytest.mark.asyncio
    async def test_retry_on_no_connection_recovery_timeout(self) -> None:
        """Test that NoConnectionException with recovery timeout raises."""
        handler = CommandRetryHandler(
            interface_id="test",
            timeout_config=TimeoutConfig(command_retry_recovery_wait=0.05),
            event_bus=_make_event_bus(),
        )
        operation = AsyncMock(side_effect=NoConnectionException())
        with pytest.raises(NoConnectionException):
            await handler.execute_with_retry(
                operation=operation,
                dpk=_make_dpk(),
            )
        assert handler.metrics.recovery_wait_timeouts >= 1

    @pytest.mark.asyncio
    async def test_retry_on_no_connection_with_recovery(self) -> None:
        """Test retry on NoConnectionException when recovery succeeds."""
        from aiohomematic.central.events import RecoveryCompletedEvent

        event_bus = _make_event_bus()
        handler = CommandRetryHandler(
            interface_id="test-interface",
            timeout_config=TimeoutConfig(command_retry_recovery_wait=5.0),
            event_bus=event_bus,
        )

        # Capture the handler registered with subscribe
        subscribe_call_args: list[dict[str, Any]] = []

        def _capture_subscribe(**kwargs: Any) -> MagicMock:
            subscribe_call_args.append(kwargs)
            return MagicMock()  # unsubscribe callable

        event_bus.subscribe = _capture_subscribe  # type: ignore[assignment]

        operation = AsyncMock(side_effect=[NoConnectionException(), "ok"])

        async def _simulate_recovery() -> None:
            """Wait a bit then call the recovery handler."""
            await asyncio.sleep(0.01)
            # Find and call the recovery handler
            if subscribe_call_args:
                recovery_handler = subscribe_call_args[-1]["handler"]
                event = MagicMock(spec=RecoveryCompletedEvent)
                event.interface_id = "test-interface"
                recovery_handler(event=event)

        # Run operation and recovery simulation concurrently
        background_tasks: set[asyncio.Task[None]] = set()
        task = asyncio.create_task(_simulate_recovery())
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        result = await handler.execute_with_retry(
            operation=operation,
            dpk=_make_dpk(),
        )
        assert result == "ok"
        assert operation.call_count == 2
        assert handler.metrics.recovery_waits == 1

    @pytest.mark.asyncio
    async def test_retry_on_retryable_fault_code(self, retry_handler: CommandRetryHandler) -> None:
        """Test retry on XML-RPC fault code -1 (UNREACH)."""
        fault = XmlRpcFault(-1, "device unreachable")
        exc = ClientException("failed")
        exc.__cause__ = fault
        operation = AsyncMock(side_effect=[exc, "ok"])
        result = await retry_handler.execute_with_retry(
            operation=operation,
            dpk=_make_dpk(),
        )
        assert result == "ok"
        assert operation.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, retry_handler: CommandRetryHandler) -> None:
        """Test retry on TimeoutError with eventual success."""
        operation = AsyncMock(side_effect=[TimeoutError(), TimeoutError(), "ok"])
        result = await retry_handler.execute_with_retry(
            operation=operation,
            dpk=_make_dpk(),
        )
        assert result == "ok"
        assert operation.call_count == 3
        assert retry_handler.metrics.total_retries == 2
        assert retry_handler.metrics.successful_retries == 1

    @pytest.mark.asyncio
    async def test_success_no_retry(self, retry_handler: CommandRetryHandler) -> None:
        """Test successful execution without any retry."""
        operation = AsyncMock(return_value="ok")
        result = await retry_handler.execute_with_retry(
            operation=operation,
            dpk=_make_dpk(),
        )
        assert result == "ok"
        assert operation.call_count == 1
        assert retry_handler.metrics.total_retries == 0


class TestCommandRetryHandlerCancellation:
    """Tests for retry cancellation."""

    def test_cancel_retries_for_device_empty(self, retry_handler: CommandRetryHandler) -> None:
        """Test cancelling retries when none exist."""
        count = retry_handler.cancel_retries_for_device(device_address="VCU0000001")
        assert count == 0

    def test_cancel_retries_for_dpk_empty(self, retry_handler: CommandRetryHandler) -> None:
        """Test cancelling retry for non-existent dpk."""
        count = retry_handler.cancel_retries_for_dpk(dpk=_make_dpk())
        assert count == 0

    def test_cancel_retries_for_interface_empty(self, retry_handler: CommandRetryHandler) -> None:
        """Test cancelling all retries when none exist."""
        count = retry_handler.cancel_retries_for_interface()
        assert count == 0


class TestCommandRetryHandlerProperties:
    """Tests for retry handler properties."""

    def test_active_retry_count_initial(self, retry_handler: CommandRetryHandler) -> None:
        """Test active retry count is 0 initially."""
        assert retry_handler.active_retry_count == 0

    def test_disabled_property(self) -> None:
        """Test disabled when max_attempts=0."""
        handler = CommandRetryHandler(
            interface_id="test",
            timeout_config=TimeoutConfig(command_retry_max_attempts=0),
            event_bus=_make_event_bus(),
        )
        assert handler.enabled is False

    def test_enabled_property(self, retry_handler: CommandRetryHandler) -> None:
        """Test enabled property reflects config."""
        assert retry_handler.enabled is True

    def test_metrics_initial(self, retry_handler: CommandRetryHandler) -> None:
        """Test metrics are all zero initially."""
        metrics = retry_handler.metrics
        assert metrics.total_retries == 0
        assert metrics.successful_retries == 0
        assert metrics.exhausted_retries == 0
        assert metrics.recovery_waits == 0
        assert metrics.recovery_wait_timeouts == 0
        assert metrics.cancelled_retries == 0


class TestCommandRetryHandlerDelay:
    """Tests for delay calculation."""

    @pytest.mark.asyncio
    async def test_duty_cycle_delay(self) -> None:
        """Test special delay for DutyCycle fault."""
        handler = CommandRetryHandler(
            interface_id="test",
            timeout_config=TimeoutConfig(command_retry_duty_cycle_delay=40.0),
            event_bus=_make_event_bus(),
        )
        fault = XmlRpcFault(-8, "insufficient duty cycle")
        exc = ClientException("failed")
        exc.__cause__ = fault
        delay = handler._calculate_delay(attempt=1, exc=exc)
        assert delay == 40.0

    @pytest.mark.asyncio
    async def test_exponential_backoff(self) -> None:
        """Test that delays increase with exponential backoff."""
        handler = CommandRetryHandler(
            interface_id="test",
            timeout_config=TimeoutConfig(
                command_retry_max_attempts=3,
                command_retry_base_delay=1.0,
                command_retry_backoff_factor=2.0,
                command_retry_max_delay=100.0,
            ),
            event_bus=_make_event_bus(),
        )
        delay1 = handler._calculate_delay(attempt=1, exc=TimeoutError())
        delay2 = handler._calculate_delay(attempt=2, exc=TimeoutError())
        delay3 = handler._calculate_delay(attempt=3, exc=TimeoutError())
        assert delay1 == 1.0
        assert delay2 == 2.0
        assert delay3 == 4.0

    @pytest.mark.asyncio
    async def test_max_delay_cap(self) -> None:
        """Test that delay is capped at max_delay."""
        handler = CommandRetryHandler(
            interface_id="test",
            timeout_config=TimeoutConfig(
                command_retry_base_delay=10.0,
                command_retry_backoff_factor=10.0,
                command_retry_max_delay=50.0,
            ),
            event_bus=_make_event_bus(),
        )
        delay = handler._calculate_delay(attempt=3, exc=TimeoutError())
        assert delay == 50.0

    @pytest.mark.asyncio
    async def test_transmission_pending_delay(self) -> None:
        """Test special delay for transmission pending fault."""
        handler = CommandRetryHandler(
            interface_id="test",
            timeout_config=TimeoutConfig(command_retry_transmission_pending_delay=5.0),
            event_bus=_make_event_bus(),
        )
        fault = XmlRpcFault(-10, "transmission pending")
        exc = ClientException("failed")
        exc.__cause__ = fault
        delay = handler._calculate_delay(attempt=1, exc=exc)
        assert delay == 5.0


# =============================================================================
# Collector retry derivation tests
# =============================================================================


class TestCollectorRetryDerivation:
    """Tests for CallParameterCollector retry logic."""

    def test_all_retryable_data_points(self) -> None:
        """Test that retry=True when all collected data points are retryable."""
        from aiohomematic.model.data_point import CallParameterCollector

        collector = CallParameterCollector(client=MagicMock())
        dp1 = self._make_dp(retryable=True)
        dp2 = self._make_dp(retryable=True)
        collector._collected_data_points.append((dp1, 0.5, None))
        collector._collected_data_points.append((dp2, 1.0, None))

        # Derive retry from _retryable (no explicit override)
        explicit_retries = [r for _, _, r in collector._collected_data_points if r is not None]
        assert not explicit_retries
        retry = all(getattr(dp, "_retryable", True) for dp, _, _ in collector._collected_data_points)
        assert retry is True

    def test_empty_collector_defaults_to_true(self) -> None:
        """Test that empty collector defaults to retry=True."""
        from aiohomematic.model.data_point import CallParameterCollector

        collector = CallParameterCollector(client=MagicMock())
        # No data points collected — default
        if explicit_retries := [r for _, _, r in collector._collected_data_points if r is not None]:
            retry = any(explicit_retries)
        elif collector._collected_data_points:
            retry = all(getattr(dp, "_retryable", True) for dp, _, _ in collector._collected_data_points)
        else:
            retry = True
        assert retry is True

    def test_explicit_false_overrides_retryable(self) -> None:
        """Test that explicit retry=False overrides _retryable=True."""
        from aiohomematic.model.data_point import CallParameterCollector

        collector = CallParameterCollector(client=MagicMock())
        dp1 = self._make_dp(retryable=True)
        collector._collected_data_points.append((dp1, 0.5, False))

        explicit_retries = [r for _, _, r in collector._collected_data_points if r is not None]
        assert explicit_retries == [False]
        retry = any(explicit_retries)
        assert retry is False

    def test_explicit_override_wins_over_retryable(self) -> None:
        """Test that explicit retry=True overrides _retryable=False."""
        from aiohomematic.model.data_point import CallParameterCollector

        collector = CallParameterCollector(client=MagicMock())
        dp1 = self._make_dp(retryable=False)
        # Explicit retry=True override (as set by climate.set_mode for DpAction)
        collector._collected_data_points.append((dp1, True, True))

        explicit_retries = [r for _, _, r in collector._collected_data_points if r is not None]
        assert explicit_retries == [True]
        retry = any(explicit_retries)
        assert retry is True

    def test_one_non_retryable_data_point(self) -> None:
        """Test that retry=False when any collected data point is non-retryable."""
        from aiohomematic.model.data_point import CallParameterCollector

        collector = CallParameterCollector(client=MagicMock())
        dp1 = self._make_dp(retryable=True)
        dp2 = self._make_dp(retryable=False)
        collector._collected_data_points.append((dp1, 0.5, None))
        collector._collected_data_points.append((dp2, True, None))

        retry = all(getattr(dp, "_retryable", True) for dp, _, _ in collector._collected_data_points)
        assert retry is False

    def _make_dp(self, *, retryable: bool = True) -> MagicMock:
        """Create a mock data point with _retryable attribute."""
        dp = MagicMock()
        dp._retryable = retryable
        dp.paramset_key = "VALUES"
        dp.channel.address = "VCU0000001:1"
        dp.parameter = "LEVEL"
        dp.get_command_priority.return_value = MagicMock(value=1)
        return dp


# =============================================================================
# Retryable attribute tests for data point types
# =============================================================================


class TestDataPointRetryableAttribute:
    """Tests that _retryable is correctly set on data point types."""

    def test_dp_action_float_retryable(self) -> None:
        """Test DpActionFloat has _retryable=True (inherited default)."""
        from aiohomematic.model.generic import DpActionFloat

        assert DpActionFloat._retryable is True

    def test_dp_action_not_retryable(self) -> None:
        """Test DpAction has _retryable=False."""
        from aiohomematic.model.generic import DpAction

        assert DpAction._retryable is False

    def test_dp_action_select_retryable(self) -> None:
        """Test DpActionSelect has _retryable=True (inherited default)."""
        from aiohomematic.model.generic import DpActionSelect

        assert DpActionSelect._retryable is True

    def test_dp_button_not_retryable(self) -> None:
        """Test DpButton has _retryable=False."""
        from aiohomematic.model.generic import DpButton

        assert DpButton._retryable is False

    def test_dp_float_retryable(self) -> None:
        """Test DpFloat has _retryable=True (inherited default)."""
        from aiohomematic.model.generic import DpFloat

        assert DpFloat._retryable is True

    def test_dp_select_retryable(self) -> None:
        """Test DpSelect has _retryable=True (inherited default)."""
        from aiohomematic.model.generic import DpSelect

        assert DpSelect._retryable is True

    def test_dp_switch_retryable(self) -> None:
        """Test DpSwitch has _retryable=True (inherited default)."""
        from aiohomematic.model.generic import DpSwitch

        assert DpSwitch._retryable is True

    def test_generic_data_point_retryable_default(self) -> None:
        """Test GenericDataPoint has _retryable=True by default."""
        from aiohomematic.model.generic import GenericDataPoint

        assert GenericDataPoint._retryable is True


# =============================================================================
# Integration tests: retry flow through model layer
# =============================================================================


class TestRetryIntegration:
    """Integration tests for retry parameter flow through model/client layers."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            ({"VCU9724704"}, True, None, None),
        ],
    )
    async def test_action_select_passes_retry_true(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpActionSelect (retryable) passes retry=True through to client."""
        from unittest.mock import call

        from aiohomematic.model.generic import DpActionSelect

        central, mock_client, _ = central_client_factory_with_homegear_client
        action_select = cast(
            DpActionSelect,
            central.query_facade.get_generic_data_point(channel_address="VCU9724704:1", parameter="LOCK_TARGET_LEVEL"),
        )
        await action_select.send_value(value="LOCKED")
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9724704:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LOCK_TARGET_LEVEL",
            value="LOCKED",
            priority=CommandPriority.HIGH,
            retry=True,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            ({"VCU1437294"}, True, None, None),
        ],
    )
    async def test_button_passes_retry_false(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpButton (non-retryable) passes retry=False through to client."""
        from typing import cast
        from unittest.mock import call

        from aiohomematic.model.generic import DpButton

        central, mock_client, _ = central_client_factory_with_homegear_client
        button = cast(
            DpButton,
            central.query_facade.get_generic_data_point(channel_address="VCU1437294:1", parameter="RESET_MOTION"),
        )
        await button.press()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1437294:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="RESET_MOTION",
            value=True,
            priority=CommandPriority.HIGH,
            retry=False,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            ({"VCU9724704"}, True, None, None),
        ],
    )
    async def test_explicit_retry_false_overrides_retryable(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that explicit retry=False on send_value overrides _retryable=True."""
        from unittest.mock import call

        from aiohomematic.model.generic import DpActionSelect

        central, mock_client, _ = central_client_factory_with_homegear_client
        action_select = cast(
            DpActionSelect,
            central.query_facade.get_generic_data_point(channel_address="VCU9724704:1", parameter="LOCK_TARGET_LEVEL"),
        )
        await action_select.send_value(value="OPEN", retry=False)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9724704:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LOCK_TARGET_LEVEL",
            value="OPEN",
            priority=CommandPriority.HIGH,
            retry=False,
        )


# =============================================================================
# Purge cancellation tests
# =============================================================================


class TestPurgeCancellation:
    """Tests for purge_addresses cancelling pending retries."""

    @pytest.mark.asyncio
    async def test_purge_addresses_cancels_device_retries(self) -> None:
        """Test that set_value with purge_addresses cancels device retries."""
        handler = CommandRetryHandler(
            interface_id="test",
            timeout_config=TimeoutConfig(),
            event_bus=_make_event_bus(),
        )
        # Manually inject a fake active retry
        dpk = _make_dpk(parameter="LEVEL")
        fake_task = MagicMock()
        fake_task.done.return_value = False
        handler._active_retries[dpk] = fake_task

        assert handler.active_retry_count == 1

        # Cancel retries for the device
        cancelled = handler.cancel_retries_for_device(device_address="VCU0000001")
        assert cancelled == 1
        assert handler.active_retry_count == 0
        fake_task.cancel.assert_called_once()
        assert handler.metrics.cancelled_retries == 1

    @pytest.mark.asyncio
    async def test_purge_does_not_cancel_other_devices(self) -> None:
        """Test that purge only cancels retries for the targeted device."""
        handler = CommandRetryHandler(
            interface_id="test",
            timeout_config=TimeoutConfig(),
            event_bus=_make_event_bus(),
        )
        dpk1 = DataPointKey(
            interface_id="test",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
        )
        dpk2 = DataPointKey(
            interface_id="test",
            channel_address="VCU0000002:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        task1 = MagicMock()
        task1.done.return_value = False
        task2 = MagicMock()
        task2.done.return_value = False
        handler._active_retries[dpk1] = task1
        handler._active_retries[dpk2] = task2

        cancelled = handler.cancel_retries_for_device(device_address="VCU0000001")
        assert cancelled == 1
        assert handler.active_retry_count == 1
        task1.cancel.assert_called_once()
        task2.cancel.assert_not_called()


# =============================================================================
# Interface-level cancellation tests
# =============================================================================


class TestInterfaceCancellation:
    """Tests for interface-level retry cancellation (e.g., on stop)."""

    def test_cancel_all_retries_for_interface(self) -> None:
        """Test that cancel_retries_for_interface cancels all active retries."""
        handler = CommandRetryHandler(
            interface_id="test",
            timeout_config=TimeoutConfig(),
            event_bus=_make_event_bus(),
        )
        dpk1 = _make_dpk(parameter="LEVEL")
        dpk2 = _make_dpk(parameter="STATE")
        task1 = MagicMock()
        task1.done.return_value = False
        task2 = MagicMock()
        task2.done.return_value = False
        handler._active_retries[dpk1] = task1
        handler._active_retries[dpk2] = task2

        cancelled = handler.cancel_retries_for_interface()
        assert cancelled == 2
        assert handler.active_retry_count == 0
        task1.cancel.assert_called_once()
        task2.cancel.assert_called_once()
        assert handler.metrics.cancelled_retries == 2

    def test_cancel_already_done_task(self) -> None:
        """Test that cancelling an already-done task does not call cancel()."""
        handler = CommandRetryHandler(
            interface_id="test",
            timeout_config=TimeoutConfig(),
            event_bus=_make_event_bus(),
        )
        dpk = _make_dpk()
        done_task = MagicMock()
        done_task.done.return_value = True
        handler._active_retries[dpk] = done_task

        cancelled = handler.cancel_retries_for_dpk(dpk=dpk)
        assert cancelled == 1
        done_task.cancel.assert_not_called()  # Already done, no cancel needed
