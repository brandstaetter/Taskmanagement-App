import logging
from datetime import datetime
from typing import Any, Dict

from escpos.printer import Usb
from fastapi import Response
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
    "reward": "Reward: ",
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
                "Initializing USB printer with "
                "vendor_id=0x%04x, product_id=0x%04x, profile=%s",
                self.vendor_id,
                self.product_id,
                self.profile,
            )

            # Initialize device as None until we connect
            self.device: Usb | None = None

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
            if self.device is not None:
                self.logger.info("USB printer already connected")
                return
            self.logger.debug("Searching for USB device...")
            self.device = Usb(self.vendor_id, self.product_id, timeout=0)

            if self.device is None:
                error_msg = "Printer not found: "
                f"vendor_id=0x{self.vendor_id:04x}, product_id=0x{self.product_id:04x}"
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

    def printHeading(self, printer: Usb, title: str) -> None:
        """Apply heading style to printer."""
        printer.set(align="center", bold=True, double_height=True, double_width=True)
        printer.text("\n")
        lines = self.wrap_text(title, max_length=16)
        for line in lines:
            printer.text(line + "\n")

    def printLabel(self, printer: Usb, label: str) -> None:
        """Apply label style to printer."""
        printer.set(align="left", bold=True, double_height=False, double_width=False)
        printer.text(label)

    def printSpacer(self, printer: Usb) -> None:
        """Print a spacer line."""
        printer.set(align="left", bold=False, double_height=True, double_width=False)
        printer.text("\n")

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

    def printQRCode(self, printer: Usb, task_id: int) -> None:
        """Print QR code for task."""
        printer.set(align="center")
        printer.qr(
            f"{self.config.get('frontend_url', 'http://localhost:4200')}"
            f"/tasks/{task_id}/details",
            size=5,
        )

    def cut(self, printer: Usb) -> None:
        """Cut paper."""
        printer.cut()

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
            self.printHeading(self.device, task.title)

            # Print Description
            if task.description:
                self.printLabel(self.device, label["description"])
                self.printValue(self.device, task.description)

            # Print State
            self.printLabel(self.device, label["state"])
            self.printValue(self.device, task.state)

            # Print Due Date
            if task.due_date:
                self.printLabel(self.device, label["due_date"])
                due_date = self.format_datetime(task.due_date)
                self.printValue(self.device, f'{due_date.strftime("%Y-%m-%d %H:%M")}\n')

            if task.reward:
                self.printLabel(self.device, label["reward"])
                self.printValue(self.device, f"{task.reward}\n")

            self.printSpacer(self.device)

            # Print Created At
            if task.created_at:
                created_at = self.format_datetime(task.created_at)
                self.printLabel(self.device, label["created_at"])
                self.printValue(
                    self.device, f'{created_at.strftime("%Y-%m-%d %H:%M")}\n'
                )

            # Print Started At
            if task.started_at:
                started_at = self.format_datetime(task.started_at)
                self.printLabel(self.device, label["started_at"])
                self.printValue(
                    self.device, f'{started_at.strftime("%Y-%m-%d %H:%M")}\n'
                )

            # Print Completed At
            if task.completed_at:
                completed_at = self.format_datetime(task.completed_at)
                self.printLabel(self.device, label["completed_at"])
                self.printValue(
                    self.device, f'{completed_at.strftime("%Y-%m-%d %H:%M")}\n'
                )

            # Print QR code
            self.printQRCode(self.device, task.id)

            # Cut paper
            self.cut(self.device)

            self.logger.info("Successfully printed task %d", task.id)
            return JSONResponse(content={"message": "Task printed successfully"})

        except Exception as e:
            error_msg = f"Failed to print task {task.id}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise PrinterError(error_msg)
