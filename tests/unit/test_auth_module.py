"""
Unit tests for the authentication module.

This module contains tests for the AuthenticationModule class.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from core.interfaces import BrowserInterface
from modules.authentication.auth_module import AuthenticationModule


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


@pytest.fixture
def config():
    """Create a mock configuration."""
    return {
        "browser": {
            "headless": True,
            "timeout": 30
        }
    }


@pytest.fixture
def auth_module(browser_mock, config):
    """Create an authentication module with mocked dependencies."""
    with patch.dict('os.environ', {
        'VAUTO_USERNAME': 'test_user',
        'VAUTO_PASSWORD': 'test_password'
    }):
        return AuthenticationModule(browser_mock, config)


@pytest.mark.asyncio
async def test_login_success(auth_module, browser_mock):
    """Test successful login."""
    # Set up browser mock to simulate successful login
    browser_mock.wait_for_presence.side_effect = [
        asyncio.Future(),  # username field
        asyncio.Future(),  # password field
        asyncio.Future(),  # dashboard
    ]
    browser_mock.wait_for_presence.side_effect[0].set_result(MagicMock())
    browser_mock.wait_for_presence.side_effect[1].set_result(MagicMock())
    browser_mock.wait_for_presence.side_effect[2].set_result(MagicMock())
    
    # Call login method
    result = await auth_module.login()
    
    # Verify result
    assert result is True
    
    # Verify browser interactions
    browser_mock.navigate_to.assert_called_once_with("https://app.vauto.com/login")
    browser_mock.fill_input.assert_any_call("//input[@id='username']", "test_user")
    browser_mock.fill_input.assert_any_call("//input[@type='password']", "test_password")
    
    # Verify session expiration is set
    assert auth_module.session_valid_until is not None
    assert auth_module.session_valid_until > datetime.now()


@pytest.mark.asyncio
async def test_login_failure_username_field_not_found(auth_module, browser_mock):
    """Test login failure when username field is not found."""
    # Set up browser mock to simulate username field not found
    browser_mock.wait_for_presence.side_effect = [
        asyncio.Future(),  # username field
    ]
    browser_mock.wait_for_presence.side_effect[0].set_result(None)
    
    # Call login method
    result = await auth_module.login()
    
    # Verify result
    assert result is False
    
    # Verify browser interactions
    browser_mock.navigate_to.assert_called_once_with("https://app.vauto.com/login")
    
    # Verify session expiration is not set
    assert auth_module.session_valid_until is None


@pytest.mark.asyncio
async def test_login_failure_password_field_not_found(auth_module, browser_mock):
    """Test login failure when password field is not found."""
    # Set up browser mock to simulate password field not found
    browser_mock.wait_for_presence.side_effect = [
        asyncio.Future(),  # username field
        asyncio.Future(),  # password field
    ]
    browser_mock.wait_for_presence.side_effect[0].set_result(MagicMock())
    browser_mock.wait_for_presence.side_effect[1].set_result(None)
    
    # Call login method
    result = await auth_module.login()
    
    # Verify result
    assert result is False
    
    # Verify browser interactions
    browser_mock.navigate_to.assert_called_once_with("https://app.vauto.com/login")
    browser_mock.fill_input.assert_called_once_with("//input[@id='username']", "test_user")
    
    # Verify session expiration is not set
    assert auth_module.session_valid_until is None


@pytest.mark.asyncio
async def test_login_failure_dashboard_not_found(auth_module, browser_mock):
    """Test login failure when dashboard is not found."""
    # Set up browser mock to simulate dashboard not found
    browser_mock.wait_for_presence.side_effect = [
        asyncio.Future(),  # username field
        asyncio.Future(),  # password field
        asyncio.Future(),  # dashboard
    ]
    browser_mock.wait_for_presence.side_effect[0].set_result(MagicMock())
    browser_mock.wait_for_presence.side_effect[1].set_result(MagicMock())
    browser_mock.wait_for_presence.side_effect[2].set_result(None)
    
    # Call login method
    result = await auth_module.login()
    
    # Verify result
    assert result is False
    
    # Verify browser interactions
    browser_mock.navigate_to.assert_called_once_with("https://app.vauto.com/login")
    browser_mock.fill_input.assert_any_call("//input[@id='username']", "test_user")
    browser_mock.fill_input.assert_any_call("//input[@type='password']", "test_password")
    
    # Verify session expiration is not set
    assert auth_module.session_valid_until is None


@pytest.mark.asyncio
async def test_is_logged_in_true(auth_module):
    """Test is_logged_in returns True when session is valid."""
    # Set session expiration to future time
    auth_module.session_valid_until = datetime.now() + timedelta(minutes=10)
    
    # Mock _check_logged_in_action to return True
    auth_module._check_logged_in_action = MagicMock(return_value=asyncio.Future())
    auth_module._check_logged_in_action.return_value.set_result(True)
    
    # Call is_logged_in method
    result = await auth_module.is_logged_in()
    
    # Verify result
    assert result is True


@pytest.mark.asyncio
async def test_is_logged_in_false_expired_session(auth_module):
    """Test is_logged_in returns False when session is expired."""
    # Set session expiration to past time
    auth_module.session_valid_until = datetime.now() - timedelta(minutes=10)
    
    # Call is_logged_in method
    result = await auth_module.is_logged_in()
    
    # Verify result
    assert result is False
    
    # Verify _check_logged_in_action was not called
    assert not hasattr(auth_module, '_check_logged_in_action') or not auth_module._check_logged_in_action.called


@pytest.mark.asyncio
async def test_is_logged_in_false_no_session(auth_module):
    """Test is_logged_in returns False when no session exists."""
    # Set session expiration to None
    auth_module.session_valid_until = None
    
    # Call is_logged_in method
    result = await auth_module.is_logged_in()
    
    # Verify result
    assert result is False
    
    # Verify _check_logged_in_action was not called
    assert not hasattr(auth_module, '_check_logged_in_action') or not auth_module._check_logged_in_action.called


@pytest.mark.asyncio
async def test_ensure_logged_in_already_logged_in(auth_module):
    """Test ensure_logged_in when already logged in."""
    # Mock is_logged_in to return True
    auth_module.is_logged_in = MagicMock(return_value=asyncio.Future())
    auth_module.is_logged_in.return_value.set_result(True)
    
    # Mock login
    auth_module.login = MagicMock()
    
    # Call ensure_logged_in method
    result = await auth_module.ensure_logged_in()
    
    # Verify result
    assert result is True
    
    # Verify login was not called
    auth_module.login.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_logged_in_not_logged_in(auth_module):
    """Test ensure_logged_in when not logged in."""
    # Mock is_logged_in to return False
    auth_module.is_logged_in = MagicMock(return_value=asyncio.Future())
    auth_module.is_logged_in.return_value.set_result(False)
    
    # Mock login to return True
    auth_module.login = MagicMock(return_value=asyncio.Future())
    auth_module.login.return_value.set_result(True)
    
    # Call ensure_logged_in method
    result = await auth_module.ensure_logged_in()
    
    # Verify result
    assert result is True
    
    # Verify login was called
    auth_module.login.assert_called_once()


@pytest.mark.asyncio
async def test_logout_success(auth_module, browser_mock):
    """Test successful logout."""
    # Set up browser mock to simulate successful logout
    browser_mock.find_elements.return_value = asyncio.Future()
    browser_mock.find_elements.return_value.set_result([MagicMock()])
    
    browser_mock.find_element.return_value = asyncio.Future()
    browser_mock.find_element.return_value.set_result(MagicMock())
    
    browser_mock.wait_for_presence.return_value = asyncio.Future()
    browser_mock.wait_for_presence.return_value.set_result(MagicMock())
    
    # Set session expiration
    auth_module.session_valid_until = datetime.now() + timedelta(minutes=10)
    
    # Mock _logout_action to return True
    auth_module._logout_action = MagicMock(return_value=asyncio.Future())
    auth_module._logout_action.return_value.set_result(True)
    
    # Call logout method
    result = await auth_module.logout()
    
    # Verify result
    assert result is True
    
    # Verify session expiration is cleared
    assert auth_module.session_valid_until is None
