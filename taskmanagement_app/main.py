from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from taskmanagement_app.api.v1.api import api_router
from taskmanagement_app.core.config import get_settings
from taskmanagement_app.core.logging import setup_logging
from taskmanagement_app.jobs.scheduler import start_scheduler, stop_scheduler
from taskmanagement_app.schemas.common import RootResponse

# Set up logging first
logger = setup_logging()

# Get settings
settings = get_settings()


def _get_app_version() -> str:
    try:
        return version("taskmanagement_app")
    except PackageNotFoundError:
        return "0.0.1-SNAPSHOT"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Handle startup and shutdown events for the FastAPI application.
    """
    # Startup
    logger.info("Starting application")
    start_scheduler()
    yield
    # Shutdown
    logger.info("Shutting down application")
    stop_scheduler()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for managing tasks with printing capabilities",
    version=_get_app_version(),
    lifespan=lifespan,
)

# Setup CORS
origins = settings.BACKEND_CORS_ORIGINS
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", response_model=RootResponse)
async def root() -> RootResponse:
    """Root endpoint."""
    return RootResponse(message="Task Management API")
