from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud
from app.db.base import get_db
from app.schemas.task import Task, TaskCreate

router = APIRouter()


@router.get("/", response_model=List[Task])
def read_tasks(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> List[Task]:
    """
    Retrieve tasks.
    """
    tasks = crud.get_tasks(db, skip=skip, limit=limit)
    return tasks


@router.post("/", response_model=Task)
def create_task(task: TaskCreate, db: Session = Depends(get_db)) -> Task:
    """
    Create new task.
    """
    return crud.create_task(db=db, task=task)


@router.get("/due/", response_model=List[Task])
def read_due_tasks(db: Session = Depends(get_db)) -> List[Task]:
    """
    Retrieve all tasks that are due within the next 24 hours.
    """
    tasks = crud.get_due_tasks(db)
    return tasks


@router.get("/random/", response_model=Task)
def read_random_task(db: Session = Depends(get_db)) -> Task:
    """
    Get a random task, prioritizing tasks that are due sooner.
    Raises HTTPException if no tasks are available.
    """
    task = crud.get_random_task(db)
    if task is None:
        raise HTTPException(status_code=404, detail="No tasks available")
    return task


@router.get("/{task_id}", response_model=Task)
def read_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    """
    Get a specific task by ID.
    """
    task = crud.get_task(db, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/complete", response_model=Task)
def complete_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    """
    Mark a task as completed.
    """
    task = crud.get_task(db, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.state == "done":
        raise HTTPException(status_code=400, detail="Task is already completed")
    return crud.complete_task(db=db, task=task)


@router.post("/{task_id}/start", response_model=Task)
def start_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    """
    Mark a task as in progress.
    """
    task = crud.get_task(db, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.state == "done":
        raise HTTPException(status_code=400, detail="Cannot start a completed task")
    if task.state == "in_progress":
        raise HTTPException(status_code=400, detail="Task is already in progress")
    return crud.start_task(db=db, task=task)


@router.post("/{task_id}/print")
def print_task(task_id: int, db: Session = Depends(get_db)):
    """
    Print a task. Implementation pending.
    """
    # Implementation will be added later
    pass
