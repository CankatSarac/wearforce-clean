from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class WearForceException(Exception):
    """Base exception class for WearForce services."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationException(WearForceException):
    """Exception raised when data validation fails."""
    pass


class NotFoundException(WearForceException):
    """Exception raised when a resource is not found."""
    pass


class AlreadyExistsException(WearForceException):
    """Exception raised when trying to create a resource that already exists."""
    pass


class UnauthorizedException(WearForceException):
    """Exception raised when user is not authorized."""
    pass


class ForbiddenException(WearForceException):
    """Exception raised when user doesn't have permission."""
    pass


class ServiceUnavailableException(WearForceException):
    """Exception raised when a service is unavailable."""
    pass


class DatabaseException(WearForceException):
    """Exception raised when database operations fail."""
    pass


class EventPublishException(WearForceException):
    """Exception raised when event publishing fails."""
    pass


def exception_handler(exc: WearForceException) -> HTTPException:
    """Convert WearForce exceptions to HTTP exceptions."""
    if isinstance(exc, NotFoundException):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": exc.message, "details": exc.details}
        )
    elif isinstance(exc, AlreadyExistsException):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": exc.message, "details": exc.details}
        )
    elif isinstance(exc, ValidationException):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": exc.message, "details": exc.details}
        )
    elif isinstance(exc, UnauthorizedException):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": exc.message, "details": exc.details}
        )
    elif isinstance(exc, ForbiddenException):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": exc.message, "details": exc.details}
        )
    elif isinstance(exc, ServiceUnavailableException):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": exc.message, "details": exc.details}
        )
    else:
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": exc.message, "details": exc.details}
        )