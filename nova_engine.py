"""
Core Nova Act Engine module.

This module provides the foundation for browser automation using Selenium.
"""

import asyncio
import logging
from datetime import datetime
import os
from dotenv import load_dotenv
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

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class NovaActEngine:
    """
    Core Nova Act Engine for browser automation using Selenium.
    """
    
    def __init__(self, config):
        """
        Initialize the Nova Act Engine.
        
        Args:
            config (dict): System configuration
        """
        self.config = config
        self.browser = None
        self.session_start_time = None
        self.default_timeout = config["nova_act"]["timeout"]
        
        logger.info("Nova Act Engine initialized with Selenium")
    
    async def initialize_browser(self):
        """
        Initialize a new browser session with Selenium.
        
        Returns:
            object: Browser instance
        """
        logger.info("Initializing browser session")
        
        options = Options()
        if self.config["nova_act"]["headless"]:
            options.add_argument("--headless")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # Add user agent to avoid detection
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
        
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
        return self.browser
    
    async def is_session_valid(self):
        """
        Check if the current session is still valid.
        
        Returns:
            bool: True if session is valid, False otherwise
        """
        if not self.browser or not self.session_start_time:
            return False
        
        session_age = (datetime.now() - self.session_start_time).total_seconds() / 60
        
        try:
            # Check if browser is still responsive
            self.browser.current_url
            return session_age < self.config["processing"]["session_timeout"]
        except WebDriverException:
            logger.warning("Browser session is no longer responsive")
            return False
    
    async def ensure_browser(self):
        """
        Ensure a valid browser session exists.
        
        Returns:
            object: Browser instance
        """
        if not await self.is_session_valid():
            if self.browser:
                await self.close_browser()
            await self.initialize_browser()
        return self.browser
    
    async def close_browser(self):
        """
        Close the browser session.
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
    
    async def execute_action(self, action_fn, max_retries=None):
        """
        Execute an action with retry logic.
        
        Args:
            action_fn (callable): Async function to execute
            max_retries (int, optional): Maximum number of retry attempts
            
        Returns:
            Any: Result of the action
            
        Raises:
            Exception: If all retry attempts fail
        """
        if max_retries is None:
            max_retries = self.config["nova_act"]["retry_attempts"]
            
        attempts = 0
        last_error = None
        
        while attempts < max_retries:
            try:
                browser = await self.ensure_browser()
                result = await action_fn(browser)
                return result
            except Exception as e:
                last_error = e
                attempts += 1
                logger.warning(f"Action failed (attempt {attempts}/{max_retries}): {str(e)}")
                
                if attempts >= max_retries:
                    break
                
                # Implement exponential backoff
                backoff_time = 2 ** attempts
                logger.info(f"Retrying in {backoff_time} seconds...")
                await asyncio.sleep(backoff_time)
        
        # If we reach here, all attempts failed
        logger.error(f"Action failed after {max_retries} attempts: {str(last_error)}")
        raise Exception(f"Action failed after {max_retries} attempts: {last_error}")
    
    async def navigate_to(self, url):
        """
        Navigate to a URL.
        
        Args:
            url (str): URL to navigate to
        """
        logger.info(f"Navigating to: {url}")
        await asyncio.to_thread(self.browser.get, url)
    
    async def find_element(self, by, selector, timeout=None):
        """
        Find an element on the page.
        
        Args:
            by (By): Selenium By selector (e.g., By.ID, By.XPATH)
            selector (str): Element selector
            timeout (int, optional): Wait timeout in seconds
            
        Returns:
            WebElement: Found element
            
        Raises:
            TimeoutException: If element is not found within timeout
        """
        if timeout is None:
            timeout = self.default_timeout
            
        logger.debug(f"Finding element: {by} '{selector}'")
        
        try:
            element = await asyncio.to_thread(
                WebDriverWait(self.browser, timeout).until,
                EC.presence_of_element_located((by, selector))
            )
            return element
        except TimeoutException:
            logger.error(f"Element not found: {by} '{selector}'")
            raise
    
    async def find_elements(self, by, selector, timeout=None):
        """
        Find multiple elements on the page.
        
        Args:
            by (By): Selenium By selector (e.g., By.ID, By.XPATH)
            selector (str): Element selector
            timeout (int, optional): Wait timeout in seconds
            
        Returns:
            list: Found elements
            
        Raises:
            TimeoutException: If no elements are found within timeout
        """
        if timeout is None:
            timeout = self.default_timeout
            
        logger.debug(f"Finding elements: {by} '{selector}'")
        
        try:
            # First wait for at least one element to be present
            await asyncio.to_thread(
                WebDriverWait(self.browser, timeout).until,
                EC.presence_of_element_located((by, selector))
            )
            
            # Then get all matching elements
            elements = await asyncio.to_thread(
                self.browser.find_elements,
                by,
                selector
            )
            return elements
        except TimeoutException:
            logger.warning(f"No elements found: {by} '{selector}'")
            return []
    
    async def click_element(self, element_or_selector, by=By.XPATH, timeout=None):
        """
        Click an element.
        
        Args:
            element_or_selector: Element or selector string
            by (By, optional): Selenium By selector if selector string is provided
            timeout (int, optional): Wait timeout in seconds
        """
        if timeout is None:
            timeout = self.default_timeout
        
        if isinstance(element_or_selector, str):
            logger.debug(f"Clicking element by selector: {by} '{element_or_selector}'")
            element = await self.find_element(by, element_or_selector, timeout)
        else:
            logger.debug("Clicking provided element")
            element = element_or_selector
        
        try:
            # First wait for element to be clickable
            if isinstance(element_or_selector, str):
                await asyncio.to_thread(
                    WebDriverWait(self.browser, timeout).until,
                    EC.element_to_be_clickable((by, element_or_selector))
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
    
    async def fill_input(self, element_or_selector, text, by=By.XPATH, timeout=None, clear_first=True):
        """
        Fill an input field.
        
        Args:
            element_or_selector: Element or selector string
            text (str): Text to enter
            by (By, optional): Selenium By selector if selector string is provided
            timeout (int, optional): Wait timeout in seconds
            clear_first (bool, optional): Whether to clear the input first
        """
        if timeout is None:
            timeout = self.default_timeout
        
        if isinstance(element_or_selector, str):
            logger.debug(f"Filling input {by} '{element_or_selector}' with text: {text}")
            element = await self.find_element(by, element_or_selector, timeout)
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
    
    async def get_text(self, element_or_selector, by=By.XPATH, timeout=None):
        """
        Get text from an element.
        
        Args:
            element_or_selector: Element or selector string
            by (By, optional): Selenium By selector if selector string is provided
            timeout (int, optional): Wait timeout in seconds
            
        Returns:
            str: Element text
        """
        if timeout is None:
            timeout = self.default_timeout
        
        if isinstance(element_or_selector, str):
            logger.debug(f"Getting text from element: {by} '{element_or_selector}'")
            element = await self.find_element(by, element_or_selector, timeout)
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
    
    async def get_attribute(self, element_or_selector, attribute, by=By.XPATH, timeout=None):
        """
        Get attribute from an element.
        
        Args:
            element_or_selector: Element or selector string
            attribute (str): Attribute name
            by (By, optional): Selenium By selector if selector string is provided
            timeout (int, optional): Wait timeout in seconds
            
        Returns:
            str: Attribute value
        """
        if timeout is None:
            timeout = self.default_timeout
        
        if isinstance(element_or_selector, str):
            logger.debug(f"Getting attribute '{attribute}' from element: {by} '{element_or_selector}'")
            element = await self.find_element(by, element_or_selector, timeout)
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
    
    async def wait_for_url_contains(self, text, timeout=None):
        """
        Wait until URL contains specified text.
        
        Args:
            text (str): Text to wait for in URL
            timeout (int, optional): Wait timeout in seconds
            
        Returns:
            bool: True if condition was met, False on timeout
        """
        if timeout is None:
            timeout = self.default_timeout
            
        logger.debug(f"Waiting for URL to contain: {text}")
        
        try:
            result = await asyncio.to_thread(
                WebDriverWait(self.browser, timeout).until,
                EC.url_contains(text)
            )
            return result
        except TimeoutException:
            logger.warning(f"Timeout waiting for URL to contain: {text}")
            return False
    
    async def wait_for_invisibility(self, by, selector, timeout=None):
        """
        Wait for an element to become invisible.
        
        Args:
            by (By): Selenium By selector
            selector (str): Element selector
            timeout (int, optional): Wait timeout in seconds
            
        Returns:
            bool: True if element became invisible, False on timeout
        """
        if timeout is None:
            timeout = self.default_timeout
            
        logger.debug(f"Waiting for element to become invisible: {by} '{selector}'")
        
        try:
            result = await asyncio.to_thread(
                WebDriverWait(self.browser, timeout).until,
                EC.invisibility_of_element_located((b
(Content truncated due to size limit. Use line ranges to read in chunks)