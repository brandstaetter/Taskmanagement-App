import logging
from unittest.mock import MagicMock

import pytest
from escpos.printer import Usb

from taskmanagement_app.core.printing.usb_printer import USBPrinter

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestTextWrapping:
    def test_simple(self):
        """A simple test to check if pytest is working."""
        logger.debug("Running simple test")
        assert True

    def test_empty_text(self, mock_usb_printer):
        """Test that empty text returns a list with an empty string."""
        logger.debug("Testing empty text")
        result = mock_usb_printer.wrap_text("")
        logger.debug(f"Result: {result}")
        assert result == [""]
        assert mock_usb_printer.wrap_text(" ") == [""]

    def test_single_line_text(self, mock_usb_printer):
        """Test text that fits in a single line."""
        text = "Hello world"
        logger.debug(f"Testing single line text: {text}")
        result = mock_usb_printer.wrap_text(text, max_length=32)
        logger.debug(f"Result: {result}")
        assert len(result) == 1
        assert result[0] == text
        assert len(result[0]) <= 32

    def test_multi_line_text(self, mock_usb_printer):
        """Test text that needs to be wrapped into multiple lines."""
        text = "This is a longer text that needs to be wrapped into multiple lines"
        logger.debug(f"Testing multi line text: {text}")
        result = mock_usb_printer.wrap_text(text, max_length=20)
        logger.debug(f"Result: {result}")
        assert len(result) > 1
        assert all(len(line) <= 20 for line in result)

    def test_label_length_reduction(self, mock_usb_printer):
        """Test that label_length properly reduces first line length."""
        text = "This is a text with a label that should affect first line"
        label_length = 10
        logger.debug(
            f"Testing label length reduction: text={text}, label_length={label_length}"
        )
        result = mock_usb_printer.wrap_text(
            text, label_length=label_length, max_length=32
        )
        logger.debug(f"Result: {result}")
        assert len(result[0]) <= 32 - label_length

    def test_wide_mode(self, mock_usb_printer):
        """Test that wide mode properly halves the max length."""
        text = "This text should be wrapped to half width when wide mode is enabled"
        max_length = 32
        logger.debug(f"Testing wide mode: text={text}, max_length={max_length}")
        result = mock_usb_printer.wrap_text(text, max_length=max_length, wide=True)
        logger.debug(f"Result: {result}")
        assert all(len(line) <= max_length / 2 for line in result)

    def test_long_word(self, mock_usb_printer):
        """Test handling of words longer than max_length."""
        text = "This contains a verylongwordthatwontfit in the line"
        logger.debug(f"Testing long word: {text}")
        result = mock_usb_printer.wrap_text(text, max_length=20)
        logger.debug(f"Result: {result}")
        assert all(len(line) <= 20 for line in result)

    def test_multiple_spaces(self, mock_usb_printer):
        """Test that multiple spaces are handled correctly."""
        text = "This   has   multiple   spaces   between   words"
        logger.debug(f"Testing multiple spaces: {text}")
        result = mock_usb_printer.wrap_text(text, max_length=20)
        logger.debug(f"Result: {result}")
        assert all(len(line) <= 20 for line in result)
        assert all("  " not in line for line in result)  # No double spaces

    @pytest.mark.parametrize(
        "max_length,label_length,wide",
        [
            (32, 0, False),  # Normal case
            (32, 10, False),  # With label
            (32, 0, True),  # Wide mode
            (32, 10, True),  # Wide mode with label (label only affects first line)
        ],
    )
    def test_line_length_constraints(
        self, mock_usb_printer, max_length, label_length, wide
    ):
        """Test various combinations of constraints on line length."""
        text = "This is a sample text that will be wrapped according to various constraints"
        logger.debug(
            f"Testing line length constraints: text={text}, max_length={max_length}, label_length={label_length}, wide={wide}"
        )
        result = mock_usb_printer.wrap_text(
            text, label_length=label_length, max_length=max_length, wide=wide
        )
        logger.debug(f"Result: {result}")

        # Check first line considering label_length
        expected_first_line_max = (
            ((max_length - label_length) / 2) if wide else max_length - label_length
        )
        actual_first_line_length = len(result[0])
        logger.debug(
            f"First line check: expected_max={expected_first_line_max}, actual_length={actual_first_line_length}"
        )
        assert actual_first_line_length <= expected_first_line_max

        # Check remaining lines
        if len(result) > 1:
            expected_other_lines_max = (
                (max_length / 2) if wide else (max_length - label_length)
            )
            other_line_lengths = [len(line) for line in result[1:]]
            logger.debug(
                f"Other lines check: expected_max={expected_other_lines_max}, actual_lengths={other_line_lengths}"
            )
            assert all(len(line) <= expected_other_lines_max for line in result[1:])


class TestAsciiMode:
    """Tests for per-printer ASCII mode character replacement."""

    @pytest.fixture
    def ascii_printer(self) -> USBPrinter:
        config = {
            "vendor_id": "0x0416",
            "product_id": "0x5011",
            "frontend_url": "http://localhost:4200",
            "ascii_mode": True,
        }
        printer = USBPrinter(config)
        printer.device = MagicMock(spec=Usb)
        return printer

    @pytest.fixture
    def non_ascii_printer(self) -> USBPrinter:
        config = {
            "vendor_id": "0x0416",
            "product_id": "0x5011",
            "frontend_url": "http://localhost:4200",
            "ascii_mode": False,
        }
        printer = USBPrinter(config)
        printer.device = MagicMock(spec=Usb)
        return printer

    def test_german_lowercase_replacements(self, ascii_printer: USBPrinter) -> None:
        assert ascii_printer._ascii_replace("ä") == "ae"
        assert ascii_printer._ascii_replace("ö") == "oe"
        assert ascii_printer._ascii_replace("ü") == "ue"
        assert ascii_printer._ascii_replace("ß") == "ss"

    def test_german_uppercase_replacements(self, ascii_printer: USBPrinter) -> None:
        assert ascii_printer._ascii_replace("Ä") == "Ae"
        assert ascii_printer._ascii_replace("Ö") == "Oe"
        assert ascii_printer._ascii_replace("Ü") == "Ue"

    def test_unknown_non_ascii_replaced_with_question_mark(
        self, ascii_printer: USBPrinter
    ) -> None:
        assert ascii_printer._ascii_replace("é") == "?"
        assert ascii_printer._ascii_replace("日本語") == "???"

    def test_mixed_text(self, ascii_printer: USBPrinter) -> None:
        result = ascii_printer._ascii_replace("Müller straße café")
        assert result == "Mueller strasse caf?"

    def test_ascii_mode_disabled_preserves_text(
        self, non_ascii_printer: USBPrinter
    ) -> None:
        text = "Müller straße"
        assert non_ascii_printer._ascii_replace(text) == text

    def test_pure_ascii_unchanged(self, ascii_printer: USBPrinter) -> None:
        text = "Hello world 123 !@#"
        assert ascii_printer._ascii_replace(text) == text

    def test_wrapping_recalculated_after_replacement(
        self, ascii_printer: USBPrinter
    ) -> None:
        """Replacement expands text (ü→ue), so wrapping must use the longer string."""
        # "für" (3 chars) becomes "fuer" (4 chars) — verify wrap uses replaced length
        text = "für"
        replaced = ascii_printer._ascii_replace(text)
        assert replaced == "fuer"
        lines = ascii_printer.wrap_text(replaced, max_length=4)
        assert lines == ["fuer"]

    def test_heading_applies_ascii_replacement(self, ascii_printer: USBPrinter) -> None:
        """printHeading should apply ASCII replacement before wrapping."""
        device = ascii_printer.device
        assert device is not None
        ascii_printer.printHeading(device, "Übung")
        # Verify the printer received the replaced text
        text_calls = device.text.call_args_list
        printed_text = "".join(
            call.args[0] for call in text_calls if call.args[0].strip()
        )
        assert "Ue" in printed_text
        assert "Ü" not in printed_text

    def test_print_value_applies_ascii_replacement(
        self, ascii_printer: USBPrinter
    ) -> None:
        """printValue should apply ASCII replacement before wrapping."""
        device = ascii_printer.device
        assert device is not None
        ascii_printer.printValue(device, "Größe", label_length=5)
        text_calls = device.text.call_args_list
        printed_text = "".join(
            call.args[0] for call in text_calls if call.args[0].strip()
        )
        assert "Groesse" in printed_text
        assert "ö" not in printed_text

    def test_default_ascii_mode_is_false(self) -> None:
        """Without ascii_mode in config, it defaults to False."""
        config = {
            "vendor_id": "0x0416",
            "product_id": "0x5011",
            "frontend_url": "http://localhost:4200",
        }
        printer = USBPrinter(config)
        assert printer.ascii_mode is False
