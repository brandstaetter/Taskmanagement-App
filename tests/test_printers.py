"""Tests for printer functionality."""

import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from taskmanagement_app.core.exceptions import PrinterError
from taskmanagement_app.core.printing.base_printer import BasePrinter
from taskmanagement_app.core.printing.pdf_printer import PDFPrinter
from taskmanagement_app.core.printing.printer_factory import PrinterFactory
from taskmanagement_app.crud.task import create_task
from taskmanagement_app.db.models.task import TaskModel
from taskmanagement_app.schemas.task import TaskCreate


@pytest.fixture
def temp_output_dir() -> Generator[str, None, None]:
    """Create a temporary directory for PDF output."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create output directory
        output_dir = Path(temp_dir) / "output"
        output_dir.mkdir(exist_ok=True)
        yield str(output_dir)


def create_test_task(db: Session) -> TaskModel:
    """Create a test task for printing."""
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    )
    task = create_task(db=db, task=task_in)
    return task


def test_pdf_printer(db_session: Session, temp_output_dir: str) -> None:
    """Test PDF printer functionality."""

    # Create printer with test config
    config = {"output_dir": temp_output_dir}
    printer = PDFPrinter(config)

    # Create and print a task
    task = create_test_task(db_session)
    response = printer.print(task)

    # Verify response
    assert isinstance(response, FileResponse)
    assert response.status_code == 200
    assert response.media_type == "application/pdf"

    # Wait a moment for file operations to complete
    time.sleep(0.1)

    # Verify PDF was created
    pdf_files = list(Path(temp_output_dir).glob("*.pdf"))
    assert len(pdf_files) >= 1  # May be more due to temp files
    assert any(f.stat().st_size > 0 for f in pdf_files)


@pytest.mark.asyncio
async def test_pdf_printer_invalid_config() -> None:
    """Test PDF printer with invalid configuration."""
    # Test with missing output directory
    with pytest.raises(PrinterError) as exc_info:
        PDFPrinter({})
    assert "output_dir" in str(exc_info.value)


def test_usb_printer(db_session: Session) -> None:
    """Test USB printer functionality."""
    try:
        from escpos.printer import Usb
        from taskmanagement_app.core.printing.usb_printer import USBPrinter
    except Exception as e:
        pytest.skip(f"USB printer backend unavailable: {e}")

    # Mock USB device
    mock_device = MagicMock(spec=Usb)
    mock_device.text = MagicMock()
    mock_device.cut = MagicMock()
    mock_device.qr = MagicMock()
    mock_device.set = MagicMock()

    # Create printer with test config
    config = {
        "vendor_id": "0x0416",
        "product_id": "0x5011",
        "frontend_url": "http://localhost:4200",
    }
    printer = USBPrinter(config)

    # Replace device with mock
    printer.device = mock_device

    # Create and print a task
    task = create_test_task(db_session)
    response = printer.print(task)

    # Verify response
    assert isinstance(response, JSONResponse)
    assert response.status_code == 200

    # Verify printer methods were called
    mock_device.text.assert_called()
    mock_device.cut.assert_called_once()
    mock_device.qr.assert_called_once()
    mock_device.set.assert_called()


@pytest.mark.asyncio
async def test_usb_printer_invalid_config() -> None:
    """Test USB printer with invalid configuration."""
    try:
        from taskmanagement_app.core.printing.usb_printer import USBPrinter
    except Exception as e:
        pytest.skip(f"USB printer backend unavailable: {e}")

    # Test with missing vendor_id
    with pytest.raises(PrinterError):
        USBPrinter({"product_id": "0x5011"})

    # Test with missing product_id
    with pytest.raises(PrinterError):
        USBPrinter({"vendor_id": "0x0416"})


@pytest.mark.asyncio
async def test_usb_printer_connection_error(db_session: Session) -> None:
    """Test USB printer handling of connection errors."""
    try:
        from taskmanagement_app.core.printing.usb_printer import USBPrinter
    except Exception as e:
        pytest.skip(f"USB printer backend unavailable: {e}")

    config = {
        "vendor_id": "0x0416",
        "product_id": "0x5011",
    }
    printer = USBPrinter(config)

    # Simulate connection error
    with patch("usb.core.find", return_value=None):
        with pytest.raises(PrinterError) as exc_info:
            printer.connect()
        assert "USB device not found" in str(exc_info.value)


def test_printer_factory() -> None:
    """Test printer factory functionality."""
    # Test PDF printer creation
    pdf_config = {"type": "pdf", "output_dir": tempfile.gettempdir()}
    pdf_printer = PrinterFactory.create_printer(pdf_config)
    assert isinstance(pdf_printer, PDFPrinter)

    # Test USB printer creation
    try:
        from taskmanagement_app.core.printing.usb_printer import USBPrinter
    except Exception as e:
        pytest.skip(f"USB printer backend unavailable: {e}")
    else:
        usb_config = {
            "type": "usb",
            "vendor_id": "0x0416",
            "product_id": "0x5011",
        }
        with patch("usb.core.find", return_value=MagicMock()):
            usb_printer = PrinterFactory.create_printer(usb_config)
            assert isinstance(usb_printer, USBPrinter)

    # Test invalid printer type
    invalid_config = {"type": "invalid"}
    with pytest.raises(PrinterError) as exc_info:
        PrinterFactory.create_printer(invalid_config)
    assert "Unsupported printer type" in str(exc_info.value)


class MockPrinter(BasePrinter):
    """Mock printer for testing."""

    def __init__(self, config: dict = {}) -> None:
        super().__init__(config)
        self._print = AsyncMock()

    @property
    def print(self):
        """Get print method."""
        return self._print

    @print.setter
    def print(self, value):
        """Set print method."""
        self._print = value


@pytest.mark.asyncio
async def test_base_printer() -> None:
    """Test base printer functionality."""

    # Test mock printer implementation
    printer = MockPrinter({"test": "config"})
    assert printer.config == {"test": "config"}

    # Test print method
    printer.print = AsyncMock(return_value=JSONResponse(content={"message": "success"}))
    response = await printer.print(None)
    assert isinstance(response, JSONResponse)
    assert response.status_code == 200
    printer.print.assert_called_once_with(None)
