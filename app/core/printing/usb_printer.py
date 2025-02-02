from typing import Any, Dict
import os
from datetime import datetime

from escpos.printer import Usb
from fastapi import Response, HTTPException
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

    def format_datetime(self, dt_str: str) -> datetime:
        """Convert ISO datetime string to datetime object."""
        if not dt_str:
            return None
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

    def styleHeading(self, printer: Usb) -> None:
        printer.set(align="center", bold=True, double_height=True, double_width=True)

    def styleLabel(self, printer: Usb) -> None:
        printer.set(align="left", bold=True, double_height=False, double_width=False)

    def printValue(self, printer: Usb, text: str, wide=False) -> None:
        printer.set(align="left", bold=False, double_height=False, double_width=wide)
        printer.text(text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
                    .replace("ß", "ss").replace("Ä", "Ae").replace("Ö", "Oe")
                    .replace("Ü", "Ue"))

    def printHeading(self, printer: Usb, task: Task) -> None:
        self.styleHeading(printer)
        printer.text(f'{task.title}\n\n')

    def printTaskDetails(self, printer: Usb, task: Task) -> None:
        label = {
            "description": "Description: ",
            "due_date":    "   Due Date: ",
            "created_at":  "    Created: ",
            "reward":      "     Reward: ",
        }
        # Print Description
        if task.description:
            self.styleLabel(printer)
            printer.text(label["description"])
            self.printValue(printer, f'{task.description}\n\n')

        # Print Due Date
        if task.due_date:
            due_date = self.format_datetime(task.due_date)
            if due_date:
                self.styleLabel(printer)
                printer.text(label["due_date"])
                self.printValue(printer, f'{due_date.strftime("%Y-%m-%d %H:%M")}\n\n', wide=True)

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
        printer.qr(f'{self.frontend_url}/tasks/{task.id}', size=6)
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
                printer = Usb(
                    self.vendor_id,
                    self.product_id,
                    profile=self.profile
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to connect to USB printer: {str(e)}"
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
                content={"message": "Task printed successfully"},
                status_code=200
            )

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to print task: {str(e)}"
            )
