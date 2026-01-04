from typing import Any, Optional

from pydantic import BaseModel


class DbOperationResponse(BaseModel):
    """Response for database operations."""

    message: str
    details: Optional[str] = None


class MigrationResponse(BaseModel):
    """Response for database migration operations."""

    message: str
    details: str


class PasswordResetResponse(BaseModel):
    """Response for password reset operations."""

    email: str
    new_password: str


class MaintenanceResponse(BaseModel):
    """Response for maintenance operations."""

    message: str


class RootResponse(BaseModel):
    """Response for root endpoint."""

    message: str


class GenericDictResponse(BaseModel):
    """Generic response for endpoints returning dict-like data."""

    data: dict[str, Any]


__all__ = [
    "DbOperationResponse",
    "MigrationResponse",
    "PasswordResetResponse",
    "MaintenanceResponse",
    "RootResponse",
    "GenericDictResponse",
]
