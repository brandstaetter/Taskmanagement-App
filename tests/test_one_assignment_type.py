from sqlalchemy.orm import Session

from taskmanagement_app.crud.task import create_task, get_task
from taskmanagement_app.db.models.task import AssignmentType
from taskmanagement_app.db.models.user import User
from taskmanagement_app.schemas.task import TaskCreate


def test_create_task_with_one_assignment_type(db_session: Session) -> None:
    """Test creating a task assigned to exactly one user."""
    # Create users in the database with unique emails
    creator = User(
        email="creator_one@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    assigned_user = User(
        email="assigned_one@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    other_user = User(
        email="other_one@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    db_session.add(creator)
    db_session.add(assigned_user)
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(creator)
    db_session.refresh(assigned_user)
    db_session.refresh(other_user)

    # Create task with "one" assignment type
    task_data = TaskCreate(
        title="Single User Task",
        description="Assigned to exactly one user",
        created_by=creator.id,
        assignment_type="one",
        assigned_to=assigned_user.id,
    )

    created_task = create_task(db_session, task_data)

    # Verify the task was created correctly
    assert created_task.title == "Single User Task"
    assert created_task.created_by == creator.id
    assert created_task.assignment_type == AssignmentType.one
    assert created_task.assigned_to == assigned_user.id

    # Verify the assigned user relationship works
    assert created_task.assigned_user is not None
    assert created_task.assigned_user.id == assigned_user.id
    assert created_task.assigned_user.email == "assigned_one@example.com"

    # Verify no users are in the assigned_users list (that's for "some" type)
    assert len(created_task.assigned_users) == 0

    # Verify we can retrieve the task and it has the same assignment
    retrieved_task = get_task(db_session, created_task.id)
    assert retrieved_task is not None
    assert retrieved_task.assignment_type == AssignmentType.one
    assert retrieved_task.assigned_to == assigned_user.id
    assert retrieved_task.assigned_user is not None
    assert retrieved_task.assigned_user.id == assigned_user.id


def test_create_task_with_one_assignment_type_no_assigned_user(
    db_session: Session,
) -> None:
    """Test creating a task with 'one' assignment type but no assigned user."""
    # Create a user with unique email
    creator = User(
        email="creator_no_assign@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    db_session.add(creator)
    db_session.commit()
    db_session.refresh(creator)

    # Create task with "one" assignment type but no assigned_to
    task_data = TaskCreate(
        title="Unassigned Single Task",
        description="One assignment type but no assigned user",
        created_by=creator.id,
        assignment_type="one",
        assigned_to=None,  # This should be allowed
    )

    created_task = create_task(db_session, task_data)

    # Verify the task was created
    assert created_task.title == "Unassigned Single Task"
    assert created_task.assignment_type == AssignmentType.one
    assert created_task.assigned_to is None
    assert created_task.assigned_user is None


def test_create_task_with_one_assignment_type_invalid_user(db_session: Session) -> None:
    """Test creating a task with 'one' assignment type assigned to non-existent user."""
    # Create a user with unique email
    creator = User(
        email="creator_invalid@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    db_session.add(creator)
    db_session.commit()
    db_session.refresh(creator)

    # Try to create task with non-existent assigned user
    task_data = TaskCreate(
        title="Invalid Assignment Task",
        description="Assigned to non-existent user",
        created_by=creator.id,
        assignment_type="one",
        assigned_to=99999,  # Non-existent user ID
    )

    # This should not raise an error during creation (foreign key constraint
    # might be enforced at database level, but SQLAlchemy allows it)
    created_task = create_task(db_session, task_data)

    # Verify the task was created but assigned_to points to invalid user
    assert created_task.title == "Invalid Assignment Task"
    assert created_task.assignment_type == AssignmentType.one
    assert created_task.assigned_to == 99999
    assert created_task.assigned_user is None  # Should be None since user doesn't exist
