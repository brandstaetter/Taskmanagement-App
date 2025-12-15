import configparser
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union

from taskmanagement_app.core.exceptions import PrinterError
from taskmanagement_app.core.printing.base_printer import BasePrinter
from taskmanagement_app.core.printing.pdf_printer import PDFPrinter

logger = logging.getLogger(__name__)


class PrinterFactory:
    """Factory class for creating printer instances."""

    _supported_printer_types = {"pdf", "usb"}

    @classmethod
    def _get_printer_class(cls, printer_type: str) -> Type[BasePrinter]:
        if printer_type == "pdf":
            return PDFPrinter
        if printer_type == "usb":
            try:
                from taskmanagement_app.core.printing.usb_printer import USBPrinter
            except Exception as e:
                raise PrinterError(f"USB printer backend unavailable: {e}") from e
            return USBPrinter
        raise PrinterError(f"Unsupported printer type: {printer_type}")

    @classmethod
    def create_printer(
        cls, printer_type: Optional[Union[str, Dict[str, Any]]] = None
    ) -> BasePrinter:
        """
        Create a printer instance based on the configuration.

        Args:
            printer_type: Optional printer type (str) or printer config (dict) to
            override the default

        Returns:
            An instance of the configured printer
        """
        # Load printer configuration
        config = configparser.ConfigParser()
        config_path = (
            Path(__file__).parent.parent.parent.parent / "config" / "printers.ini"
        )

        logger.debug(f"Looking for printer config at: {config_path}")

        # Create default config if it doesn't exist
        if not config_path.exists():
            logger.warning(
                f"Printer config not found at {config_path}, creating default"
            )
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config["DEFAULT"] = {"default_printer": "pdf"}
            config["pdf"] = {
                "type": "pdf",
                "name": "PDF Printer",
                "description": "Creates and downloads PDF files",
                "class": "PDFPrinter",
                "output_dir": "output/pdf",
            }
            config["usb"] = {
                "type": "usb",
                "name": "USB Receipt Printer",
                "description": "Prints to USB thermal printer",
                "class": "USBPrinter",
                "vendor_id": "0x28E9",
                "product_id": "0x0289",
                "profile": "ZJ-5870",
                "frontend_url": "http://localhost:4200",
            }
            with open(config_path, "w") as f:
                config.write(f)

        config.read(config_path)
        logger.debug(f"Loaded printer config sections: {config.sections()}")

        # Handle dictionary input for printer_type
        printer_config = {}
        if isinstance(printer_type, dict):
            printer_config = printer_type.copy()
            printer_type = printer_config.pop("type", None)

        # Get printer type from config if not specified
        if not printer_type and not isinstance(printer_type, str):
            printer_type = config.get("DEFAULT", "default_printer", fallback="pdf")
            logger.debug(f"Using printer type from config: {printer_type}")

        # Get printer class
        if printer_type not in cls._supported_printer_types:
            logger.error(f"Unsupported printer type: {printer_type}")
            raise PrinterError(f"Unsupported printer type: {printer_type}")

        # Get printer configuration from ini file if not provided in dict
        if not printer_config and printer_type in config:
            printer_config = dict(config[str(printer_type)])
        logger.debug(f"Printer config for {printer_type}: {printer_config}")

        # Create and return printer instance
        logger.debug(f"Creating printer instance for type: {printer_type}")
        printer_class = cls._get_printer_class(str(printer_type))
        return printer_class(printer_config)
