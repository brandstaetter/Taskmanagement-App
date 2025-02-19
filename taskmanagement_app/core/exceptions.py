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


class TaskStatusError(TaskManagementError):
    """Exception raised when an invalid task status
    transition is encountered."""

    pass


class TaskNotFoundError(TaskManagementError):
    """Exception raised when a requested task cannot be found.

    This exception is used when:
    - Task ID does not exist in the database
    - Task was deleted or is otherwise inaccessible
    """

    def __init__(self, task_id: int):
        self.task_id = task_id
        super().__init__(f"Task with id {task_id} not found")
