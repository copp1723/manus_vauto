"""
Authentication Module for vAuto Feature Verification System.

Handles:
- Secure credential management
- vAuto login and session management
- Session validation and renewal
"""

import logging
import os
from datetime import datetime, timedelta
import asyncio
from typing import Dict, Optional, Any

from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv

from core.interfaces import BrowserInterface, AuthenticationInterface
from utils.common import retry_async

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class AuthenticationModule(AuthenticationInterface):
    """
    Module for handling vAuto authentication.
    """
    
    def __init__(self, browser: BrowserInterface, config: Dict[str, Any]):
        """
        Initialize the authentication module.
        
        Args:
            browser: Browser interface implementation
            config: System configuration
        """
        self.browser = browser
        self.config = config
        self.session_valid_until = None
        
        # Get credentials from environment variables
        self.credentials = {
            "username": os.getenv("VAUTO_USERNAME"),
            "password": os.getenv("VAUTO_PASSWORD")
        }
        
        if not self.credentials["username"] or not self.credentials["password"]:
            logger.error("vAuto credentials not found in environment variables")
            raise ValueError("vAuto credentials are required (VAUTO_USERNAME and VAUTO_PASSWORD)")
        
        logger.info("Authentication module initialized")
    
    async def login(self, dealership_id: Optional[str] = None) -> bool:
        """
        Log in to vAuto.
        
        Args:
            dealership_id: Dealership ID to select after login
            
        Returns:
            bool: True if login successful, False otherwise
        """
        logger.info("Logging in to vAuto")
        
        try:
            # Use retry mechanism for login
            result = await retry_async(
                self._login_action,
                dealership_id,
                max_retries=3,
                delay=2,
                exceptions=(TimeoutException, NoSuchElementException)
            )
            
            if result:
                # Set session expiration (30 minutes as per requirements)
                self.session_valid_until = datetime.now() + timedelta(minutes=30)
                logger.info("Successfully logged in to vAuto")
            else:
                logger.error("Failed to log in to vAuto")
            
            return result
            
        except Exception as e:
            logger.error(f"Error logging in to vAuto: {str(e)}")
            return False
    
    async def _login_action(self, dealership_id: Optional[str] = None) -> bool:
        """
        Internal action to perform login.
        
        Args:
            dealership_id: Dealership ID to select after login
            
        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            # Navigate to login page
            await self.browser.navigate_to("https://app.vauto.com/login")
            
            # Wait for the username field to load
            username_field = await self.browser.wait_for_presence("//input[@id='username']")
            if not username_field:
                logger.error("Username field not found")
                return False
            
            # Enter username
            await self.browser.fill_input("//input[@id='username']", self.credentials["username"])
            
            # Click Next button
            await self.browser.click_element("//button[contains(text(), 'Next')]")
            
            # Wait for password field to load
            password_field = await self.browser.wait_for_presence("//input[@type='password']")
            if not password_field:
                logger.error("Password field not found")
                return False
            
            # Enter password
            await self.browser.fill_input("//input[@type='password']", self.credentials["password"])
            
            # Click login button
            await self.browser.click_element("//button[@type='submit']")
            
            # Handle 2FA if required
            if await self._is_2fa_required():
                logger.info("2FA required, handling OTP")
                if not await self._handle_2fa():
                    logger.error("Failed to handle 2FA")
                    return False
            
            # Wait for login to complete
            dashboard_selector = "//div[contains(@class, 'dashboard') or contains(@class, 'inventory')]"
            dashboard = await self.browser.wait_for_presence(dashboard_selector)
            
            if not dashboard:
                # Check for error messages
                error_message = await self._check_login_errors()
                if error_message:
                    logger.error(f"Login failed: {error_message}")
                return False
            
            # Select dealership if specified
            if dealership_id:
                success = await self._select_dealership(dealership_id)
                return success
            
            return True
            
        except Exception as e:
            logger.error(f"Login action failed: {str(e)}")
            # Take a screenshot for debugging
            await self.browser.take_screenshot("logs/login_failure.png")
            return False
    
    async def _is_2fa_required(self) -> bool:
        """
        Check if 2FA is required.
        
        Returns:
            bool: True if 2FA is required, False otherwise
        """
        # Look for OTP input field or 2FA indicators
        otp_selectors = [
            "//input[contains(@id, 'otp')]",
            "//input[contains(@id, '2fa')]",
            "//div[contains(text(), 'verification code')]",
            "//div[contains(text(), 'two-factor')]"
        ]
        
        for selector in otp_selectors:
            element = await self.browser.wait_for_presence(selector, timeout=3)
            if element:
                return True
        
        return False
    
    async def _handle_2fa(self) -> bool:
        """
        Handle 2FA verification.
        
        Returns:
            bool: True if 2FA handled successfully, False otherwise
        """
        try:
            # Get OTP from email or Twilio (implementation depends on requirements)
            otp = await self._get_otp()
            
            if not otp:
                logger.error("Failed to get OTP")
                return False
            
            # Find OTP input field
            otp_selectors = [
                "//input[contains(@id, 'otp')]",
                "//input[contains(@id, '2fa')]",
                "//input[contains(@placeholder, 'code')]"
            ]
            
            otp_field = None
            for selector in otp_selectors:
                field = await self.browser.wait_for_presence(selector)
                if field:
                    otp_field = selector
                    break
            
            if not otp_field:
                logger.error("OTP input field not found")
                return False
            
            # Enter OTP
            await self.browser.fill_input(otp_field, otp)
            
            # Click verify button
            verify_selectors = [
                "//button[contains(text(), 'Verify')]",
                "//button[contains(text(), 'Submit')]",
                "//button[@type='submit']"
            ]
            
            for selector in verify_selectors:
                button = await self.browser.wait_for_presence(selector)
                if button:
                    await self.browser.click_element(selector)
                    break
            
            # Wait for verification to complete
            dashboard_selector = "//div[contains(@class, 'dashboard') or contains(@class, 'inventory')]"
            dashboard = await self.browser.wait_for_presence(dashboard_selector, timeout=10)
            
            return dashboard is not None
            
        except Exception as e:
            logger.error(f"Error handling 2FA: {str(e)}")
            return False
    
    async def _get_otp(self) -> str:
        """
        Get OTP from email or Twilio.
        
        Returns:
            str: OTP code or empty string if not found
        """
        # This is a placeholder implementation
        # In a real implementation, this would retrieve the OTP from email or Twilio
        logger.warning("Using mock OTP implementation")
        
        # Simulate OTP retrieval delay
        await asyncio.sleep(2)
        
        # Return a mock OTP
        return "123456"
    
    async def _check_login_errors(self) -> Optional[str]:
        """
        Check for login error messages.
        
        Returns:
            str: Error message if found, None otherwise
        """
        error_selectors = [
            "//div[contains(@class, 'error')]",
            "//span[contains(@class, 'error')]",
            "//p[contains(@class, 'error')]",
            "//div[contains(@class, 'alert')]"
        ]
        
        for selector in error_selectors:
            try:
                elements = await self.browser.find_elements(selector)
                for element in elements:
                    text = await self.browser.get_text(element)
                    if text and len(text.strip()) > 0 and "error" in text.lower():
                        return text.strip()
            except:
                continue
        
        return None
    
    async def _select_dealership(self, dealership_id: str) -> bool:
        """
        Select a dealership after login.
        
        Args:
            dealership_id: Dealership ID to select
            
        Returns:
            bool: True if dealership selected successfully, False otherwise
        """
        logger.info(f"Selecting dealership: {dealership_id}")
        
        try:
            # Check if dealership dropdown is present
            dealer_dropdown = await self.browser.find_element(
                "//div[contains(@class, 'dealerSelect') or contains(@class, 'dealer-select')]",
                timeout=5
            )
            
            if dealer_dropdown:
                # Click the dropdown to show options
                await self.browser.click_element(dealer_dropdown)
                
                # Wait for dropdown options to appear
                await asyncio.sleep(1)
                
                # Look for the specified dealership
                dealership_option = await self.browser.find_element(
                    f"//div[contains(text(), '{dealership_id}') or contains(@id, '{dealership_id}')]",
                    timeout=5
                )
                
                if dealership_option:
                    await self.browser.click_element(dealership_option)
                    
                    # Wait for the page to refresh with selected dealership
                    await asyncio.sleep(2)
                    
                    logger.info(f"Successfully selected dealership: {dealership_id}")
                    return True
                else:
                    logger.error(f"Dealership not found: {dealership_id}")
                    return False
            
            # If no dropdown is found, we may already be in the correct dealership
            logger.info("No dealership selection needed")
            return True
            
        except Exception as e:
            logger.error(f"Error selecting dealership: {str(e)}")
            return False
    
    async def is_logged_in(self) -> bool:
        """
        Check if the current session is logged in.
        
        Returns:
            bool: True if logged in, False otherwise
        """
        if not self.session_valid_until or datetime.now() > self.session_valid_until:
            return False
        
        try:
            result = await retry_async(
                self._check_logged_in_action,
                max_retries=2,
                delay=1
            )
            return result
        except Exception as e:
            logger.error(f"Error checking login status: {str(e)}")
            return False
    
    async def _check_logged_in_action(self) -> bool:
        """
        Internal action to check if logged in.
        
        Returns:
            bool: True if logged in, False otherwise
        """
        try:
            # Check for login page
            login_elements = await self.browser.find_elements(
                "//*[@id='username' or contains(@class, 'login')]",
                timeout=3
            )
            
            if login_elements:
                return False
            
            # Check for elements that indicate we're logged in
            dashboard_elements = await self.browser.find_elements(
                "//div[contains(@class, 'dashboard') or contains(@class, 'inventory') or contains(@class, 'navbar')]",
                timeout=3
            )
            
            return len(dashboard_elements) > 0
            
        except Exception as e:
            logger.warning(f"Check logged in action failed: {str(e)}")
            return False
    
    async def ensure_logged_in(self, dealership_id: Optional[str] = None) -> bool:
        """
        Ensure the session is logged in, logging in if necessary.
        
        Args:
            dealership_id: Dealership ID to select if login is needed
            
        Returns:
            bool: True if logged in, False otherwise
        """
        if await self.is_logged_in():
            return True
        
        return await self.login(dealership_id)
    
    async def logout(self) -> bool:
        """
        Log out from vAuto.
        
        Returns:
            bool: True if logout successful, False otherwise
        """
        logger.info("Logging out from vAuto")
        
        try:
            result = await retry_async(
                self._logout_action,
                max_retries=2,
                delay=1
            )
            
            if result:
                self.session_valid_until = None
                logger.info("Successfully logged out from vAuto")
            else:
                logger.error("Failed to log out from vAuto")
            
            return result
            
        except Exception as e:
            logger.error(f"Error logging out from vAuto: {str(e)}")
            return False
    
    async def _logout_action(self) -> bool:
        """
        Internal action to perform logout.
        
        Returns:
            bool: True if logout successful, False otherwise
        """
        try:
            # Look for user menu or account dropdown
            user_menu_selectors = [
                "//div[contains(@class, 'user-menu')]",
                "//button[contains(@class, 'user-menu')]",
                "//div[contains(@class, 'account')]",
                "//span[contains(@class, 'username')]",
                "//div[contains(@class, 'profile')]"
            ]
            
            user_menu = None
            for selector in user_menu_selectors:
                try:
                    elements = await self.browser.find_elements(selector, timeout=1)
                    if elements:
                        user_menu = elements[0]
                        break
                except:
                    continue
            
            if not user_menu:
                logger.warning("User menu not found, trying logout directly")
                
                # Try direct logout link
                logout_selectors = [
                    "//a[contains(text(), 'Logout')]",
                    "//a[contains(text(), 'Log out')]",
                    "//button[contains(text(), 'Logout')]",
                    "//button[contains(text(), 'Log out')]",
                    "//a[contains(@href, 'logout')]"
                ]
                
                for selector in logout_selectors:
                    try:
                        logout_button = await self.browser.find_element(selector, timeout=1)
                        if logout_button:
                            await self.browser.click_element(logout_button)
                            
                            # Wait for login page to appear
                            login_page = await self.browser.wait_for_presence("//input[@id='username']", timeout=5)
                            return login_page is not None
                    except:
                        continue
                
                logger.error("Logout link not found")
                return False
            
            # Click user menu to open dropdown
            await self.browser.click_element(user_menu)
            
            # Wait for dropdown to appear
            await asyncio.sleep(1)
            
            # Look for logout option
            logout_selectors = [
                "//a[contains(text(), 'Logout')]",
                "//a[contains(text(), 'Log out')]",
                "//button[contains(text(), 'Logout')]",
                "//button[contains(text(), 'Log out')]",
                "//a[contains(@href, 'logout')]",
                "//div[contains(text(), 'Logout')]"
            ]
            
            for selector in logout_selectors:
                try:
                    logout_option = await self.browser.find_element(selector, timeout=1)
                    if logout_option:
                        await self.browser.click_element(logout_option)
                        
                        # Wait for login page to appear
                        login_page = await self.browser.wait_for_presence("//input[@id='username']", timeout=5)
                        return login_page is not None
                except:
                    continue
            
            logger.error("Logout option not found in user menu")
            return False
            
        except Exception as e:
            logger.error(f"Logout action failed: {str(e)}")
            return False
