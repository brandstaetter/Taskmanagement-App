import logging
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from escpos.printer import Usb
from fastapi import Response
from fastapi.responses import JSONResponse

from taskmanagement_app.core.exceptions import PrinterError
from taskmanagement_app.core.printing.base_printer import BasePrinter
from taskmanagement_app.schemas.task import Task

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
max_label_length = max(len(lbl) for lbl in label_dict.values())


class USBPrinter(BasePrinter):
    """USB printer implementation."""

    def __init__(self, config: dict[str, Any]) -> None:
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

    def _detach_kernel_driver(self) -> None:
        """Detach the kernel driver from all interfaces of the USB device.

        The Linux kernel's usblp driver claims the printer automatically,
        which causes [Errno 16] Resource busy when python-escpos tries to
        set the USB configuration. We must release it first.

        Skips gracefully if PyUSB (usb.core) is not installed.
        """
        try:
            import usb.core as usb_core  # type: ignore  # noqa: PLC0415
        except ImportError:
            self.logger.warning("PyUSB not available; skipping kernel driver detach")
            return

        raw = usb_core.find(idVendor=self.vendor_id, idProduct=self.product_id)
        if raw is None:
            return
        for config in raw:
            for interface in config:
                iface_num = interface.bInterfaceNumber
                try:
                    if raw.is_kernel_driver_active(iface_num):
                        raw.detach_kernel_driver(iface_num)
                        self.logger.debug(
                            "Detached kernel driver from interface %d", iface_num
                        )
                except (usb_core.USBError, NotImplementedError) as e:
                    self.logger.warning(
                        "Could not detach kernel driver from interface %d: %s",
                        iface_num,
                        e,
                    )

    def connect(self) -> None:
        """Connect to the USB printer device.

        Raises:
            PrinterError: If printer cannot be found or accessed
        """
        try:
            if self.device is not None:
                self.logger.info("USB printer already connected")
                return

            self.logger.debug("Initializing USB device...")

            # Release the kernel usblp driver so libusb can claim the device
            self._detach_kernel_driver()

            # Create USB printer instance, passing profile so paper width
            # (media.width.pixel) is known and centering works correctly
            self.device = Usb(
                self.vendor_id, self.product_id, timeout=0, profile=self.profile
            )

            # Open connection to device (required in python-escpos v3.1+)
            self.logger.debug("Opening connection to USB device...")
            self.device.open()

            self.logger.info("Successfully connected to USB printer")

        except Exception as e:
            self.device = None  # clear broken state so retries work
            error_msg = f"Failed to connect to USB printer: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise PrinterError(error_msg)

    def format_datetime(self, dt_str: str, tz: Optional[ZoneInfo] = None) -> datetime:
        """Convert ISO datetime string to datetime object in the given timezone.

        Args:
            dt_str: ISO-8601 datetime string.
            tz: Target timezone.  ``None`` keeps the original offset (UTC).
        """
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if tz is not None:
            dt = dt.astimezone(tz)
        return dt

    def printHeading(self, printer: Usb, title: str) -> None:
        """Apply heading style to printer."""
        printer.set(align="center", bold=True, double_height=True, double_width=True)
        printer.text("\n")  # Ensure no leftover from previous print
        lines = self.wrap_text(title, wide=True)
        for line in lines:
            printer.text(line + "\n")

    def printLabel(self, printer: Usb, label_key: str) -> int:
        """Apply label style to printer."""
        printer.set(align="left", bold=True, double_height=False, double_width=False)
        label = label_dict[label_key]
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

        # Calculate effective line length.
        # When not wide, ALL lines (including continuations) must fit in
        # max_length - label_length because printValue indents continuation
        # lines by label_length spaces.
        effective_max_length = (
            (max_length // 2) if wide else (max_length - label_length)
        )
        first_line_length = (
            (max_length - label_length) // 2 if wide else effective_max_length
        )
        current_length = 0

        for word in words:
            # Split long words that exceed line length
            current_word = word
            while len(current_word) > effective_max_length:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = []
                    current_length = 0
                lines.append(current_word[:effective_max_length])
                current_word = current_word[effective_max_length:]

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

    def printValue(self, printer: Usb, text: str, label_length: int) -> None:
        """Print text value with proper wrapping and formatting."""
        printer.set(align="left", bold=False, double_height=False, double_width=False)

        # Wrap text to printer width
        lines = self.wrap_text(text, label_length=label_length)
        indent = " " * label_length
        for i, line in enumerate(lines):
            if i > 0:
                printer.text(indent)
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

    def disconnect(self) -> None:
        """Reset and release the USB device handle.

        Called after every print (success or failure) so the interface is
        freed before the next request arrives.

        Gunicorn runs multiple worker processes that share the same physical
        USB printer.  ``Usb.close()`` only releases the libusb handle inside
        the *calling* process; it does **not** reset the device at the OS
        level.  A subsequent request routed to a different worker will still
        see the interface as "busy".

        ``device.device.reset()`` issues a USB-level reset
        (``USBDEVFS_RESET``), which releases all claimed interfaces and lets
        the kernel usblp driver re-probe.  We call it *before* ``close()``
        so the physical device is fully released for any process.
        """
        if self.device is None:
            return
        try:
            # USB-level reset — releases all claimed interfaces across all
            # processes and lets the kernel driver re-probe the device.
            if hasattr(self.device, "device") and self.device.device is not None:
                self.device.device.reset()
            # Python-escpos cleanup — disposes the libusb handle.
            self.device.close()
            self.logger.debug("USB device reset and closed after print")
        except Exception as e:
            self.logger.warning("Error closing USB device: %s", e)
        finally:
            self.device = None

    def print(self, task: Task, tz_name: Optional[str] = None) -> Response:
        """
        Print a task to the USB printer.

        Args:
            task: Task to print
            tz_name: Optional IANA timezone name (e.g. "Europe/Vienna").

        Returns:
            Response indicating success or failure
        """
        tz = ZoneInfo(tz_name) if tz_name else None

        try:
            self.logger.info("Starting to print task %d", task.id)

            # Initialize USB printer
            self.connect()

            # Print header
            self.printHeading(self.device, task.title)

            self.printSpacer(self.device)

            # Print Description
            if task.description:
                indent = self.printLabel(self.device, "description")
                self.printValue(self.device, task.description, indent)
                self.printSpacer(self.device)

            # Print Due Date
            if task.due_date:
                indent = self.printLabel(self.device, "due_date")
                due_date = self.format_datetime(task.due_date, tz)
                self.printValue(
                    self.device,
                    due_date.strftime("%Y-%m-%d %H:%M"),
                    indent,
                )
                self.printSpacer(self.device)

            if task.reward:
                indent = self.printLabel(self.device, "reward")
                self.printValue(self.device, task.reward, indent)
                self.printSpacer(self.device)

            # Print Created At
            if task.created_at:
                created_at = self.format_datetime(task.created_at, tz)
                indent = self.printLabel(self.device, "created_at")
                self.printValue(
                    self.device, created_at.strftime("%Y-%m-%d %H:%M"), indent
                )

            # Print Started At
            if task.started_at:
                started_at = self.format_datetime(task.started_at, tz)
                indent = self.printLabel(self.device, "started_at")
                self.printValue(
                    self.device, started_at.strftime("%Y-%m-%d %H:%M"), indent
                )

            # Print Completed At
            if task.completed_at:
                completed_at = self.format_datetime(task.completed_at, tz)
                indent = self.printLabel(self.device, "completed_at")
                self.printValue(
                    self.device, completed_at.strftime("%Y-%m-%d %H:%M"), indent
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

        finally:
            # Always release the USB handle so the next request can claim it
            self.disconnect()
