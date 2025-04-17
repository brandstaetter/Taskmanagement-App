# Task Management API

Backend REST API for the Task Management application.

[![codecov](https://codecov.io/gh/brandstaetter/Taskmanagement-App/graph/badge.svg?token=WOG6NB0DBV)](https://codecov.io/gh/brandstaetter/Taskmanagement-App)

## Features

- Task creation, reading, updating, and deletion
- Task state management (todo, in_progress, done, archived)
- Due date tracking and automatic task processing
- Task printing support (PDF and USB thermal printer)
- Automatic task archiving after completion
- RESTful API with OpenAPI documentation
- Comprehensive logging and error handling

## Setup

1. Install Poetry (if not already installed):

    ```powershell
    (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
    ```

    or

    ```bash
    curl -sSL https://install.python-poetry.org | python3 -
    ```

2. Install dependencies:

    ```powershell
    poetry install  # Installs all dependencies including development ones
    # OR
    poetry install --only main  # For production dependencies only
    ```

3. Set up environment variables:

    ```powershell
    Copy-Item .env.example .env
    poetry run python -c "import secrets; print(f'SECRET_KEY: {secrets.token_hex(32)}\nADMIN_API_KEY: {secrets.token_hex(32)}')"
    ```

4. Run database migrations:

    ```powershell
    poetry run alembic upgrade head
    ```

5. Start the development server:

    ```powershell
    poetry run uvicorn taskmanagement_app.main:app --reload
    ```

## Project Structure

```text
├── taskmanagement_app/
│   ├── api/            # API routes and endpoints
│   │   └── v1/         # API version 1
│   ├── core/           # Core functionality, config, printing
│   ├── crud/           # Database operations
│   ├── db/             # Database models and sessions
│   ├── jobs/           # Background jobs and schedulers
│   └── schemas/        # Pydantic models
├── tests/              # Test files
├── alembic/            # Database migrations
├── .env               # Environment variables
├── pyproject.toml    # Project dependencies and configuration
└── README.md         # Project documentation
```

## Development

Run quality checks with individual tools:


```powershell
poetry run black .
poetry run isort .
poetry run flake8
poetry run mypy .
poetry run pytest --cov
```

## Printer Setup

### PDF Printer


- Automatically creates PDF files in the configured output directory
- Configure output directory in `config/printers.ini`

### USB Thermal Printer


- Supports ESC/POS compatible printers
- Configure USB vendor_id and product_id in `config/printers.ini`
- Prints task details with QR code for quick access
- Default configuration for ZJ-5870 printer included

## API Documentation

When the server is running:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI Schema: <http://localhost:8000/openapi.json>

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI Schema: <http://localhost:8000/openapi.json>

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run all quality checks
5. Submit a pull request

## License

MIT License - see LICENSE file for details
