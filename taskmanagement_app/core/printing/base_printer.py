from abc import ABC, abstractmethod
from typing import Any, Dict

from fastapi import Response

from taskmanagement_app.schemas.task import Task


class BasePrinter(ABC):
    """Base class for all printer implementations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def print(self, task: Task) -> Response:
        """Print the task and return a FastAPI Response object."""
        pass
