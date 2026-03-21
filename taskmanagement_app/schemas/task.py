from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
)


class AssignedUserDisplay(BaseModel):
    """Minimal user info for display in task assignment lists."""

    id: int
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class TaskBase(BaseModel):
    title: str
    description: str
    state: Literal["todo", "in_progress", "done", "archived"] = "todo"
    due_date: Optional[str] = None
    reward: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_by: Optional[int] = None
    assigned_user_ids: Optional[list[int]] = None

    model_config = ConfigDict(from_attributes=True)


class Task(TaskBase):
    id: int
    started_by: Optional[int] = None
    creator_display_name: Optional[str] = None
    worker_display_name: Optional[str] = None
    creator_avatar_url: Optional[str] = None
    worker_avatar_url: Optional[str] = None
    assigned_users_display: Optional[list[AssignedUserDisplay]] = None


class TaskCreate(TaskBase):
    created_by: int


class TaskUpdate(BaseModel):
    title: Optional[Annotated[str, StringConstraints(min_length=1)]] = None
    description: Optional[Annotated[str, StringConstraints(min_length=1)]] = None
    state: Optional[Literal["todo", "in_progress", "done", "archived"]] = None
    due_date: Optional[str] = None
    reward: Optional[str] = None
    assigned_user_ids: Optional[list[int]] = None

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except (ValueError, TypeError):
            raise ValueError(
                "Invalid date format. Must be ISO format (e.g. 2025-02-21T12:00:00Z)"
            )

    model_config = ConfigDict(from_attributes=True)


class TaskInDB(Task):
    pass
