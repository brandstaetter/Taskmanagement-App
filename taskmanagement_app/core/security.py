from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Define password requirements
PASSWORD_SPECIAL_CHARS = set("!@#$%^&*()_+-=[]{}|;:'\",.<>/?")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


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
