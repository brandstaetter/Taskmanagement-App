"""Custom exceptions for the taskmanagement_app."""


class TaskManagementError(Exception):
    """Base exception class for all taskmanagement_app exceptions."""

    pass


class PrinterError(TaskManagementError):
    """Exception raised when there is an error during printing operations.

    This exception is used when:
    - PDF generation fails
    - Printer initialization fails
    - File system operations fail during printing
    - Invalid task data is provided for printing
    """

    pass
