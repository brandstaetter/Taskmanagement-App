import os
from datetime import datetime
from typing import Any, Dict

from escpos.printer import Usb
from fastapi import HTTPException, Response
from fastapi.responses import JSONResponse

from app.schemas.task import Task

from .base_printer import BasePrinter


class USBPrinter(BasePrinter):
    """USB printer implementation using ESC/POS protocol."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Get USB parameters from environment variables
        self.vendor_id = int(os.getenv("USB_PRINTER_VENDOR_ID", "0x28E9"), 16)
        self.product_id = int(os.getenv("USB_PRINTER_PRODUCT_ID", "0x0289"), 16)
        self.profile = os.getenv("USB_PRINTER_PROFILE", "ZJ-5870")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:4200")
        # Receipt is 32 characters wide, first line has 13 chars label
        self.max_line_length = 32
        self.first_line_offset = 13

    def format_datetime(self, dt_str: str) -> datetime:
        """Convert ISO datetime string to datetime object."""
        if not dt_str:
            return None
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

    def styleHeading(self, printer: Usb) -> None:
        printer.set(align="center", bold=True, double_height=True, double_width=True)

    def styleLabel(self, printer: Usb) -> None:
        printer.set(align="left", bold=True, double_height=False, double_width=False)

    def normalize_text(self, text: str) -> str:
        """Replace German umlauts with ASCII characters."""
        return (
            text.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
            .replace("Ä", "Ae")
            .replace("Ö", "Oe")
            .replace("Ü", "Ue")
        )

    def wrap_text(self, text: str, first_line: bool = True) -> list[str]:
        """Wrap text to fit receipt width, considering label space on first line."""
        # Calculate available width for this line
        width = (
            self.max_line_length - self.first_line_offset
            if first_line
            else self.max_line_length
        )

        # Split text into words
        words = self.normalize_text(text).split()
        if not words:
            return [""]

        lines = []
        current_line = []
        current_length = 0

        for word in words:
            # Check if adding this word exceeds the line width
            word_length = len(word)
            if current_length + word_length + (1 if current_line else 0) <= width:
                # Add word to current line
                if current_line:
                    current_line.append(word)
                    current_length += word_length + 1  # +1 for space
                else:
                    current_line.append(word)
                    current_length += word_length
            else:
                # Complete current line and start new one
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length
                # Subsequent lines use full width
                width = self.max_line_length

        # Add last line if there is one
        if current_line:
            lines.append(" ".join(current_line))

        return lines

    def printValue(self, printer: Usb, text: str, wide=False) -> None:
        """Print text value with proper wrapping and formatting."""
        printer.set(align="left", bold=False, double_height=False, double_width=wide)

        # Get wrapped lines
        lines = self.wrap_text(text, first_line=True)

        # Print first line
        if lines:
            printer.text(lines[0])

        # Print subsequent lines with proper indentation
        if len(lines) > 1:
            printer.text("\n")
            for line in lines[1:]:
                printer.text(line + "\n")

    def printHeading(self, printer: Usb, task: Task) -> None:
        self.styleHeading(printer)
        printer.text(f"{task.title}\n\n")

    def printTaskDetails(self, printer: Usb, task: Task) -> None:
        label = {
            "description": "Description: ",
            "due_date": "   Due Date: ",
            "created_at": "    Created: ",
            "reward": "     Reward: ",
        }
        # Print Description
        if task.description:
            self.styleLabel(printer)
            printer.text(label["description"])
            self.printValue(printer, f"{task.description}\n\n")

        # Print Due Date
        if task.due_date:
            due_date = self.format_datetime(task.due_date)
            if due_date:
                self.styleLabel(printer)
                printer.text(label["due_date"])
                self.printValue(
                    printer, f'{due_date.strftime("%Y-%m-%d %H:%M")}\n\n', wide=True
                )

        # Print Created At
        created_at = self.format_datetime(task.created_at)
        if created_at:
            self.styleLabel(printer)
            printer.text(label["created_at"])
            self.printValue(printer, f'{created_at.strftime("%Y-%m-%d %H:%M")}\n\n')

        # Print Started At
        if task.started_at:
            started_at = self.format_datetime(task.started_at)
            if started_at:
                self.styleLabel(printer)
                printer.text(label["started_at"])
                self.printValue(printer, f'{started_at.strftime("%Y-%m-%d %H:%M")}\n\n')

    def printFooter(self, printer: Usb, task: Task) -> None:
        printer.set(align="center")
        printer.text("\n")
        printer.qr(f"{self.frontend_url}/tasks/{task.id}", size=6)
        printer.text("\n")
        printer.text("Scan to view task details\n")

    async def print(self, task: Task) -> Response:
        """
        Print a task to a USB printer using ESC/POS commands.

        Args:
            task: Task model instance to print
        """
        try:
            # Initialize printer
            try:
                printer = Usb(self.vendor_id, self.product_id, profile=self.profile)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to connect to USB printer: {str(e)}",
                )

            # Print title
            self.printHeading(printer, task)

            # Print task details
            self.printTaskDetails(printer, task)

            # Print footer with QR code
            self.printFooter(printer, task)

            # Add final spacing and cut
            printer.text("\n")
            printer.cut()

            # Close the connection
            printer.close()

            return JSONResponse(
                content={"message": "Task printed successfully"}, status_code=200
            )

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to print task: {str(e)}"
            )
