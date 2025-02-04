from datetime import datetime

from escpos.printer import Usb
from fastapi import HTTPException, Response
from fastapi.responses import JSONResponse

from taskmanagement_app.core.printing.base_printer import BasePrinter
from taskmanagement_app.schemas.task import Task

# Constants for USB printer
VENDOR_ID = 0x0456
PRODUCT_ID = 0x0808
IN_EP = 0x81
OUT_EP = 0x03

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
            # Initialize USB printer
            printer = Usb(
                VENDOR_ID,
                PRODUCT_ID,
                timeout=0,
                in_ep=IN_EP,
                out_ep=OUT_EP,
            )

            # Print header
            self.styleHeading(printer)
            printer.text("TASK DETAILS\n\n")

            # Print Title
            self.styleLabel(printer)
            printer.text(label["title"])
            self.printValue(printer, task.title, wide=True)
            printer.text("\n")

            # Print Description
            if task.description:
                self.styleLabel(printer)
                printer.text(label["description"])
                self.printValue(printer, task.description)
                printer.text("\n")

            # Print State
            self.styleLabel(printer)
            printer.text(label["state"])
            self.printValue(printer, task.state)
            printer.text("\n")

            # Print Due Date
            if task.due_date:
                self.styleLabel(printer)
                printer.text(label["due_date"])
                due_date = self.format_datetime(task.due_date)
                self.printValue(printer, f'{due_date.strftime("%Y-%m-%d %H:%M")}\n\n')

            # Print Created At
            if task.created_at:
                created_at = self.format_datetime(task.created_at)
                self.styleLabel(printer)
                printer.text(label["created_at"])
                self.printValue(printer, f'{created_at.strftime("%Y-%m-%d %H:%M")}\n\n')

            # Print Started At
            if task.started_at:
                started_at = self.format_datetime(task.started_at)
                self.styleLabel(printer)
                printer.text(label["started_at"])
                self.printValue(printer, f'{started_at.strftime("%Y-%m-%d %H:%M")}\n\n')

            # Print Completed At
            if task.completed_at:
                completed_at = self.format_datetime(task.completed_at)
                self.styleLabel(printer)
                printer.text(label["completed_at"])
                self.printValue(
                    printer, f'{completed_at.strftime("%Y-%m-%d %H:%M")}\n\n'
                )

            # Cut paper
            printer.cut()

            return JSONResponse(content={"message": "Task printed successfully"})

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error printing task: {str(e)}",
            )
