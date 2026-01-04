"""
Centralized test utilities for user creation and management.
Ensures unique email addresses across all tests to avoid constraint violations.
"""

import time
from typing import Any, Dict

from sqlalchemy.orm import Session

from taskmanagement_app.crud.user import create_user
from taskmanagement_app.schemas.user import UserCreate


class TestUserFactory:
    """Factory for creating test users with unique email addresses."""

    _counter = 0

    @classmethod
    def create_test_user(
        cls, db_session: Session, email_prefix: str = "test_user"
    ) -> Dict[str, Any]:
        """
        Create a test user and return their details as a dict.

        Args:
            db_session: Database session
            email_prefix: Prefix for the email address

        Returns:
            Dict containing user details with keys:
            - id: The user's ID (int)
            - email: The user's unique email address (str)
        """
        cls._counter += 1
        timestamp = int(time.time() * 1000000)  # Microsecond precision
        unique_email = f"{email_prefix}_{timestamp}_{cls._counter}@example.com"

        user_in = UserCreate(
            email=unique_email,
            password="TestPassword123!",
        )
        user = create_user(db=db_session, user=user_in)
        return {
            "id": user.id,
            "email": user.email,
        }

    @classmethod
    def create_multiple_users(
        cls, db_session: Session, count: int, email_prefix: str = "test_user"
    ) -> list[Dict[str, Any]]:
        """
        Create multiple test users with unique email addresses.

        Args:
            db_session: Database session
            count: Number of users to create
            email_prefix: Prefix for the email addresses

        Returns:
            List of dicts containing user id and email
        """
        users = []
        for i in range(count):
            user = cls.create_test_user(db_session, f"{email_prefix}_{i}")
            users.append(user)
        return users

    @classmethod
    def reset_counter(cls) -> None:
        """Reset the internal counter. Useful for test isolation."""
        cls._counter = 0


# Global instance for backward compatibility
def create_test_user(
    db_session: Session, email_prefix: str = "test_user"
) -> Dict[str, Any]:
    """
    Create a test user with a unique email address.

    This is a convenience function that uses TestUserFactory.

    Args:
        db_session: Database session
        email_prefix: Prefix for the email address

    Returns:
        Dict containing user id and email
    """
    return TestUserFactory.create_test_user(db_session, email_prefix)
