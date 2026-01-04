import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Union

from sqlalchemy.orm import Session

from taskmanagement_app.core.exceptions import TaskNotFoundError, TaskStatusError
from taskmanagement_app.crud.user import get_user
from taskmanagement_app.db.models.task import TaskModel, TaskState
from taskmanagement_app.schemas.task import TaskCreate, TaskUpdate


def validate_user_references(
    db: Session, task_data: Union[TaskCreate, TaskUpdate, Dict[str, Any]]
) -> None:
    """
    Validate that all referenced user IDs exist in the database.

    Args:
        db: Database session
        task_data: Task data containing user references

    Raises:
        ValueError: If any referenced user ID does not exist
    """
    # Convert to dict if needed
    if isinstance(task_data, dict):
        data = task_data
    else:
        data = (
            task_data.model_dump(exclude_unset=True)
            if hasattr(task_data, "model_dump")
            else task_data.dict(exclude_unset=True)
        )

    user_ids_to_check = []

    # Check created_by
    if "created_by" in data and data["created_by"] is not None:
        user_ids_to_check.append(data["created_by"])

    # Check assigned_to
    if "assigned_to" in data and data["assigned_to"] is not None:
        user_ids_to_check.append(data["assigned_to"])

    # Check assigned_user_ids
    if "assigned_user_ids" in data and data["assigned_user_ids"] is not None:
        user_ids_to_check.extend(data["assigned_user_ids"])

    # Validate each user ID exists
    for user_id in user_ids_to_check:
        user = get_user(db, user_id)
        if user is None:
            raise ValueError(f"User with ID {user_id} does not exist")


def get_tasks(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    include_archived: bool = False,
    state: Optional[str] = None,
    user_id: Optional[int] = None,
    include_created: bool = True,
) -> Sequence[TaskModel]:
    """Get a list of tasks.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        include_archived: Whether to include archived tasks in the result
        state: Optional state to filter by
        user_id: Optional user ID to filter tasks by visibility/assignment
        include_created: Whether to include tasks created by the user

    Returns:
        List of tasks
    """
    from taskmanagement_app.db.models.task import AssignmentType

    query = db.query(TaskModel)

    # Apply user visibility filter if user_id is provided
    if user_id is not None:
        from sqlalchemy import or_

        # Use explicit join with association table instead of .any()
        # to avoid N+1 queries
        from taskmanagement_app.db.models.task import task_assigned_users

        # Join with the association table to check user assignment efficiently
        user_assigned_filter = TaskModel.id.in_(
            db.query(task_assigned_users.c.task_id)
            .filter(task_assigned_users.c.user_id == user_id)
            .subquery()
            .select()
        )

        visibility_filter = or_(
            TaskModel.assignment_type == AssignmentType.any,
            TaskModel.assigned_to == user_id,
            TaskModel.created_by == user_id,
            user_assigned_filter,
        )

        if include_created:
            # Include tasks created by user
            query = query.filter(visibility_filter)
        else:
            # Exclude tasks created by user, only show assigned tasks
            visibility_filter = or_(
                TaskModel.assignment_type == AssignmentType.any,
                TaskModel.assigned_to == user_id,
                user_assigned_filter,
            )
            query = query.filter(visibility_filter)

    # Apply state filter if provided
    if state:
        query = query.filter(TaskModel.state == state)
    # Otherwise apply archived filter
    elif not include_archived:
        query = query.filter(TaskModel.state != TaskState.archived)

    return (
        query.order_by(TaskModel.due_date.asc().nulls_last())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_task(db: Session, task: TaskCreate) -> TaskModel:
    from taskmanagement_app.db.models.task import AssignmentType

    # Validate user references before creating task
    validate_user_references(db, task)

    db_task = TaskModel(
        title=task.title,
        description=task.description,
        state=task.state,
        due_date=task.due_date,
        reward=task.reward,
        created_by=task.created_by,
        assignment_type=task.assignment_type,
        assigned_to=task.assigned_to,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    # Handle assigned_users for "some" assignment type
    if task.assignment_type == AssignmentType.some and task.assigned_user_ids:
        from taskmanagement_app.db.models.user import User

        users = db.query(User).filter(User.id.in_(task.assigned_user_ids)).all()
        db_task.assigned_users = users
        db.commit()
        db.refresh(db_task)

    return db_task


def get_due_tasks(db: Session) -> Sequence[TaskModel]:
    """Get all tasks that are due within the next 24 hours."""
    now = datetime.now(timezone.utc)
    tomorrow = now + timedelta(days=1)

    logger = logging.getLogger(__name__)

    candidates = db.query(TaskModel).filter(TaskModel.due_date.isnot(None)).all()

    invalid_tasks: List[TaskModel] = []
    due_tasks: List[tuple[datetime, TaskModel]] = []

    for task in candidates:
        if not task.due_date:
            continue
        try:
            due_date = datetime.fromisoformat(task.due_date.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            logger.warning(
                f"Task {task.id} has invalid due_date format: {task.due_date}. "
                "Setting to None."
            )
            task.due_date = None
            invalid_tasks.append(task)
            continue

        if (
            task.state not in (TaskState.done, TaskState.archived)
            and now <= due_date <= tomorrow
        ):
            due_tasks.append((due_date, task))

    if invalid_tasks:
        for task in invalid_tasks:
            db.add(task)
        db.commit()

    due_tasks.sort(key=lambda x: x[0])
    return [task for _, task in due_tasks]


def weighted_random_choice(tasks: Sequence[TaskModel]) -> Optional[TaskModel]:
    """
    Select a random task with higher probability for tasks due sooner.
    Tasks without due dates are treated as lowest priority.
    """
    if not tasks:
        return None

    now = datetime.now(timezone.utc)
    weights: List[float] = []

    for task in tasks:
        weight: float = 1.0  # Default weight
        if task.due_date:
            try:
                due_date = datetime.fromisoformat(task.due_date)
                time_diff = due_date - now

                # Convert time difference to hours
                hours_remaining = time_diff.total_seconds() / 3600

                if hours_remaining <= 0:
                    # Overdue tasks get highest weight
                    weight = 1000.0
                elif hours_remaining <= 24:
                    # Due within 24 hours: weight from 100 to 1000
                    weight = 1000.0 - (hours_remaining / 24.0 * 900.0)
                elif hours_remaining <= 168:  # 7 days
                    # Due within a week: weight from 10 to 100
                    weight = 100.0 - ((hours_remaining - 24.0) / 144.0 * 90.0)
                else:
                    # Due later: weight from 1 to 10
                    weight = 10.0 - min(
                        9.0, hours_remaining / 336.0
                    )  # 336 = 14 days in hours
            except ValueError:
                # Invalid date format, treat as no due date
                weight = 1.0
        else:
            # No due date, lowest priority
            weight = 1.0

        weights.append(max(1.0, weight))  # Ensure minimum weight of 1

    # Use random.choices which allows weights
    return random.choices(tasks, weights=weights, k=1)[0]


def get_random_task(db: Session) -> Optional[TaskModel]:
    """
    Get a random task, prioritizing tasks that are due sooner.
    Only considers non-completed tasks.
    """
    tasks = (
        db.query(TaskModel)
        .filter(TaskModel.state.notin_([TaskState.done, TaskState.archived]))
        .all()
    )
    if not tasks:
        return None

    return weighted_random_choice(tasks)


def get_task(db: Session, task_id: int) -> Optional[TaskModel]:
    """
    Get a task by its ID.
    """
    return db.query(TaskModel).filter(TaskModel.id == task_id).first()


def update_task(
    db: Session, task_id: int, task: Union[TaskUpdate, Dict[str, Any]]
) -> Optional[TaskModel]:
    """
    Update a task with new values.

    Args:
        db: Database session
        task_id: ID of task to update
        task: TaskUpdate model or dictionary with new values

    Returns:
        Updated task or None if task not found
    """
    db_task = get_task(db, task_id)
    if db_task is None:
        return None

    # Convert TaskUpdate to dict if needed
    update_data = (
        task if isinstance(task, dict) else task.model_dump(exclude_unset=True)
    )

    # Validate user references before updating task
    if update_data:
        validate_user_references(db, update_data)

    # Update task attributes
    for key, value in update_data.items():
        setattr(db_task, key, value)

    db.commit()
    db.refresh(db_task)
    return db_task


def complete_task(db: Session, task: TaskModel) -> TaskModel:
    """
    Mark a task as completed and set the completion timestamp.
    """
    if task.state != TaskState.in_progress:
        raise TaskStatusError("Task must be in_progress to be set to done")
    task.state = TaskState.done
    task.completed_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    return task


def start_task(db: Session, task: TaskModel) -> TaskModel:
    """
    Mark a task as in progress and set the start timestamp.
    """
    task.state = TaskState.in_progress
    task.started_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    return task


def archive_task(db: Session, task_id: int) -> Optional[TaskModel]:
    """
    Archive a task by ID.

    Args:
        db: Database session
        task_id: ID of task to archive

    Returns:
        Archived task or None if task not found

    Raises:
        TaskStatusError: If task is not in a state that can be archived
    """
    task = get_task(db, task_id)
    if task:
        if task.state == TaskState.archived:
            raise TaskStatusError("Task is already archived")
        elif task.state not in [TaskState.done, TaskState.todo]:
            raise TaskStatusError(
                f"Cannot archive task in state {task.state}. "
                "Task must be in 'done' or 'todo' state to be archived."
            )
        task.state = TaskState.archived
        db.commit()
    return task


def read_random_task(db: Session) -> Optional[TaskModel]:
    """
    Get a random task, prioritizing tasks that are:
    1. Not completed
    2. Due sooner
    3. Not yet started

    Uses weighted random selection where tasks due sooner have higher weights.
    """
    tasks = (
        db.query(TaskModel)
        .filter(
            TaskModel.state != TaskState.done,
            TaskModel.state != TaskState.archived,
        )
        .all()
    )

    if not tasks:
        return None

    now = datetime.now(timezone.utc)
    weights = []

    for task in tasks:
        if task.due_date:
            try:
                due_date = datetime.fromisoformat(task.due_date)
                time_diff = due_date - now

                # Convert time difference to hours
                hours_remaining = time_diff.total_seconds() / 3600

                if hours_remaining <= 0:
                    # Overdue tasks get highest weight
                    weight = 1000.0
                elif hours_remaining <= 24:
                    # Due within 24 hours: weight from 100 to 1000
                    weight = 1000.0 - (hours_remaining / 24.0 * 900.0)
                elif hours_remaining <= 168:  # 7 days
                    # Due within a week: weight from 10 to 100
                    weight = 100.0 - ((hours_remaining - 24.0) / 144.0 * 90.0)
                else:
                    # Due later: weight from 1 to 10
                    weight = 10 - min(
                        9, hours_remaining / 336
                    )  # 336 = 14 days in hours
            except ValueError:
                # Invalid date format, treat as no due date
                weight = 1
        else:
            # No due date, lowest priority
            weight = 1

        weights.append(max(1, weight))  # Ensure minimum weight of 1

    # Use random.choices which allows weights
    return random.choices(tasks, weights=weights, k=1)[0]


def reset_task_to_todo(db: Session, task_id: int) -> TaskModel:
    """Reset a task to todo state and clear its progress timestamps.

    Args:
        db: Database session
        task_id: ID of the task to reset

    Returns:
        Updated task

    Raises:
        TaskNotFoundError: If task doesn't exist
    """
    task = get_task(db, task_id)
    if not task:
        raise TaskNotFoundError(task_id)

    task.state = TaskState.todo
    task.started_at = None
    task.completed_at = None

    db.commit()
    db.refresh(task)
    return task
