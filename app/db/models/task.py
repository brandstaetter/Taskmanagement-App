import enum

from sqlalchemy import Column, Enum, Integer, String
from sqlalchemy.sql import func

from app.db.base import Base


class TaskState(str, enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    state = Column(Enum(TaskState), default=TaskState.todo)
    due_date = Column(String, nullable=True)
    reward = Column(String, nullable=True)
    created_at = Column(String, server_default=func.now())
    started_at = Column(String, nullable=True)
    completed_at = Column(String, nullable=True)
