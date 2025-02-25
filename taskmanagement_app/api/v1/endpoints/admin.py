import subprocess
import sys
from pathlib import Path
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from taskmanagement_app.core.auth import verify_admin, require_admin
from taskmanagement_app.db.base import Base, engine
from taskmanagement_app.api.deps import get_db
from taskmanagement_app.crud.user import (
    create_user,
    get_user,
    get_user_by_email,
    reset_user_password,
)
from taskmanagement_app.schemas.user import User, UserCreate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/db/init")
async def init_db(authorized: bool = Depends(verify_admin)) -> dict:
    """
    Initialize database by creating all tables.
    Requires admin authentication.
    """
    try:
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


@router.post("/users", response_model=User)
def create_new_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
) -> User:
    """
    Create a new user.
    Only accessible by admin users.
    """
    # Check if user with this email already exists
    db_user = get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )

    try:
        user = create_user(db=db, user=user)
        logger.info("Created new user with email: %s", user.email)
        return user
    except Exception as e:
        logger.error("Error creating user: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Error creating user",
        )


@router.post("/users/{user_id}/reset-password", response_model=dict)
def reset_password(
    user_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
) -> dict:
    """
    Reset a user's password to a random string.
    Only accessible by admin users.
    Returns the new password.
    """
    # Check if user exists
    if not get_user(db, user_id=user_id):
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    try:
        user, new_password = reset_user_password(db=db, user_id=user_id)
        if not user or not new_password:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )
        logger.info("Reset password for user: %s", user.email)
        return {"email": user.email, "new_password": new_password}
    except Exception as e:
        logger.error("Error resetting password: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Error resetting password",
        )
