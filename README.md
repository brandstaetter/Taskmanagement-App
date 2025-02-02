# Task Management API

Backend REST API for the Task Management application.

## Setup

1. Create a virtual environment:
```powershell
python -m venv venv
.\venv\Scripts\Activate
```

2. Install dependencies:
```powershell
pip install -r requirements.txt  # For development with flexible versions
# OR
pip install -r requirements.lock  # For exact versions (recommended for production)
```

3. Set up environment variables:
```powershell
Copy-Item .env.example .env
.\venv\Scripts\Activate.ps1; python -c "import secrets; print(f'SECRET_KEY: {secrets.token_hex(32)}\nADMIN_API_KEY: {secrets.token_hex(32)}')"
```

4. Run database migrations:
```powershell
alembic upgrade head
```

5. Start the development server:
```powershell
uvicorn app.main:app --reload
```

## Project Structure

```
├── app/
│   ├── api/            # API routes
│   ├── core/           # Core functionality, config
│   ├── db/             # Database models and sessions
│   ├── schemas/        # Pydantic models
│   └── services/       # Business logic
├── tests/              # Test files
├── alembic/            # Database migrations
├── .env               # Environment variables
├── requirements.txt   # Project dependencies
└── README.md         # Project documentation
```

## Development

- Format code: `black .`
- Sort imports: `isort .`
- Run linter: `flake8`
- Run tests: `pytest`

## API Documentation

When the server is running:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
