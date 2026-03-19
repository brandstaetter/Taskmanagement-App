from abc import ABC, abstractmethod
from typing import Any, Optional

from fastapi import Response

from taskmanagement_app.schemas.task import Task


class BasePrinter(ABC):
    """Base class for all printer implementations."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    def print(self, task: Task, tz_name: Optional[str] = None) -> Response:
        """Print the task and return a FastAPI Response object.

        Args:
            task: The task to print.
            tz_name: Optional IANA timezone name (e.g. "Europe/Vienna").
                     When provided, all timestamps are converted to this
                     timezone before formatting.  Defaults to UTC.
        """
        pass
