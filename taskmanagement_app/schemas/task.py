from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from taskmanagement_app.core.datetime_utils import ensure_timezone_aware


class TaskBase(BaseModel):
    title: str
    description: str
    state: Literal["todo", "in_progress", "done", "archived"] = "todo"
    due_date: Optional[datetime] = None
    reward: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda dt: (
                dt.astimezone(timezone.utc).isoformat().replace("Z", "+00:00")
                if dt
                else None
            )
        },
    )

    @field_validator("due_date", "created_at", "started_at", "completed_at")
    @classmethod
    def ensure_timezone(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields have timezone information."""
        return ensure_timezone_aware(v) if v else None


class Task(TaskBase):
    id: int


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[Annotated[str, StringConstraints(min_length=1)]] = None
    description: Optional[Annotated[str, StringConstraints(min_length=1)]] = None
    state: Optional[Literal["todo", "in_progress", "done", "archived"]] = None
    due_date: Optional[datetime] = None
    reward: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda dt: (
                dt.astimezone(timezone.utc).isoformat().replace("Z", "+00:00")
                if dt
                else None
            )
        },
    )

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate and ensure timezone information for due_date."""
        if v is None:
            return None
        return ensure_timezone_aware(v)


class TaskInDB(Task):
    pass
