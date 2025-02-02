from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, Response, HTTPException
from pydantic import BaseModel

from app.core.printing import PrinterFactory

router = APIRouter()
logger = logging.getLogger(__name__)


class PrintRequest(BaseModel):
    """Model for print requests."""
    title: str
    content: List[Dict[str, Any]]
    printer_type: Optional[str] = None


@router.post("/print")
async def print_data(request: PrintRequest) -> Response:
    """
    Print data using the configured printer.
    
    Args:
        request: PrintRequest object containing the data to print
        
    Returns:
        Response from the printer (e.g., PDF file for download)
    """
    try:
        logger.debug(f"Creating printer with type: {request.printer_type}")
        printer = PrinterFactory.create_printer(request.printer_type)
        
        logger.debug(f"Printing data with title: {request.title}")
        logger.debug(f"Content: {request.content}")
        
        response = await printer.print({
            "title": request.title,
            "content": request.content
        })
        
        logger.debug("Print completed successfully")
        return response
        
    except Exception as e:
        logger.error(f"Error during printing: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
