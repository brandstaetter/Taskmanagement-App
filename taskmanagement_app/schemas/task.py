from datetime import datetime
from typing import Annotated, Any, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
    model_validator,
)


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
    assignment_type: Literal["any", "some", "one"] = "any"
    assigned_to: Optional[int] = None
    assigned_user_ids: Optional[list[int]] = None

    @model_validator(mode="after")
    def validate_assignment_consistency(self) -> Any:
        assignment_type = self.assignment_type
        assigned_to = self.assigned_to
        assigned_user_ids = self.assigned_user_ids

        if assignment_type == "one":
            if assigned_to is None:
                raise ValueError(
                    "assigned_to must be specified when assignment_type is 'one'"
                )
            if assigned_user_ids is not None and assigned_user_ids:
                raise ValueError(
                    "assigned_user_ids must be None or empty "
                    "when assignment_type is 'one'"
                )

        elif assignment_type == "some":
            if assigned_user_ids is None or not assigned_user_ids:
                raise ValueError(
                    "assigned_user_ids must be specified when assignment_type is 'some'"
                )
            if assigned_to is not None:
                raise ValueError(
                    "assigned_to must be None when assignment_type is 'some'"
                )

        elif assignment_type == "any":
            if assigned_to is not None:
                raise ValueError(
                    "assigned_to must be None when assignment_type is 'any'"
                )
            if assigned_user_ids is not None and assigned_user_ids:
                raise ValueError(
                    "assigned_user_ids must be None or empty "
                    "when assignment_type is 'any'"
                )

        return self

    model_config = ConfigDict(from_attributes=True)


class Task(TaskBase):
    id: int


class TaskCreate(TaskBase):
    created_by: int


class TaskUpdate(BaseModel):
    title: Optional[Annotated[str, StringConstraints(min_length=1)]] = None
    description: Optional[Annotated[str, StringConstraints(min_length=1)]] = None
    state: Optional[Literal["todo", "in_progress", "done", "archived"]] = None
    due_date: Optional[str] = None
    reward: Optional[str] = None
    assignment_type: Optional[Literal["any", "some", "one"]] = None
    assigned_to: Optional[int] = None
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
