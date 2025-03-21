from typing import Generator

from sqlalchemy.orm import Session

from taskmanagement_app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Get a database session.

    Yields:
        Database session that will be automatically closed after use
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
