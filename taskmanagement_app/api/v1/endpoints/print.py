import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from taskmanagement_app.core.auth import verify_access_token
from taskmanagement_app.core.printing.printer_factory import PrinterFactory
from taskmanagement_app.schemas.task import Task

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(verify_access_token)])


class PrintRequest(BaseModel):
    """Model for print requests."""

    title: str
    content: List[Dict[str, Any]]
    printer_type: Optional[str] = None


@router.post("/")
async def print_data(request: PrintRequest) -> Response:
    """
    Print data using the configured printer.

    Args:
        request: PrintRequest object containing the data to print

    Returns:
        Response from the printer (e.g., PDF file for download)
    """
    try:
        # Create printer instance
        printer = PrinterFactory.create_printer(request.printer_type)

        logger.debug(f"Printing data with title: {request.title}")
        logger.debug(f"Content: {request.content}")

        # Create a Task object from the request data
        task_data = Task(
            id=0,  # Placeholder ID
            title=request.title,
            description=request.content[0].get("description", ""),
            state="todo",
            created_at=None,
            due_date=None,
            started_at=None,
            completed_at=None,
        )

        response = printer.print(task_data)

        logger.debug("Print completed successfully")
        return response

    except Exception as e:
        logger.error(f"Error printing data: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error printing data: {str(e)} {type(e)}"
        )
