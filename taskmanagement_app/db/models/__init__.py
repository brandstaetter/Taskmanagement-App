from .task import AssignmentType, TaskModel, TaskState
from .user import User

__all__ = [
    "AssignmentType",
    "TaskModel",
    "TaskState",
    "User",
    "ensure_models_registered",
]


def ensure_models_registered() -> None:
    """
    Ensure all models are imported and registered with SQLAlchemy Base.

    This function should be called before creating database tables or running
    migrations to ensure all models are available in Base.metadata.
    """
    # Import all models to register them with SQLAlchemy Base
    _ = (TaskModel, User)  # noqa: F841
