"""Utility functions for datetime handling."""

from datetime import datetime, timezone
from typing import Optional


def ensure_timezone_aware(dt: datetime) -> datetime:
    """Ensure datetime has timezone information."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utc_now() -> datetime:
    """Get current UTC datetime with timezone information."""
    return datetime.now(timezone.utc)


def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime consistently with +00:00 timezone format."""
    if dt is None:
        return None
    dt = ensure_timezone_aware(dt)
    return dt.isoformat().replace('Z', '+00:00')
