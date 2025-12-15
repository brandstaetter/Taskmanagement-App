import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from taskmanagement_app.core.auth import verify_admin
from taskmanagement_app.crud.user import (
    admin_create_user,
    get_user,
    get_user_by_email,
    reset_user_password,
)
from taskmanagement_app.db.base import Base, engine
from taskmanagement_app.db.session import get_db
from taskmanagement_app.schemas.user import AdminUserCreate
from taskmanagement_app.schemas.user import User as UserSchema

router = APIRouter()


@router.post("/db/init")
async def init_db(authorized: bool = Depends(verify_admin)) -> dict:
    """
    Initialize database by creating all tables.
    Requires admin authentication.
    """
    try:
        from taskmanagement_app.db.models import ensure_models_registered

        ensure_models_registered()
        Base.metadata.create_all(bind=engine)
        return {"message": "Database initialized successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize database: {str(e)}"
        )


@router.post("/db/migrate")
async def run_migrations(authorized: bool = Depends(verify_admin)) -> dict:
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

        return {
            "message": "Migrations completed successfully",
            "details": result.stdout,
        }
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


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin),
) -> dict:
    if get_user(db, user_id=user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    user, new_password = reset_user_password(db, user_id=user_id)
    if user is None or new_password is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"email": user.email, "new_password": new_password}
