import pytest
from unittest.mock import MagicMock

from escpos.printer import Usb
from taskmanagement_app.core.printing.usb_printer import USBPrinter


@pytest.fixture
def mock_usb_printer():
    """Test USB printer functionality."""
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
    return printer

@pytest.fixture(autouse=True)
async def cleanup_printer():
    yield
    # Clean up any remaining printer connections
    import asyncio
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()