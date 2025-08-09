"""Custom exceptions for AI services."""

from typing import Any, Dict, Optional


class WearForceException(Exception):
    """Base exception for WearForce services."""
    
    def __init__(
        self,
        message: str,
        error_code: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
    ) -> None:
        """Initialize exception."""
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.status_code = status_code


class ValidationError(WearForceException):
    """Validation error."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize validation error."""
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details or {},
            status_code=400,
        )
        if field:
            self.details["field"] = field


class AudioProcessingError(WearForceException):
    """Audio processing error."""
    
    def __init__(
        self,
        message: str,
        operation: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize audio processing error."""
        super().__init__(
            message=message,
            error_code="AUDIO_PROCESSING_ERROR",
            details=details or {},
            status_code=422,
        )
        self.details["operation"] = operation


class ModelInferenceError(WearForceException):
    """Model inference error."""
    
    def __init__(
        self,
        message: str,
        model_name: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize model inference error."""
        super().__init__(
            message=message,
            error_code="MODEL_INFERENCE_ERROR",
            details=details or {},
            status_code=502,
        )
        self.details["model"] = model_name


class VectorDatabaseError(WearForceException):
    """Vector database error."""
    
    def __init__(
        self,
        message: str,
        operation: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize vector database error."""
        super().__init__(
            message=message,
            error_code="VECTOR_DB_ERROR",
            details=details or {},
            status_code=503,
        )
        self.details["operation"] = operation


class ExternalServiceError(WearForceException):
    """External service error."""
    
    def __init__(
        self,
        message: str,
        service_name: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize external service error."""
        super().__init__(
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
            details=details or {},
            status_code=503,
        )
        self.details["service"] = service_name


class RateLimitError(WearForceException):
    """Rate limit exceeded error."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize rate limit error."""
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            details=details or {},
            status_code=429,
        )


class AuthenticationError(WearForceException):
    """Authentication error."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize authentication error."""
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            details=details or {},
            status_code=401,
        )


class AuthorizationError(WearForceException):
    """Authorization error."""
    
    def __init__(
        self,
        message: str = "Access denied",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize authorization error."""
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            details=details or {},
            status_code=403,
        )


class ResourceNotFoundError(WearForceException):
    """Resource not found error."""
    
    def __init__(
        self,
        resource: str,
        identifier: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize resource not found error."""
        super().__init__(
            message=f"{resource} not found: {identifier}",
            error_code="RESOURCE_NOT_FOUND",
            details=details or {},
            status_code=404,
        )
        self.details.update({
            "resource": resource,
            "identifier": identifier,
        })


class ConversationError(WearForceException):
    """Conversation management error."""
    
    def __init__(
        self,
        message: str,
        conversation_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize conversation error."""
        super().__init__(
            message=message,
            error_code="CONVERSATION_ERROR",
            details=details or {},
            status_code=422,
        )
        self.details["conversation_id"] = conversation_id


class ConfigurationError(WearForceException):
    """Configuration error."""
    
    def __init__(
        self,
        message: str,
        config_key: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize configuration error."""
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            details=details or {},
            status_code=500,
        )
        self.details["config_key"] = config_key