import logging
import sys


def setup_logging():
    """Configure logging for the application."""
    # Get the root logger
    root_logger = logging.getLogger()

    # Clear any existing handlers
    root_logger.handlers = []

    # Set the root logger level to INFO
    root_logger.setLevel(logging.INFO)

    # Create console handler that matches uvicorn's format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Add formatter to console handler
    console_handler.setFormatter(formatter)

    # Add console handler to root logger
    root_logger.addHandler(console_handler)

    # Set levels for specific loggers
    logging.getLogger("apscheduler").setLevel(logging.INFO)
    logging.getLogger("app.jobs").setLevel(logging.INFO)

    return root_logger
