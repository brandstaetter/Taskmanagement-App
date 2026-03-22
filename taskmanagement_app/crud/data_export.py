import logging
from typing import Any

from sqlalchemy.orm import Session

from taskmanagement_app.crud.user import get_user, get_user_by_email
from taskmanagement_app.db.models.task import TaskModel, TaskState
from taskmanagement_app.db.models.user import User
from taskmanagement_app.schemas.data_export import (
    DataExport,
    ExportedTask,
    ExportedUser,
    ImportResult,
    ImportSkippedItem,
)

logger = logging.getLogger(__name__)


def export_data(db: Session) -> DataExport:
    """Export all users and tasks as a DataExport object."""
    users = db.query(User).all()
    tasks = db.query(TaskModel).all()

    exported_users = [
        ExportedUser(
            id=u.id,
            email=u.email,
            is_active=u.is_active,
            is_admin=u.is_admin,
            display_name=u.display_name,
            avatar_url=u.avatar_url,
        )
        for u in users
    ]

    exported_tasks = []
    for t in tasks:
        assigned_ids = [u.id for u in t.assigned_users] if t.assigned_users else []
        exported_tasks.append(
            ExportedTask(
                id=t.id,
                title=t.title,
                description=t.description,
                state=t.state.value if isinstance(t.state, TaskState) else t.state,
                due_date=t.due_date,
                reward=t.reward,
                created_at=t.created_at,
                started_at=t.started_at,
                completed_at=t.completed_at,
                created_by=t.created_by,
                started_by=t.started_by,
                assigned_user_ids=assigned_ids,
            )
        )

    return DataExport(version=1, users=exported_users, tasks=exported_tasks)


def _import_users(
    db: Session,
    users_data: list[dict[str, Any]],
    result: ImportResult,
    id_map: dict[int, int],
) -> None:
    """Import users, populating id_map for old→new ID translation."""
    for user_data in users_data:
        email = user_data.get("email", "")
        existing = get_user_by_email(db, email=email)
        if existing is not None:
            old_id = user_data.get("id")
            if old_id is not None:
                id_map[old_id] = existing.id
            result.users_skipped += 1
            result.skipped_items.append(
                ImportSkippedItem(
                    type="user",
                    identifier=email,
                    reason="User with this email already exists",
                )
            )
            continue

        try:
            new_user = User(
                email=email,
                hashed_password="!imported",  # unusable hash, requires reset
                is_active=user_data.get("is_active", True),
                is_admin=user_data.get("is_admin", False),
                display_name=user_data.get("display_name"),
                avatar_url=user_data.get("avatar_url"),
            )
            db.add(new_user)
            db.flush()
            old_id = user_data.get("id")
            if old_id is not None:
                id_map[old_id] = new_user.id
            result.users_imported += 1
        except Exception as e:
            logger.warning("Failed to import user %s: %s", email, e)
            result.users_skipped += 1
            result.skipped_items.append(
                ImportSkippedItem(type="user", identifier=email, reason=str(e))
            )


def _resolve_user_id(
    db: Session, raw_id: int | None, id_map: dict[int, int]
) -> int | None:
    """Map an old user ID to its new ID, returning None if the user is missing."""
    if raw_id is None:
        return None
    mapped = id_map.get(raw_id, raw_id)
    return mapped if get_user(db, mapped) is not None else None


def _import_tasks(
    db: Session,
    tasks_data: list[dict[str, Any]],
    result: ImportResult,
    id_map: dict[int, int],
) -> None:
    """Import tasks, resolving user references via id_map."""
    for task_data in tasks_data:
        title = task_data.get("title", "")
        created_by = _resolve_user_id(db, task_data.get("created_by"), id_map)
        started_by = _resolve_user_id(db, task_data.get("started_by"), id_map)

        assigned_users = []
        for uid in task_data.get("assigned_user_ids", []):
            user = get_user(db, id_map.get(uid, uid))
            if user is not None:
                assigned_users.append(user)

        state_str = task_data.get("state", "todo")
        try:
            state = TaskState(state_str)
        except ValueError:
            result.tasks_skipped += 1
            result.skipped_items.append(
                ImportSkippedItem(
                    type="task",
                    identifier=title,
                    reason=f"Invalid state: {state_str}",
                )
            )
            continue

        try:
            new_task = TaskModel(
                title=title,
                description=task_data.get("description", ""),
                state=state,
                due_date=task_data.get("due_date"),
                reward=task_data.get("reward"),
                created_at=task_data.get("created_at"),
                started_at=task_data.get("started_at"),
                completed_at=task_data.get("completed_at"),
                created_by=created_by,
                started_by=started_by,
            )
            new_task.assigned_users = assigned_users
            db.add(new_task)
            db.flush()
            result.tasks_imported += 1
        except Exception as e:
            db.rollback()
            logger.warning("Failed to import task '%s': %s", title, e)
            result.tasks_skipped += 1
            result.skipped_items.append(
                ImportSkippedItem(type="task", identifier=title, reason=str(e))
            )


def _import_v1(db: Session, data: dict[str, Any]) -> ImportResult:
    """Import data in version 1 format."""
    result = ImportResult()
    id_map: dict[int, int] = {}
    _import_users(db, data.get("users", []), result, id_map)
    _import_tasks(db, data.get("tasks", []), result, id_map)
    db.commit()
    return result


def import_data(db: Session, data: dict[str, Any]) -> ImportResult:
    """Import data from a JSON export, merging with existing data.

    Supports version-based dispatch for backwards compatibility.
    """
    version = data.get("version", 1)
    if version == 1:
        return _import_v1(db, data)
    raise ValueError(f"Unsupported export version: {version}")
