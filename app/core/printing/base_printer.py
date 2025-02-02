from abc import ABC, abstractmethod
from typing import Any, Dict

from fastapi import Response
from sqlalchemy.orm import Session

from app.schemas.task import Task


class BasePrinter(ABC):
    """Base class for all printer implementations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def print(self, task: Task) -> Response:
        """Print the task and return a FastAPI Response object."""
        pass
