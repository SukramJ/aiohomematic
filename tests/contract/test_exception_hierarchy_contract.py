# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for exception hierarchy stability.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for exception types.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. Exception types exist with correct hierarchy
2. BaseHomematicException has name attribute
3. Exception types can be caught correctly
4. Exception message handling works

See ADR-0018 for architectural context.
"""

from __future__ import annotations

from aiohomematic.exceptions import (
    AioHomematicConfigException,
    AioHomematicException,
    AuthFailure,
    BaseHomematicException,
    CircuitBreakerOpenException,
    ClientException,
    DescriptionNotFoundException,
    InternalBackendException,
    NoClientsException,
    NoConnectionException,
    UnsupportedException,
    ValidationException,
)

# =============================================================================
# Contract: BaseHomematicException
# =============================================================================


class TestBaseHomematicExceptionContract:
    """Contract: BaseHomematicException must remain stable."""

    def test_basehomematicexception_extends_exception(self) -> None:
        """Contract: BaseHomematicException extends Exception."""
        assert issubclass(BaseHomematicException, Exception)

    def test_basehomematicexception_has_name_attribute(self) -> None:
        """Contract: BaseHomematicException has name attribute."""
        exc = BaseHomematicException("TestException", "test message")
        assert hasattr(exc, "name")
        assert exc.name == "TestException"

    def test_basehomematicexception_stores_message(self) -> None:
        """Contract: BaseHomematicException stores message in args."""
        exc = BaseHomematicException("TestException", "test message")
        assert "test message" in str(exc.args)

    def test_basehomematicexception_wraps_exception_name(self) -> None:
        """Contract: BaseHomematicException extracts name from wrapped exception."""
        original = ValueError("original error")
        exc = BaseHomematicException("WrapperException", original)
        # When wrapping, the name becomes the wrapped exception's class name
        assert exc.name == "ValueError"


# =============================================================================
# Contract: ClientException
# =============================================================================


class TestClientExceptionContract:
    """Contract: ClientException must remain stable."""

    def test_clientexception_extends_basehomematicexception(self) -> None:
        """Contract: ClientException extends BaseHomematicException."""
        assert issubclass(ClientException, BaseHomematicException)

    def test_clientexception_has_correct_name(self) -> None:
        """Contract: ClientException has name 'ClientException'."""
        exc = ClientException("test message")
        assert exc.name == "ClientException"

    def test_clientexception_is_catchable_as_base(self) -> None:
        """Contract: ClientException can be caught as BaseHomematicException."""
        caught_exception: BaseHomematicException | None = None
        try:
            raise ClientException("test")
        except BaseHomematicException as exc:
            caught_exception = exc
        assert caught_exception is not None
        assert isinstance(caught_exception, ClientException)


# =============================================================================
# Contract: NoConnectionException
# =============================================================================


class TestNoConnectionExceptionContract:
    """Contract: NoConnectionException must remain stable."""

    def test_noconnectionexception_extends_basehomematicexception(self) -> None:
        """Contract: NoConnectionException extends BaseHomematicException."""
        assert issubclass(NoConnectionException, BaseHomematicException)

    def test_noconnectionexception_has_correct_name(self) -> None:
        """Contract: NoConnectionException has name 'NoConnectionException'."""
        exc = NoConnectionException("test message")
        assert exc.name == "NoConnectionException"


# =============================================================================
# Contract: CircuitBreakerOpenException
# =============================================================================


class TestCircuitBreakerOpenExceptionContract:
    """Contract: CircuitBreakerOpenException must remain stable."""

    def test_circuitbreakeropenexception_extends_basehomematicexception(self) -> None:
        """Contract: CircuitBreakerOpenException extends BaseHomematicException."""
        assert issubclass(CircuitBreakerOpenException, BaseHomematicException)

    def test_circuitbreakeropenexception_has_correct_name(self) -> None:
        """Contract: CircuitBreakerOpenException has name 'CircuitBreakerOpenException'."""
        exc = CircuitBreakerOpenException("test message")
        assert exc.name == "CircuitBreakerOpenException"


# =============================================================================
# Contract: AuthFailure
# =============================================================================


class TestAuthFailureContract:
    """Contract: AuthFailure must remain stable."""

    def test_authfailure_extends_basehomematicexception(self) -> None:
        """Contract: AuthFailure extends BaseHomematicException."""
        assert issubclass(AuthFailure, BaseHomematicException)

    def test_authfailure_has_correct_name(self) -> None:
        """Contract: AuthFailure has name 'AuthFailure'."""
        exc = AuthFailure("test message")
        assert exc.name == "AuthFailure"


# =============================================================================
# Contract: ValidationException
# =============================================================================


class TestValidationExceptionContract:
    """Contract: ValidationException must remain stable."""

    def test_validationexception_extends_basehomematicexception(self) -> None:
        """Contract: ValidationException extends BaseHomematicException."""
        assert issubclass(ValidationException, BaseHomematicException)

    def test_validationexception_has_correct_name(self) -> None:
        """Contract: ValidationException has name 'ValidationException'."""
        exc = ValidationException("test message")
        assert exc.name == "ValidationException"


# =============================================================================
# Contract: UnsupportedException
# =============================================================================


class TestUnsupportedExceptionContract:
    """Contract: UnsupportedException must remain stable."""

    def test_unsupportedexception_extends_basehomematicexception(self) -> None:
        """Contract: UnsupportedException extends BaseHomematicException."""
        assert issubclass(UnsupportedException, BaseHomematicException)

    def test_unsupportedexception_has_correct_name(self) -> None:
        """Contract: UnsupportedException has name 'UnsupportedException'."""
        exc = UnsupportedException("test message")
        assert exc.name == "UnsupportedException"


# =============================================================================
# Contract: AioHomematicException
# =============================================================================


class TestAioHomematicExceptionContract:
    """Contract: AioHomematicException must remain stable."""

    def test_aiohomematicexception_extends_basehomematicexception(self) -> None:
        """Contract: AioHomematicException extends BaseHomematicException."""
        assert issubclass(AioHomematicException, BaseHomematicException)

    def test_aiohomematicexception_has_correct_name(self) -> None:
        """Contract: AioHomematicException has name 'AioHomematicException'."""
        exc = AioHomematicException("test message")
        assert exc.name == "AioHomematicException"


# =============================================================================
# Contract: AioHomematicConfigException
# =============================================================================


class TestAioHomematicConfigExceptionContract:
    """Contract: AioHomematicConfigException must remain stable."""

    def test_aiohomematicconfigexception_extends_basehomematicexception(self) -> None:
        """Contract: AioHomematicConfigException extends BaseHomematicException."""
        assert issubclass(AioHomematicConfigException, BaseHomematicException)

    def test_aiohomematicconfigexception_has_correct_name(self) -> None:
        """Contract: AioHomematicConfigException has name 'AioHomematicConfigException'."""
        exc = AioHomematicConfigException("test message")
        assert exc.name == "AioHomematicConfigException"


# =============================================================================
# Contract: NoClientsException
# =============================================================================


class TestNoClientsExceptionContract:
    """Contract: NoClientsException must remain stable."""

    def test_noclientsexception_extends_basehomematicexception(self) -> None:
        """Contract: NoClientsException extends BaseHomematicException."""
        assert issubclass(NoClientsException, BaseHomematicException)

    def test_noclientsexception_has_correct_name(self) -> None:
        """Contract: NoClientsException has name 'NoClientsException'."""
        exc = NoClientsException("test message")
        assert exc.name == "NoClientsException"


# =============================================================================
# Contract: InternalBackendException
# =============================================================================


class TestInternalBackendExceptionContract:
    """Contract: InternalBackendException must remain stable."""

    def test_internalbackendexception_extends_basehomematicexception(self) -> None:
        """Contract: InternalBackendException extends BaseHomematicException."""
        assert issubclass(InternalBackendException, BaseHomematicException)

    def test_internalbackendexception_has_correct_name(self) -> None:
        """Contract: InternalBackendException has name 'InternalBackendException'."""
        exc = InternalBackendException("test message")
        assert exc.name == "InternalBackendException"


# =============================================================================
# Contract: DescriptionNotFoundException
# =============================================================================


class TestDescriptionNotFoundExceptionContract:
    """Contract: DescriptionNotFoundException must remain stable."""

    def test_descriptionnotfoundexception_extends_basehomematicexception(self) -> None:
        """Contract: DescriptionNotFoundException extends BaseHomematicException."""
        assert issubclass(DescriptionNotFoundException, BaseHomematicException)

    def test_descriptionnotfoundexception_has_correct_name(self) -> None:
        """Contract: DescriptionNotFoundException has name 'DescriptionNotFoundException'."""
        exc = DescriptionNotFoundException("test message")
        assert exc.name == "DescriptionNotFoundException"


# =============================================================================
# Contract: Exception Hierarchy Completeness
# =============================================================================


class TestExceptionHierarchyContract:
    """Contract: Exception hierarchy must be complete."""

    def test_all_exceptions_extend_basehomematicexception(self) -> None:
        """Contract: All custom exceptions extend BaseHomematicException."""
        exception_classes = [
            ClientException,
            NoConnectionException,
            CircuitBreakerOpenException,
            AuthFailure,
            ValidationException,
            UnsupportedException,
            AioHomematicException,
            AioHomematicConfigException,
            NoClientsException,
            InternalBackendException,
            DescriptionNotFoundException,
        ]

        for exc_class in exception_classes:
            assert issubclass(exc_class, BaseHomematicException), (
                f"{exc_class.__name__} should extend BaseHomematicException"
            )

    def test_all_exceptions_have_name_attribute(self) -> None:
        """Contract: All custom exceptions have name attribute after instantiation."""
        exception_classes = [
            (ClientException, "ClientException"),
            (NoConnectionException, "NoConnectionException"),
            (CircuitBreakerOpenException, "CircuitBreakerOpenException"),
            (AuthFailure, "AuthFailure"),
            (ValidationException, "ValidationException"),
            (UnsupportedException, "UnsupportedException"),
            (AioHomematicException, "AioHomematicException"),
            (AioHomematicConfigException, "AioHomematicConfigException"),
            (NoClientsException, "NoClientsException"),
            (InternalBackendException, "InternalBackendException"),
            (DescriptionNotFoundException, "DescriptionNotFoundException"),
        ]

        for exc_class, expected_name in exception_classes:
            exc = exc_class("test")
            assert hasattr(exc, "name"), f"{exc_class.__name__} should have name attribute"
            assert exc.name == expected_name, f"{exc_class.__name__}.name should be {expected_name}"


# =============================================================================
# Contract: Exception Catching Patterns
# =============================================================================


class TestExceptionCatchingPatternsContract:
    """Contract: Exception catching patterns must work correctly."""

    def test_auth_failure_can_be_caught_specifically(self) -> None:
        """Contract: AuthFailure can be caught specifically."""
        caught_exception: AuthFailure | None = None
        try:
            raise AuthFailure("test")
        except AuthFailure as exc:
            caught_exception = exc
        assert caught_exception is not None
        assert caught_exception.name == "AuthFailure"

    def test_catch_all_aiohomematic_exceptions(self) -> None:
        """Contract: All aiohomematic exceptions can be caught with BaseHomematicException."""
        exceptions_to_test = [
            ClientException("test"),
            NoConnectionException("test"),
            CircuitBreakerOpenException("test"),
            AuthFailure("test"),
            ValidationException("test"),
            UnsupportedException("test"),
            AioHomematicException("test"),
            AioHomematicConfigException("test"),
            NoClientsException("test"),
            InternalBackendException("test"),
            DescriptionNotFoundException("test"),
        ]

        for exc in exceptions_to_test:
            try:
                raise exc
            except BaseHomematicException:
                pass  # Should be caught
            except Exception:
                raise AssertionError(f"{type(exc).__name__} was not caught by BaseHomematicException") from None

    def test_client_exception_not_caught_as_auth_failure(self) -> None:
        """Contract: ClientException is not caught by except AuthFailure."""
        try:
            raise ClientException("test")
        except AuthFailure:
            raise AssertionError("ClientException should not be caught as AuthFailure") from None
        except BaseHomematicException:
            pass  # Correct - caught as base
