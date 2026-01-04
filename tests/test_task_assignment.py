import pytest
from sqlalchemy.orm import Session

from taskmanagement_app.crud.task import create_task, get_tasks, update_task
from taskmanagement_app.db.models.task import AssignmentType
from taskmanagement_app.db.models.user import User
from taskmanagement_app.schemas.task import TaskCreate, TaskUpdate


def test_create_task_with_assignment(db_session: Session, test_user: dict) -> None:
    """Test creating a task with assignment information."""
    # Create a user in the database with unique email
    user = User(
        email=f"user0_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    task_data = TaskCreate(
        title="Test Task",
        description="Test Description",
        created_by=user.id,
        assignment_type="one",
        assigned_to=user.id,
    )

    task = create_task(db_session, task_data)

    assert task.title == "Test Task"
    assert task.created_by == user.id
    assert task.assignment_type == AssignmentType.one
    assert task.assigned_to == user.id


def test_get_tasks_user_visibility_filtering(
    db_session: Session, test_user: dict
) -> None:
    """Test that users only see tasks they're assigned to or created."""
    # Create users in the database with unique emails
    user = User(
        email=f"user_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add(user)
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(admin_user)

    # Create task assigned to test_user
    task_assigned = TaskCreate(
        title="Assigned Task",
        description="For test user",
        created_by=admin_user.id,
        assignment_type="one",
        assigned_to=user.id,
    )
    created_task_assigned = create_task(db_session, task_assigned)

    # Create task created by test_user (but not assigned to them)
    task_created = TaskCreate(
        title="Created Task",
        description="By test user",
        created_by=user.id,
        assignment_type="one",
        assigned_to=admin_user.id,  # Assigned to admin, not to user
    )
    created_task_created = create_task(db_session, task_created)

    # Create task for different user (should not be visible)
    other_user = User(email="other@example.com", hashed_password="hash")
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    task_other = TaskCreate(
        title="Other Task",
        description="For other user",
        created_by=admin_user.id,
        assignment_type="one",
        assigned_to=other_user.id,
    )
    created_task_other = create_task(db_session, task_other)

    # Test visibility filtering
    visible_tasks = get_tasks(db_session, user_id=user.id, include_created=True)
    visible_task_ids = {task.id for task in visible_tasks}

    # Should see assigned and created tasks
    assert created_task_assigned.id in visible_task_ids
    assert created_task_created.id in visible_task_ids
    # Should not see other user's task
    assert created_task_other.id not in visible_task_ids

    # Test filtering out created tasks
    assigned_only = get_tasks(db_session, user_id=user.id, include_created=False)
    assigned_task_ids = {task.id for task in assigned_only}

    assert created_task_assigned.id in assigned_task_ids
    assert created_task_created.id not in assigned_task_ids


def test_create_task_with_any_assignment_type_null_fields(
    db_session: Session, test_user: dict
) -> None:
    """Test creating a task with 'any' assignment type and null assignment fields."""
    # Create a user in the database with unique email
    user = User(
        email=f"user_any_null_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    task_data = TaskCreate(
        title="Any Assignment Task",
        description="Task with no specific assignment",
        created_by=user.id,
        assignment_type="any",
        # Explicitly not setting assigned_to or assigned_user_ids
    )

    task = create_task(db_session, task_data)

    # Verify task properties
    assert task.title == "Any Assignment Task"
    assert task.created_by == user.id
    assert task.assignment_type == AssignmentType.any
    assert (
        task.assigned_to is None
    ), "assigned_to should be None for 'any' assignment type"
    assert (
        task.assigned_user is None
    ), "assigned_user relationship should be None for 'any' assignment type"
    assert (
        task.assigned_users == []
    ), "assigned_users should be empty list for 'any' assignment type"


def test_get_tasks_any_assignment_type(db_session: Session, test_user: dict) -> None:
    """Test that 'any' assignment type tasks are visible to all users."""
    # Create users in the database with unique emails
    user = User(
        email=f"user2_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin2@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add(user)
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(admin_user)

    task_any = TaskCreate(
        title="Any Assignment Task",
        description="Visible to all",
        created_by=admin_user.id,
        assignment_type="any",
    )
    created_task = create_task(db_session, task_any)

    # Should be visible to any user
    tasks = get_tasks(db_session, user_id=user.id, include_created=False)
    task_ids = {task.id for task in tasks}

    assert created_task.id in task_ids


def test_create_task_with_some_assignment_type(
    db_session: Session, test_user: dict
) -> None:
    """Test creating a task assigned to multiple users."""
    # Create users in the database with unique emails
    user = User(
        email=f"user3_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin3@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add(user)
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(admin_user)

    task_data = TaskCreate(
        title="Multi-user Task",
        description="For multiple users",
        created_by=admin_user.id,
        assignment_type="some",
        assigned_user_ids=[user.id, admin_user.id],
    )

    task = create_task(db_session, task_data)

    assert task.assignment_type == AssignmentType.some
    assert len(task.assigned_users) == 2
    assigned_user_ids = {user.id for user in task.assigned_users}
    assert user.id in assigned_user_ids
    assert admin_user.id in assigned_user_ids


def test_get_tasks_multi_user_assignment_visibility(
    db_session: Session, test_user: dict
) -> None:
    """Test that multi-user assigned tasks are visible to all assigned users."""
    # Create users in the database with unique emails
    user1 = User(
        email=f"user_multi1_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    user2 = User(
        email=f"user_multi2_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    user3 = User(
        email=f"user_multi3_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin_multi@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add_all([user1, user2, user3, admin_user])
    db_session.commit()
    for user in [user1, user2, user3, admin_user]:
        db_session.refresh(user)

    # Create task assigned to user1 and user2 (but not user3)
    task_multi = TaskCreate(
        title="Multi-user Assignment Task",
        description="Assigned to user1 and user2",
        created_by=admin_user.id,
        assignment_type="some",
        assigned_user_ids=[user1.id, user2.id],
    )
    created_task = create_task(db_session, task_multi)

    # Test that user1 can see the task
    user1_tasks = get_tasks(db_session, user_id=user1.id, include_created=False)
    user1_task_ids = {task.id for task in user1_tasks}
    assert created_task.id in user1_task_ids

    # Test that user2 can see the task
    user2_tasks = get_tasks(db_session, user_id=user2.id, include_created=False)
    user2_task_ids = {task.id for task in user2_tasks}
    assert created_task.id in user2_task_ids

    # Test that user3 CANNOT see the task (not assigned)
    user3_tasks = get_tasks(db_session, user_id=user3.id, include_created=False)
    user3_task_ids = {task.id for task in user3_tasks}
    assert created_task.id not in user3_task_ids

    # Test that admin can see the task (created by them)
    admin_tasks = get_tasks(db_session, user_id=admin_user.id, include_created=True)
    admin_task_ids = {task.id for task in admin_tasks}
    assert created_task.id in admin_task_ids

    # Test that admin cannot see the task when include_created=False
    admin_assigned_only = get_tasks(
        db_session, user_id=admin_user.id, include_created=False
    )
    admin_assigned_ids = {task.id for task in admin_assigned_only}
    assert created_task.id not in admin_assigned_ids


def test_update_task_assignment_to_any(db_session: Session, test_user: dict) -> None:
    """Test updating a task to 'any' assignment type clears assignment fields."""
    # Create users
    user = User(
        email=f"user_update_any_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin_update_any@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add(user)
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(admin_user)

    # Create task initially assigned to one user
    task_data = TaskCreate(
        title="Task to Update",
        description="Initial assignment",
        created_by=admin_user.id,
        assignment_type="one",
        assigned_to=user.id,
    )
    task = create_task(db_session, task_data)
    assert task.assignment_type == AssignmentType.one
    assert task.assigned_to == user.id

    # Update to 'any' assignment type
    task_update = TaskUpdate(
        assignment_type="any",
        assigned_to=None,  # Should be cleared
        assigned_user_ids=None,  # Should be cleared
    )

    updated_task = update_task(db_session, task.id, task_update)

    assert updated_task is not None
    assert updated_task.assignment_type == AssignmentType.any
    assert updated_task.assigned_to is None
    assert updated_task.assigned_user is None


def test_update_task_assignment_to_one(db_session: Session, test_user: dict) -> None:
    """Test updating a task to 'one' assignment type with assigned_to field."""
    # Create users
    user1 = User(
        email=f"user_update_one1_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    user2 = User(
        email=f"user_update_one2_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin_update_one@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add_all([user1, user2, admin_user])
    db_session.commit()
    for u in [user1, user2, admin_user]:
        db_session.refresh(u)

    # Create task initially with 'any' assignment
    task_data = TaskCreate(
        title="Task to Update to One",
        description="Initial any assignment",
        created_by=admin_user.id,
        assignment_type="any",
    )
    task = create_task(db_session, task_data)
    assert task.assignment_type == AssignmentType.any
    assert task.assigned_to is None

    # Update to 'one' assignment type
    task_update = TaskUpdate(
        assignment_type="one",
        assigned_to=user1.id,
    )

    updated_task = update_task(db_session, task.id, task_update)

    assert updated_task is not None
    assert updated_task.assignment_type == AssignmentType.one
    assert updated_task.assigned_to == user1.id
    assert updated_task.assigned_user is not None
    assert updated_task.assigned_user.id == user1.id


def test_update_task_assignment_to_some(db_session: Session, test_user: dict) -> None:
    """Test updating a task to 'some' assignment type with assigned_user_ids field."""
    # Create users
    user1 = User(
        email=f"user_update_some1_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    user2 = User(
        email=f"user_update_some2_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    user3 = User(
        email=f"user_update_some3_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin_update_some@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add_all([user1, user2, user3, admin_user])
    db_session.commit()
    for u in [user1, user2, user3, admin_user]:
        db_session.refresh(u)

    # Create task initially assigned to one user
    task_data = TaskCreate(
        title="Task to Update to Some",
        description="Initial one assignment",
        created_by=admin_user.id,
        assignment_type="one",
        assigned_to=user1.id,
    )
    task = create_task(db_session, task_data)
    assert task.assignment_type == AssignmentType.one
    assert task.assigned_to == user1.id

    # Update to 'some' assignment type
    task_update = TaskUpdate(
        assignment_type="some",
        assigned_to=None,  # Should be cleared
        assigned_user_ids=[user2.id, user3.id],
    )

    updated_task = update_task(db_session, task.id, task_update)

    assert updated_task is not None
    assert updated_task.assignment_type == AssignmentType.some
    assert updated_task.assigned_to is None
    # Verify assigned_users relationship is properly updated
    assert len(updated_task.assigned_users) == 2
    assigned_user_ids = {user.id for user in updated_task.assigned_users}
    assert user2.id in assigned_user_ids
    assert user3.id in assigned_user_ids
    assert user1.id not in assigned_user_ids


def test_update_task_assignment_validation_errors(
    db_session: Session, test_user: dict
) -> None:
    """Test that assignment field validation works correctly during updates."""
    # Create users
    user1 = User(
        email=f"user_update_val1_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    user2 = User(
        email=f"user_update_val2_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin_update_val@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add_all([user1, user2, admin_user])
    db_session.commit()
    for u in [user1, user2, admin_user]:
        db_session.refresh(u)

    # Create task with 'any' assignment
    task_data = TaskCreate(
        title="Task for Validation Tests",
        description="Testing validation",
        created_by=admin_user.id,
        assignment_type="any",
    )
    task = create_task(db_session, task_data)

    # Test 1: 'one' assignment type without assigned_to should fail
    with pytest.raises(
        ValueError, match="assigned_to must be specified when assignment_type is 'one'"
    ):
        task_update = TaskUpdate(
            assignment_type="one",
            assigned_to=None,
        )
        update_task(db_session, task.id, task_update)

    # Test 2: 'one' assignment type with assigned_user_ids should fail
    with pytest.raises(
        ValueError,
        match="assigned_user_ids must be None or empty when assignment_type is 'one'",
    ):
        task_update = TaskUpdate(
            assignment_type="one",
            assigned_to=user1.id,
            assigned_user_ids=[user1.id, user2.id],
        )
        update_task(db_session, task.id, task_update)

    # Test 3: 'some' assignment type without assigned_user_ids should fail
    with pytest.raises(
        ValueError,
        match="assigned_user_ids must be specified when assignment_type is 'some'",
    ):
        task_update = TaskUpdate(
            assignment_type="some",
            assigned_user_ids=None,
        )
        update_task(db_session, task.id, task_update)

    # Test 4: 'some' assignment type with assigned_to should fail
    with pytest.raises(
        ValueError, match="assigned_to must be None when assignment_type is 'some'"
    ):
        task_update = TaskUpdate(
            assignment_type="some",
            assigned_to=user1.id,
            assigned_user_ids=[user1.id, user2.id],
        )
        update_task(db_session, task.id, task_update)

    # Test 5: 'any' assignment type with assigned_to should fail
    with pytest.raises(
        ValueError, match="assigned_to must be None when assignment_type is 'any'"
    ):
        task_update = TaskUpdate(
            assignment_type="any",
            assigned_to=user1.id,
        )
        update_task(db_session, task.id, task_update)

    # Test 6: 'any' assignment type with assigned_user_ids should fail
    with pytest.raises(
        ValueError,
        match="assigned_user_ids must be None or empty when assignment_type is 'any'",
    ):
        task_update = TaskUpdate(
            assignment_type="any",
            assigned_user_ids=[user1.id, user2.id],
        )
        update_task(db_session, task.id, task_update)


def test_update_task_assignment_partial_updates(
    db_session: Session, test_user: dict
) -> None:
    """Test updating only assignment fields without changing assignment_type."""
    # Create users
    user1 = User(
        email=f"user_update_partial1_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    user2 = User(
        email=f"user_update_partial2_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin_update_partial@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add_all([user1, user2, admin_user])
    db_session.commit()
    for u in [user1, user2, admin_user]:
        db_session.refresh(u)

    # Create task with 'one' assignment
    task_data = TaskCreate(
        title="Task for Partial Updates",
        description="Testing partial updates",
        created_by=admin_user.id,
        assignment_type="one",
        assigned_to=user1.id,
    )
    task = create_task(db_session, task_data)
    assert task.assigned_to == user1.id

    # Update only the assigned_to field (keep same assignment_type)
    task_update = TaskUpdate(
        assigned_to=user2.id,
    )

    updated_task = update_task(db_session, task.id, task_update)

    assert updated_task is not None
    assert updated_task.assignment_type == AssignmentType.one  # Should remain unchanged
    assert updated_task.assigned_to == user2.id  # Should be updated
    assert updated_task.assigned_user is not None
    assert updated_task.assigned_user.id == user2.id


def test_update_task_assignment_with_invalid_user_ids(
    db_session: Session, test_user: dict
) -> None:
    """Test that updating assignment fields with invalid user IDs fails properly."""
    # Create user
    user = User(
        email=f"user_update_invalid_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin_update_invalid@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add_all([user, admin_user])
    db_session.commit()
    for u in [user, admin_user]:
        db_session.refresh(u)

    # Create task with 'any' assignment
    task_data = TaskCreate(
        title="Task for Invalid User Tests",
        description="Testing invalid user references",
        created_by=admin_user.id,
        assignment_type="any",
    )
    task = create_task(db_session, task_data)

    # Test updating with invalid assigned_to
    with pytest.raises(ValueError, match="User with ID 99999 does not exist"):
        task_update = TaskUpdate(
            assignment_type="one",
            assigned_to=99999,  # Non-existent user ID
        )
        update_task(db_session, task.id, task_update)

    # Test updating with invalid assigned_user_ids
    with pytest.raises(ValueError, match="User with ID 88888 does not exist"):
        task_update = TaskUpdate(
            assignment_type="some",
            assigned_user_ids=[user.id, 88888],  # One valid, one invalid
        )
        update_task(db_session, task.id, task_update)
