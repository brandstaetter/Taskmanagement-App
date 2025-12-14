from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Define password requirements
PASSWORD_SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:'\",.<>/?"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> bool:
    """
    Validate that a password meets strength requirements.
    
    Requirements:
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character from PASSWORD_SPECIAL_CHARS
    
    Args:
        password: The password to validate
        
    Returns:
        True if password meets all requirements, False otherwise
    """
    return (
        any(c.isupper() for c in password)
        and any(c.islower() for c in password)
        and any(c.isdigit() for c in password)
        and any(c in PASSWORD_SPECIAL_CHARS for c in password)
    )
