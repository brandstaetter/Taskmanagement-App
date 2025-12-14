import pytest

from taskmanagement_app.core.security import (
    PASSWORD_SPECIAL_CHARS,
    validate_password_strength,
)


class TestPasswordValidation:
    """Tests for password strength validation."""

    def test_validate_password_strength_valid(self) -> None:
        """Test that a valid password passes validation."""
        assert validate_password_strength("Str0ng!Pass")
        assert validate_password_strength("MyP@ssw0rd")
        assert validate_password_strength("C0mpl3x!ty")

    def test_validate_password_strength_missing_uppercase(self) -> None:
        """Test that password without uppercase fails validation."""
        assert not validate_password_strength("weakpass1!")

    def test_validate_password_strength_missing_lowercase(self) -> None:
        """Test that password without lowercase fails validation."""
        assert not validate_password_strength("WEAKPASS1!")

    def test_validate_password_strength_missing_digit(self) -> None:
        """Test that password without digit fails validation."""
        assert not validate_password_strength("WeakPass!!")

    def test_validate_password_strength_missing_special(self) -> None:
        """Test that password without special character fails validation."""
        assert not validate_password_strength("WeakPass11")

    def test_validate_password_strength_all_character_types(self) -> None:
        """Test that password with all character types passes."""
        # Test with different special characters from PASSWORD_SPECIAL_CHARS
        for special_char in "!@#$%^&*()_+-=[]{}|;:'\",.<>/?":
            password = f"Test{special_char}123"
            assert validate_password_strength(password), (
                f"Password with special char '{special_char}' should be valid"
            )

    def test_validate_password_strength_edge_cases(self) -> None:
        """Test edge cases for password validation."""
        # Minimum valid password
        assert validate_password_strength("Aa1!")
        
        # Very long password
        long_password = "A" * 50 + "a" * 50 + "1" * 50 + "!" * 50
        assert validate_password_strength(long_password)

    def test_password_special_chars_constant(self) -> None:
        """Test that PASSWORD_SPECIAL_CHARS contains expected characters."""
        expected = "!@#$%^&*()_+-=[]{}|;:'\",.<>/?"
        assert PASSWORD_SPECIAL_CHARS == expected
