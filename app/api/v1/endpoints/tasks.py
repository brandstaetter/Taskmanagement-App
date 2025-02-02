from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.printing import PrinterFactory
from app.db.base import get_db
from app.schemas.task import Task, TaskCreate, TaskUpdate
from app.crud.task import (
    create_task,
    get_task,
    get_tasks,
)

router = APIRouter()


@router.get("", response_model=List[Task])
def read_tasks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Retrieve tasks.
    """
    tasks = get_tasks(db, skip=skip, limit=limit)
    return tasks


@router.post("", response_model=Task)
def create_new_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
):
    """
    Create new task.
    """
    return create_task(db=db, task=task)


@router.get("/due/", response_model=List[Task])
def read_due_tasks(db: Session = Depends(get_db)) -> List[Task]:
    """
    Retrieve all tasks that are due within the next 24 hours.
    """
    tasks = get_tasks(db, skip=0, limit=100)
    due_tasks = [task for task in tasks if task.due_date and (task.due_date - datetime.now()).days <= 1]
    return due_tasks


@router.get("/random/", response_model=Task)
def read_random_task(db: Session = Depends(get_db)) -> Task:
    """
    Get a random task, prioritizing tasks that are due sooner.
    Raises HTTPException if no tasks are available.
    """
    tasks = get_tasks(db, skip=0, limit=100)
    if not tasks:
        raise HTTPException(status_code=404, detail="No tasks available")
    tasks.sort(key=lambda task: task.due_date if task.due_date else datetime.max)
    return tasks[0]


@router.get("/{task_id}", response_model=Task)
def read_task(
    task_id: int,
    db: Session = Depends(get_db),
):
    """
    Get task by ID.
    """
    db_task = get_task(db=db, task_id=task_id)
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return db_task


@router.post("/{task_id}/complete", response_model=Task)
def complete_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    """
    Mark a task as completed.
    """
    task = get_task(db, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.state == "done":
        raise HTTPException(status_code=400, detail="Task is already completed")
    return update_task(db=db, task_id=task_id, task={"state": "done"})


@router.post("/{task_id}/start", response_model=Task)
def start_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    """
    Mark a task as in progress.
    """
    task = get_task(db, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.state == "done":
        raise HTTPException(status_code=400, detail="Cannot start a completed task")
    if task.state == "in_progress":
        raise HTTPException(status_code=400, detail="Task is already in progress")
    return update_task(db=db, task_id=task_id, task={"state": "in_progress"})


@router.get("/{task_id}/print")
async def print_task(
    task_id: int,
    printer_type: Optional[str] = Query(None, description="Type of printer to use"),
    db: Session = Depends(get_db),
) -> Response:
    """
    Print a task using the specified printer (defaults to PDF).
    """
    # Get the task
    db_task = get_task(db=db, task_id=task_id)
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    try:
        # Create printer instance
        printer = PrinterFactory.create_printer(printer_type)
         
        # Generate and return the printed document
        return await printer.print(db_task)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error printing task: {str(e)} {type(e)}"
        )
