import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError as SQLAlchemyIntegrityError
from sqlalchemy.orm import Session

from taskmanagement_app.core.auth import (
    verify_admin,
    verify_superadmin,
)
from taskmanagement_app.crud.user import (
    admin_create_user,
    delete_user,
    get_all_users,
    get_user,
    get_user_by_email,
    reset_user_password,
    update_user_role,
)
from taskmanagement_app.db.base import Base, engine
from taskmanagement_app.db.session import get_db
from taskmanagement_app.schemas.common import (
    DbOperationResponse,
    MigrationResponse,
    PasswordResetResponse,
)
from taskmanagement_app.schemas.user import AdminUserCreate, AdminUserRoleUpdate
from taskmanagement_app.schemas.user import User as UserSchema
from taskmanagement_app.utils.gravatar import gravatar_url

logger = logging.getLogger(__name__)


def _get_db_location_for_log() -> str:
    """Return a string describing the database location for logging purposes."""
    try:
        url = engine.url
    except Exception:
        return "unknown"

    try:
        if url.get_backend_name() == "sqlite":
            db_path = url.database
            if db_path is None or db_path == "":
                return url.render_as_string(hide_password=True)
            if db_path == ":memory:":
                return ":memory:"
            return str(Path(db_path).resolve())

        return url.render_as_string(hide_password=True)
    except Exception:
        return str(url)


router = APIRouter()


def _user_response(user: object) -> UserSchema:
    """Build a UserSchema with gravatar_url from a DB user model."""
    data = {
        "id": user.id,  # type: ignore[attr-defined]
        "email": user.email,  # type: ignore[attr-defined]
        "is_active": user.is_active,  # type: ignore[attr-defined]
        "is_admin": user.is_admin,  # type: ignore[attr-defined]
        "is_superadmin": False,
        "display_name": getattr(user, "display_name", None),
        "avatar_url": getattr(user, "avatar_url", None),
        "gravatar_url": gravatar_url(user.email),  # type: ignore[attr-defined]
        "last_login": getattr(user, "last_login", None),
        "created_at": user.created_at,  # type: ignore[attr-defined]
        "updated_at": user.updated_at,  # type: ignore[attr-defined]
    }
    return UserSchema.model_validate(data)


@router.post("/db/init", response_model=DbOperationResponse)
async def init_db(authorized: bool = Depends(verify_superadmin)) -> DbOperationResponse:
    """
    Initialize database by creating all tables.
    Requires superadmin authentication.
    """
    try:
        from taskmanagement_app.db.models import ensure_models_registered

        ensure_models_registered()
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        return DbOperationResponse(message="Database initialized successfully")
    except Exception as e:
        logger.exception(
            "Failed to initialize database (db=%s)",
            _get_db_location_for_log(),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize database: {str(e)}"
        )


@router.post("/db/migrate", response_model=MigrationResponse)
async def run_migrations(authorized: bool = Depends(verify_admin)) -> MigrationResponse:
    """
    Run all pending Alembic migrations.
    Requires admin authentication.

    Uses the Alembic API programmatically so that migrations work regardless
    of where the package is installed (dev checkout vs site-packages wheel).
    """
    try:
        from alembic import command as alembic_command
        from alembic.config import Config as AlembicConfig
        from taskmanagement_app.core.config import get_settings

        settings = get_settings()

        # Locate the migrations directory bundled inside the package
        package_root = Path(__file__).resolve().parent.parent.parent.parent
        migrations_dir = str(package_root / "migrations")

        # Build an Alembic config programmatically — no alembic.ini needed
        alembic_cfg = AlembicConfig()
        alembic_cfg.set_main_option("script_location", migrations_dir)
        alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

        # Detect untracked databases created outside of Alembic (e.g. via
        # create_all).  We must distinguish two cases:
        #   1. Fresh empty DB   → no tables exist → let Alembic run all migrations
        #   2. Pre-existing DB  → tables exist but no alembic_version row → stamp
        #                         at 0996a25c0866 so Alembic skips create-table
        #                         migrations and only runs additive ones.
        inspector = sa_inspect(engine)
        table_names = inspector.get_table_names()
        has_existing_tables = bool(table_names)
        has_alembic_version = "alembic_version" in table_names

        if has_existing_tables and not has_alembic_version:
            alembic_command.stamp(alembic_cfg, "0996a25c0866")

        alembic_command.upgrade(alembic_cfg, "head")

        return MigrationResponse(
            message="Migrations completed successfully",
            details="All migrations applied via Alembic API.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Migration failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to run migrations: {str(e)}"
        )


@router.post("/users", response_model=UserSchema)
def create_new_user(
    user: AdminUserCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin),
) -> UserSchema:
    existing = get_user_by_email(db, email=user.email)
    if existing is not None:
        raise HTTPException(status_code=400, detail="Email already registered")
    created = admin_create_user(db, user=user)
    return _user_response(created)


@router.post("/users/{user_id}/reset-password", response_model=PasswordResetResponse)
def reset_password(
    user_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin),
) -> PasswordResetResponse:
    if get_user(db, user_id=user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    user, new_password = reset_user_password(db, user_id=user_id)
    if user is None or new_password is None:
        raise HTTPException(status_code=404, detail="User not found")
    return PasswordResetResponse(email=user.email, new_password=new_password)


@router.get("/users", response_model=list[UserSchema])
def list_users(
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin),
) -> list[UserSchema]:
    users = get_all_users(db, skip=skip, limit=limit)
    return [_user_response(u) for u in users]


@router.delete("/users/{user_id}", response_model=UserSchema)
def remove_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin),
) -> UserSchema:
    try:
        deleted = delete_user(db, user_id=user_id)
    except SQLAlchemyIntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete user: they have associated tasks or other references",
        )
    if deleted is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_response(deleted)


@router.patch("/users/{user_id}/role", response_model=UserSchema)
def update_role(
    user_id: int,
    role_update: AdminUserRoleUpdate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin),
) -> UserSchema:
    updated = update_user_role(db, user_id=user_id, is_admin=role_update.is_admin)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_response(updated)
