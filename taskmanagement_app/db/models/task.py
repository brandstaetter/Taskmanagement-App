import enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from taskmanagement_app.db.base import Base

# Constant for users.id foreign key reference
USERS_ID_FK = "users.id"

if TYPE_CHECKING:
    from .user import User


class TaskState(str, enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"
    archived = "archived"


# Association table for many-to-many relationship between tasks and users
task_assigned_users = Table(
    "task_assigned_users",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id"), primary_key=True),
    Column("user_id", ForeignKey(USERS_ID_FK), primary_key=True),
)


class TaskModel(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)
    state: Mapped[TaskState] = mapped_column(Enum(TaskState), default=TaskState.todo)
    due_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reward: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, server_default=func.now())
    started_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # Creator and worker fields
    created_by: Mapped[int] = mapped_column(
        ForeignKey(USERS_ID_FK), nullable=False, index=True
    )
    started_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey(USERS_ID_FK), nullable=True, index=True
    )

    # Relationships
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    assigned_users: Mapped[list["User"]] = relationship(
        "User", secondary=task_assigned_users, back_populates="assigned_tasks"
    )
    worker: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[started_by], back_populates="working_tasks"
    )
