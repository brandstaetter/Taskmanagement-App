# Copilot Instructions for Task Management App

## Project Overview

This is a FastAPI-based Task Management application with printing capabilities. The application provides a REST API for managing tasks with features including task state management, due date tracking, automatic task processing, and PDF/thermal printer support.

## Technology Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI 0.124.4
- **ORM**: SQLAlchemy 2.0.45
- **Migrations**: Alembic 1.17.2
- **Validation**: Pydantic 2.12.5
- **Server**: Uvicorn 0.38.0
- **Package Manager**: Poetry
- **Testing**: pytest with pytest-asyncio and pytest-cov
- **Authentication**: JWT with python-jose and passlib

## Project Structure

```
├── taskmanagement_app/
│   ├── api/            # API routes and endpoints
│   │   └── v1/         # API version 1
│   │       └── endpoints/  # Individual endpoint modules
│   ├── core/           # Core functionality, config, printing
│   ├── crud/           # Database CRUD operations
│   ├── db/             # Database models and sessions
│   │   └── models/     # SQLAlchemy models
│   ├── jobs/           # Background jobs and schedulers
│   └── schemas/        # Pydantic models for validation
├── tests/              # Test files
├── alembic/            # Database migrations
└── config/             # Configuration files (e.g., printers.ini)
```

## Code Style and Formatting

### Python Code Style

- **Line Length**: 88 characters (Black default)
- **Python Version**: 3.11+ (use modern type hints)
- **Formatter**: Black
- **Import Sorter**: isort with Black profile
- **Linter**: flake8 with max-line-length=88
- **Type Checker**: mypy

### Code Quality Tools

Always run these before committing:

```bash
poetry run black .
poetry run isort .
poetry run flake8
poetry run mypy .
poetry run pytest --cov
```

### Import Organization

Use isort sections in this order:
1. FUTURE
2. STDLIB
3. THIRDPARTY
4. FIRSTPARTY (taskmanagement_app)
5. LOCALFOLDER

### Type Hints

- Always use type hints for function parameters and return values
- Use modern Python 3.11+ type hint syntax (e.g., `list[str]` instead of `List[str]`)
- For FastAPI endpoints, use proper typing for responses
- Use `typing.Any` sparingly and prefer specific types

### Docstrings

- Use concise docstrings for functions and classes
- Example: `"""Create a new task with given title."""`
- Keep docstrings simple and clear
- Focus on what the function does, not how

## API Design Patterns

### Endpoint Structure

- All endpoints are under `/api/v1/` prefix
- Organize endpoints by domain in separate modules under `api/v1/endpoints/`
- Use FastAPI's dependency injection for common dependencies (see `api/deps.py`)

### Response Models

- Define Pydantic schemas in `schemas/` directory
- Use separate schemas for create, update, and response models
- Example: `TaskCreate`, `TaskUpdate`, `TaskResponse`

### Error Handling

- Use FastAPI's HTTPException for API errors
- Include descriptive error messages
- Use appropriate HTTP status codes

### Authentication

- JWT-based authentication is implemented
- Admin endpoints require API key authentication
- Use dependencies from `api/deps.py` for authentication checks

## Database Patterns

### Models

- SQLAlchemy models are in `db/models/`
- Use declarative base from `db/base.py`
- Include proper relationships and constraints
- Add indexes for frequently queried fields

### CRUD Operations

- Separate CRUD logic in `crud/` directory
- Use type hints for all CRUD functions
- Return SQLAlchemy models from CRUD operations
- Convert to Pydantic schemas in the API layer

### Migrations

- Use Alembic for all database schema changes
- Generate migrations with: `poetry run alembic revision --autogenerate -m "description"`
- Apply migrations with: `poetry run alembic upgrade head`

### Session Management

- Use `get_db()` dependency for database sessions
- Sessions are automatically closed after request
- Use context managers for transactions when needed

## Testing Conventions

### Test Organization

- Mirror the source structure in `tests/` directory
- Test file naming: `test_<module>.py`
- Use `conftest.py` for shared fixtures

### Test Style

- Use descriptive test function names: `test_<what>_<scenario>()`
- Use helper functions for common test operations
- Example: `create_test_task()`, `verify_task_state()`
- Use pytest fixtures for test data and clients
- Use `TestClient` from FastAPI for API testing

### Test Coverage

- Aim for high test coverage
- Test happy paths and error cases
- Use `pytest --cov` to check coverage
- Tests should be independent and idempotent

### Async Testing

- Use `pytest-asyncio` for async tests
- Mark async tests with `@pytest.mark.asyncio`

## Configuration Management

### Settings

- Use Pydantic Settings for configuration (`core/config.py`)
- Load from environment variables or `.env` file
- Never commit sensitive data (API keys, secrets)
- Use `.env.example` as a template

### Environment Variables

- `SECRET_KEY`: JWT secret key
- `ADMIN_API_KEY`: Admin API authentication key
- `DATABASE_URL`: Database connection string
- `PROJECT_NAME`: Application name
- `VERSION`: API version

## Background Jobs

- Use APScheduler for scheduled tasks
- Job definitions in `jobs/` directory
- Jobs start on application startup via lifespan context manager
- Example: Automatic task archiving after completion

## Printer Integration

### Supported Printers

- PDF printer (creates PDF files)
- USB thermal printer (ESC/POS compatible)

### Configuration

- Printer settings in `config/printers.ini`
- Use `core/printer/` modules for printer logic
- Generate QR codes for task quick access

## Development Workflow

### Setup

1. Install Poetry
2. Run `poetry install`
3. Copy `.env.example` to `.env` and configure
4. Run migrations: `poetry run alembic upgrade head`
5. Start server: `poetry run uvicorn taskmanagement_app.main:app --reload`

### Adding New Features

1. Create database models if needed
2. Generate and apply Alembic migration
3. Create Pydantic schemas
4. Implement CRUD operations
5. Create API endpoints
6. Write tests
7. Run code quality tools

### Code Review Checklist

- [ ] Type hints on all functions
- [ ] Tests written and passing
- [ ] Code formatted with Black and isort
- [ ] No flake8 warnings
- [ ] No mypy errors
- [ ] Documentation updated if needed
- [ ] Environment variables in `.env.example`

## Common Patterns

### Creating an API Endpoint

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from taskmanagement_app.api import deps
from taskmanagement_app import schemas, crud

router = APIRouter()

@router.post("/items", response_model=schemas.ItemResponse)
async def create_item(
    item: schemas.ItemCreate,
    db: Session = Depends(deps.get_db),
) -> Any:
    """Create a new item."""
    return crud.item.create(db, obj_in=item)
```

### Creating a Database Model

```python
from sqlalchemy import Column, Integer, String, DateTime
from taskmanagement_app.db.base import Base

class Item(Base):
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
```

### Creating a Pydantic Schema

```python
from pydantic import BaseModel, Field
from datetime import datetime

class ItemBase(BaseModel):
    name: str = Field(..., description="Item name")

class ItemCreate(ItemBase):
    pass

class ItemResponse(ItemBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True
```

## Best Practices

- Keep functions small and focused
- Use meaningful variable and function names
- Avoid magic numbers; use named constants
- Validate inputs with Pydantic models
- Use dependency injection for reusable logic
- Log important events and errors
- Handle edge cases gracefully
- Write self-documenting code
- Keep business logic separate from API layer
- Use transactions for multi-step database operations
