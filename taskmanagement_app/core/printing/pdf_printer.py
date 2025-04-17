import io
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import qrcode
from fastapi import Response
from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer

from taskmanagement_app.core.exceptions import PrinterError
from taskmanagement_app.schemas.task import Task

from .base_printer import BasePrinter


class QRCodeFlowable(Flowable):
    """A Flowable wrapper for QR Code."""

    def __init__(self, qr_code_data: str) -> None:
        Flowable.__init__(self)
        self.qr_code_data = qr_code_data
        self.temp_file: str | None = None
        # Set width to match the document's available width
        self.width = 70 * mm  # 80mm - 2*5mm margins
        self.height = 30 * mm

    def draw(self) -> None:
        """Draw the QR code on the canvas."""
        try:
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=3,
                border=2,
            )
            qr.add_data(self.qr_code_data)
            qr.make(fit=True)

            # Create QR code image
            img = qr.make_image(fill_color="black", back_color="white")

            # Create a temporary file for the QR code
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                # Save QR code to bytes buffer first
                img_buffer = io.BytesIO()
                img.save(img_buffer)
                # Write bytes to temporary file
                tmp_file.write(img_buffer.getvalue())
                self.temp_file = tmp_file.name

            # Draw on the canvas
            qr_size = 25 * mm  # QR code size in millimeters
            # Center the QR code within the flowable's width
            x_pos = (self.width - qr_size) / 2
            self.canv.drawImage(
                self.temp_file, x_pos, 0, width=qr_size, height=qr_size, mask="auto"
            )
        finally:
            # Clean up temporary file
            if self.temp_file is not None and os.path.exists(self.temp_file):
                os.unlink(self.temp_file)


class DottedLine(Flowable):
    """A Flowable that draws a dotted line."""

    def __init__(self, width: float) -> None:
        Flowable.__init__(self)
        self.width = width

    def draw(self) -> None:
        """Draw the dotted line on the canvas."""
        self.canv.setDash(1, 2)  # 1 point dash, 2 points space
        self.canv.line(0, 0, self.width, 0)


class PDFPrinter(BasePrinter):
    """PDF printer implementation that creates receipt-like PDF files."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the PDF printer with output directory and logger."""
        super().__init__(config)
        self.logger = logging.getLogger(__name__)

        if "output_dir" not in config:
            self.logger.error("Missing required configuration: output_dir")
            raise PrinterError("Missing required configuration: output_dir")

        self.output_dir = Path(config["output_dir"])
        try:
            self.output_dir.mkdir(exist_ok=True, parents=True)
            self.logger.info(
                "PDF printer initialized. Output directory: %s", self.output_dir
            )
        except Exception as e:
            self.logger.error(
                "Failed to create output directory: %s", str(e), exc_info=True
            )
            raise PrinterError(f"Failed to initialize PDF printer: {str(e)}")

    def format_datetime(self, dt_str: str) -> Optional[datetime]:
        """Convert ISO datetime string to datetime object."""
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, TypeError) as e:
            self.logger.warning("Failed to parse datetime %s: %s", dt_str, str(e))
            return None

    def _create_document_styles(self) -> Dict[str, ParagraphStyle]:
        """Create and return the document styles."""
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "Title",
            parent=styles["Normal"],
            fontName="Courier-Bold",
            fontSize=16,
            alignment=1,  # Center alignment
            spaceAfter=4 * mm,
            leftIndent=0,
            rightIndent=0,
            leading=18,
        )

        label_style = ParagraphStyle(
            "Label",
            parent=styles["Normal"],
            fontName="Courier-Bold",
            fontSize=10,
            alignment=0,  # Left alignment
            leading=12,
            leftIndent=0,
            rightIndent=0,
        )

        value_style = ParagraphStyle(
            "Value",
            parent=styles["Normal"],
            fontName="Courier",
            fontSize=10,
            alignment=0,  # Left alignment
            leading=12,
            leftIndent=4 * mm,  # Slight indent for values
            rightIndent=0,
            spaceBefore=1 * mm,
        )

        return {
            "title": title_style,
            "label": label_style,
            "value": value_style,
        }

    def _add_task_header(
        self,
        elements: List[Flowable],
        task: Task,
        styles: Dict[str, ParagraphStyle],
        doc_width: float,
    ) -> None:
        """Add task header elements."""
        elements.append(Paragraph(task.title, styles["title"]))
        elements.append(DottedLine(doc_width))
        elements.append(Spacer(1, 2 * mm))

    def _add_task_details(
        self, elements: List[Flowable], task: Task, styles: Dict[str, ParagraphStyle]
    ) -> None:
        """Add task details like description and reward."""
        if task.description:
            elements.append(Paragraph("Description:", styles["label"]))
            elements.append(Paragraph(task.description, styles["value"]))
            elements.append(Spacer(1, 2 * mm))

        if task.due_date:
            elements.append(Paragraph("Due date:", styles["label"]))
            elements.append(
                Paragraph(task.due_date.strftime("%Y-%m-%d %H:%M"), styles["value"])
            )
            elements.append(Spacer(1, 2 * mm))

        if task.reward:
            elements.append(Paragraph("Reward:", styles["label"]))
            elements.append(Paragraph(task.reward, styles["value"]))
            elements.append(Spacer(1, 2 * mm))

    def _add_task_dates(
        self, elements: List[Flowable], task: Task, styles: Dict[str, ParagraphStyle]
    ) -> None:
        """Add task dates (created, started, completed)."""
        elements.append(Spacer(1, 4 * mm))

        date_fields = [
            ("created_at", "Created:"),
            ("started_at", "Started:"),
            ("completed_at", "Completed:"),
        ]

        for field, label in date_fields:
            date_value = getattr(task, field)
            if date_value is not None:
                formatted_date = self.format_datetime(date_value)
                if formatted_date is not None:
                    elements.append(Paragraph(label, styles["label"]))
                    elements.append(
                        Paragraph(
                            formatted_date.strftime("%Y-%m-%d %H:%M"), styles["value"]
                        )
                    )
                    elements.append(Spacer(1, 2 * mm))

    def print_task(self, task: Task) -> Path:
        """Print a task to a receipt-like PDF file."""
        try:
            self.logger.info("Starting PDF generation for task %d", task.id)
            filename = f"task_{task.id}_{task.title.lower().replace(' ', '_')}.pdf"

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                self.logger.debug("Creating temporary file: %s", tmp_file.name)

                # Create custom page size (80mm wide receipt)
                page_width = 80 * mm
                page_height = A4[1]  # Use A4 height
                custom_pagesize = (page_width, page_height)

                # Create the PDF document
                doc = SimpleDocTemplate(
                    tmp_file.name,
                    pagesize=custom_pagesize,
                    rightMargin=6 * mm,  # Slightly larger right margin
                    leftMargin=4 * mm,  # Slightly smaller left margin
                    topMargin=5 * mm,
                    bottomMargin=5 * mm,
                )

                # Get document styles
                styles = self._create_document_styles()

                # Container for the 'Flowable' objects
                elements: List[Flowable] = []

                # Build the document content
                self._add_task_header(elements, task, styles, doc.width)
                self._add_task_details(elements, task, styles)
                self._add_task_dates(elements, task, styles)

                # Add QR code (centered)
                elements.append(Spacer(1, 4 * mm))
                elements.append(DottedLine(doc.width))
                elements.append(Spacer(1, 8 * mm))
                elements.append(
                    QRCodeFlowable(
                        f"{self.config.get('frontend_url', 'http://localhost:4200')}"
                        f"/tasks/{task.id}/details"
                    )
                )
                elements.append(Spacer(1, 8 * mm))
                elements.append(DottedLine(doc.width))

                # Build PDF
                self.logger.debug("Building final PDF document")
                doc.build(elements)
                self.logger.info("Successfully generated PDF at: %s", tmp_file.name)
                shutil.copy2(tmp_file.name, self.output_dir.joinpath(filename))
                self.logger.info(
                    "Successfully copied PDF to: %s", self.output_dir.joinpath(filename)
                )

                return self.output_dir.joinpath(filename)

        except Exception as e:
            error_msg = f"Failed to generate PDF for task {task.id}"
            self.logger.error("%s: %s", error_msg, str(e), exc_info=True)
            raise PrinterError(f"{error_msg}: {str(e)}")

    def print(self, task: Task) -> Response:
        """Print the task and return a FastAPI Response object."""
        filepath = self.print_task(task)

        return FileResponse(
            path=filepath.absolute().as_posix(),
            filename=filepath.name,
            media_type="application/pdf",
        )
