"""
Unit tests for the window sticker processor module.

This module contains tests for the WindowStickerProcessor class.
"""

import pytest
import asyncio
import os
from unittest.mock import MagicMock, patch, mock_open

from core.interfaces import BrowserInterface
from modules.inventory.window_sticker import WindowStickerProcessor


@pytest.fixture
def browser_mock():
    """Create a mock browser interface."""
    browser = MagicMock(spec=BrowserInterface)
    
    # Set up async methods to return awaitable values
    browser.navigate_to.return_value = asyncio.Future()
    browser.navigate_to.return_value.set_result(None)
    
    browser.wait_for_presence.return_value = asyncio.Future()
    browser.wait_for_presence.return_value.set_result(MagicMock())
    
    browser.find_elements.return_value = asyncio.Future()
    browser.find_elements.return_value.set_result([])
    
    browser.get_attribute.return_value = asyncio.Future()
    browser.get_attribute.return_value.set_result("")
    
    browser.take_screenshot.return_value = asyncio.Future()
    browser.take_screenshot.return_value.set_result("")
    
    return browser


@pytest.fixture
def config():
    """Create a mock configuration."""
    return {
        "browser": {
            "headless": True,
            "timeout": 30
        },
        "feature_mapping": {
            "confidence_threshold": 0.8
        }
    }


@pytest.fixture
def window_sticker_processor(browser_mock, config):
    """Create a window sticker processor with mocked dependencies."""
    return WindowStickerProcessor(browser_mock, config)


@pytest.mark.asyncio
async def test_extract_features_from_url(window_sticker_processor):
    """Test extracting features from a URL."""
    # Mock _download_window_sticker
    window_sticker_processor._download_window_sticker = MagicMock(return_value=asyncio.Future())
    window_sticker_processor._download_window_sticker.return_value.set_result("/tmp/test.pdf")
    
    # Mock _extract_text_from_window_sticker
    window_sticker_processor._extract_text_from_window_sticker = MagicMock(return_value=asyncio.Future())
    window_sticker_processor._extract_text_from_window_sticker.return_value.set_result(
        "Standard Equipment:\n- Leather Seats\n- Navigation System\n- Bluetooth\n"
    )
    
    # Call extract_features method
    features = await window_sticker_processor.extract_features("https://example.com/sticker.pdf")
    
    # Verify result
    assert len(features) == 3
    assert "Leather Seats" in features
    assert "Navigation System" in features
    assert "Bluetooth" in features
    
    # Verify method calls
    window_sticker_processor._download_window_sticker.assert_called_once_with("https://example.com/sticker.pdf")
    window_sticker_processor._extract_text_from_window_sticker.assert_called_once_with("/tmp/test.pdf")


@pytest.mark.asyncio
async def test_extract_features_from_local_path(window_sticker_processor):
    """Test extracting features from a local path."""
    # Mock _extract_text_from_window_sticker
    window_sticker_processor._extract_text_from_window_sticker = MagicMock(return_value=asyncio.Future())
    window_sticker_processor._extract_text_from_window_sticker.return_value.set_result(
        "Standard Equipment:\n- Leather Seats\n- Navigation System\n- Bluetooth\n"
    )
    
    # Call extract_features method
    features = await window_sticker_processor.extract_features("/tmp/local_sticker.pdf")
    
    # Verify result
    assert len(features) == 3
    assert "Leather Seats" in features
    assert "Navigation System" in features
    assert "Bluetooth" in features
    
    # Verify method calls
    window_sticker_processor._extract_text_from_window_sticker.assert_called_once_with("/tmp/local_sticker.pdf")


@pytest.mark.asyncio
async def test_extract_features_download_failure(window_sticker_processor):
    """Test extracting features when download fails."""
    # Mock _download_window_sticker to return None (failure)
    window_sticker_processor._download_window_sticker = MagicMock(return_value=asyncio.Future())
    window_sticker_processor._download_window_sticker.return_value.set_result(None)
    
    # Call extract_features method
    features = await window_sticker_processor.extract_features("https://example.com/sticker.pdf")
    
    # Verify result
    assert features == []
    
    # Verify method calls
    window_sticker_processor._download_window_sticker.assert_called_once_with("https://example.com/sticker.pdf")


@pytest.mark.asyncio
async def test_extract_features_text_extraction_failure(window_sticker_processor):
    """Test extracting features when text extraction fails."""
    # Mock _download_window_sticker
    window_sticker_processor._download_window_sticker = MagicMock(return_value=asyncio.Future())
    window_sticker_processor._download_window_sticker.return_value.set_result("/tmp/test.pdf")
    
    # Mock _extract_text_from_window_sticker to return empty string (failure)
    window_sticker_processor._extract_text_from_window_sticker = MagicMock(return_value=asyncio.Future())
    window_sticker_processor._extract_text_from_window_sticker.return_value.set_result("")
    
    # Call extract_features method
    features = await window_sticker_processor.extract_features("https://example.com/sticker.pdf")
    
    # Verify result
    assert features == []
    
    # Verify method calls
    window_sticker_processor._download_window_sticker.assert_called_once_with("https://example.com/sticker.pdf")
    window_sticker_processor._extract_text_from_window_sticker.assert_called_once_with("/tmp/test.pdf")


@pytest.mark.asyncio
async def test_download_window_sticker_success(window_sticker_processor):
    """Test successful download of window sticker."""
    # Mock aiohttp.ClientSession
    session_mock = MagicMock()
    response_mock = MagicMock()
    response_mock.status = 200
    response_mock.headers = {"Content-Type": "application/pdf"}
    response_mock.read.return_value = asyncio.Future()
    response_mock.read.return_value.set_result(b"PDF content")
    
    session_mock.__aenter__ = MagicMock(return_value=asyncio.Future())
    session_mock.__aenter__.return_value.set_result(session_mock)
    session_mock.__aexit__ = MagicMock(return_value=asyncio.Future())
    session_mock.__aexit__.return_value.set_result(None)
    
    session_mock.get.return_value = MagicMock()
    session_mock.get.return_value.__aenter__ = MagicMock(return_value=asyncio.Future())
    session_mock.get.return_value.__aenter__.return_value.set_result(response_mock)
    session_mock.get.return_value.__aexit__ = MagicMock(return_value=asyncio.Future())
    session_mock.get.return_value.__aexit__.return_value.set_result(None)
    
    # Mock open
    with patch("aiohttp.ClientSession", return_value=session_mock), \
         patch("builtins.open", mock_open()) as mock_file, \
         patch("os.path.exists", return_value=False):
        
        # Call _download_window_sticker method
        result = await window_sticker_processor._download_window_sticker("https://example.com/sticker.pdf")
        
        # Verify result
        assert result is not None
        assert "sticker.pdf" in result
        
        # Verify file was written
        mock_file.assert_called_once()
        mock_file().write.assert_called_once_with(b"PDF content")


@pytest.mark.asyncio
async def test_download_window_sticker_http_error(window_sticker_processor):
    """Test window sticker download with HTTP error."""
    # Mock aiohttp.ClientSession
    session_mock = MagicMock()
    response_mock = MagicMock()
    response_mock.status = 404  # Not Found
    
    session_mock.__aenter__ = MagicMock(return_value=asyncio.Future())
    session_mock.__aenter__.return_value.set_result(session_mock)
    session_mock.__aexit__ = MagicMock(return_value=asyncio.Future())
    session_mock.__aexit__.return_value.set_result(None)
    
    session_mock.get.return_value = MagicMock()
    session_mock.get.return_value.__aenter__ = MagicMock(return_value=asyncio.Future())
    session_mock.get.return_value.__aenter__.return_value.set_result(response_mock)
    session_mock.get.return_value.__aexit__ = MagicMock(return_value=asyncio.Future())
    session_mock.get.return_value.__aexit__.return_value.set_result(None)
    
    # Mock open
    with patch("aiohttp.ClientSession", return_value=session_mock):
        # Call _download_window_sticker method
        result = await window_sticker_processor._download_window_sticker("https://example.com/sticker.pdf")
        
        # Verify result
        assert result is None


@pytest.mark.asyncio
async def test_extract_text_from_pdf(window_sticker_processor):
    """Test extracting text from a PDF file."""
    # Mock _extract_text_from_pdf_sync
    with patch.object(
        window_sticker_processor, 
        "_extract_text_from_pdf_sync", 
        return_value="Sample PDF text with features"
    ):
        # Call _extract_text_from_pdf method
        result = await window_sticker_processor._extract_text_from_pdf("/tmp/test.pdf")
        
        # Verify result
        assert result == "Sample PDF text with features"
        
        # Verify method calls
        window_sticker_processor._extract_text_from_pdf_sync.assert_called_once_with("/tmp/test.pdf")


@pytest.mark.asyncio
async def test_extract_text_from_pdf_fallback_to_ocr(window_sticker_processor):
    """Test extracting text from a PDF file with fallback to OCR."""
    # Mock _extract_text_from_pdf_sync to return minimal text
    window_sticker_processor._extract_text_from_pdf_sync = MagicMock(return_value="")
    
    # Mock _extract_text_from_pdf_with_ocr
    window_sticker_processor._extract_text_from_pdf_with_ocr = MagicMock(return_value=asyncio.Future())
    window_sticker_processor._extract_text_from_pdf_with_ocr.return_value.set_result("OCR extracted text")
    
    # Call _extract_text_from_pdf method
    result = await window_sticker_processor._extract_text_from_pdf("/tmp/test.pdf")
    
    # Verify result
    assert result == "OCR extracted text"
    
    # Verify method calls
    window_sticker_processor._extract_text_from_pdf_sync.assert_called_once_with("/tmp/test.pdf")
    window_sticker_processor._extract_text_from_pdf_with_ocr.assert_called_once_with("/tmp/test.pdf")


def test_extract_features_from_text(window_sticker_processor):
    """Test extracting features from text."""
    # Sample window sticker text
    text = """
    WINDOW STICKER
    
    2023 Toyota Camry XSE
    
    STANDARD EQUIPMENT:
    - Leather Seats
    - Navigation System
    - Bluetooth
    - Backup Camera
    
    OPTIONAL EQUIPMENT:
    - Sunroof
    - Premium Sound System
    
    SAFETY RATINGS:
    5-Star Overall Rating
    
    FUEL ECONOMY:
    28 City / 39 Highway
    
    MSRP: $35,000
    """
    
    # Call _extract_features_from_text method
    features = window_sticker_processor._extract_features_from_text(text)
    
    # Verify result
    assert len(features) == 6
    assert "Leather Seats" in features
    assert "Navigation System" in features
    assert "Bluetooth" in features
    assert "Backup Camera" in features
    assert "Sunroof" in features
    assert "Premium Sound System" in features
    
    # Verify that price information is not included
    assert "MSRP: $35,000" not in features
    assert "$35,000" not in features
    
    # Verify that fuel economy is not included
    assert "28 City / 39 Highway" not in features


def test_extract_features_by_pattern(window_sticker_processor):
    """Test extracting features by pattern when no feature sections are found."""
    # Sample text without explicit feature sections
    text = """
    2023 Toyota Camry XSE
    
    VIN: 1234567890ABCDEFG
    
    Leather Seats: Yes
    Navigation System: Yes
    Bluetooth: Yes
    Backup Camera: Yes
    Sunroof: No
    Premium Sound System: Included
    
    MSRP: $35,000
    """
    
    # Call _extract_features_by_pattern method
    features = window_sticker_processor._extract_features_by_pattern(text.split("\n"))
    
    # Verify result
    assert len(features) >= 6
    assert any("Leather Seats" in feature for feature in features)
    assert any("Navigation System" in feature for feature in features)
    assert any("Bluetooth" in feature for feature in features)
    assert any("Backup Camera" in feature for feature in features)
    assert any("Sunroof" in feature for feature in features)
    assert any("Premium Sound System" in feature for feature in features)


def test_clean_feature_text(window_sticker_processor):
    """Test cleaning feature text."""
    # Test cases
    test_cases = [
        ("• Leather Seats", "Leather Seats"),
        ("- Navigation System", "Navigation System"),
        ("* Bluetooth", "Bluetooth"),
        ("  Backup Camera  ", "Backup Camera"),
        ("Sunroof.", "Sunroof"),
        ("Premium Sound System,", "Premium Sound System"),
        ("• - * Heated Seats", "Heated Seats"),
        ("   ", "")
    ]
    
    # Test each case
    for input_text, expected_output in test_cases:
        result = window_sticker_processor._clean_feature_text(input_text)
        assert result == expected_output
