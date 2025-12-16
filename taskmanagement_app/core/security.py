import bcrypt

# Define password requirements
PASSWORD_SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:'\",.<>/?"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.
    
    Args:
        plain_password: The plain text password to verify
        hashed_password: The bcrypt hash string from the database
        
    Returns:
        True if the password matches the hash, False otherwise
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash for the given password.
    
    Args:
        password: The plain text password to hash
        
    Returns:
        A bcrypt hash string suitable for database storage
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def validate_password_strength(password: str) -> str:
    """Validate password strength requirements.

    Note: Minimum length validation is handled by Pydantic's Field
    min_length constraint.

    Requirements:
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character from PASSWORD_SPECIAL_CHARS

    Args:
        password: The password to validate

    Returns:
        The validated password

    Raises:
        ValueError: If password doesn't meet strength requirements
    """
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one digit")
    if not any(c in PASSWORD_SPECIAL_CHARS for c in password):
        raise ValueError("Password must contain at least one special character")
    return password
