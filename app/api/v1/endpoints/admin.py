import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import verify_admin
from app.db.base import Base, engine

router = APIRouter()


@router.post("/db/init")
async def init_db(authorized: bool = Depends(verify_admin)):
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
async def run_migrations(authorized: bool = Depends(verify_admin)):
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
