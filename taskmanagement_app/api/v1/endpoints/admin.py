import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from taskmanagement_app.core.auth import (
    verify_admin,
    verify_admin_only,
    verify_superadmin,
)
from taskmanagement_app.crud.user import (
    admin_create_user,
    get_user,
    get_user_by_email,
    reset_user_password,
)
from taskmanagement_app.db.base import Base, engine
from taskmanagement_app.db.session import get_db
from taskmanagement_app.schemas.common import (
    DbOperationResponse,
    MigrationResponse,
    PasswordResetResponse,
)
from taskmanagement_app.schemas.user import AdminUserCreate
from taskmanagement_app.schemas.user import User as UserSchema

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


@router.post("/db/init", response_model=DbOperationResponse)
async def init_db(authorized: bool = Depends(verify_superadmin)) -> DbOperationResponse:
    """
    Initialize database by creating all tables.
    Requires superadmin authentication.
    """
    try:
        from taskmanagement_app.db.models import ensure_models_registered

        ensure_models_registered()
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
    """
    try:
        # Get the project root directory
        project_root = Path(__file__).parent.parent.parent.parent.parent

        # Create Alembic config
        alembic_ini_path = project_root / "alembic.ini"
        if not alembic_ini_path.exists():
            raise HTTPException(status_code=500, detail="alembic.ini not found")

        # Run alembic upgrade using subprocess
        # We use subprocess because alembic.config.main() is not thread-safe
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500, detail=f"Migration failed: {result.stderr}"
            )

        return MigrationResponse(
            message="Migrations completed successfully",
            details=result.stdout,
        )
    except HTTPException:
        raise
    except Exception as e:
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
    return UserSchema.model_validate(created)


@router.post("/users/{user_id}/reset-password", response_model=PasswordResetResponse)
def reset_password(
    user_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_only),
) -> PasswordResetResponse:
    if get_user(db, user_id=user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    user, new_password = reset_user_password(db, user_id=user_id)
    if user is None or new_password is None:
        raise HTTPException(status_code=404, detail="User not found")
    return PasswordResetResponse(email=user.email, new_password=new_password)
