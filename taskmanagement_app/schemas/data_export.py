from typing import Optional

from pydantic import BaseModel


class ExportedUser(BaseModel):
    """User data for export (excludes sensitive fields like hashed_password)."""

    id: int
    email: str
    is_active: bool
    is_admin: bool
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class ExportedTask(BaseModel):
    """Task data for export."""

    id: int
    title: str
    description: str
    state: str
    due_date: Optional[str] = None
    reward: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_by: Optional[int] = None
    started_by: Optional[int] = None
    assigned_user_ids: list[int] = []


class DataExport(BaseModel):
    """Root export envelope with version for backwards compatibility."""

    version: int = 1
    users: list[ExportedUser]
    tasks: list[ExportedTask]


class ImportSkippedItem(BaseModel):
    """An item that was skipped during import."""

    type: str  # "user" or "task"
    identifier: str  # email for users, title for tasks
    reason: str


class ImportResult(BaseModel):
    """Summary of an import operation."""

    users_imported: int = 0
    users_skipped: int = 0
    tasks_imported: int = 0
    tasks_skipped: int = 0
    skipped_items: list[ImportSkippedItem] = []
