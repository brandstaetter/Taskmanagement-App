from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator


class TaskBase(BaseModel):
    title: str
    description: str
    state: Literal["todo", "in_progress", "done", "archived"] = "todo"
    due_date: Optional[datetime] = None
    reward: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


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

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        try:
            return v
        except (ValueError, TypeError):
            raise ValueError("Invalid date format. Must be datetime object")

    model_config = ConfigDict(from_attributes=True)


class TaskInDB(Task):
    pass
