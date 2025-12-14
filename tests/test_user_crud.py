from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from taskmanagement_app.crud import user as user_crud
from taskmanagement_app.schemas.user import (
    AdminUserCreate,
    UserCreate,
    UserPasswordReset,
    UserUpdate,
)


def test_create_user(db_session: Session) -> None:
    data = UserCreate(email=f"u1_{uuid4()}@example.com", password="StrongPass1!")
    created = user_crud.create_user(db_session, data)
    assert created.email == data.email
    assert created.id is not None
    assert created.hashed_password != data.password
    assert created.is_active is True
    assert created.is_admin is False
    assert created.avatar_url is None


def test_admin_create_user(db_session: Session) -> None:
    data = AdminUserCreate(
        email=f"admin2_{uuid4()}@example.com",
        password="AdminPass2@",
        is_admin=True,
    )
    created = user_crud.admin_create_user(db_session, data)
    assert created.is_admin is True


def test_get_user_by_email(db_session: Session) -> None:
    email = f"u2_{uuid4()}@example.com"
    data = UserCreate(email=email, password="StrongPass2!")
    created = user_crud.create_user(db_session, data)

    found = user_crud.get_user_by_email(db_session, email)
    assert found is not None
    assert found.id == created.id


def test_update_user(db_session: Session) -> None:
    data = UserCreate(email=f"u3_{uuid4()}@example.com", password="StrongPass3!")
    created = user_crud.create_user(db_session, data)

    update = UserUpdate(
        email=f"u3b_{uuid4()}@example.com",
        is_active=False,
        avatar_url="/avatar.png",
    )
    updated = user_crud.update_user(db_session, created.id, update)
    assert updated is not None
    assert updated.email == update.email
    assert updated.is_active is False
    assert updated.avatar_url == "/avatar.png"


def test_change_user_password(db_session: Session) -> None:
    data = UserCreate(email=f"u4_{uuid4()}@example.com", password="StrongPass4!")
    created = user_crud.create_user(db_session, data)

    old_hashed_password = created.hashed_password
    reset = UserPasswordReset(new_password="NewPass4!")

    changed = user_crud.change_user_password(db_session, created.id, reset)
    assert changed is not None
    assert changed.hashed_password != old_hashed_password


def test_reset_user_password(db_session: Session) -> None:
    data = UserCreate(email=f"u5_{uuid4()}@example.com", password="StrongPass5!")
    created = user_crud.create_user(db_session, data)

    user, new_pw = user_crud.reset_user_password(db_session, created.id)
    assert user is not None
    assert new_pw is not None
    assert isinstance(new_pw, str)


def test_update_last_login(db_session: Session) -> None:
    data = UserCreate(email=f"u6_{uuid4()}@example.com", password="StrongPass6!")
    created = user_crud.create_user(db_session, data)

    user = user_crud.update_last_login(db_session, created.id)
    assert user is not None
    assert user.last_login is not None


def test_get_all_users(db_session: Session) -> None:
    created_ids: list[int] = []
    for i in range(3):
        data = UserCreate(
            email=f"bulkuser{i}_{uuid4()}@example.com", password="BulkPass1!"
        )
        created = user_crud.create_user(db_session, data)
        created_ids.append(created.id)

    all_users = user_crud.get_all_users(db_session)
    ids = {u.id for u in all_users}
    for user_id in created_ids:
        assert user_id in ids


def test_unique_email_constraint(db_session: Session) -> None:
    unique_email = f"unique_{uuid4()}@example.com"
    data = UserCreate(email=unique_email, password="UniquePass1!")

    user_crud.create_user(db_session, data)
    with pytest.raises(IntegrityError):
        user_crud.create_user(db_session, data)

    db_session.rollback()
