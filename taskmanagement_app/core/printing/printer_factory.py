import configparser
import logging
from pathlib import Path
from typing import Dict, Optional, Type

from taskmanagement_app.core.printing.base_printer import BasePrinter
from taskmanagement_app.core.printing.pdf_printer import PDFPrinter
from taskmanagement_app.core.printing.usb_printer import USBPrinter

logger = logging.getLogger(__name__)


class PrinterFactory:
    """Factory class for creating printer instances."""

    _printer_classes: Dict[str, Type[BasePrinter]] = {
        "pdf": PDFPrinter,
        "usb": USBPrinter,
    }

    @classmethod
    def create_printer(cls, printer_type: Optional[str] = None) -> BasePrinter:
        """
        Create a printer instance based on the configuration.

        Args:
            printer_type: Optional printer type to override the default from config

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

        # Get printer type from config if not specified
        if not printer_type:
            printer_type = config.get("DEFAULT", "default_printer", fallback="pdf")
            logger.debug(f"Using printer type from config: {printer_type}")

        # Get printer class
        if printer_type not in cls._printer_classes:
            logger.error(f"Unsupported printer type: {printer_type}")
            raise ValueError(f"Unsupported printer type: {printer_type}")

        # Get printer configuration
        printer_config = dict(config[printer_type]) if printer_type in config else {}
        logger.debug(f"Printer config for {printer_type}: {printer_config}")

        # Create and return printer instance
        logger.debug(f"Creating printer instance for type: {printer_type}")
        return cls._printer_classes[printer_type](printer_config)
