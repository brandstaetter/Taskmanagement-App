from abc import ABC, abstractmethod
from typing import Any, Dict

from fastapi import Response


class BasePrinter(ABC):
    """Base class for all printer implementations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def print(self, data: Dict[str, Any]) -> Response:
        """Print the data and return a FastAPI Response object."""
        pass
