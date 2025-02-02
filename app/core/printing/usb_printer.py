from typing import Any, Dict
import os

from escpos.printer import Usb
from fastapi import Response, HTTPException
from fastapi.responses import JSONResponse

from .base_printer import BasePrinter


class USBPrinter(BasePrinter):
    """USB printer implementation using ESC/POS protocol."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Get USB parameters from environment variables
        self.vendor_id = int(os.getenv("USB_PRINTER_VENDOR_ID", "0x28E9"), 16)
        self.product_id = int(os.getenv("USB_PRINTER_PRODUCT_ID", "0x0289"), 16)
        self.profile = os.getenv("USB_PRINTER_PROFILE", "ZJ-5870")

    async def print(self, data: Dict[str, Any]) -> Response:
        """
        Print the data to a USB printer using ESC/POS commands.
        
        Args:
            data: Dictionary containing:
                 - title: str
                 - content: List[Dict] with Field and Value keys
        """
        try:
            # Initialize printer
            printer = Usb(
                self.vendor_id,
                self.product_id,
                profile=self.profile
            )

            # Print title
            printer.set(align='center', bold=True, double_height=True)
            printer.text(data["title"] + "\n\n")

            # Print content
            printer.set(align='left', bold=False, double_height=False)
            max_field_width = max(len(item["Field"]) for item in data["content"])
            
            for item in data["content"]:
                field = item["Field"].ljust(max_field_width)
                value = item["Value"]
                printer.text(f"{field}: {value}\n")

            # Add final spacing and cut
            printer.text("\n\n\n")
            printer.cut()

            # Close the connection
            printer.close()

            return JSONResponse(
                content={"message": "Document printed successfully"},
                status_code=200
            )

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to print to USB printer: {str(e)}"
            )
