import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from app.db.models.task import Task, TaskState
from app.schemas.task import TaskCreate, TaskUpdate


def get_tasks(db: Session, skip: int = 0, limit: int = 100) -> List[Task]:
    return (
        db.query(Task)
        .order_by(Task.due_date.asc().nulls_last())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_task(db: Session, task: TaskCreate) -> Task:
    db_task = Task(
        title=task.title,
        description=task.description,
        state=task.state,
        due_date=task.due_date,
        reward=task.reward,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def get_due_tasks(db: Session) -> List[Task]:
    """Get all tasks that are due within the next 24 hours."""
    now = datetime.now()
    tomorrow = now + timedelta(days=1)

    return (
        db.query(Task)
        .filter(
            Task.due_date.isnot(None),  # Filter out tasks with no due date
            Task.due_date
            <= tomorrow.strftime("%Y-%m-%d %H:%M:%S"),  # Due before tomorrow
            Task.due_date >= now.strftime("%Y-%m-%d %H:%M:%S"),  # Due after now
            Task.state != "done",  # Not already completed
        )
        .all()
    )


def weighted_random_choice(tasks: List[Task]) -> Optional[Task]:
    """
    Select a random task with higher probability for tasks due sooner.
    Tasks without due dates are treated as lowest priority.
    """
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
                    weight = 1000
                elif hours_remaining <= 24:
                    # Due within 24 hours: weight from 100 to 1000
                    weight = 1000 - (hours_remaining / 24 * 900)
                elif hours_remaining <= 168:  # 7 days
                    # Due within a week: weight from 10 to 100
                    weight = 100 - ((hours_remaining - 24) / 144 * 90)
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


def get_random_task(db: Session) -> Optional[Task]:
    """
    Get a random task, prioritizing tasks that are due sooner.
    Only considers non-completed tasks.
    """
    # Get all non-completed tasks
    tasks = db.query(Task).filter(Task.state != "done").all()

    return weighted_random_choice(tasks)


def get_task(db: Session, task_id: int) -> Optional[Task]:
    """
    Get a task by its ID.
    """
    return db.query(Task).filter(Task.id == task_id).first()


def update_task(
    db: Session, task_id: int, task: Union[TaskUpdate, Dict[str, Any]]
) -> Optional[Task]:
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
    if db_task:
        # Handle both Pydantic models and dictionaries
        update_data = (
            task.model_dump(exclude_unset=True) if hasattr(task, "model_dump") else task
        )

        for field, value in update_data.items():
            setattr(db_task, field, value)
        db.commit()
        db.refresh(db_task)
    return db_task


def complete_task(db: Session, task: Task) -> Task:
    """
    Mark a task as completed and set the completion timestamp.
    """
    task.state = "done"
    task.completed_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(task)
    return task


def start_task(db: Session, task: Task) -> Task:
    """
    Mark a task as in progress and set the start timestamp.
    """
    task.state = "in_progress"
    task.started_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: int) -> Optional[Task]:
    """
    Delete a task by ID.

    Args:
        db: Database session
        task_id: ID of task to delete

    Returns:
        Deleted task or None if task not found
    """
    db_task = get_task(db, task_id)
    if db_task:
        db.delete(db_task)
        db.commit()
    return db_task


def read_random_task(db: Session) -> Optional[Task]:
    """
    Get a random task, prioritizing tasks that are:
    1. Not completed
    2. Due sooner
    3. Not yet started

    Uses weighted random selection where tasks due sooner have higher weights.
    """
    # Get all non-completed tasks, ordered by due date
    tasks = (
        db.query(Task)
        .filter(Task.state != TaskState.done.value)
        .order_by(Task.due_date.asc().nulls_last())
        .all()
    )

    if not tasks:
        return None

    # Calculate weights based on position in the sorted list
    # Earlier tasks (due sooner) get higher weights
    now = datetime.now(timezone.utc)
    weights = []

    for task in tasks:
        weight = 1.0  # Base weight

        # Increase weight for tasks that are due soon or overdue
        if task.due_date:
            due_date = datetime.fromisoformat(task.due_date.replace("Z", "+00:00"))
            time_until_due = due_date - now
            days_until_due = time_until_due.total_seconds() / (24 * 3600)

            if days_until_due <= 0:  # Overdue tasks
                weight *= 3.0
            elif days_until_due <= 1:  # Due within 24 hours
                weight *= 2.5
            elif days_until_due <= 7:  # Due within a week
                weight *= 2.0

        # Increase weight for tasks that haven't been started
        if task.state == TaskState.todo:
            weight *= 1.5

        weights.append(weight)

    # Normalize weights
    total_weight = sum(weights)
    if total_weight > 0:
        weights = [w / total_weight for w in weights]

    # Select random task using weights
    return random.choices(tasks, weights=weights, k=1)[0]
