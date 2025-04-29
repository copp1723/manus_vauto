"""
Checkbox Management Module for vAuto Feature Verification System.

Handles:
- Updating vehicle checkboxes in vAuto based on mapped features
- Managing checkbox state
- Tracking update history
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any

from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from core.interfaces import BrowserInterface, AuthenticationInterface, CheckboxManagementInterface
from utils.common import retry_async

logger = logging.getLogger(__name__)


class CheckboxManagementModule(CheckboxManagementInterface):
    """
    Module for managing vehicle checkboxes in vAuto.
    """
    
    def __init__(self, browser: BrowserInterface, auth_module: AuthenticationInterface, config: Dict[str, Any]):
        """
        Initialize the checkbox management module.
        
        Args:
            browser: Browser interface implementation
            auth_module: Authentication module instance
            config: System configuration
        """
        self.browser = browser
        self.auth_module = auth_module
        self.config = config
        
        logger.info("Checkbox Management module initialized")
    
    async def update_vehicle_checkboxes(self, vehicle_data: Dict[str, Any], 
                                      extracted_features: List[str]) -> Dict[str, Any]:
        """
        Update vehicle checkboxes based on extracted features.
        
        Args:
            vehicle_data: Vehicle data dictionary
            extracted_features: List of extracted features
            
        Returns:
            dict: Result of the update operation
        """
        vehicle_id = vehicle_data.get("id", "unknown")
        logger.info(f"Updating checkboxes for vehicle {vehicle_id}")
        
        result = {
            "success": False,
            "vehicle_id": vehicle_id,
            "updated_checkboxes": 0,
            "total_checkboxes": 0,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Ensure logged in
            logged_in = await self.auth_module.ensure_logged_in()
            if not logged_in:
                logger.error(f"Not logged in, cannot update checkboxes for vehicle {vehicle_id}")
                result["error"] = "Authentication failed"
                return result
            
            # Navigate to vehicle detail page
            if not await self._navigate_to_vehicle_detail(vehicle_data):
                logger.error(f"Failed to navigate to vehicle detail page for {vehicle_id}")
                result["error"] = "Navigation to vehicle detail failed"
                return result
            
            # Navigate to the Features tab
            if not await self._navigate_to_features_tab():
                logger.error(f"Failed to navigate to Features tab for vehicle {vehicle_id}")
                result["error"] = "Navigation to Features tab failed"
                return result
            
            # Update checkboxes based on extracted features
            update_result = await self._update_checkboxes(extracted_features)
            
            # Update result
            result.update(update_result)
            result["success"] = True
            
            logger.info(f"Successfully updated {result['updated_checkboxes']} checkboxes for vehicle {vehicle_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error updating checkboxes for vehicle {vehicle_id}: {str(e)}")
            result["error"] = str(e)
            return result
    
    async def _navigate_to_vehicle_detail(self, vehicle_data: Dict[str, Any]) -> bool:
        """
        Navigate to the vehicle detail page.
        
        Args:
            vehicle_data: Vehicle data dictionary
            
        Returns:
            bool: True if navigation successful, False otherwise
        """
        try:
            # Check if we have a detail URL
            detail_url = vehicle_data.get("detail_url")
            if detail_url:
                logger.info(f"Navigating to vehicle detail URL: {detail_url}")
                await self.browser.navigate_to(detail_url)
            else:
                # If no detail URL, navigate to the vehicle using ID
                vehicle_id = vehicle_data.get("id", "unknown")
                logger.info(f"Navigating to vehicle detail using ID: {vehicle_id}")
                
                # This is a placeholder implementation
                # In a real implementation, this would navigate to the vehicle detail page using the ID
                await self.browser.navigate_to(f"https://provision.vauto.app.coxautoinc.com/Va/Inventory/Detail.aspx?vehicleId={vehicle_id}")
            
            # Wait for the detail page to load
            detail_loaded = await self.browser.wait_for_presence(
                "//div[contains(@class, 'vehicle-detail') or contains(@class, 'inventory-detail')]"
            )
            
            if not detail_loaded:
                logger.error("Vehicle detail page failed to load")
                return False
            
            logger.info("Successfully navigated to vehicle detail page")
            return True
            
        except Exception as e:
            logger.error(f"Error navigating to vehicle detail: {str(e)}")
            return False
    
    async def _navigate_to_features_tab(self) -> bool:
        """
        Navigate to the Features tab.
        
        Returns:
            bool: True if navigation successful, False otherwise
        """
        try:
            # Look for the Features tab
            features_tab_selectors = [
                "//div[@id='ext-gen201']",  # Example from original code
                "//a[contains(text(), 'Features')]",
                "//div[contains(text(), 'Features')]",
                "//span[contains(text(), 'Features')]",
                "//li[contains(@class, 'features-tab')]"
            ]
            
            for selector in features_tab_selectors:
                features_tab = await self.browser.wait_for_presence(selector, timeout=3)
                if features_tab:
                    await self.browser.click_element(features_tab)
                    
                    # Wait for the Features tab to load
                    await asyncio.sleep(2)
                    
                    # Check if checkboxes are visible
                    checkboxes = await self.browser.find_elements(
                        "//input[@type='checkbox']",
                        timeout=5
                    )
                    
                    if checkboxes:
                        logger.info("Successfully navigated to Features tab")
                        return True
            
            logger.error("Features tab not found or checkboxes not visible")
            return False
            
        except Exception as e:
            logger.error(f"Error navigating to Features tab: {str(e)}")
            return False
    
    async def _update_checkboxes(self, extracted_features: List[str]) -> Dict[str, Any]:
        """
        Update checkboxes based on extracted features.
        
        Args:
            extracted_features: List of extracted features
            
        Returns:
            dict: Result of the update operation
        """
        result = {
            "updated_checkboxes": 0,
            "total_checkboxes": 0,
            "checkbox_details": []
        }
        
        try:
            # Get all checkboxes
            checkboxes = await self.browser.find_elements("//input[@type='checkbox']")
            result["total_checkboxes"] = len(checkboxes)
            
            if not checkboxes:
                logger.warning("No checkboxes found")
                return result
            
            logger.info(f"Found {len(checkboxes)} checkboxes")
            
            # Process each checkbox
            for i, checkbox in enumerate(checkboxes):
                try:
                    # Get checkbox label
                    label_text = await self._get_checkbox_label(checkbox)
                    if not label_text:
                        continue
                    
                    # Check if this feature is present in extracted features
                    is_present = await self._is_feature_present(label_text, extracted_features)
                    
                    # Get current checkbox state
                    is_checked = await self.browser.get_attribute(checkbox, "checked") == "true"
                    
                    # Update checkbox if needed
                    if is_present != is_checked:
                        await self.browser.click_element(checkbox)
                        result["updated_checkboxes"] += 1
                        
                        logger.info(f"Updated checkbox: {label_text} -> {is_present}")
                    
                    # Add to details
                    result["checkbox_details"].append({
                        "label": label_text,
                        "was_checked": is_checked,
                        "now_checked": is_present,
                        "updated": is_present != is_checked
                    })
                    
                except Exception as e:
                    logger.warning(f"Error processing checkbox {i}: {str(e)}")
                    continue
            
            # Save changes if any checkboxes were updated
            if result["updated_checkboxes"] > 0:
                await self._save_changes()
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating checkboxes: {str(e)}")
            return result
    
    async def _get_checkbox_label(self, checkbox: Any) -> str:
        """
        Get the label text for a checkbox.
        
        Args:
            checkbox: Checkbox element
            
        Returns:
            str: Label text
        """
        try:
            # Get checkbox ID
            checkbox_id = await self.browser.get_attribute(checkbox, "id")
            
            if checkbox_id:
                # Look for label with for attribute
                label_selector = f"//label[@for='{checkbox_id}']"
                label = await self.browser.wait_for_presence(label_selector, timeout=1)
                
                if label:
                    return await self.browser.get_text(label)
            
            # If no label found with for attribute, look for parent or sibling label
            parent_label = await self.browser.execute_script("""
                function getLabel(element) {
                    // Check parent
                    let parent = element.parentElement;
                    if (parent && parent.tagName === 'LABEL') {
                        return parent.textContent;
                    }
                    
                    // Check siblings
                    let sibling = element.nextElementSibling;
                    if (sibling && sibling.tagName === 'LABEL') {
                        return sibling.textContent;
                    }
                    
                    // Check for any text node siblings
                    sibling = element.nextSibling;
                    if (sibling && sibling.nodeType === 3) {
                        return sibling.textContent;
                    }
                    
                    // Check for any nearby div or span with text
                    let container = element.parentElement;
                    if (container) {
                        let spans = container.querySelectorAll('span, div');
                        for (let span of spans) {
                            if (span.textContent.trim()) {
                                return span.textContent;
                            }
                        }
                    }
                    
                    return '';
                }
                return getLabel(arguments[0]);
            """, checkbox)
            
            if parent_label:
                return parent_label.strip()
            
            return ""
            
        except Exception as e:
            logger.warning(f"Error getting checkbox label: {str(e)}")
            return ""
    
    async def _is_feature_present(self, label_text: str, extracted_features: List[str]) -> bool:
        """
        Check if a feature is present in the extracted features.
        
        Args:
            label_text: Checkbox label text
            extracted_features: List of extracted features
            
        Returns:
            bool: True if feature is present, False otherwise
        """
        # This is a simplified implementation
        # In a real implementation, this would use the FeatureMapper to check if the feature is present
        
        # Normalize label text
        normalized_label = label_text.lower().strip()
        
        # Check if any extracted feature contains this label
        for feature in extracted_features:
            normalized_feature = feature.lower().strip()
            
            # Check for exact match
            if normalized_label == normalized_feature:
                return True
            
            # Check for partial match
            if normalized_label in normalized_feature or normalized_feature in normalized_label:
                return True
        
        return False
    
    async def _save_changes(self) -> bool:
        """
        Save changes to checkboxes.
        
        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            # Look for save button
            save_button_selectors = [
                "//button[contains(text(), 'Save')]",
                "//button[contains(@class, 'save')]",
                "//input[@type='submit']",
                "//button[@type='submit']"
            ]
            
            for selector in save_button_selectors:
                save_button = await self.browser.wait_for_presence(selector, timeout=3)
                if save_button:
                    await self.browser.click_element(save_button)
                    
                    # Wait for save to complete
                    await asyncio.sleep(2)
                    
                    # Check for success message
                    success_message = await self.browser.wait_for_presence(
                        "//div[contains(@class, 'success') or contains(text(), 'success')]",
                        timeout=5
                    )
                    
                    if success_message:
                        logger.info("Changes saved successfully")
                        return True
                    
                    # If no success message, assume save was successful
                    logger.info("No success message found, assuming save was successful")
                    return True
            
            logger.warning("Save button not found")
            return False
            
        except Exception as e:
            logger.error(f"Error saving changes: {str(e)}")
            return False
