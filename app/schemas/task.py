from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class TaskBase(BaseModel):
    title: str
    description: str
    state: Literal["todo", "in_progress", "done"] = "todo"
    due_date: Optional[str] = None
    reward: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class Task(TaskBase):
    id: int

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    state: Optional[Literal["todo", "in_progress", "done"]] = None
    due_date: Optional[str] = None
    reward: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class TaskInDB(Task):
    pass
