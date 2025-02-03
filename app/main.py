from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.jobs.scheduler import start_scheduler, stop_scheduler

# Set up logging first
logger = setup_logging()

# Get settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    version=settings.VERSION,
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


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Task Management API"}
