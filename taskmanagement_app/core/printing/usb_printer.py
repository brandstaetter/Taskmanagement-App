from datetime import datetime
import logging
from typing import Any, Dict, Optional

from escpos.printer import Usb
from fastapi import HTTPException, Response
from fastapi.responses import JSONResponse

from taskmanagement_app.core.exceptions import PrinterError
from taskmanagement_app.core.printing.base_printer import BasePrinter
from taskmanagement_app.schemas.task import Task


# Constants for USB printer
VENDOR_ID = 0x0456
PRODUCT_ID = 0x0808

# Labels for task fields
label = {
    "title": "Title: ",
    "description": "Description: ",
    "due_date": "Due Date: ",
    "state": "State: ",
    "created_at": "Created: ",
    "started_at": "Started: ",
    "completed_at": "Completed: ",
}


class USBPrinter(BasePrinter):
    """USB printer implementation."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize USB printer with vendor and product IDs.
        
        Args:
            config: Dictionary containing USB printer configuration:
                - vendor_id: USB vendor ID in hex format (e.g., "0x28E9")
                - product_id: USB product ID in hex format (e.g., "0x0289")
                - profile: Printer profile name (e.g., "ZJ-5870")
        """
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
        
        try:
            # Parse vendor and product IDs from config
            self.vendor_id = int(config["vendor_id"], 16)
            self.product_id = int(config["product_id"], 16)
            self.profile = config.get("profile", "default")
            
            self.logger.info(
                "Initializing USB printer with vendor_id=0x%04x, product_id=0x%04x, profile=%s",
                self.vendor_id, self.product_id, self.profile
            )
            
            # Initialize device as None until we connect
            self.device: Optional[Usb] = None
            
        except KeyError as e:
            error_msg = f"Missing required config parameter: {e}"
            self.logger.error(error_msg)
            raise PrinterError(error_msg)
        except ValueError as e:
            error_msg = f"Invalid vendor or product ID format: {e}"
            self.logger.error(error_msg)
            raise PrinterError(error_msg)

    def connect(self) -> None:
        """Connect to the USB printer device.
        
        Raises:
            PrinterError: If printer cannot be found or accessed
        """
        try:
            self.logger.debug("Searching for USB device...")
            self.device = Usb(
                self.vendor_id,
                self.product_id,
                timeout=0
            )
            
            if self.device is None:
                error_msg = f"Printer not found: vendor_id=0x{self.vendor_id:04x}, product_id=0x{self.product_id:04x}"
                self.logger.error(error_msg)
                raise PrinterError(error_msg)
                
            self.logger.info("USB printer found: %s", self.device)
            
            self.logger.info("Successfully connected to USB printer")
            
        except Exception as e:
            error_msg = f"Unexpected error while connecting to printer: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise PrinterError(error_msg)

    def format_datetime(self, dt_str: str) -> datetime:
        """Convert ISO datetime string to datetime object."""
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

    def styleHeading(self, printer: Usb) -> None:
        """Apply heading style to printer."""
        printer.set(align="center", bold=True, double_height=True, double_width=True)

    def styleLabel(self, printer: Usb) -> None:
        """Apply label style to printer."""
        printer.set(align="left", bold=True, double_height=False, double_width=False)

    def wrap_text(self, text: str, max_length: int = 32) -> list[str]:
        """
        Wrap text to fit printer width.

        Args:
            text: Text to wrap
            max_length: Maximum line length

        Returns:
            List of wrapped lines
        """
        if not text:
            return [""]

        words = text.split()
        if not words:
            return [""]

        lines = []
        current_line: list[str] = []
        current_length = 0

        for word in words:
            word_length = len(word)
            if current_length + word_length + 1 <= max_length:
                current_line.append(word)
                current_length += word_length + 1
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length

        if current_line:
            lines.append(" ".join(current_line))

        return lines

    def printValue(self, printer: Usb, text: str, wide: bool = False) -> None:
        """Print text value with proper wrapping and formatting."""
        printer.set(align="left", bold=False, double_height=False, double_width=wide)

        # Wrap text to printer width
        lines = self.wrap_text(text)
        for line in lines:
            printer.text(line + "\n")

    async def print(self, task: Task) -> Response:
        """
        Print a task to the USB printer.

        Args:
            task: Task to print

        Returns:
            Response indicating success or failure
        """
        try:
            self.logger.info("Starting to print task %d", task.id)
            
            # Initialize USB printer
            self.connect()
            
            # Print header
            self.styleHeading(self.device)
            self.device.text("TASK DETAILS\n\n")

            # Print Title
            self.styleLabel(self.device)
            self.device.text(label["title"])
            self.printValue(self.device, task.title, wide=True)
            self.device.text("\n")

            # Print Description
            if task.description:
                self.styleLabel(self.device)
                self.device.text(label["description"])
                self.printValue(self.device, task.description)
                self.device.text("\n")

            # Print State
            self.styleLabel(self.device)
            self.device.text(label["state"])
            self.printValue(self.device, task.state)
            self.device.text("\n")

            # Print Due Date
            if task.due_date:
                self.styleLabel(self.device)
                self.device.text(label["due_date"])
                due_date = self.format_datetime(task.due_date)
                self.printValue(self.device, f'{due_date.strftime("%Y-%m-%d %H:%M")}\n\n')

            # Print Created At
            if task.created_at:
                created_at = self.format_datetime(task.created_at)
                self.styleLabel(self.device)
                self.device.text(label["created_at"])
                self.printValue(self.device, f'{created_at.strftime("%Y-%m-%d %H:%M")}\n\n')

            # Print Started At
            if task.started_at:
                started_at = self.format_datetime(task.started_at)
                self.styleLabel(self.device)
                self.device.text(label["started_at"])
                self.printValue(self.device, f'{started_at.strftime("%Y-%m-%d %H:%M")}\n\n')

            # Print Completed At
            if task.completed_at:
                completed_at = self.format_datetime(task.completed_at)
                self.styleLabel(self.device)
                self.device.text(label["completed_at"])
                self.printValue(
                    self.device, f'{completed_at.strftime("%Y-%m-%d %H:%M")}\n\n'
                )

            frontend_url = self.config.get("frontend_url", "http://localhost:4200")

            # Print QR code
            self.device.set(align="center")
            self.device.qr(frontend_url + "/tasks/"+str(task.id)+"/details", size=5)

            # Cut paper
            self.device.cut()

            self.logger.info("Successfully printed task %d", task.id)
            return JSONResponse(content={"message": "Task printed successfully"})

        except Exception as e:
            error_msg = f"Failed to print task {task.id}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=error_msg,
            )
