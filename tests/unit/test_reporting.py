"""
Unit tests for the reporting module.

This module contains tests for the ReportingModule class.
"""

import pytest
import asyncio
import os
from datetime import datetime
from unittest.mock import MagicMock, patch, mock_open

from modules.reporting.reporting import ReportingModule


@pytest.fixture
def config():
    """Create a mock configuration."""
    return {
        "reporting": {
            "email_recipients": ["test@example.com"],
            "report_format": "html",
            "include_screenshots": True
        }
    }


@pytest.fixture
def reporting_module(config):
    """Create a reporting module with mocked dependencies."""
    with patch.dict('os.environ', {
        'SMTP_HOST': 'smtp.example.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'test_user',
        'SMTP_PASSWORD': 'test_password',
        'EMAIL_FROM': 'noreply@example.com'
    }), patch("utils.common.ensure_dir", return_value="reports"):
        return ReportingModule(config)


@pytest.mark.asyncio
async def test_generate_report_success(reporting_module):
    """Test successful report generation."""
    # Test data
    dealer_config = {
        "name": "Test Dealership",
        "dealer_id": "TEST123"
    }
    
    stats = {
        "start_time": datetime.now(),
        "end_time": datetime.now(),
        "duration_seconds": 120,
        "vehicles_processed": 10,
        "successful_updates": 8,
        "results": [
            {
                "success": True,
                "stock_number": "S123",
                "vin": "1234567890ABCDEFG",
                "year": "2023",
                "make": "Toyota",
                "model": "Camry",
                "updated_checkboxes": 5,
                "total_checkboxes": 20
            },
            {
                "success": False,
                "stock_number": "S124",
                "vin": "ABCDEFG1234567890",
                "year": "2023",
                "make": "Honda",
                "model": "Accord",
                "error": "Failed to update checkboxes",
                "updated_checkboxes": 0,
                "total_checkboxes": 20
            }
        ]
    }
    
    # Mock file operations
    with patch("builtins.open", mock_open()) as mock_file:
        # Call generate_report method
        report_path = await reporting_module.generate_report(dealer_config, stats)
        
        # Verify result
        assert report_path is not None
        assert "Test_Dealership_" in report_path
        assert report_path.endswith(".html")
        
        # Verify file was written
        mock_file.assert_called_once()
        mock_file().write.assert_called_once()
        
        # Verify HTML content
        html_content = mock_file().write.call_args[0][0]
        assert "Test Dealership" in html_content
        assert "10" in html_content  # vehicles_processed
        assert "8" in html_content   # successful_updates
        assert "S123" in html_content
        assert "S124" in html_content
        assert "Failed to update checkboxes" in html_content


@pytest.mark.asyncio
async def test_generate_report_failure(reporting_module):
    """Test report generation failure."""
    # Test data
    dealer_config = {
        "name": "Test Dealership",
        "dealer_id": "TEST123"
    }
    
    stats = {
        "start_time": datetime.now(),
        "end_time": datetime.now(),
        "duration_seconds": 120,
        "vehicles_processed": 0,
        "successful_updates": 0,
        "results": []
    }
    
    # Mock file operations to raise an exception
    with patch("builtins.open", side_effect=Exception("File write error")):
        # Call generate_report method
        report_path = await reporting_module.generate_report(dealer_config, stats)
        
        # Verify result
        assert report_path == ""


def test_get_success_class(reporting_module):
    """Test getting CSS class based on success rate."""
    # Test cases
    test_cases = [
        (100, "success"),
        (95, "success"),
        (90, "success"),
        (80, "warning"),
        (75, "warning"),
        (70, "warning"),
        (60, "danger"),
        (50, "danger"),
        (0, "danger")
    ]
    
    # Test each case
    for rate, expected_class in test_cases:
        result = reporting_module._get_success_class(rate)
        assert result == expected_class


@pytest.mark.asyncio
async def test_send_email_notification_success(reporting_module):
    """Test successful email notification."""
    # Test data
    dealer_config = {
        "name": "Test Dealership",
        "dealer_id": "TEST123",
        "send_email": True,
        "email_recipients": ["dealer@example.com"]
    }
    
    stats = {
        "vehicles_processed": 10,
        "successful_updates": 8
    }
    
    report_path = "reports/Test_Dealership_20250428_123456.html"
    
    # Mock file operations
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=b"HTML content")), \
         patch("aiosmtplib.send") as mock_send:
        
        mock_send.return_value = asyncio.Future()
        mock_send.return_value.set_result(None)
        
        # Call send_email_notification method
        result = await reporting_module.send_email_notification(dealer_config, stats, report_path)
        
        # Verify result
        assert result is True
        
        # Verify aiosmtplib.send was called
        mock_send.assert_called_once()
        
        # Verify email parameters
        call_args = mock_send.call_args[1]
        assert call_args["hostname"] == "smtp.example.com"
        assert call_args["port"] == 587
        assert call_args["username"] == "test_user"
        assert call_args["password"] == "test_password"
        assert call_args["use_tls"] is True


@pytest.mark.asyncio
async def test_send_email_notification_disabled(reporting_module):
    """Test email notification when disabled."""
    # Test data
    dealer_config = {
        "name": "Test Dealership",
        "dealer_id": "TEST123",
        "send_email": False
    }
    
    stats = {
        "vehicles_processed": 10,
        "successful_updates": 8
    }
    
    report_path = "reports/Test_Dealership_20250428_123456.html"
    
    # Call send_email_notification method
    result = await reporting_module.send_email_notification(dealer_config, stats, report_path)
    
    # Verify result
    assert result is False


@pytest.mark.asyncio
async def test_send_email_notification_no_recipients(reporting_module):
    """Test email notification with no recipients."""
    # Test data
    dealer_config = {
        "name": "Test Dealership",
        "dealer_id": "TEST123",
        "send_email": True,
        "email_recipients": []
    }
    
    # Override config to have no recipients
    reporting_module.config["reporting"]["email_recipients"] = []
    
    stats = {
        "vehicles_processed": 10,
        "successful_updates": 8
    }
    
    report_path = "reports/Test_Dealership_20250428_123456.html"
    
    # Call send_email_notification method
    result = await reporting_module.send_email_notification(dealer_config, stats, report_path)
    
    # Verify result
    assert result is False


@pytest.mark.asyncio
async def test_process_results_success(reporting_module):
    """Test successful processing of results."""
    # Test data
    dealer_config = {
        "name": "Test Dealership",
        "dealer_id": "TEST123"
    }
    
    results = [
        {
            "success": True,
            "stock_number": "S123",
            "vin": "1234567890ABCDEFG",
            "updated_checkboxes": 5,
            "total_checkboxes": 20,
            "timestamp": datetime.now().isoformat()
        },
        {
            "success": False,
            "stock_number": "S124",
            "vin": "ABCDEFG1234567890",
            "error": "Failed to update checkboxes",
            "updated_checkboxes": 0,
            "total_checkboxes": 20,
            "timestamp": datetime.now().isoformat()
        }
    ]
    
    # Mock methods
    reporting_module.generate_report = MagicMock(return_value=asyncio.Future())
    reporting_module.generate_report.return_value.set_result("reports/Test_Dealership_20250428_123456.html")
    
    reporting_module.send_email_notification = MagicMock(return_value=asyncio.Future())
    reporting_module.send_email_notification.return_value.set_result(True)
    
    # Call process_results method
    result = await reporting_module.process_results(dealer_config, results)
    
    # Verify result
    assert result["success"] is True
    assert result["report_path"] == "reports/Test_Dealership_20250428_123456.html"
    assert result["email_sent"] is True
    assert "stats" in result
    assert result["stats"]["vehicles_processed"] == 2
    assert result["stats"]["successful_updates"] == 1
    assert result["stats"]["failed_updates"] == 1
    
    # Verify method calls
    reporting_module.generate_report.assert_called_once()
    reporting_module.send_email_notification.assert_called_once()


@pytest.mark.asyncio
async def test_process_results_report_generation_failure(reporting_module):
    """Test processing results when report generation fails."""
    # Test data
    dealer_config = {
        "name": "Test Dealership",
        "dealer_id": "TEST123"
    }
    
    results = [
        {
            "success": True,
            "stock_number": "S123",
            "vin": "1234567890ABCDEFG",
            "updated_checkboxes": 5,
            "total_checkboxes": 20,
            "timestamp": datetime.now().isoformat()
        }
    ]
    
    # Mock methods
    reporting_module.generate_report = MagicMock(return_value=asyncio.Future())
    reporting_module.generate_report.return_value.set_result("")  # Empty path indicates failure
    
    # Call process_results method
    result = await reporting_module.process_results(dealer_config, results)
    
    # Verify result
    assert result["success"] is False
    assert "report_path" in result
    assert result["report_path"] == ""
    assert result["email_sent"] is False
    
    # Verify method calls
    reporting_module.generate_report.assert_called_once()


@pytest.mark.asyncio
async def test_send_alert_success(reporting_module):
    """Test successful alert sending."""
    # Test data
    subject = "Test Alert"
    message = "This is a test alert message"
    
    # Mock aiosmtplib.send
    with patch("aiosmtplib.send") as mock_send:
        mock_send.return_value = asyncio.Future()
        mock_send.return_value.set_result(None)
        
        # Call send_alert method
        result = await reporting_module.send_alert(subject, message)
        
        # Verify result
        assert result is True
        
        # Verify aiosmtplib.send was called
        mock_send.assert_called_once()
        
        # Verify email parameters
        call_args = mock_send.call_args[1]
        assert call_args["hostname"] == "smtp.example.com"
        assert call_args["port"] == 587
        assert call_args["username"] == "test_user"
        assert call_args["password"] == "test_password"
        assert call_args["use_tls"] is True


@pytest.mark.asyncio
async def test_send_alert_with_dealer_config(reporting_module):
    """Test alert sending with dealer config."""
    # Test data
    subject = "Test Alert"
    message = "This is a test alert message"
    dealer_config = {
        "name": "Test Dealership",
        "dealer_id": "TEST123",
        "email_recipients": ["dealer@example.com"]
    }
    
    # Mock aiosmtplib.send
    with patch("aiosmtplib.send") as mock_send:
        mock_send.return_value = asyncio.Future()
        mock_send.return_value.set_result(None)
        
        # Call send_alert method
        result = await reporting_module.send_alert(subject, message, dealer_config)
        
        # Verify result
        assert result is True
        
        # Verify aiosmtplib.send was called
        mock_send.assert_called_once()
        
        # Verify email was sent to dealer recipients
        msg = mock_send.call_args[0][0]
        assert "dealer@example.com" in msg["To"]


@pytest.mark.asyncio
async def test_send_alert_no_credentials(reporting_module):
    """Test alert sending with no SMTP credentials."""
    # Test data
    subject = "Test Alert"
    message = "This is a test alert message"
    
    # Clear SMTP credentials
    reporting_module.smtp_username = None
    reporting_module.smtp_password = None
    
    # Call send_alert method
    result = await reporting_module.send_alert(subject, message)
    
    # Verify result
    assert result is False
