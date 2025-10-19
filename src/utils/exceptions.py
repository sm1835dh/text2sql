"""
Custom exception classes for the Text2SQL application.
"""

from typing import Optional, Dict, Any
from src.config.constants import ErrorCode


class Text2SQLException(Exception):
    """Base exception for all Text2SQL errors."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize exception.

        Args:
            message: Error message
            error_code: Standardized error code
            details: Additional error details
        """
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code.value,
            "details": self.details
        }


class ConnectionError(Text2SQLException):
    """Raised when connection to external service fails."""

    def __init__(self, message: str, service: str, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.CONNECTION_ERROR,
            details={"service": service, **kwargs}
        )


class ValidationError(Text2SQLException):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details={"field": field, **kwargs} if field else kwargs
        )


class SQLGenerationError(Text2SQLException):
    """Raised when SQL generation fails."""

    def __init__(self, message: str, question: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.SQL_GENERATION_ERROR,
            details={"question": question, **kwargs} if question else kwargs
        )


class SQLExecutionError(Text2SQLException):
    """Raised when SQL execution fails."""

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        original_error: Optional[str] = None,
        **kwargs
    ):
        details = {}
        if query:
            details["query"] = query
        if original_error:
            details["original_error"] = original_error
        details.update(kwargs)

        super().__init__(
            message=message,
            error_code=ErrorCode.SQL_EXECUTION_ERROR,
            details=details
        )


class IntentClassificationError(Text2SQLException):
    """Raised when intent classification fails."""

    def __init__(self, message: str, question: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.INTENT_CLASSIFICATION_ERROR,
            details={"question": question, **kwargs} if question else kwargs
        )


class EntityExtractionError(Text2SQLException):
    """Raised when entity extraction fails."""

    def __init__(self, message: str, question: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.ENTITY_EXTRACTION_ERROR,
            details={"question": question, **kwargs} if question else kwargs
        )


class RateLimitError(Text2SQLException):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[float] = None,
        **kwargs
    ):
        details = {"retry_after": retry_after} if retry_after else {}
        details.update(kwargs)

        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_ERROR,
            details=details
        )


class TimeoutError(Text2SQLException):
    """Raised when operation times out."""

    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[float] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        details = {}
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds
        if operation:
            details["operation"] = operation
        details.update(kwargs)

        super().__init__(
            message=message,
            error_code=ErrorCode.TIMEOUT_ERROR,
            details=details
        )


class AuthenticationError(Text2SQLException):
    """Raised when authentication fails."""

    def __init__(self, message: str, service: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHENTICATION_ERROR,
            details={"service": service, **kwargs} if service else kwargs
        )


class ConfigurationError(Text2SQLException):
    """Raised when configuration is invalid."""

    def __init__(self, message: str, setting: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details={"setting": setting, **kwargs} if setting else kwargs
        )


class SchemaError(Text2SQLException):
    """Raised when database schema issues occur."""

    def __init__(
        self,
        message: str,
        table: Optional[str] = None,
        column: Optional[str] = None,
        **kwargs
    ):
        details = {}
        if table:
            details["table"] = table
        if column:
            details["column"] = column
        details.update(kwargs)

        super().__init__(
            message=message,
            error_code=ErrorCode.SQL_GENERATION_ERROR,
            details=details
        )


class WorkflowError(Text2SQLException):
    """Raised when workflow execution fails."""

    def __init__(
        self,
        message: str,
        node: Optional[str] = None,
        state: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        details = {}
        if node:
            details["node"] = node
        if state:
            details["state"] = state
        details.update(kwargs)

        super().__init__(
            message=message,
            error_code=ErrorCode.UNKNOWN_ERROR,
            details=details
        )


class RetryableError(Text2SQLException):
    """Base class for errors that can be retried."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        max_retries: int = 3,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, details)
        self.max_retries = max_retries


class NonRetryableError(Text2SQLException):
    """Base class for errors that should not be retried."""
    pass


# Helper functions
def is_retryable(exception: Exception) -> bool:
    """
    Check if an exception is retryable.

    Args:
        exception: The exception to check

    Returns:
        True if the exception can be retried
    """
    # Retryable exceptions
    if isinstance(exception, RetryableError):
        return True

    # Specific retryable cases
    if isinstance(exception, (ConnectionError, TimeoutError, RateLimitError)):
        return True

    # Non-retryable exceptions
    if isinstance(exception, NonRetryableError):
        return False

    # Specific non-retryable cases
    if isinstance(exception, (ValidationError, AuthenticationError, ConfigurationError)):
        return False

    # Default to not retrying unknown exceptions
    return False


def get_retry_delay(exception: Exception, attempt: int = 1) -> float:
    """
    Calculate retry delay based on exception type and attempt number.

    Args:
        exception: The exception that occurred
        attempt: Current retry attempt number

    Returns:
        Delay in seconds before retrying
    """
    base_delay = 1.0

    # Rate limit errors may have specific retry-after
    if isinstance(exception, RateLimitError):
        if exception.details.get("retry_after"):
            return float(exception.details["retry_after"])

    # Exponential backoff for other retryable errors
    if is_retryable(exception):
        return min(base_delay * (2 ** attempt), 60)  # Cap at 60 seconds

    return 0