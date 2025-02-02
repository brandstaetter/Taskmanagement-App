from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from app.db.base import engine, Base
from app.core.auth import require_admin
import alembic.config
import subprocess
import sys
from pathlib import Path

router = APIRouter()

@router.post("/db/init")
async def init_db(is_admin: bool = Depends(require_admin)):
    """
    Initialize the database by creating all tables.
    This is useful for initial setup or testing.
    Requires admin authentication.
    """
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        return {"message": "Database initialized successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize database: {str(e)}"
        )

@router.post("/db/migrate")
async def run_migrations(is_admin: bool = Depends(require_admin)):
    """
    Run all pending Alembic migrations.
    This should be used when updating the database schema.
    Requires admin authentication.
    """
    try:
        # Get the project root directory
        project_root = Path(__file__).parent.parent.parent.parent.parent
        
        # Create Alembic config
        alembic_ini_path = project_root / "alembic.ini"
        if not alembic_ini_path.exists():
            raise HTTPException(
                status_code=500,
                detail="alembic.ini not found"
            )

        # Run alembic upgrade using subprocess
        # We use subprocess because alembic.config.main() is not thread-safe
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Migration failed: {result.stderr}"
            )

        return {
            "message": "Database migrations completed successfully",
            "details": result.stdout
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run migrations: {str(e)}"
        )
