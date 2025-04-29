"""
Checkbox Management Module for vAuto Feature Verification System.

Handles:
- Navigation to vAuto checkbox page
- Mapping extracted features to checkboxes
- Setting/clearing checkboxes based on mapped features
- Saving changes to vAuto system
"""

import logging
import asyncio
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)

class CheckboxManagementModule:
    """
    Module for managing vAuto checkboxes based on extracted features.
    """
    
    def __init__(self, nova_engine, auth_module, feature_mapper, config):
        """
        Initialize the checkbox management module.
        
        Args:
            nova_engine (NovaActEngine): Nova Act Engine instance
            auth_module (AuthenticationModule): Authentication module instance
            feature_mapper (FeatureMapper): Feature mapping module
            config (dict): System configuration
        """
        self.nova_engine = nova_engine
        self.auth_module = auth_module
        self.feature_mapper = feature_mapper
        self.config = config
        
        logger.info("Checkbox Management module initialized")
    
    async def update_vehicle_checkboxes(self, vehicle_data, extracted_features):
        """
        Update vehicle checkboxes based on extracted features.
        
        Args:
            vehicle_data (dict): Vehicle data including ID and detail URL
            extracted_features (list): List of extracted features from window sticker
            
        Returns:
            dict: Results of the update operation
        """
        logger.info(f"Updating checkboxes for vehicle {vehicle_data.get('id')}")
        
        # Ensure logged in
        logged_in = await self.auth_module.ensure_logged_in()
        if not logged_in:
            logger.error("Not logged in, cannot update checkboxes")
            return {
                "success": False,
                "vehicle_id": vehicle_data.get("id"),
                "error": "Not logged in"
            }
        
        try:
            # Map extracted features to vAuto checkboxes
            mapped_features = await self.feature_mapper.map_features(extracted_features)
            
            if not mapped_features:
                logger.warning(f"No features mapped for vehicle {vehicle_data.get('id')}")
                return {
                    "success": True,
                    "vehicle_id": vehicle_data.get("id"),
                    "updated": 0,
                    "features": []
                }
            
            # Execute the checkbox update
            result = await self.nova_engine.execute_action(
                lambda browser: self._update_checkboxes_action(browser, vehicle_data, mapped_features)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating vehicle checkboxes: {str(e)}")
            return {
                "success": False,
                "vehicle_id": vehicle_data.get("id"),
                "error": str(e)
            }
    
    async def _update_checkboxes_action(self, browser, vehicle_data, mapped_features):
        """
        Internal action to update checkboxes.
        
        Args:
            browser: Browser instance
            vehicle_data (dict): Vehicle data
            mapped_features (list): Mapped features
            
        Returns:
            dict: Results of the update operation
        """
        try:
            # Navigate to vehicle edit page
            await self._navigate_to_edit_page(vehicle_data)
            
            # Navigate to checkboxes section
            await self._navigate_to_checkboxes_section()
            
            # Get current checkbox states
            current_states = await self._get_checkbox_states()
            
            # Set checkboxes according to mapped features
            updated_checkboxes = await self._set_checkboxes(mapped_features, current_states)
            
            # Save changes
            saved = await self._save_changes()
            
            if not saved:
                logger.error(f"Failed to save changes for vehicle {vehicle_data.get('id')}")
                return {
                    "success": False,
                    "vehicle_id": vehicle_data.get("id"),
                    "error": "Failed to save changes"
                }
            
            return {
                "success": True,
                "vehicle_id": vehicle_data.get("id"),
                "updated": len(updated_checkboxes),
                "features": updated_checkboxes
            }
            
        except Exception as e:
            logger.error(f"Update checkboxes action failed: {str(e)}")
            # Take a screenshot for debugging
            await self.nova_engine.take_screenshot(f"logs/checkbox_failure_{vehicle_data.get('id')}.png")
            raise
    
    async def _navigate_to_edit_page(self, vehicle_data):
        """
        Navigate to the vehicle edit page.
        
        Args:
            vehicle_data (dict): Vehicle data
        """
        logger.info(f"Navigating to edit page for vehicle {vehicle_data.get('id')}")
        
        # Ensure we have a detail URL
        if not vehicle_data.get("detail_url"):
            logger.error("No detail URL provided")
            raise ValueError("No detail URL provided")
        
        # Navigate to detail page
        await self.nova_engine.navigate_to(vehicle_data["detail_url"])
        
        # Wait for detail page to load
        await self.nova_engine.wait_for_presence(
            By.XPATH,
            "//div[contains(@class, 'vehicle-detail') or contains(@class, 'inventory-detail')]"
        )
        
        # Look for edit button
        edit_button_selectors = [
            "//button[contains(text(), 'Edit')]",
            "//a[contains(text(), 'Edit')]",
            "//button[contains(@aria-label, 'Edit')]",
            "//button[@title='Edit']"
        ]
        
        edit_button = None
        for selector in edit_button_selectors:
            try:
                elements = await self.nova_engine.find_elements(By.XPATH, selector)
                if elements:
                    edit_button = elements[0]
                    break
            except:
                continue
        
        if not edit_button:
            logger.error("Edit button not found")
            raise Exception("Edit button not found")
        
        # Click edit button
        await self.nova_engine.click_element(edit_button)
        
        # Wait for edit page to load
        await self.nova_engine.wait_for_presence(
            By.XPATH,
            "//div[contains(@class, 'edit-form') or contains(@class, 'vehicle-edit')]"
        )
        
        logger.info("Successfully navigated to edit page")
    
    async def _navigate_to_checkboxes_section(self):
        """
        Navigate to the checkboxes section on the edit page.
        """
        logger.info("Navigating to checkboxes section")
        
        # Look for features/checkboxes tab
        tab_selectors = [
            "//a[contains(text(), 'Features') or contains(@aria-label, 'Features')]",
            "//div[contains(text(), 'Features')]/parent::a",
            "//button[contains(text(), 'Features')]",
            "//a[contains(text(), 'Options') or contains(@aria-label, 'Options')]",
            "//div[contains(text(), 'Options')]/parent::a",
            "//button[contains(text(), 'Options')]",
            "//a[contains(text(), 'Checkboxes') or contains(@aria-label, 'Checkboxes')]",
            "//div[contains(text(), 'Checkboxes')]/parent::a",
            "//button[contains(text(), 'Checkboxes')]"
        ]
        
        tab_element = None
        for selector in tab_selectors:
            try:
                elements = await self.nova_engine.find_elements(By.XPATH, selector, timeout=2)
                if elements:
                    tab_element = elements[0]
                    break
            except:
                continue
        
        if tab_element:
            await self.nova_engine.click_element(tab_element)
            
            # Wait for tab to load
            await asyncio.sleep(1)
        
        # Check if checkboxes are visible, even if tab wasn't found
        # (sometimes they're directly visible without clicking a tab)
        checkboxes_visible = await self.nova_engine.find_elements(
            By.XPATH,
            "//input[@type='checkbox']"
        )
        
        if not checkboxes_visible:
            logger.error("Checkboxes section not found")
            raise Exception("Checkboxes section not found")
        
        logger.info("Successfully navigated to checkboxes section")
    
    async def _get_checkbox_states(self):
        """
        Get current states of all checkboxes.
        
        Returns:
            dict: Dictionary mapping checkbox labels to their current states
        """
        logger.info("Getting current checkbox states")
        
        checkbox_states = {}
        
        try:
            # Find all checkbox containers
            checkbox_containers = await self.nova_engine.find_elements(
                By.XPATH,
                "//div[contains(@class, 'checkbox') or .//input[@type='checkbox']]"
            )
            
            for container in checkbox_containers:
                try:
                    # Find checkbox input
                    checkbox = await self.nova_engine.find_element(
                        By.XPATH,
                        ".//input[@type='checkbox']",
                        container
                    )
                    
                    # Find label
                    label_element = await self.nova_engine.find_element(
                        By.XPATH,
                        ".//label | .//span[not(contains(@class, 'checkbox'))]",
                        container
                    )
                    
                    if checkbox and label_element:
                        label = await self.nova_engine.get_text(label_element)
                        label = label.strip()
                        
                        if label:
                            # Get checked state
                            checked = await self.nova_engine.get_attribute(checkbox, "checked")
                            checkbox_states[label] = checked == "true" or checked == True
                except:
                    continue
            
            logger.info(f"Found {len(checkbox_states)} checkboxes")
            return checkbox_states
            
        except Exception as e:
            logger.error(f"Error getting checkbox states: {str(e)}")
            return {}
    
    async def _set_checkboxes(self, mapped_features, current_states):
        """
        Set checkboxes according to mapped features.
        
        Args:
            mapped_features (dict): Dictionary mapping vAuto checkbox labels to boolean values
            current_states (dict): Dictionary of current checkbox states
            
        Returns:
            list: List of updated features with their new states
        """
        logger.info(f"Setting checkboxes for {len(mapped_features)} mapped features")
        
        updated_features = []
        
        try:
            for feature_label, should_be_checked in mapped_features.items():
                try:
                    # Find feature checkbox container
                    container_selectors = [
                        f"//div[contains(@class, 'checkbox') and .//label[contains(text(), '{feature_label}')]]",
                        f"//div[contains(@class, 'checkbox') and .//span[contains(text(), '{feature_label}')]]",
                        f"//label[contains(text(), '{feature_label}')]/ancestor::div[contains(@class, 'checkbox')]",
                        f"//span[contains(text(), '{feature_label}')]/ancestor::div[contains(@class, 'checkbox')]"
                    ]
                    
                    container = None
                    for selector in container_selectors:
                        try:
                            elements = await self.nova_engine.find_elements(By.XPATH, selector)
                            if elements:
                                container = elements[0]
                                break
                        except:
                            continue
                    
                    if not container:
                        logger.warning(f"Checkbox container not found for feature: {feature_label}")
                        continue
                    
                    # Find checkbox input
                    checkbox = await self.nova_engine.find_element(
                        By.XPATH,
                        ".//input[@type='checkbox']",
                        container
                    )
                    
                    if not checkbox:
                        logger.warning(f"Checkbox input not found for feature: {feature_label}")
                        continue
                    
                    # Get current state
                    is_checked = await self.nova_engine.get_attribute(checkbox, "checked")
                    is_checked = is_checked == "true" or is_checked == True
                    
                    # Only update if state needs to change
                    if is_checked != should_be_checked:
                        await self.nova_engine.click_element(checkbox)
                        
                        # Verify the change
                        new_checked = await self.nova_engine.get_attribute(checkbox, "checked")
                        new_checked = new_checked == "true" or new_checked == True
                        
                        if new_checked == should_be_checked:
                            logger.info(f"Updated checkbox for feature: {feature_label} (set to {should_be_checked})")
                            updated_features.append({
                                "feature": feature_label,
                                "new_state": should_be_checked
                            })
                        else:
                            logger.warning(f"Failed to update checkbox for feature: {feature_label}")
                            
                except Exception as e:
                    logger.warning(f"Error setting checkbox for feature {feature_label}: {str(e)}")
                    continue
            
            logger.info(f"Updated {len(updated_features)} checkboxes")
            return updated_features
            
        except Exception as e:
            logger.error(f"Error setting checkboxes: {str(e)}")
            return []
    
    async def _save_changes(self):
        """
        Save changes to the edit form.
        
        Returns:
            bool: True if save successful, False otherwise
        """
        logger.info("Saving changes")
        
        try:
            # Look for save button
            save_button_selectors = [
                "//button[contains(text(), 'Save')]",
                "//button[contains(@class, 'save')]",
                "//button[@type='submit']",
                "//input[@type='submit']"
            ]
            
            save_button = None
            for selector in save_button_selectors:
                try:
                    elements = await self.nova_engine.find_elements(By.XPATH, selector)
                    if elements:
                        save_button = elements[0]
                        break
                except:
                    continue
            
            if not save_button:
                logger.error("Save button not found")
                
(Content truncated due to size limit. Use line ranges to read in chunks)