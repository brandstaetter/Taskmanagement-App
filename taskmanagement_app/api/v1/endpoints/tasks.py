import logging
from datetime import datetime, timezone
from typing import List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from taskmanagement_app.core.exceptions import TaskStatusError
from taskmanagement_app.core.printing.printer_factory import PrinterFactory
from taskmanagement_app.crud.task import archive_task
from taskmanagement_app.crud.task import complete_task as complete_task_crud
from taskmanagement_app.crud.task import (
    create_task,
    get_task,
    get_tasks,
    read_random_task,
    reset_task_to_todo,
)
from taskmanagement_app.crud.task import start_task as start_task_crud
from taskmanagement_app.db.models.task import TaskModel, TaskState
from taskmanagement_app.db.session import get_db
from taskmanagement_app.schemas.task import Task, TaskCreate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[Task])
def read_tasks(
    skip: int = 0,
    limit: int = 100,
    include_archived: bool = False,
    state: Optional[str] = Query(None, description="Filter tasks by state"),
    db: Session = Depends(get_db),
) -> List[Task]:
    """
    Retrieve tasks.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        include_archived: Whether to include archived tasks in the result
        state: Optional state to filter tasks by (todo, in_progress, done, archived)
        db: Database session
    """
    db_tasks = get_tasks(
        db,
        skip=skip,
        limit=limit,
        include_archived=include_archived,
        state=state,
    )
    return [Task.model_validate(task) for task in db_tasks]


@router.post("", response_model=Task)
def create_new_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
) -> Task:
    """
    Create new task.
    """
    db_task = create_task(db=db, task=task)
    return Task.model_validate(db_task)


@router.get("/due/", response_model=List[Task])
def read_due_tasks(db: Session = Depends(get_db)) -> List[Task]:
    """
    Retrieve all tasks that are due within the next 24 hours.
    """
    now = datetime.now(timezone.utc)
    db_tasks = get_tasks(db, include_archived=False)  # Exclude archived tasks
    due_tasks = []
    for task in db_tasks:
        if task.due_date:
            due_date = datetime.fromisoformat(task.due_date.replace("Z", "+00:00"))
            if (due_date - now).total_seconds() <= 24 * 3600:  # 24 hours in seconds
                due_tasks.append(Task.model_validate(task))
    return due_tasks


@router.get("/random/", response_model=Task)
def get_random_task(
    db: Session = Depends(get_db),
) -> Task:
    """
    Get a random task, prioritizing tasks that are:
    1. Not completed
    2. Due sooner
    3. Not yet started

    Note: Archived tasks are excluded.
    """
    db_task = read_random_task(db)  # read_random_task already excludes archived tasks
    if not db_task:
        raise HTTPException(status_code=404, detail="No tasks found")
    return Task.model_validate(db_task)


@router.get("/search/", response_model=List[Task])
def search_tasks(
    q: str = Query(..., description="Search query"),
    include_archived: bool = False,
    db: Session = Depends(get_db),
) -> List[Task]:
    """
    Search tasks by title or description.

    Args:
        q: Search query
        include_archived: Whether to include archived tasks in the result
        db: Database session
    """
    # Create base query
    query = db.query(TaskModel)

    # Apply archived filter if needed
    if not include_archived:
        query = query.filter(TaskModel.state != TaskState.archived)

    # Apply search filter using SQLite's LIKE operator (case-insensitive by default)
    search_pattern = f"%{q}%"
    query = query.filter(
        TaskModel.title.like(search_pattern)
        | TaskModel.description.like(search_pattern)
    )

    # Execute query and log results
    tasks = query.all()
    logger.debug("Found %d tasks matching query '%s'", len(tasks), q)

    # Convert to response models
    return [Task.model_validate(task) for task in tasks]


@router.get("/{task_id}", response_model=Task)
def read_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> Task:
    """
    Get task by ID.
    """
    db_task = get_task(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    return Task.model_validate(db_task)


@router.post("/{task_id}/start", response_model=Task)
def start_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    """
    Mark a task as in progress and set the started_at timestamp.
    """
    db_task = get_task(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    if db_task.state != TaskState.todo:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start task in state {db_task.state}. "
            "Task must be in 'todo' state.",
        )

    updated_db_task = start_task_crud(db, db_task)
    return Task.model_validate(updated_db_task)


@router.post("/{task_id}/complete", response_model=Task)
def complete_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    """
    Mark a task as completed and set the completed_at timestamp.
    """
    db_task = get_task(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    if db_task.state != TaskState.in_progress:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot complete task in state {db_task.state}. "
            "Task must be in 'in_progress' state.",
        )

    try:
        updated_db_task = complete_task_crud(db, db_task)
        return Task.model_validate(updated_db_task)
    except TaskStatusError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{task_id}", response_model=Task)
def delete_task_endpoint(task_id: int, db: Session = Depends(get_db)) -> Task:
    """
    Archive a task by ID.

    Args:
        task_id: ID of task to archive
        db: Database session
    """
    try:
        task = archive_task(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return Task.model_validate(task)
    except TaskStatusError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{task_id}/print")
async def print_task(
    task_id: int,
    printer_type: Optional[str] = Query(None, description="Type of printer to use"),
    db: Session = Depends(get_db),
) -> Response:
    """
    Print a task using the specified printer (defaults to PDF).
    """
    task = get_task(db, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        printer = PrinterFactory.create_printer(printer_type)
        response = printer.print(task)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error printing task: {str(e)}",
        )


@router.post("/maintenance")
async def trigger_maintenance(db: Session = Depends(get_db)) -> dict:
    """
    Manually trigger the task maintenance job.
    This will process due tasks and clean up old ones.
    """
    from taskmanagement_app.jobs.task_maintenance import run_maintenance

    try:
        run_maintenance()
        return {"message": "Maintenance job completed successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error running maintenance job: {str(e)}",
        )


@router.patch("/{task_id}/reset-to-todo", response_model=Task)
def reset_task_to_todo_endpoint(task_id: int, db: Session = Depends(get_db)) -> Any:
    """Reset a task to todo state and clear its progress timestamps."""
    return reset_task_to_todo(db=db, task_id=task_id)
