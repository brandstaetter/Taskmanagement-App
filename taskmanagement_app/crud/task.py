import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Sequence, Union

from sqlalchemy.orm import Session

from taskmanagement_app.core.exceptions import TaskNotFoundError, TaskStatusError
from taskmanagement_app.crud.user import get_user
from taskmanagement_app.db.models.task import TaskModel, TaskState
from taskmanagement_app.schemas.task import TaskCreate, TaskUpdate


def validate_user_references(
    db: Session, task_data: Union[TaskCreate, TaskUpdate, dict[str, Any]]
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
    include_private: bool = False,
    search: Optional[str] = None,
    show_all: bool = False,
) -> Sequence[TaskModel]:
    """Get a list of tasks.

    Visibility rules:
    - user_id is None (admin): see all tasks
    - show_all=True: bypass assignment filter but still enforce private visibility
    - assigned_users is empty: visible to everyone
    - assigned_users is non-empty: visible to assigned users + task creator
    - private tasks: only visible to creator/assignee when include_private=True
    """
    query = db.query(TaskModel)

    # Apply user visibility filter if user_id is provided
    if user_id is not None:
        from sqlalchemy import and_, or_

        from taskmanagement_app.db.models.task import task_assigned_users

        # Subquery: tasks where this user is in assigned_users
        user_assigned_filter = TaskModel.id.in_(
            db.query(task_assigned_users.c.task_id)
            .filter(task_assigned_users.c.user_id == user_id)
            .subquery()
            .select()
        )

        if not show_all:
            # Subquery: tasks with no assigned users (open to all)
            no_assigned_users_filter = ~TaskModel.id.in_(
                db.query(task_assigned_users.c.task_id).subquery().select()
            )

            # Base visibility: open tasks OR tasks assigned to this user
            base_visibility_filter = or_(
                no_assigned_users_filter,
                user_assigned_filter,
            )

            if include_created:
                visibility_filter = or_(
                    base_visibility_filter, TaskModel.created_by == user_id
                )
            else:
                visibility_filter = base_visibility_filter

            # Private task filtering
            if include_private:
                # Show private tasks only if user is creator or assignee
                private_visible = and_(
                    TaskModel.is_private.is_(True),
                    or_(
                        TaskModel.created_by == user_id,
                        user_assigned_filter,
                    ),
                )
                query = query.filter(
                    or_(
                        and_(visibility_filter, TaskModel.is_private.is_(False)),
                        private_visible,
                    )
                )
            else:
                # Exclude all private tasks
                query = query.filter(visibility_filter)
                query = query.filter(TaskModel.is_private.is_(False))
        else:
            # show_all: skip assignment filter but still enforce privacy
            if include_private:
                # Show private tasks only if user is creator or assignee
                private_visible = and_(
                    TaskModel.is_private.is_(True),
                    or_(
                        TaskModel.created_by == user_id,
                        user_assigned_filter,
                    ),
                )
                query = query.filter(
                    or_(
                        TaskModel.is_private.is_(False),
                        private_visible,
                    )
                )
            else:
                query = query.filter(TaskModel.is_private.is_(False))
    else:
        # Admin: if not including private, filter them out
        if not include_private:
            query = query.filter(TaskModel.is_private.is_(False))

    # Apply state filter if provided
    if state:
        query = query.filter(TaskModel.state == state)
    # Otherwise apply archived filter
    elif not include_archived:
        query = query.filter(TaskModel.state != TaskState.archived)

    # Apply search filter if provided
    if search:
        from sqlalchemy import or_

        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                TaskModel.title.ilike(search_pattern),
                TaskModel.description.ilike(search_pattern),
            )
        )

    return (
        query.order_by(TaskModel.due_date.asc().nulls_last())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_task(db: Session, task: TaskCreate) -> TaskModel:
    # Validate user references before creating task
    validate_user_references(db, task)

    db_task = TaskModel(
        title=task.title,
        description=task.description,
        state=task.state,
        due_date=task.due_date,
        reward=task.reward,
        is_private=task.is_private,
        created_by=task.created_by,
    )
    db.add(db_task)

    # Handle assigned users
    if task.assigned_user_ids:
        from taskmanagement_app.db.models.user import User

        users = db.query(User).filter(User.id.in_(task.assigned_user_ids)).all()
        db_task.assigned_users = users

    # Single commit for both task creation and user assignment
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
    db: Session, task_id: int, task: Union[TaskUpdate, dict[str, Any]]
) -> Optional[TaskModel]:
    """
    Update a task with new values.
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

    # Handle assigned_user_ids update
    if "assigned_user_ids" in update_data:
        assigned_user_ids = update_data.get("assigned_user_ids")
        db_task.assigned_users.clear()
        if assigned_user_ids:
            from taskmanagement_app.db.models.user import User

            users = db.query(User).filter(User.id.in_(assigned_user_ids)).all()
            db_task.assigned_users = users

    # Remove assigned_user_ids from update_data since it's handled above
    update_data_for_attrs = {
        k: v for k, v in update_data.items() if k != "assigned_user_ids"
    }

    # Update task attributes
    for key, value in update_data_for_attrs.items():
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


def start_task(
    db: Session, task: TaskModel, started_by_user_id: Optional[int] = None
) -> TaskModel:
    """
    Mark a task as in progress and set the start timestamp.
    Auto-assigns the user if they are not already in assigned_users.
    """
    task.state = TaskState.in_progress
    task.started_at = datetime.now(timezone.utc).isoformat()
    task.started_by = started_by_user_id

    # Auto-assign the user who starts the task
    if started_by_user_id is not None:
        assigned_user_ids = {u.id for u in task.assigned_users}
        if started_by_user_id not in assigned_user_ids:
            from taskmanagement_app.db.models.user import User

            user = db.query(User).filter(User.id == started_by_user_id).first()
            if user:
                task.assigned_users.append(user)

    db.commit()
    return task


def archive_task(db: Session, task_id: int) -> Optional[TaskModel]:
    """
    Archive a task by ID.
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
    """Reset a task to todo state and clear its progress timestamps."""
    task = get_task(db, task_id)
    if not task:
        raise TaskNotFoundError(task_id)

    task.state = TaskState.todo
    task.started_at = None
    task.completed_at = None
    task.started_by = None

    db.commit()
    db.refresh(task)
    return task
