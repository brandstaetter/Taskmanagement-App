import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Response
from fastapi.responses import FileResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Table, TableStyle

from taskmanagement_app.core.exceptions import PrinterError
from taskmanagement_app.schemas.task import Task

from .base_printer import BasePrinter


class PDFPrinter(BasePrinter):
    """PDF printer implementation that creates and returns a PDF file."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the PDF printer with output directory and logger.

        Args:
            config: Dictionary containing configuration values
        """
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
        self.output_dir = Path(config.get("output_dir", "output"))
        try:
            self.output_dir.mkdir(exist_ok=True)
            self.logger.info(
                "PDF printer initialized. Output directory: %s", self.output_dir
            )
        except Exception as e:
            self.logger.error(
                "Failed to create output directory: %s", str(e), exc_info=True
            )
            raise PrinterError(f"Failed to initialize PDF printer: {str(e)}")

    def format_datetime(self, dt_str: str) -> Optional[datetime]:
        """Convert ISO datetime string to datetime object.

        Args:
            dt_str: ISO format datetime string

        Returns:
            datetime object or None if parsing fails
        """
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, TypeError) as e:
            self.logger.warning("Failed to parse datetime %s: %s", dt_str, str(e))
            return None

    def create_table_style(self) -> TableStyle:
        """Create the table style for the PDF document.

        Returns:
            TableStyle object with formatting rules
        """
        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 14),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 12),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )

    def print_task(self, task: Task) -> Response:
        """Print a task to a PDF file.

        Args:
            task: Task model instance to print

        Returns:
            FileResponse containing the generated PDF

        Raises:
            PrinterError: If PDF generation fails
        """
        try:
            self.logger.info("Starting PDF generation for task %d", task.id)
            filename = f"task_{task.id}_{task.title.lower().replace(' ', '_')}.pdf"

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                self.logger.debug("Creating temporary file: %s", tmp_file.name)

                # Create the PDF document
                doc = SimpleDocTemplate(
                    tmp_file.name,
                    pagesize=letter,
                    rightMargin=72,
                    leftMargin=72,
                    topMargin=72,
                    bottomMargin=72,
                )

                # Container for the 'Flowable' objects
                elements: List[Flowable] = []

                # Add title
                self.logger.debug("Adding title to PDF")
                styles = getSampleStyleSheet()
                title = Paragraph(f"Task Details - {task.title}", styles["Heading1"])
                elements.append(title)

                # Convert task to table data
                self.logger.debug("Converting task data to table format")
                task_dict: dict[str, str] = {
                    "ID": str(task.id),
                    "Title": task.title,
                    "Description": task.description or "",
                    "Status": task.state,
                    "Reward": task.reward or "None",
                }

                # Add dates if they exist
                for date_field in [
                    "due_date",
                    "created_at",
                    "started_at",
                    "completed_at",
                ]:
                    date_str = getattr(task, date_field, None)
                    if date_str:
                        date_obj = self.format_datetime(date_str)
                        if date_obj:
                            formatted_name = date_field.replace("_", " ").title()
                            task_dict[formatted_name] = date_obj.strftime(
                                "%Y-%m-%d %H:%M"
                            )

                # Create table data
                table_data = [["Field", "Value"]]  # Headers
                for field, value in task_dict.items():
                    table_data.append([field, value])

                # Create and style table
                self.logger.debug("Creating table with %d rows", len(table_data))
                table = Table(table_data)
                table.setStyle(self.create_table_style())
                elements.append(table)

                # Build PDF
                self.logger.debug("Building final PDF document")
                doc.build(elements)
                self.logger.info("Successfully generated PDF at: %s", tmp_file.name)

                return FileResponse(
                    path=tmp_file.name,
                    filename=filename,
                    media_type="application/pdf",
                )

        except Exception as e:
            error_msg = f"Failed to generate PDF for task {task.id}"
            self.logger.error("%s: %s", error_msg, str(e), exc_info=True)
            raise PrinterError(f"{error_msg}: {str(e)}")

    async def print(self, task: Task) -> Response:
        """Print the task and return a FastAPI Response object.

        This is the implementation of the abstract method from BasePrinter.

        Args:
            task: Task model instance to print

        Returns:
            FileResponse containing the generated PDF

        Raises:
            PrinterError: If PDF generation fails
        """
        return self.print_task(task)
