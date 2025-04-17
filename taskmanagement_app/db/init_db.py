"""Initialize database with tables and default admin user."""

import logging

from sqlalchemy import inspect

from taskmanagement_app.core.config import get_settings
from taskmanagement_app.core.security import get_password_hash
from taskmanagement_app.db.base import Base
from taskmanagement_app.db.models.user import User
from taskmanagement_app.db.session import SessionLocal, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db() -> None:
    """Initialize database with tables and default admin user."""
    settings = get_settings()

    # Create tables
    tables_before = set(inspect(engine).get_table_names())
    Base.metadata.create_all(bind=engine)
    tables_after = set(inspect(engine).get_table_names())

    created_tables = tables_after - tables_before
    if created_tables:
        logger.info(f"Created tables: {', '.join(created_tables)}")
    else:
        logger.info("No tables created, they already exist")

    # Create admin user if it doesn't exist
    db = SessionLocal()
    try:
        admin_email = settings.ADMIN_EMAIL
        admin_password = settings.ADMIN_PASSWORD

        admin_exists = db.query(User).filter(User.email == admin_email).first()
        if not admin_exists:
            admin_user = User(
                email=admin_email,
                hashed_password=get_password_hash(admin_password),
                is_admin=True,
            )
            db.add(admin_user)
            db.commit()
            logger.info(f"Created admin user with email: {admin_email}")
        else:
            logger.info(f"Admin user with email {admin_email} already exists")

    except Exception as e:
        logger.error(f"Error creating admin user: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Creating database tables and admin user...")
    init_db()
    logger.info("Database initialization completed.")
