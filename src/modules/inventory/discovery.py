"""
Inventory Discovery Module for vAuto Feature Verification System.

Handles:
- Discovery of vehicles in the inventory
- Filtering of vehicles that need feature verification
- Retrieval of window sticker URLs
"""

import logging
import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from core.interfaces import BrowserInterface, AuthenticationInterface, InventoryDiscoveryInterface
from utils.common import retry_async

logger = logging.getLogger(__name__)


class InventoryDiscoveryModule(InventoryDiscoveryInterface):
    """
    Module for discovering vehicles in inventory that need feature verification.
    """
    
    def __init__(self, browser: BrowserInterface, auth_module: AuthenticationInterface, config: Dict[str, Any]):
        """
        Initialize the inventory discovery module.
        
        Args:
            browser: Browser interface implementation
            auth_module: Authentication module instance
            config: System configuration
        """
        self.browser = browser
        self.auth_module = auth_module
        self.config = config
        
        logger.info("Inventory Discovery module initialized")
    
    async def get_vehicles_needing_verification(self, dealership_config: Dict[str, Any], 
                                              max_vehicles: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get vehicles that need feature verification.
        
        Args:
            dealership_config: Dealership configuration
            max_vehicles: Maximum number of vehicles to retrieve
            
        Returns:
            list: List of vehicle data dictionaries
        """
        if max_vehicles is None:
            max_vehicles = self.config["processing"]["max_vehicles_per_batch"]
        
        logger.info(f"Discovering vehicles needing verification for {dealership_config['name']} (max: {max_vehicles})")
        
        # Ensure logged in
        logged_in = await self.auth_module.ensure_logged_in(dealership_config.get("dealership_id"))
        if not logged_in:
            logger.error("Not logged in, cannot discover inventory")
            return []
        
        try:
            # Use retry mechanism for vehicle discovery
            vehicles = await retry_async(
                self._discover_vehicles_action,
                dealership_config,
                max_vehicles,
                max_retries=3,
                delay=2,
                exceptions=(TimeoutException, NoSuchElementException)
            )
            
            logger.info(f"Discovered {len(vehicles)} vehicles needing verification")
            return vehicles
            
        except Exception as e:
            logger.error(f"Error discovering vehicles: {str(e)}")
            return []
    
    async def _discover_vehicles_action(self, dealership_config: Dict[str, Any], max_vehicles: int) -> List[Dict[str, Any]]:
        """
        Internal action to discover vehicles.
        
        Args:
            dealership_config: Dealership configuration
            max_vehicles: Maximum number of vehicles to retrieve
            
        Returns:
            list: List of vehicle data dictionaries
        """
        vehicles = []
        
        try:
            # Navigate to inventory page
            await self._navigate_to_inventory(dealership_config)
            
            # Apply filters to find vehicles needing verification
            await self._apply_inventory_filters(dealership_config)
            
            # Extract vehicle data
            vehicles = await self._extract_vehicle_data(max_vehicles)
            
            return vehicles
            
        except Exception as e:
            logger.error(f"Discover vehicles action failed: {str(e)}")
            # Take a screenshot for debugging
            await self.browser.take_screenshot("logs/inventory_discovery_failure.png")
            raise
    
    async def _navigate_to_inventory(self, dealership_config: Dict[str, Any]) -> None:
        """
        Navigate to the inventory page.
        
        Args:
            dealership_config: Dealership configuration
        """
        logger.info("Navigating to inventory page")
        
        # Navigate to the Provision dashboard
        await self.browser.navigate_to("https://provision.vauto.app.coxautoinc.com/Va/Dashboard/ProvisionEnterprise/Default.aspx")
        
        # Wait for the dashboard to load
        dashboard_loaded = await self.browser.wait_for_presence(
            "//div[contains(@class, 'dashboard') or contains(@id, 'dashboard')]"
        )
        
        if not dashboard_loaded:
            logger.error("Dashboard failed to load")
            raise Exception("Dashboard failed to load")
        
        # Click the "View Inventory" link under the Pricing tab
        view_inventory_link = await self.browser.wait_for_presence(
            "//a[contains(text(), 'View Inventory')]"
        )
        
        if not view_inventory_link:
            logger.error("View Inventory link not found")
            raise Exception("View Inventory link not found")
        
        await self.browser.click_element(view_inventory_link)
        
        # Wait for inventory to load
        inventory_loaded = await self.browser.wait_for_presence(
            "//div[contains(@class, 'inventory-grid') or contains(@class, 'inventory-table')]"
        )
        
        if not inventory_loaded:
            logger.error("Inventory page failed to load")
            raise Exception("Inventory page failed to load")
        
        logger.info("Successfully navigated to inventory page")
    
    async def _apply_inventory_filters(self, dealership_config: Dict[str, Any]) -> None:
        """
        Apply filters to find vehicles needing verification.
        
        Args:
            dealership_config: Dealership configuration
        """
        logger.info("Applying inventory filters")
        
        try:
            # Click the Filter tab
            filter_tab = await self.browser.wait_for_presence("//div[@id='ext-gen73']")
            if filter_tab:
                await self.browser.click_element(filter_tab)
            else:
                logger.warning("Filter tab not found, trying alternative selectors")
                
                # Try alternative selectors
                filter_buttons = [
                    "//button[contains(text(), 'Filter')]",
                    "//button[contains(@class, 'filter')]",
                    "//div[contains(text(), 'Filter')]"
                ]
                
                for selector in filter_buttons:
                    filter_button = await self.browser.wait_for_presence(selector)
                    if filter_button:
                        await self.browser.click_element(filter_button)
                        break
            
            # Wait for filter panel to appear
            await asyncio.sleep(1)
            
            # Enable the Age filter
            age_checkbox = await self.browser.wait_for_presence("//input[@id='ext-gen119']")
            if age_checkbox:
                # Check if it's already checked
                is_checked = await self.browser.get_attribute(age_checkbox, "checked")
                if not is_checked or is_checked == "false":
                    await self.browser.click_element(age_checkbox)
            else:
                logger.warning("Age checkbox not found, trying alternative selectors")
                
                # Try alternative selectors
                age_labels = [
                    "//label[contains(text(), 'Age')]",
                    "//div[contains(text(), 'Age')]"
                ]
                
                for selector in age_labels:
                    age_label = await self.browser.wait_for_presence(selector)
                    if age_label:
                        await self.browser.click_element(age_label)
                        break
            
            # Set the age range to 0-1 days
            min_age_field = await self.browser.wait_for_presence("//input[@id='ext-gen114']")
            if min_age_field:
                await self.browser.fill_input(min_age_field, "0")
            else:
                logger.warning("Minimum age field not found")
            
            max_age_field = await self.browser.wait_for_presence("//input[@id='ext-gen115']")
            if max_age_field:
                await self.browser.fill_input(max_age_field, "1")
            else:
                logger.warning("Maximum age field not found")
            
            # Apply the filter
            apply_button = await self.browser.wait_for_presence("//button[@id='ext-gen745']")
            if apply_button:
                await self.browser.click_element(apply_button)
            else:
                logger.warning("Apply button not found, trying alternative selectors")
                
                # Try alternative selectors
                apply_buttons = [
                    "//button[contains(text(), 'Apply')]",
                    "//button[contains(text(), 'Search')]",
                    "//button[contains(@class, 'apply')]",
                    "//button[contains(@class, 'search-button')]"
                ]
                
                for selector in apply_buttons:
                    apply_btn = await self.browser.wait_for_presence(selector)
                    if apply_btn:
                        await self.browser.click_element(apply_btn)
                        break
            
            # Wait for filtered results to load
            await self.browser.wait_for_invisibility(
                "//div[contains(@class, 'loading') or contains(@class, 'spinner')]"
            )
            
            logger.info("Inventory filters applied")
            
        except Exception as e:
            logger.error(f"Error applying inventory filters: {str(e)}")
            # Continue without filters if they fail
            logger.warning("Continuing without filters")
    
    async def _extract_vehicle_data(self, max_vehicles: int) -> List[Dict[str, Any]]:
        """
        Extract vehicle data from the inventory page.
        
        Args:
            max_vehicles: Maximum number of vehicles to retrieve
            
        Returns:
            list: List of vehicle data dictionaries
        """
        logger.info(f"Extracting vehicle data (max: {max_vehicles})")
        
        vehicles = []
        
        try:
            # Identify vehicle elements using the XPath from the vision document
            vehicle_rows = await self.browser.find_elements(
                "//div[@id='ext-gen25']/div/table/tbody/tr/td[4]/div/div[1]/a/div"
            )
            
            if not vehicle_rows:
                logger.warning("No vehicle rows found using primary selector, trying alternative selectors")
                
                # Try alternate selectors
                vehicle_rows = await self.browser.find_elements(
                    "//tr[contains(@class, 'inventory') or contains(@data-vehicle-id, '') or .//a[contains(@href, 'vehicle')]]"
                )
            
            if not vehicle_rows:
                logger.error("No vehicles found in inventory")
                return []
            
            # Limit to max_vehicles
            vehicle_rows = vehicle_rows[:max_vehicles]
            
            logger.info(f"Found {len(vehicle_rows)} vehicle rows")
            
            # Process each vehicle row
            for i, row in enumerate(vehicle_rows):
                try:
                    # Extract vehicle ID
                    vehicle_id = await self.browser.get_attribute(row, "data-vehicle-id")
                    
                    if not vehicle_id:
                        # Try to extract from other attributes
                        vehicle_id = await self._extract_vehicle_id_from_element(row)
                    
                    if not vehicle_id:
                        logger.warning(f"Could not extract vehicle ID for row {i+1}, skipping")
                        continue
                    
                    # Extract vehicle detail URL by clicking the row and getting the URL
                    # First, store the current URL
                    current_url = await self.browser.execute_script("return window.location.href")
                    
                    # Click the row to navigate to the detail page
                    await self.browser.click_element(row)
                    
                    # Wait for the detail page to load
                    detail_loaded = await self.browser.wait_for_presence(
                        "//div[contains(@class, 'vehicle-detail') or contains(@class, 'inventory-detail')]"
                    )
                    
                    if not detail_loaded:
                        logger.warning(f"Detail page failed to load for vehicle {vehicle_id}, skipping")
                        # Navigate back to the inventory page
                        await self.browser.navigate_to(current_url)
                        continue
                    
                    # Get the detail URL
                    detail_url = await self.browser.execute_script("return window.location.href")
                    
                    # Extract basic vehicle info from the detail page
                    vehicle_info = await self._extract_vehicle_info_from_detail()
                    
                    # Get window sticker URL
                    window_sticker_url = await self._get_window_sticker_url()
                    
                    # Create vehicle data entry
                    vehicle_data = {
                        "id": vehicle_id,
                        "detail_url": detail_url,
                        "window_sticker_url": window_sticker_url,
                        **vehicle_info
                    }
                    
                    # Only add vehicles with window sticker URLs
                    if window_sticker_url:
                        vehicles.append(vehicle_data)
                    else:
                        logger.warning(f"No window sticker URL found for vehicle {vehicle_id}, skipping")
                    
                    # Navigate back to the inventory page
                    await self.browser.navigate_to(current_url)
                    
                    # Wait for inventory to load again
                    await self.browser.wait_for_presence(
                        "//div[contains(@class, 'inventory-grid') or contains(@class, 'inventory-table')]"
                    )
                    
                except Exception as e:
                    logger.warning(f"Error extracting data for vehicle row {i+1}: {str(e)}")
                    # Try to navigate back to the inventory page
                    try:
                        await self.browser.navigate_to(current_url)
                    except:
                        pass
                    continue
            
            logger.info(f"Extracted data for {len(vehicles)} vehicles with window sticker URLs")
            return vehicles
            
        except Exception as e:
            logger.error(f"Error extracting vehicle data: {str(e)}")
            return []
    
    async def _extract_vehicle_id_from_element(self, element: Any) -> Optional[str]:
        """
        Extract vehicle ID from element.
        
        Args:
            element: Vehicle row element
            
        Returns:
            str: Vehicle ID or None if not found
        """
        # Try various attributes that might contain the ID
        attrs_to_check = ["id", "data-id", "data-key", "data-row-key"]
        
        for attr in attrs_to_check:
            value = await self.browser.get_attribute(element, attr)
            if value:
                # Extract numeric ID if present
                match = re.search(r'\d+', value)
                if match:
                    return match.group(0)
                return value
        
        # Try to find links that might contain the ID
        links = await self.browser.find_elements(
            ".//a[contains(@href, 'vehicle') or contains(@href, 'inventory') or contains(@href, 'detail')]",
            element
        )
        
        for link in links:
            href = await self.browser.get_attribute(link, "href")
            if href:
                # Extract ID from URL
                match = re.search(r'[?&]id=(\d+)', href)
                if match:
                    return match.group(1)
        
        return None
    
    async def _extract_vehicle_info_from_detail(self) -> Dict[str, Any]:
        """
        Extract vehicle information from the detail page.
        
        Returns:
            dict: Vehicle information
        """
        info = {}
        
        try:
            # Extract year, make, model
            title_element = await self.browser.wait_for_presence(
                "//h1[contains(@class, 'vehicle-title') or contains(@class, 'detail-title')]"
            )
            
            if title_element:
                title_text = await self.browser.get_text(title_element)
                # Parse title text (e.g., "2024 Toyota Corolla LE")
                parts = title_text.split()
                if len(parts) >= 2:
                    # First part is usually the year
                    if parts[0].isdigit() and len(parts[0]) == 4:
                        info["year"] = parts[0]
                        # Second part is usually the make
                        info["make"] = parts[1]
                        # The rest could be model and trim
                        if len(parts) >= 3:
                            info["model"] = " ".join(parts[2:])
            
            # Extract VIN
            vin_selectors = [
                "//span[contains(text(), 'VIN')]/following-sibling::span",
                "//div[contains(text(), 'VIN')]/following-sibling::div",
                "//label[contains(text(), 'VIN')]/following-sibling::div"
            ]
            
            for selector in vin_selectors:
                vin_element = await self.browser.wait_for_presence(selector)
                if vin_element:
                    vin_text = await self.browser.get_text(vin_element)
                    if vin_text and len(vin_text) >= 17:  # VINs are typically 17 characters
                        info["vin"] = vin_text.strip()
                        break
            
            # Extract stock number
            stock_selectors = [
                "//span[contains(text(), 'Stock')]/following-sibling::span",
                "//div[contains(text(), 'Stock')]/following-sibling::div",
                "//label[contains(text(), 'Stock')]/following-sibling::div"
            ]
            
            for selector in stock_selectors:
                stock_element = await self.browser.wait_for_presence(selector)
                if stock_element:
                    stock_text = await self.browser.get_text(stock_element)
                    if stock_text:
                        info["stock_number"] = stock_text.strip()
                        break
            
            return info
            
        except Exception as e:
            logger.warning(f"Error extracting vehicle info from detail page: {str(e)}")
            return info
    
    async def _get_window_sticker_url(self) -> Optional[str]:
        """
        Get window sticker URL from the detail page.
        
        Returns:
            str: Window sticker URL or None if not found
        """
        try:
            # Navigate to Factory Equipment tab
            factory_equipment_tab = await self.browser.wait_for_presence("//div[@id='ext-gen201']")
            if factory_equipment_tab:
                await self.browser.click_element(factory_equipment_tab)
            else:
                logger.warning("Factory Equipment tab not found, trying alternative selectors")
                
                # Try alternative selectors
                tab_selectors = [
                    "//a[contains(text(), 'Factory Equipment')]",
                    "//div[contains(text(), 'Factory Equipment')]",
                    "//span[contains(text(), 'Factory Equipment')]"
                ]
                
                for selector in tab_selectors:
                    tab = await self.browser.wait_for_presence(selector)
                    if tab:
                        await self.browser.click_element(tab)
                        break
                else:
                    logger.error("Factory Equipment tab not found")
                    return None
            
            # Wait for the Factory Equipment tab to load
            await asyncio.sleep(2)
            
            # Look for window sticker button or link
            sticker_selectors = [
                "//button[contains(text(), 'Window Sticker')]",
                "//a[contains(text(), 'Window Sticker')]",
                "//div[contains(text(), 'Window Sticker')]",
                "//span[contains(text(), 'Window Sticker')]"
            ]
            
            for selector in sticker_selectors:
                sticker_element = await self.browser.wait_for_presence(selector)
                if sticker_element:
                    # Check if this is a link with href
                    href = await self.browser.get_attribute(sticker_element, "href")
                    if href:
                        return href
                    
                    # If not a direct link, click it to reveal the window sticker
                    await self.browser.click_element(sticker_element)
                    
                    # Wait for window sticker to load
                    await asyncio.sleep(2)
                    
                    # Look for window sticker URL in newly revealed elements
                    sticker_url_selectors = [
                        "//a[contains(@href, 'window') or contains(@href, 'sticker') or contains(@href, 'pdf')]",
                        "//iframe[contains(@src, 'window') or contains(@src, 'sticker') or contains(@src, 'pdf')]"
                    ]
                    
                    for url_selector in sticker_url_selectors:
                        url_element = await self.browser.wait_for_presence(url_selector)
                        if url_element:
                            url = await self.browser.get_attribute(url_element, "href") or await self.browser.get_attribute(url_element, "src")
                            if url:
                                return url
                    
                    break
            
            logger.warning("Window sticker URL not found")
            return None
            
        except Exception as e:
            logger.warning(f"Error getting window sticker URL: {str(e)}")
            return None
