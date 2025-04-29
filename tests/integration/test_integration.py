"""
Integration tests for the vAuto Feature Verification System.

This module contains integration tests that verify the interaction between multiple components.
"""

import pytest
import asyncio
import os
from unittest.mock import MagicMock, patch

from core.interfaces import BrowserInterface
from core.browser import BrowserModule
from modules.authentication.auth_module import AuthenticationModule
from modules.inventory.discovery import InventoryDiscoveryModule
from modules.inventory.window_sticker import WindowStickerProcessor
from modules.feature_mapping.feature_mapper import FeatureMapper
from modules.inventory.checkbox_management import CheckboxManagementModule
from modules.reporting.reporting import ReportingModule


@pytest.fixture
def config():
    """Create a test configuration."""
    return {
        "browser": {
            "headless": True,
            "timeout": 30
        },
        "authentication": {
            "login_url": "https://app.vauto.com/login",
            "session_timeout_minutes": 60
        },
        "inventory": {
            "max_vehicles": 10,
            "inventory_url": "https://app.vauto.com/inventory"
        },
        "feature_mapping": {
            "confidence_threshold": 0.8
        },
        "reporting": {
            "email_recipients": ["test@example.com"]
        }
    }


@pytest.fixture
def browser_mock():
    """Create a mock browser interface."""
    browser = MagicMock(spec=BrowserInterface)
    
    # Set up async methods to return awaitable values
    browser.navigate_to.return_value = asyncio.Future()
    browser.navigate_to.return_value.set_result(None)
    
    browser.wait_for_presence.return_value = asyncio.Future()
    browser.wait_for_presence.return_value.set_result(MagicMock())
    
    browser.click_element.return_value = asyncio.Future()
    browser.click_element.return_value.set_result(None)
    
    browser.fill_input.return_value = asyncio.Future()
    browser.fill_input.return_value.set_result(None)
    
    browser.find_elements.return_value = asyncio.Future()
    browser.find_elements.return_value.set_result([])
    
    browser.get_text.return_value = asyncio.Future()
    browser.get_text.return_value.set_result("")
    
    browser.get_attribute.return_value = asyncio.Future()
    browser.get_attribute.return_value.set_result("")
    
    browser.take_screenshot.return_value = asyncio.Future()
    browser.take_screenshot.return_value.set_result("")
    
    return browser


@pytest.mark.asyncio
async def test_authentication_and_inventory_discovery_integration(browser_mock, config):
    """Test integration between authentication and inventory discovery modules."""
    # Set up environment variables
    with patch.dict('os.environ', {
        'VAUTO_USERNAME': 'test_user',
        'VAUTO_PASSWORD': 'test_password'
    }):
        # Create modules
        auth_module = AuthenticationModule(browser_mock, config)
        inventory_module = InventoryDiscoveryModule(browser_mock, auth_module, config)
        
        # Mock successful login
        auth_module.login = MagicMock(return_value=asyncio.Future())
        auth_module.login.return_value.set_result(True)
        
        auth_module.is_logged_in = MagicMock(return_value=asyncio.Future())
        auth_module.is_logged_in.return_value.set_result(True)
        
        # Mock inventory discovery
        browser_mock.find_elements.return_value = asyncio.Future()
        browser_mock.find_elements.return_value.set_result([MagicMock(), MagicMock(), MagicMock()])
        
        browser_mock.get_attribute.side_effect = [
            asyncio.Future(),
            asyncio.Future(),
            asyncio.Future()
        ]
        browser_mock.get_attribute.side_effect[0].set_result("123")
        browser_mock.get_attribute.side_effect[1].set_result("456")
        browser_mock.get_attribute.side_effect[2].set_result("789")
        
        browser_mock.get_text.side_effect = [
            asyncio.Future(),
            asyncio.Future(),
            asyncio.Future()
        ]
        browser_mock.get_text.side_effect[0].set_result("2023 Toyota Camry")
        browser_mock.get_text.side_effect[1].set_result("2023 Honda Accord")
        browser_mock.get_text.side_effect[2].set_result("2023 Ford Mustang")
        
        # Call discover_vehicles method
        vehicles = await inventory_module.discover_vehicles()
        
        # Verify result
        assert len(vehicles) == 3
        assert vehicles[0]["id"] == "123"
        assert vehicles[1]["id"] == "456"
        assert vehicles[2]["id"] == "789"
        
        # Verify auth_module.ensure_logged_in was called
        auth_module.is_logged_in.assert_called_once()


@pytest.mark.asyncio
async def test_window_sticker_and_feature_mapper_integration(browser_mock, config):
    """Test integration between window sticker processor and feature mapper."""
    # Create modules
    window_sticker_processor = WindowStickerProcessor(browser_mock, config)
    feature_mapper = FeatureMapper(config)
    
    # Mock window sticker extraction
    window_sticker_processor.extract_features = MagicMock(return_value=asyncio.Future())
    window_sticker_processor.extract_features.return_value.set_result([
        "Leather Seats",
        "Navigation System",
        "Bluetooth",
        "Backup Camera",
        "Sunroof"
    ])
    
    # Mock feature mapping
    original_map_features = feature_mapper.map_features
    
    # Call extract_features and map_features
    extracted_features = await window_sticker_processor.extract_features("https://example.com/sticker.pdf")
    mapped_features = await original_map_features(extracted_features)
    
    # Verify results
    assert len(extracted_features) == 5
    assert "Leather Seats" in extracted_features
    assert "Navigation System" in extracted_features
    
    assert "Leather Seats" in mapped_features
    assert mapped_features["Leather Seats"] is True
    assert "Navigation System" in mapped_features
    assert mapped_features["Navigation System"] is True
    assert "Sunroof" in mapped_features
    assert mapped_features["Sunroof"] is True


@pytest.mark.asyncio
async def test_checkbox_management_and_reporting_integration(browser_mock, config):
    """Test integration between checkbox management and reporting modules."""
    # Set up environment variables
    with patch.dict('os.environ', {
        'SMTP_HOST': 'smtp.example.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'test_user',
        'SMTP_PASSWORD': 'test_password',
        'EMAIL_FROM': 'noreply@example.com'
    }), patch("utils.common.ensure_dir", return_value="reports"):
        # Create modules
        auth_module = AuthenticationModule(browser_mock, config)
        checkbox_module = CheckboxManagementModule(browser_mock, auth_module, config)
        reporting_module = ReportingModule(config)
        
        # Mock checkbox update
        checkbox_module.update_vehicle_checkboxes = MagicMock(return_value=asyncio.Future())
        checkbox_module.update_vehicle_checkboxes.return_value.set_result({
            "success": True,
            "vehicle_id": "123",
            "updated_checkboxes": 5,
            "total_checkboxes": 20,
            "timestamp": "2025-04-28T12:34:56"
        })
        
        # Mock report generation
        reporting_module.generate_report = MagicMock(return_value=asyncio.Future())
        reporting_module.generate_report.return_value.set_result("reports/Test_Dealership_20250428_123456.html")
        
        reporting_module.send_email_notification = MagicMock(return_value=asyncio.Future())
        reporting_module.send_email_notification.return_value.set_result(True)
        
        # Test data
        vehicle_data = {
            "id": "123",
            "stock_number": "S123",
            "vin": "1234567890ABCDEFG",
            "year": "2023",
            "make": "Toyota",
            "model": "Camry"
        }
        
        extracted_features = [
            "Leather Seats",
            "Navigation System",
            "Bluetooth"
        ]
        
        dealer_config = {
            "name": "Test Dealership",
            "dealer_id": "TEST123"
        }
        
        # Update checkboxes
        result = await checkbox_module.update_vehicle_checkboxes(vehicle_data, extracted_features)
        
        # Process results
        report_result = await reporting_module.process_results(dealer_config, [result])
        
        # Verify results
        assert result["success"] is True
        assert result["vehicle_id"] == "123"
        assert result["updated_checkboxes"] == 5
        
        assert report_result["success"] is True
        assert "Test_Dealership_" in report_result["report_path"]
        assert report_result["email_sent"] is True
        
        # Verify method calls
        checkbox_module.update_vehicle_checkboxes.assert_called_once()
        reporting_module.generate_report.assert_called_once()
        reporting_module.send_email_notification.assert_called_once()
