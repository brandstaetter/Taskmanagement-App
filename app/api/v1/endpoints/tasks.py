from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.printing.printer_factory import PrinterFactory
from app.crud.task import (create_task, delete_task, get_task, get_tasks,
                           read_random_task, update_task)
from app.db.models.task import TaskState
from app.db.session import get_db
from app.schemas.task import Task, TaskCreate

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
    due_tasks = [
        task
        for task in tasks
        if task.due_date
        and (
            datetime.fromisoformat(task.due_date.replace("Z", "+00:00"))
            - datetime.now(timezone.utc)
        ).days
        <= 1
    ]
    # Sort tasks by due date, handling None values
    due_tasks.sort(
        key=lambda x: datetime.fromisoformat(x.due_date.replace("Z", "+00:00"))
        if x.due_date
        else datetime.max.replace(tzinfo=timezone.utc)
    )
    return due_tasks


@router.get("/random", response_model=Optional[Task])
def get_random_task(
    db: Session = Depends(get_db),
) -> Optional[Task]:
    """
    Get a random task, prioritizing tasks that are:
    1. Not completed
    2. Due sooner
    3. Not yet started
    """
    return read_random_task(db=db)


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


@router.post("/{task_id}/start", response_model=Task)
def start_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    """
    Mark a task as in progress and set the started_at timestamp.
    """
    # Check current task state
    current_task = get_task(db=db, task_id=task_id)
    if current_task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_task.state == TaskState.done:
        raise HTTPException(status_code=400, detail="Cannot start a completed task")
    if current_task.state == TaskState.in_progress:
        raise HTTPException(status_code=400, detail="Task is already in progress")

    # Update task with new state and timestamp
    task_update = {
        "state": TaskState.in_progress,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    # Update the task
    db_task = update_task(db=db, task_id=task_id, task=task_update)
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return db_task


@router.post("/{task_id}/complete", response_model=Task)
def complete_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    """
    Mark a task as completed and set the completed_at timestamp.
    """
    # Check current task state
    current_task = get_task(db=db, task_id=task_id)
    if current_task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_task.state == TaskState.done:
        raise HTTPException(status_code=400, detail="Task is already completed")

    # Update task with new state and timestamp
    task_update = {
        "state": TaskState.done,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Update the task
    db_task = update_task(db=db, task_id=task_id, task=task_update)
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return db_task


@router.delete("/{task_id}", response_model=Task)
def delete_task_endpoint(task_id: int, db: Session = Depends(get_db)) -> Task:
    """
    Delete a task by ID.
    """
    from app.crud.task import delete_task
    
    db_task = delete_task(db=db, task_id=task_id)
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return db_task


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
            status_code=500, detail=f"Error printing task: {str(e)} {type(e)}"
        )


@router.post("/maintenance", response_model=dict)
async def trigger_maintenance(db: Session = Depends(get_db)):
    """
    Manually trigger the task maintenance job.
    This will process due tasks and clean up old ones.
    """
    from app.jobs.task_maintenance import run_maintenance

    try:
        await run_maintenance()
        return {"status": "success", "message": "Maintenance job completed"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error running maintenance job: {str(e)}"
        )
