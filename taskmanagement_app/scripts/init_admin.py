"""Initialize admin user from environment variables."""

from sqlalchemy.orm import Session

from taskmanagement_app.auth.utils import get_password_hash
from taskmanagement_app.core.config import get_settings
from taskmanagement_app.db.base import get_db
from taskmanagement_app.db.models.user import User


def init_admin(db: Session) -> None:
    """Initialize admin user if it doesn't exist."""
    settings = get_settings()

    # Check if admin exists
    admin = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
    if admin:
        return

    # Create admin user
    admin = User(
        email=settings.ADMIN_EMAIL,
        hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
        is_admin=True,
    )
    db.add(admin)
    db.commit()


if __name__ == "__main__":
    # Create a new session
    session = next(get_db())
    try:
        init_admin(session)
        print("Admin user initialized successfully")
    except Exception as e:
        print(f"Error initializing admin user: {e}")
    finally:
        session.close()
