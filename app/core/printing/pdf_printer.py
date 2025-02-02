from typing import Any, Dict
import tempfile
from datetime import datetime

from fastapi import Response
from fastapi.responses import FileResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

from app.schemas.task import Task
from .base_printer import BasePrinter


class PDFPrinter(BasePrinter):
    """PDF printer implementation that creates and returns a PDF file."""

    def format_datetime(self, dt_str: str) -> datetime:
        """Convert ISO datetime string to datetime object."""
        if not dt_str:
            return None
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

    async def print(self, task: Task) -> Response:
        """
        Create a PDF from the task and return it as a downloadable response.
        
        Args:
            task: Task model instance to print
        """
        # Create a temporary file for the PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            # Create the PDF document
            doc = SimpleDocTemplate(
                tmp_file.name,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )

            # Container for the 'Flowable' objects
            elements = []

            # Add title
            styles = getSampleStyleSheet()
            title = Paragraph(f"Task Details - {task.title}", styles["Heading1"])
            elements.append(title)

            # Convert task to table data
            task_dict = {
                "ID": str(task.id),
                "Title": task.title,
                "Description": task.description or "",
            }

            # Add dates if they exist
            if task.due_date:
                due_date = self.format_datetime(task.due_date)
                if due_date:
                    task_dict["Due Date"] = due_date.strftime("%Y-%m-%d %H:%M")

            created_at = self.format_datetime(task.created_at)
            if created_at:
                task_dict["Created at"] = created_at.strftime("%Y-%m-%d %H:%M")

            if task.started_at:
                started_at = self.format_datetime(task.started_at)
                if started_at:
                    task_dict["Started at"] = started_at.strftime("%Y-%m-%d %H:%M")

            # Create table data
            table_data = [["Field", "Value"]]  # Headers
            for field, value in task_dict.items():
                table_data.append([field, value])

            # Create table
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 14),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(table)

            # Build PDF
            doc.build(elements)

            # Return the PDF file as a response
            return FileResponse(
                path=tmp_file.name,
                filename=f"task_{task.id}_{task.title.lower().replace(' ', '_')}.pdf",
                media_type="application/pdf"
            )
