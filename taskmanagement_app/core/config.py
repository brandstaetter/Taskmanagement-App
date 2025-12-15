from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

    PROJECT_NAME: str = "Task Management API"
    API_V1_STR: str = "/api/v1"

    # CORS Configuration
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:4200"]  # Angular default port

    # Database
    DATABASE_URL: str = "sqlite:///./task_management.db"

    # Frontend
    FRONTEND_URL: str = "http://localhost:4200"

    # JWT
    SECRET_KEY: str = "your-secret-key-here"  # Change in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Admin Authentication
    ADMIN_API_KEY: str = "your-admin-key-here"  # Change in production
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"  # Change in production


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
