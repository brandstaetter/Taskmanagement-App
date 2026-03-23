import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from taskmanagement_app.core.auth import get_current_user, verify_not_superadmin
from taskmanagement_app.core.config import get_settings
from taskmanagement_app.core.exceptions import TaskNotFoundError, TaskStatusError
from taskmanagement_app.core.printing.printer_factory import PrinterFactory
from taskmanagement_app.crud.task import (
    archive_task,
)
from taskmanagement_app.crud.task import complete_task as complete_task_crud
from taskmanagement_app.crud.task import (
    create_task,
    get_task,
    get_tasks,
    reset_task_to_todo,
)
from taskmanagement_app.crud.task import start_task as start_task_crud
from taskmanagement_app.crud.task import (
    update_task,
    weighted_random_choice,
)
from taskmanagement_app.db.models.task import TaskModel, TaskState
from taskmanagement_app.db.models.user import User
from taskmanagement_app.db.session import get_db
from taskmanagement_app.schemas.common import MaintenanceResponse
from taskmanagement_app.schemas.task import (
    AssignedUserDisplay,
    Task,
    TaskCreate,
    TaskUpdate,
)
from taskmanagement_app.utils.gravatar import gravatar_url

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_not_superadmin)])


def _check_private_task_access(task: TaskModel, current_user: Optional[User]) -> None:
    """Raise 404 if the task is private and the user is not the creator or assignee.

    Admins (current_user is None) bypass this check.
    """
    if not task.is_private:
        return
    # Admins can see everything
    if current_user is None:
        return
    user_id = current_user.id
    if user_id == task.created_by:
        return
    assigned_ids = {u.id for u in task.assigned_users}
    if user_id in assigned_ids:
        return
    # Return 404 instead of 403 to avoid leaking that the task exists
    raise HTTPException(status_code=404, detail="Task not found")


def _task_response(db_task: TaskModel) -> Task:
    """Build a Task response including resolved display names."""

    assigned_user_ids = (
        [u.id for u in db_task.assigned_users] if db_task.assigned_users else None
    )
    assigned_users_display = None
    if db_task.assigned_users:
        assigned_users_display = [
            AssignedUserDisplay(
                id=u.id,
                display_name=u.display_name or u.email,
                avatar_url=u.avatar_url or gravatar_url(u.email),
            )
            for u in db_task.assigned_users
        ]

    creator_display = None
    creator_avatar = None
    if db_task.creator:
        creator_display = db_task.creator.display_name or db_task.creator.email
        creator_avatar = db_task.creator.avatar_url or gravatar_url(
            db_task.creator.email
        )
    worker_display = None
    worker_avatar = None
    if db_task.worker:
        worker_display = db_task.worker.display_name or db_task.worker.email
        worker_avatar = db_task.worker.avatar_url or gravatar_url(db_task.worker.email)
    return Task.model_validate(
        {
            "id": db_task.id,
            "title": db_task.title,
            "description": db_task.description,
            "state": db_task.state,
            "due_date": db_task.due_date,
            "reward": db_task.reward,
            "created_at": db_task.created_at,
            "started_at": db_task.started_at,
            "completed_at": db_task.completed_at,
            "created_by": db_task.created_by,
            "is_private": db_task.is_private,
            "assigned_user_ids": assigned_user_ids,
            "started_by": db_task.started_by,
            "creator_display_name": creator_display,
            "worker_display_name": worker_display,
            "creator_avatar_url": creator_avatar,
            "worker_avatar_url": worker_avatar,
            "assigned_users_display": assigned_users_display,
        }
    )


@router.get("", response_model=List[Task])
def read_tasks(
    skip: int = 0,
    limit: int = 100,
    include_archived: bool = False,
    state: Optional[str] = Query(None, description="Filter tasks by state"),
    include_created: bool = Query(
        True, description="Include tasks created by the user"
    ),
    show_all: bool = Query(
        False,
        description="Show all tasks regardless of assignment (bypasses user filtering)",
    ),
    include_private: bool = Query(
        False, description="Include private tasks (only visible to creator/assignee)"
    ),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> List[Task]:
    """
    Retrieve tasks.
    """
    user_id = current_user.id if current_user else None
    db_tasks = get_tasks(
        db,
        skip=skip,
        limit=limit,
        include_archived=include_archived,
        state=state,
        user_id=user_id,
        include_created=include_created,
        include_private=include_private,
        show_all=show_all,
    )
    return [_task_response(task) for task in db_tasks]


@router.post("", response_model=Task)
def create_new_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
) -> Task:
    """
    Create new task.
    """
    try:
        db_task = create_task(db=db, task=task)
        return _task_response(db_task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/due/", response_model=List[Task])
def read_due_tasks(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> List[Task]:
    """
    Retrieve all tasks that are due within the next 24 hours.
    """
    now = datetime.now(timezone.utc)
    user_id = current_user.id if current_user else None
    # For admin users (current_user is None), show all tasks
    # For regular users, show only their assigned/created tasks
    db_tasks = get_tasks(
        db, include_archived=False, user_id=user_id
    )  # Exclude archived tasks and apply visibility filtering
    due_tasks = []
    for task in db_tasks:
        if task.due_date:
            due_date = datetime.fromisoformat(task.due_date.replace("Z", "+00:00"))
            if (due_date - now).total_seconds() <= 24 * 3600:  # 24 hours in seconds
                due_tasks.append(_task_response(task))
    return due_tasks


@router.get("/random/", response_model=Task)
def get_random_task(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> Task:
    """
    Get a random task, prioritizing tasks that are:
    1. Not completed
    2. Due sooner
    3. Not yet started

    Note: Archived tasks are excluded.
    """
    user_id = current_user.id if current_user else None
    # For admin users (current_user is None), show all tasks
    # For regular users, show only their assigned/created tasks
    db_tasks = get_tasks(
        db, include_archived=False, user_id=user_id
    )  # Exclude archived tasks and apply visibility filtering

    if not db_tasks:
        raise HTTPException(status_code=404, detail="No tasks found")

    # Use weighted random selection from the filtered tasks
    selected_task = weighted_random_choice(db_tasks)
    if not selected_task:
        raise HTTPException(status_code=404, detail="No tasks found")

    return _task_response(selected_task)


@router.get("/search/", response_model=List[Task])
def search_tasks(
    q: str = Query(..., description="Search query"),
    include_archived: bool = False,
    include_private: bool = Query(
        False, description="Include private tasks in search results"
    ),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> List[Task]:
    """
    Search tasks by title or description.
    """
    user_id = current_user.id if current_user else None
    db_tasks = get_tasks(
        db,
        include_archived=include_archived,
        user_id=user_id,
        include_private=include_private,
        search=q,
    )

    # Log results and convert to response models
    logger.debug("Found %d tasks matching query '%s'", len(db_tasks), q)
    return [_task_response(task) for task in db_tasks]


@router.get("/{task_id}", response_model=Task)
def read_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> Task:
    """
    Get task by ID.
    """
    db_task = get_task(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    _check_private_task_access(db_task, current_user)
    return _task_response(db_task)


@router.post("/{task_id}/start", response_model=Task)
def start_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> Task:
    """
    Mark a task as in progress and set the started_at timestamp.
    """
    db_task = get_task(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    _check_private_task_access(db_task, current_user)

    if db_task.state != TaskState.todo:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start task in state {db_task.state}. "
            "Task must be in 'todo' state.",
        )

    user_id = current_user.id if current_user else None
    updated_db_task = start_task_crud(db, db_task, started_by_user_id=user_id)
    return _task_response(updated_db_task)


@router.post("/{task_id}/complete", response_model=Task)
def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> Task:
    """
    Mark a task as completed and set the completed_at timestamp.
    """
    db_task = get_task(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    _check_private_task_access(db_task, current_user)

    if db_task.state != TaskState.in_progress:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot complete task in state {db_task.state}. "
            "Task must be in 'in_progress' state.",
        )

    try:
        updated_db_task = complete_task_crud(db, db_task)
        return _task_response(updated_db_task)
    except TaskStatusError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{task_id}", response_model=Task)
def delete_task_endpoint(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> Task:
    """
    Archive a task by ID.

    Args:
        task_id: ID of task to archive
        db: Database session
    """
    # Check privacy before archiving
    db_task = get_task(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    _check_private_task_access(db_task, current_user)

    try:
        task = archive_task(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return _task_response(task)
    except TaskStatusError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{task_id}/print", response_model=None)
async def print_task(
    task_id: int,
    printer_type: Optional[str] = Query(None, description="Type of printer to use"),
    timezone: Optional[str] = Query(
        None,
        description="IANA timezone name (e.g. 'Europe/Vienna') for timestamps",
    ),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> Response:
    """
    Print a task using the specified printer (defaults to PDF).
    Private tasks cannot be printed.
    """
    task = get_task(db, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.is_private:
        raise HTTPException(
            status_code=403,
            detail="Private tasks cannot be printed.",
        )

    try:
        printer = PrinterFactory.create_printer(printer_type)
        tz = timezone or get_settings().DEFAULT_TIMEZONE
        response = printer.print(task, tz_name=tz)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error printing task: {str(e)}",
        )


@router.post("/maintenance", response_model=MaintenanceResponse)
async def trigger_maintenance(db: Session = Depends(get_db)) -> MaintenanceResponse:
    """
    Manually trigger the task maintenance job.
    This will process due tasks and clean up old ones.
    """
    from taskmanagement_app.jobs.task_maintenance import run_maintenance

    try:
        run_maintenance()
        return MaintenanceResponse(message="Maintenance job completed successfully")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error running maintenance job: {str(e)}",
        )


@router.patch("/{task_id}/reset-to-todo", response_model=Task)
def reset_task_to_todo_endpoint(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> Task:
    """Reset a task to todo state and clear its progress timestamps."""
    # Check privacy before resetting
    existing_task = get_task(db, task_id=task_id)
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")
    _check_private_task_access(existing_task, current_user)

    try:
        db_task = reset_task_to_todo(db=db, task_id=task_id)
        return _task_response(db_task)
    except TaskNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Task with id {task_id} not found",
        )
    except TaskStatusError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.patch("/{task_id}", response_model=Task)
def update_task_endpoint(
    task_id: int,
    task: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> Task:
    """
    Update an existing task.
    Private tasks can only be reassigned by their creator or current assignee.
    """
    db_task = get_task(db, task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    _check_private_task_access(db_task, current_user)

    try:
        updated_task = update_task(db, task_id, task)
        if not updated_task:
            raise HTTPException(status_code=404, detail="Task not found")
        return _task_response(updated_task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
