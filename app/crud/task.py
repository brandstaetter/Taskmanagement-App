from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import random
from app.db.models.task import Task
from app.schemas.task import TaskCreate

def get_tasks(db: Session, skip: int = 0, limit: int = 100) -> List[Task]:
    return db.query(Task).offset(skip).limit(limit).all()

def create_task(db: Session, task: TaskCreate) -> Task:
    db_task = Task(
        title=task.title,
        description=task.description,
        state=task.state,
        due_date=task.due_date,
        reward=task.reward
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def get_due_tasks(db: Session) -> List[Task]:
    """Get all tasks that are due within the next 24 hours."""
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    
    return db.query(Task).filter(
        Task.due_date.isnot(None),  # Filter out tasks with no due date
        Task.due_date <= tomorrow.strftime("%Y-%m-%d %H:%M:%S"),  # Due before tomorrow
        Task.due_date >= now.strftime("%Y-%m-%d %H:%M:%S"),  # Due after now
        Task.state != "done"  # Not already completed
    ).all()

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
                    weight = 10 - min(9, hours_remaining / 336)  # 336 = 14 days in hours
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
