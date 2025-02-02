from typing import Any, Dict
import tempfile

from fastapi import Response
from fastapi.responses import FileResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

from .base_printer import BasePrinter


class PDFPrinter(BasePrinter):
    """PDF printer implementation that creates and returns a PDF file."""

    async def print(self, data: Dict[str, Any]) -> Response:
        """
        Create a PDF from the input data and return it as a downloadable response.
        
        Args:
            data: Dictionary containing the data to be printed
                 Expected format:
                 {
                     "title": str,
                     "content": List[Dict] # List of dictionaries with data to print
                 }
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
            title = Paragraph(data.get("title", "Report"), styles["Heading1"])
            elements.append(title)

            # Convert content to table format
            if data.get("content"):
                # Get headers from first item
                headers = list(data["content"][0].keys())
                
                # Create table data
                table_data = [headers]  # First row is headers
                for item in data["content"]:
                    row = [str(item.get(header, "")) for header in headers]
                    table_data.append(row)

                # Create table
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 12),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(table)

            # Build PDF
            doc.build(elements)

            # Return the PDF file as a response
            return FileResponse(
                path=tmp_file.name,
                filename=f"{data.get('title', 'report').lower().replace(' ', '_')}.pdf",
                media_type="application/pdf"
            )
