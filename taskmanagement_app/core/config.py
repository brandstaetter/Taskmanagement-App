"""Application configuration."""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # Application
    PROJECT_NAME: str = "Task Management API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # CORS Configuration
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:4200"]  # Angular default port

    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./task_management.db", alias="DATABASE_URL"
    )

    # Frontend
    FRONTEND_URL: str = "http://localhost:4200"

    # Security
    SECRET_KEY: str = Field(
        default="your-secret-key-here", alias="SECRET_KEY"
    )  # Change in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Admin credentials
    ADMIN_API_KEY: str = Field(
        default="your-admin-key-here", alias="ADMIN_API_KEY"
    )  # Change in production
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = Field(
        default="admin", alias="ADMIN_PASSWORD"
    )  # Change in production
    ADMIN_EMAIL: str = Field(default="", alias="ADMIN_EMAIL")

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
