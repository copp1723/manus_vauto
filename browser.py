"""
Browser automation engine for the vAuto Feature Verification System.

This module provides a Selenium-based implementation of the BrowserInterface.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    StaleElementReferenceException,
    WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager

from .interfaces import BrowserInterface

logger = logging.getLogger(__name__)


class SeleniumBrowser(BrowserInterface):
    """Selenium-based implementation of the BrowserInterface."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Selenium browser.
        
        Args:
            config: Browser configuration
        """
        self.config = config
        self.browser = None
        self.session_start_time = None
        self.default_timeout = config["timeout"]
        
        logger.info("Selenium browser initialized")
    
    async def initialize(self) -> None:
        """
        Initialize the browser.
        
        Returns:
            None
        """
        logger.info("Initializing browser session")
        
        options = Options()
        if self.config["headless"]:
            options.add_argument("--headless")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(f"--window-size={self.config['window_size']['width']},{self.config['window_size']['height']}")
        
        # Add user agent to avoid detection
        options.add_argument(f"--user-agent={self.config['user_agent']}")
        
        # Disable automation flags
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Run in event loop to avoid blocking
        self.browser = await asyncio.to_thread(
            webdriver.Chrome,
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        
        # Set default timeout
        self.browser.implicitly_wait(self.default_timeout)
        self.session_start_time = datetime.now()
        
        logger.info("Browser session initialized")
    
    async def close(self) -> None:
        """
        Close the browser.
        
        Returns:
            None
        """
        if self.browser:
            try:
                await asyncio.to_thread(self.browser.quit)
                logger.info("Browser session closed")
            except Exception as e:
                logger.error(f"Error closing browser: {str(e)}")
            finally:
                self.browser = None
                self.session_start_time = None
    
    async def navigate_to(self, url: str) -> None:
        """
        Navigate to a URL.
        
        Args:
            url: URL to navigate to
            
        Returns:
            None
        """
        logger.info(f"Navigating to: {url}")
        
        if not self.browser:
            await self.initialize()
            
        await asyncio.to_thread(self.browser.get, url)
    
    async def find_element(self, selector: str, by: str = "xpath", timeout: int = None) -> Any:
        """
        Find an element on the page.
        
        Args:
            selector: Element selector
            by: Selector type (xpath, css, id, etc.)
            timeout: Wait timeout in seconds
            
        Returns:
            WebElement: Found element
            
        Raises:
            TimeoutException: If element is not found within timeout
        """
        if timeout is None:
            timeout = self.default_timeout
            
        logger.debug(f"Finding element: {by} '{selector}'")
        
        if not self.browser:
            await self.initialize()
        
        by_method = self._get_by_method(by)
        
        try:
            element = await asyncio.to_thread(
                WebDriverWait(self.browser, timeout).until,
                EC.presence_of_element_located((by_method, selector))
            )
            return element
        except TimeoutException:
            logger.error(f"Element not found: {by} '{selector}'")
            raise
    
    async def find_elements(self, selector: str, by: str = "xpath", timeout: int = None) -> List[Any]:
        """
        Find multiple elements on the page.
        
        Args:
            selector: Element selector
            by: Selector type (xpath, css, id, etc.)
            timeout: Wait timeout in seconds
            
        Returns:
            list: Found elements
            
        Raises:
            TimeoutException: If no elements are found within timeout
        """
        if timeout is None:
            timeout = self.default_timeout
            
        logger.debug(f"Finding elements: {by} '{selector}'")
        
        if not self.browser:
            await self.initialize()
        
        by_method = self._get_by_method(by)
        
        try:
            # First wait for at least one element to be present
            await asyncio.to_thread(
                WebDriverWait(self.browser, timeout).until,
                EC.presence_of_element_located((by_method, selector))
            )
            
            # Then get all matching elements
            elements = await asyncio.to_thread(
                self.browser.find_elements,
                by_method,
                selector
            )
            return elements
        except TimeoutException:
            logger.warning(f"No elements found: {by} '{selector}'")
            return []
    
    async def click_element(self, element_or_selector: Any, by: str = "xpath", timeout: int = None) -> None:
        """
        Click an element.
        
        Args:
            element_or_selector: Element or selector string
            by: Selector type if selector string is provided
            timeout: Wait timeout in seconds
            
        Returns:
            None
        """
        if timeout is None:
            timeout = self.default_timeout
        
        if not self.browser:
            await self.initialize()
        
        by_method = self._get_by_method(by)
        
        if isinstance(element_or_selector, str):
            logger.debug(f"Clicking element by selector: {by} '{element_or_selector}'")
            element = await self.find_element(element_or_selector, by, timeout)
        else:
            logger.debug("Clicking provided element")
            element = element_or_selector
        
        try:
            # First wait for element to be clickable
            if isinstance(element_or_selector, str):
                await asyncio.to_thread(
                    WebDriverWait(self.browser, timeout).until,
                    EC.element_to_be_clickable((by_method, element_or_selector))
                )
            
            # Then click it
            await asyncio.to_thread(element.click)
        except (StaleElementReferenceException, TimeoutException):
            logger.warning("Element became stale or not clickable, retrying with JavaScript")
            await asyncio.to_thread(
                self.browser.execute_script,
                "arguments[0].click();",
                element
            )
    
    async def fill_input(self, element_or_selector: Any, text: str, by: str = "xpath", 
                        timeout: int = None, clear_first: bool = True) -> None:
        """
        Fill an input field.
        
        Args:
            element_or_selector: Element or selector string
            text: Text to enter
            by: Selector type if selector string is provided
            timeout: Wait timeout in seconds
            clear_first: Whether to clear the input first
            
        Returns:
            None
        """
        if timeout is None:
            timeout = self.default_timeout
        
        if not self.browser:
            await self.initialize()
        
        by_method = self._get_by_method(by)
        
        if isinstance(element_or_selector, str):
            logger.debug(f"Filling input {by} '{element_or_selector}' with text: {text}")
            element = await self.find_element(element_or_selector, by, timeout)
        else:
            logger.debug(f"Filling provided input element with text: {text}")
            element = element_or_selector
        
        try:
            if clear_first:
                await asyncio.to_thread(element.clear)
            await asyncio.to_thread(element.send_keys, text)
        except StaleElementReferenceException:
            logger.warning("Element became stale, retrying with JavaScript")
            if clear_first:
                await asyncio.to_thread(
                    self.browser.execute_script,
                    "arguments[0].value = '';",
                    element
                )
            await asyncio.to_thread(
                self.browser.execute_script,
                f"arguments[0].value = '{text}';",
                element
            )
    
    async def get_text(self, element_or_selector: Any, by: str = "xpath", timeout: int = None) -> str:
        """
        Get text from an element.
        
        Args:
            element_or_selector: Element or selector string
            by: Selector type if selector string is provided
            timeout: Wait timeout in seconds
            
        Returns:
            str: Element text
        """
        if timeout is None:
            timeout = self.default_timeout
        
        if not self.browser:
            await self.initialize()
        
        by_method = self._get_by_method(by)
        
        if isinstance(element_or_selector, str):
            logger.debug(f"Getting text from element: {by} '{element_or_selector}'")
            element = await self.find_element(element_or_selector, by, timeout)
        else:
            logger.debug("Getting text from provided element")
            element = element_or_selector
        
        try:
            text = await asyncio.to_thread(lambda: element.text)
            if not text:  # If text is empty, try getting value attribute (for inputs)
                text = await asyncio.to_thread(lambda: element.get_attribute("value") or "")
            return text
        except StaleElementReferenceException:
            logger.warning("Element became stale, retrying with JavaScript")
            text = await asyncio.to_thread(
                self.browser.execute_script,
                "return arguments[0].textContent || arguments[0].value || '';",
                element
            )
            return text.strip()
    
    async def get_attribute(self, element_or_selector: Any, attribute: str, 
                           by: str = "xpath", timeout: int = None) -> str:
        """
        Get attribute from an element.
        
        Args:
            element_or_selector: Element or selector string
            attribute: Attribute name
            by: Selector type if selector string is provided
            timeout: Wait timeout in seconds
            
        Returns:
            str: Attribute value
        """
        if timeout is None:
            timeout = self.default_timeout
        
        if not self.browser:
            await self.initialize()
        
        by_method = self._get_by_method(by)
        
        if isinstance(element_or_selector, str):
            logger.debug(f"Getting attribute '{attribute}' from element: {by} '{element_or_selector}'")
            element = await self.find_element(element_or_selector, by, timeout)
        else:
            logger.debug(f"Getting attribute '{attribute}' from provided element")
            element = element_or_selector
        
        try:
            value = await asyncio.to_thread(lambda: element.get_attribute(attribute))
            return value
        except StaleElementReferenceException:
            logger.warning("Element became stale, retrying with JavaScript")
            value = await asyncio.to_thread(
                self.browser.execute_script,
                f"return arguments[0].getAttribute('{attribute}');",
                element
            )
            return value
    
    async def wait_for_presence(self, selector: str, by: str = "xpath", timeout: int = None) -> Any:
        """
        Wait for an element to be present.
        
        Args:
            selector: Element selector
            by: Selector type
            timeout: Wait timeout in seconds
            
        Returns:
            WebElement: Found element or None if not found
        """
        if timeout is None:
            timeout = self.default_timeout
            
        logger.debug(f"Waiting for element presence: {by} '{selector}'")
        
        if not self.browser:
            await self.initialize()
        
        by_method = self._get_by_method(by)
        
        try:
            element = await asyncio.to_thread(
                WebDriverWait(self.browser, timeout).until,
                EC.presence_of_element_located((by_method, selector))
            )
            return element
        except TimeoutException:
            logger.warning(f"Timeout waiting for element presence: {by} '{selector}'")
            return None
    
    async def wait_for_invisibility(self, selector: str, by: str = "xpath", timeout: int = None) -> bool:
        """
        Wait for an element to become invisible.
        
        Args:
            selector: Element selector
            by: Selector type
            timeout: Wait timeout in seconds
            
        Returns:
            bool: True if element became invisible, False on timeout
        """
        if timeout is None:
            timeout = self.default_timeout
            
        logger.debug(f"Waiting for element invisibility: {by} '{selector}'")
        
        if not self.browser:
            await self.initialize()
        
        by_method = self._get_by_method(by)
        
        try:
            result = await asyncio.to_thread(
                WebDriverWait(self.browser, timeout).until,
                EC.invisibility_of_element_located((by_method, selector))
            )
            return result
        except TimeoutException:
            logger.warning(f"Timeout waiting for element invisibility: {by} '{selector}'")
            return False
    
    async def take_screenshot(self, filename: str) -> str:
        """
        Take a screenshot.
        
        Args:
            filename: Path to save screenshot
            
        Returns:
            str: Path to saved screenshot
        """
        logger.info(f"Taking screenshot: {filename}")
        
        if not self.browser:
            await self.initialize()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        try:
            await asyncio.to_thread(self.browser.save_screenshot, filename)
            logger.info(f"Screenshot saved to: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Error taking screenshot: {str(e)}")
            return ""
    
    async def execute_script(self, script: str, *args) -> Any:
        """
        Execute JavaScript in the browser.
        
        Args:
            script: JavaScript code to execute
            *args: Arguments to pass to the script
            
        Returns:
            Any: Result of the script execution
        """
        logger.debug(f"Executing script: {script}")
        
        if not self.browser:
            await self.initialize()
        
        try:
            result = await asyncio.to_thread(self.browser.execute_script, script, *args)
            return result
        except Exception as e:
            logger.error(f"Error executing script: {str(e)}")
            raise
    
    def _get_by_method(self, by: str) -> Any:
        """
        Get the Selenium By method for the given selector type.
        
        Args:
            by: Selector type (xpath, css, id, etc.)
            
        Returns:
            By: Selenium By method
        """
        by_map = {
            "xpath": By.XPATH,
            "css": By.CSS_SELECTOR,
            "id": By.ID,
            "name": By.NAME,
            "tag": By.TAG_NAME,
            "class": By.CLASS_NAME,
            "link_text": By.LINK_TEXT,
            "partial_link_text": By.PARTIAL_LINK_TEXT
        }
        
        return by_map.get(by.lower(), By.XPATH)
