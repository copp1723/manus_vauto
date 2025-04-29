"""
Core interfaces for the vAuto Feature Verification System.

This module defines the abstract base classes and interfaces that form the foundation
of the system's architecture, promoting loose coupling and dependency injection.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime


class BrowserInterface(ABC):
    """Interface for browser automation."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the browser."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the browser."""
        pass
    
    @abstractmethod
    async def navigate_to(self, url: str) -> None:
        """Navigate to a URL."""
        pass
    
    @abstractmethod
    async def find_element(self, selector: str, by: str = "xpath", timeout: int = None) -> Any:
        """Find an element on the page."""
        pass
    
    @abstractmethod
    async def find_elements(self, selector: str, by: str = "xpath", timeout: int = None) -> List[Any]:
        """Find multiple elements on the page."""
        pass
    
    @abstractmethod
    async def click_element(self, element_or_selector: Any, by: str = "xpath", timeout: int = None) -> None:
        """Click an element."""
        pass
    
    @abstractmethod
    async def fill_input(self, element_or_selector: Any, text: str, by: str = "xpath", 
                        timeout: int = None, clear_first: bool = True) -> None:
        """Fill an input field."""
        pass
    
    @abstractmethod
    async def get_text(self, element_or_selector: Any, by: str = "xpath", timeout: int = None) -> str:
        """Get text from an element."""
        pass
    
    @abstractmethod
    async def get_attribute(self, element_or_selector: Any, attribute: str, 
                           by: str = "xpath", timeout: int = None) -> str:
        """Get attribute from an element."""
        pass
    
    @abstractmethod
    async def wait_for_presence(self, selector: str, by: str = "xpath", timeout: int = None) -> Any:
        """Wait for an element to be present."""
        pass
    
    @abstractmethod
    async def wait_for_invisibility(self, selector: str, by: str = "xpath", timeout: int = None) -> bool:
        """Wait for an element to become invisible."""
        pass
    
    @abstractmethod
    async def take_screenshot(self, filename: str) -> str:
        """Take a screenshot."""
        pass
    
    @abstractmethod
    async def execute_script(self, script: str, *args) -> Any:
        """Execute JavaScript in the browser."""
        pass


class AuthenticationInterface(ABC):
    """Interface for authentication functionality."""
    
    @abstractmethod
    async def login(self, dealership_id: Optional[str] = None) -> bool:
        """Log in to vAuto."""
        pass
    
    @abstractmethod
    async def logout(self) -> bool:
        """Log out from vAuto."""
        pass
    
    @abstractmethod
    async def is_logged_in(self) -> bool:
        """Check if the current session is logged in."""
        pass
    
    @abstractmethod
    async def ensure_logged_in(self, dealership_id: Optional[str] = None) -> bool:
        """Ensure the session is logged in, logging in if necessary."""
        pass


class InventoryDiscoveryInterface(ABC):
    """Interface for inventory discovery functionality."""
    
    @abstractmethod
    async def get_vehicles_needing_verification(self, dealership_config: Dict[str, Any], 
                                              max_vehicles: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get vehicles that need feature verification."""
        pass


class WindowStickerInterface(ABC):
    """Interface for window sticker processing."""
    
    @abstractmethod
    async def extract_features(self, window_sticker_path_or_url: str) -> List[str]:
        """Extract features from a window sticker."""
        pass


class FeatureMapperInterface(ABC):
    """Interface for feature mapping functionality."""
    
    @abstractmethod
    async def map_features(self, extracted_features: List[str]) -> Dict[str, bool]:
        """Map extracted features to vAuto checkboxes."""
        pass
    
    @abstractmethod
    def add_mapping(self, feature_text: str, vauto_feature: str) -> bool:
        """Add a new mapping."""
        pass
    
    @abstractmethod
    def update_mapping(self, old_feature: str, new_feature: str, vauto_feature: str) -> bool:
        """Update an existing mapping."""
        pass


class CheckboxManagementInterface(ABC):
    """Interface for checkbox management functionality."""
    
    @abstractmethod
    async def update_vehicle_checkboxes(self, vehicle_data: Dict[str, Any], 
                                      extracted_features: List[str]) -> Dict[str, Any]:
        """Update vehicle checkboxes based on extracted features."""
        pass


class ReportingInterface(ABC):
    """Interface for reporting functionality."""
    
    @abstractmethod
    async def generate_report(self, dealer_config: Dict[str, Any], stats: Dict[str, Any]) -> str:
        """Generate an HTML report."""
        pass
    
    @abstractmethod
    async def send_email_notification(self, dealer_config: Dict[str, Any], 
                                    stats: Dict[str, Any], report_path: str) -> bool:
        """Send email notification with the report."""
        pass
    
    @abstractmethod
    async def process_results(self, dealer_config: Dict[str, Any], 
                            results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process verification results and generate a report."""
        pass
    
    @abstractmethod
    async def send_alert(self, subject: str, message: str, 
                       dealer_config: Optional[Dict[str, Any]] = None) -> bool:
        """Send an alert email about system issues."""
        pass


class WorkflowInterface(ABC):
    """Interface for the verification workflow."""
    
    @abstractmethod
    async def run_verification(self, dealership_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run the verification process for a dealership."""
        pass


class ConfigurationInterface(ABC):
    """Interface for configuration management."""
    
    @abstractmethod
    def get_system_config(self) -> Dict[str, Any]:
        """Get the system configuration."""
        pass
    
    @abstractmethod
    def get_dealership_config(self, dealership_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the dealership configuration."""
        pass
    
    @abstractmethod
    def get_feature_mapping(self) -> Dict[str, List[str]]:
        """Get the feature mapping."""
        pass
    
    @abstractmethod
    def save_system_config(self, config: Dict[str, Any]) -> bool:
        """Save the system configuration."""
        pass
    
    @abstractmethod
    def save_dealership_config(self, config: Dict[str, Any]) -> bool:
        """Save the dealership configuration."""
        pass
    
    @abstractmethod
    def save_feature_mapping(self, mapping: Dict[str, List[str]]) -> bool:
        """Save the feature mapping."""
        pass
