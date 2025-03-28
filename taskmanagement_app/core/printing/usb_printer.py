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
label_dict = {
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
        lines = self.wrap_text(title, wide=True)
        for line in lines:
            printer.text(line + "\n")

    def printLabel(self, printer: Usb, label_key: str) -> int:
        """Apply label style to printer."""
        printer.set(align="left", bold=True, double_height=False, double_width=False)
        label = label_dict[label_key]
        max_label_length = max(len(lbl) for lbl in label_dict.values())
        label = " " * (max_label_length - len(label)) + label
        printer.text(label)
        return max_label_length

    def printSpacer(self, printer: Usb) -> None:
        """Print a spacer line."""
        printer.set(align="left", bold=False, double_height=True, double_width=False)
        printer.text("\n")

    def wrap_text(
        self, text: str, label_length: int = 0, max_length: int = 32, wide: bool = False
    ) -> list[str]:
        """
        Wrap text to fit printer width.

        Args:
            text: Text to wrap
            label_length: Length of label
            max_length: Maximum line length
            wide: Whether to use wide characters

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

        # Calculate effective line length
        effective_max_length = (max_length / 2) if wide else max_length
        first_line_length = effective_max_length - label_length
        current_length = 0

        for word in words:
            # Split long words that exceed line length
            current_word = word
            while len(current_word) > effective_max_length:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = []
                lines.append(current_word[: int(effective_max_length)])
                current_word = current_word[int(effective_max_length) :]

            # Check if this is the first line (with label) or subsequent lines
            current_max_length = (
                first_line_length if not lines else effective_max_length
            )

            # Calculate total length including space if needed
            word_space = 1 if current_line else 0
            total_length = current_length + len(current_word) + word_space

            if total_length <= current_max_length:
                if current_line:
                    current_line.append(current_word)
                    current_length += len(current_word) + word_space
                else:
                    current_line.append(current_word)
                    current_length = len(current_word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [current_word]
                current_length = len(current_word)

        if current_line:
            lines.append(" ".join(current_line))

        return lines if lines else [""]

    def printValue(
        self, printer: Usb, text: str, label_length: int, wide: bool = False
    ) -> None:
        """Print text value with proper wrapping and formatting."""
        printer.set(align="left", bold=False, double_height=False, double_width=wide)

        # Wrap text to printer width
        lines = self.wrap_text(text, label_length=label_length, wide=wide)
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

    def print(self, task: Task) -> Response:
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
                indent = self.printLabel(self.device, "description")
                self.printValue(self.device, task.description, indent)

            # Print Due Date
            if task.due_date:
                indent = self.printLabel(self.device, "due_date")
                due_date = self.format_datetime(task.due_date)
                self.printValue(
                    self.device,
                    f'{due_date.strftime("%Y-%m-%d %H:%M")}\n',
                    indent,
                    wide=True,
                )

            if task.reward:
                indent = self.printLabel(self.device, "reward")
                self.printValue(self.device, f"{task.reward}\n", indent)

            self.printSpacer(self.device)

            # Print Created At
            if task.created_at:
                created_at = self.format_datetime(task.created_at)
                indent = self.printLabel(self.device, "created_at")
                self.printValue(
                    self.device, f'{created_at.strftime("%Y-%m-%d %H:%M")}\n', indent
                )

            # Print Started At
            if task.started_at:
                started_at = self.format_datetime(task.started_at)
                indent = self.printLabel(self.device, "started_at")
                self.printValue(
                    self.device, f'{started_at.strftime("%Y-%m-%d %H:%M")}\n', indent
                )

            # Print Completed At
            if task.completed_at:
                completed_at = self.format_datetime(task.completed_at)
                indent = self.printLabel(self.device, "completed_at")
                self.printValue(
                    self.device, f'{completed_at.strftime("%Y-%m-%d %H:%M")}\n', indent
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
